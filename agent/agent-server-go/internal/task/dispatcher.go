package task

import (
	"context"
	"sync"
	"time"

	"ops-job-agent-server/internal/agent"
	"ops-job-agent-server/internal/controlplane"
	"ops-job-agent-server/internal/logger"
	"ops-job-agent-server/pkg/api"
)

// Dispatcher 任务分发器
type Dispatcher struct {
	agentManager *agent.Manager
	cpClient     *controlplane.Client
	taskQueue    *TaskQueue
	ctx          context.Context
	cancel       context.CancelFunc
	wg           sync.WaitGroup
	interval     time.Duration
	asynqEnabled bool
}

// NewDispatcher 创建任务分发器
func NewDispatcher(agentMgr *agent.Manager, cpClient *controlplane.Client, taskQueue *TaskQueue, interval time.Duration, asynqEnabled bool) *Dispatcher {
	ctx, cancel := context.WithCancel(context.Background())
	d := &Dispatcher{
		agentManager: agentMgr,
		cpClient:     cpClient,
		taskQueue:    taskQueue,
		ctx:          ctx,
		cancel:       cancel,
		interval:     interval,
		asynqEnabled: asynqEnabled,
	}

	// 如果启用了asynq，注册任务处理器
	if asynqEnabled && taskQueue != nil {
		taskQueue.RegisterHandler(d.handleQueuedTask)
	}

	return d
}

// Start 启动任务分发器
func (d *Dispatcher) Start() {
	d.wg.Add(1)
	go d.dispatchLoop()
	logger.GetLogger().Info("task dispatcher started")
}

// Stop 停止任务分发器
func (d *Dispatcher) Stop() {
	d.cancel()
	d.wg.Wait()
	logger.GetLogger().Info("task dispatcher stopped")
}

// dispatchLoop 任务分发循环
func (d *Dispatcher) dispatchLoop() {
	defer d.wg.Done()

	ticker := time.NewTicker(d.interval)
	defer ticker.Stop()

	for {
		select {
		case <-d.ctx.Done():
			return
		case <-ticker.C:
			d.dispatchTasks()
		}
	}
}

// dispatchTasks 分发任务到所有活跃的 Agent
func (d *Dispatcher) dispatchTasks() {
	agents := d.agentManager.List()
	for _, agentConn := range agents {
		if agentConn.Status != "active" || agentConn.Conn == nil {
			continue
		}

		// 从控制面拉取任务
		task, err := d.cpClient.FetchTask(d.ctx, agentConn.ID)
		if err != nil {
			logger.GetLogger().WithError(err).WithField("agent_id", agentConn.ID).Error("fetch task failed")
			continue
		}

		if task == nil {
			continue // 没有任务
		}

		// 将任务放入 Agent 的任务队列
		select {
		case agentConn.TaskQueue <- task:
			logger.GetLogger().WithFields(map[string]interface{}{
				"agent_id": agentConn.ID,
				"task_id":  task.ID,
			}).Info("task dispatched to agent")
		default:
			// 任务队列满，如果启用了asynq，入队
			if d.asynqEnabled && d.taskQueue != nil {
				_, err := d.taskQueue.EnqueueTask(agentConn.ID, task)
				if err != nil {
					logger.GetLogger().WithError(err).WithFields(map[string]interface{}{
						"agent_id": agentConn.ID,
						"task_id":  task.ID,
					}).Error("enqueue task failed (agent queue full)")
				} else {
					logger.GetLogger().WithFields(map[string]interface{}{
						"agent_id": agentConn.ID,
						"task_id":  task.ID,
					}).Warn("task enqueued to asynq (agent queue full)")
				}
			} else {
				// 未启用asynq，只能丢弃任务
				logger.GetLogger().WithFields(map[string]interface{}{
					"agent_id": agentConn.ID,
					"task_id":  task.ID,
				}).Warn("task queue full, dropping task (asynq not enabled)")
			}
		}
	}
}

// DispatchTaskToAgent 直接分发任务到指定 Agent（用于控制面主动推送）
// 实现混合模式：Agent在线时直接推送，离线时入队到asynq
func (d *Dispatcher) DispatchTaskToAgent(agentID string, task *api.TaskSpec) error {
	agentConn, exists := d.agentManager.Get(agentID)
	if !exists {
		// Agent不存在，如果启用了asynq，入队
		if d.asynqEnabled && d.taskQueue != nil {
			_, err := d.taskQueue.EnqueueTask(agentID, task)
			if err != nil {
				logger.GetLogger().WithError(err).WithFields(map[string]interface{}{
					"agent_id": agentID,
					"task_id":  task.ID,
				}).Error("enqueue task failed")
				return err
			}
			logger.GetLogger().WithFields(map[string]interface{}{
				"agent_id": agentID,
				"task_id":  task.ID,
			}).Info("task enqueued (agent not found)")
			return nil
		}
		return agent.ErrAgentNotFound
	}

	// 检查Agent是否在线
	if agentConn.Status != "active" || agentConn.Conn == nil {
		// Agent离线，如果启用了asynq，入队
		if d.asynqEnabled && d.taskQueue != nil {
			_, err := d.taskQueue.EnqueueTask(agentID, task)
			if err != nil {
				logger.GetLogger().WithError(err).WithFields(map[string]interface{}{
					"agent_id": agentID,
					"task_id":  task.ID,
				}).Error("enqueue task failed")
				return err
			}
			logger.GetLogger().WithFields(map[string]interface{}{
				"agent_id": agentID,
				"task_id":  task.ID,
			}).Info("task enqueued (agent offline)")
			return nil
		}
		return agent.ErrConnectionClosed
	}

	// Agent在线，尝试直接推送
	select {
	case agentConn.TaskQueue <- task:
		logger.GetLogger().WithFields(map[string]interface{}{
			"agent_id": agentID,
			"task_id":  task.ID,
		}).Info("task dispatched to agent (direct push)")
		return nil
	default:
		// 任务队列满，如果启用了asynq，入队
		if d.asynqEnabled && d.taskQueue != nil {
			_, err := d.taskQueue.EnqueueTask(agentID, task)
			if err != nil {
				logger.GetLogger().WithError(err).WithFields(map[string]interface{}{
					"agent_id": agentID,
					"task_id":  task.ID,
				}).Error("enqueue task failed")
				return err
			}
			logger.GetLogger().WithFields(map[string]interface{}{
				"agent_id": agentID,
				"task_id":  task.ID,
			}).Warn("task enqueued (agent queue full)")
			return nil
		}
		return agent.ErrConnectionClosed
	}
}

// handleQueuedTask 处理从队列中取出的任务
func (d *Dispatcher) handleQueuedTask(ctx context.Context, agentID string, task *api.TaskSpec) error {
	agentConn, exists := d.agentManager.Get(agentID)
	if !exists {
		// Agent不存在，任务会重试
		logger.GetLogger().WithFields(map[string]interface{}{
			"agent_id": agentID,
			"task_id":  task.ID,
		}).Warn("agent not found, task will retry")
		return agent.ErrAgentNotFound
	}

	// 检查Agent是否在线
	if agentConn.Status != "active" || agentConn.Conn == nil {
		// Agent离线，任务会重试
		logger.GetLogger().WithFields(map[string]interface{}{
			"agent_id": agentID,
			"task_id":  task.ID,
		}).Warn("agent offline, task will retry")
		return agent.ErrConnectionClosed
	}

	// Agent在线，尝试推送
	select {
	case agentConn.TaskQueue <- task:
		logger.GetLogger().WithFields(map[string]interface{}{
			"agent_id": agentID,
			"task_id":  task.ID,
		}).Info("task dispatched from queue to agent")
		return nil
	default:
		// 任务队列满，任务会重试
		logger.GetLogger().WithFields(map[string]interface{}{
			"agent_id": agentID,
			"task_id":  task.ID,
		}).Warn("agent queue full, task will retry")
		return agent.ErrConnectionClosed
	}
}

// ProcessPendingTasksForAgent 处理指定Agent的待处理任务（Agent上线时调用）
func (d *Dispatcher) ProcessPendingTasksForAgent(agentID string) error {
	if !d.asynqEnabled || d.taskQueue == nil {
		return nil
	}

	tasks, err := d.taskQueue.ListPendingTasks(agentID)
	if err != nil {
		logger.GetLogger().WithError(err).WithField("agent_id", agentID).Error("list pending tasks failed")
		return err
	}

	if len(tasks) == 0 {
		return nil
	}

	logger.GetLogger().WithFields(map[string]interface{}{
		"agent_id":   agentID,
		"task_count": len(tasks),
	}).Info("processing pending tasks for agent")

	// 尝试分发每个待处理任务
	for _, task := range tasks {
		if err := d.DispatchTaskToAgent(agentID, task); err != nil {
			logger.GetLogger().WithError(err).WithFields(map[string]interface{}{
				"agent_id": agentID,
				"task_id":  task.ID,
			}).Warn("dispatch pending task failed")
			// 继续处理下一个任务
		}
	}

	return nil
}
