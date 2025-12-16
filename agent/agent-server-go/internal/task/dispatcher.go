package task

import (
	"context"
	"sync"

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
	asynqEnabled bool
}

// NewDispatcher 创建任务分发器（仅支持控制面主动推送，不再轮询拉取）
func NewDispatcher(agentMgr *agent.Manager, cpClient *controlplane.Client, taskQueue *TaskQueue, asynqEnabled bool) *Dispatcher {
	ctx, cancel := context.WithCancel(context.Background())
	d := &Dispatcher{
		agentManager: agentMgr,
		cpClient:     cpClient,
		taskQueue:    taskQueue,
		ctx:          ctx,
		cancel:       cancel,
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
	// 轮询模式已移除，仅保留 Asynq 处理器（如启用）
	logger.GetLogger().Info("task dispatcher started (push-only, no polling)")
}

// Stop 停止任务分发器
func (d *Dispatcher) Stop() {
	d.cancel()
	d.wg.Wait()
	logger.GetLogger().Info("task dispatcher stopped")
}

// DispatchTaskToAgent 直接分发任务到指定 Agent（用于控制面主动推送）
// 实现混合模式：Agent在线时直接推送，离线时入队到asynq
func (d *Dispatcher) DispatchTaskToAgent(agentID string, task *api.TaskSpec) error {
	agentConn, exists := d.agentManager.Get(agentID)
	if !exists {
		// Agent不存在，如果启用了asynq，入队
		if d.asynqEnabled && d.taskQueue != nil {
			_, err := d.taskQueue.EnqueueWithPolicy(agentID, task)
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
			_, err := d.taskQueue.EnqueueWithPolicy(agentID, task)
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
			_, err := d.taskQueue.EnqueueWithPolicy(agentID, task)
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
