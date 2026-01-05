package task

import (
	"context"
	"fmt"
	"sort"
	"sync"
	"sync/atomic"
	"time"

	"ops-job-agent-server/internal/agent"
	"ops-job-agent-server/internal/controlplane"
	"ops-job-agent-server/internal/logger"
	"ops-job-agent-server/pkg/api"

	"github.com/marusama/semaphore/v2"
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
// 支持多租户隔离：检查Agent的scope是否匹配（如果配置了scope）
func (d *Dispatcher) DispatchTaskToAgent(agentID string, task *api.TaskSpec, requestScope string) error {
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

	// 多租户隔离检查：如果配置了scope，确保Agent的scope与请求的scope匹配
	if requestScope != "" {
		// 安全读取scope
		agentScope := agentConn.GetScope()

		// 如果Agent有scope且与请求的scope不匹配，拒绝分发
		if agentScope != "" && agentScope != requestScope {
			logger.GetLogger().WithFields(map[string]interface{}{
				"agent_id":      agentID,
				"task_id":       task.ID,
				"agent_scope":   agentScope,
				"request_scope": requestScope,
			}).Warn("task dispatch rejected: scope mismatch (multi-tenant isolation)")
			return fmt.Errorf("agent scope mismatch: agent belongs to scope %s, but request scope is %s", agentScope, requestScope)
		}
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
		agentConn.AddRunningTask(task)
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
		agentConn.AddRunningTask(task)
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

	// 获取Agent连接信息
	agentConn, exists := d.agentManager.Get(agentID)
	if !exists {
		logger.GetLogger().WithField("agent_id", agentID).Warn("agent connection not found, skipping pending tasks")
		return nil
	}

	requestScope := agentConn.GetScope()

	// 对任务进行优先级排序（关键任务优先）
	sortedTasks := d.sortTasksByPriority(tasks)

	// 批量处理任务，设置并发限制
	const maxConcurrentDispatch = 5
	sem := semaphore.New(maxConcurrentDispatch)

	var wg sync.WaitGroup
	var processedCount int64
	var successCount int64
	var failedCount int64

	// 使用context控制超时
	ctx, cancel := context.WithTimeout(context.Background(), 5*time.Minute)
	defer cancel()

	for _, task := range sortedTasks {
		select {
		case <-ctx.Done():
			logger.GetLogger().WithFields(map[string]interface{}{
				"agent_id":        agentID,
				"processed_count": processedCount,
				"remaining_count": int64(len(sortedTasks)) - processedCount,
			}).Warn("pending tasks processing timeout")
			break
		default:
		}

		wg.Add(1)
		go func(task *api.TaskSpec) {
			defer wg.Done()

			// 获取信号量，尊重上下文超时
			if err := sem.Acquire(ctx, 1); err != nil {
				return
			}
			defer sem.Release(1)

			atomic.AddInt64(&processedCount, 1)

			// 检查任务是否已被处理（去重检查）
			if d.isTaskAlreadyProcessed(agentID, task.ID) {
				logger.GetLogger().WithFields(map[string]interface{}{
					"agent_id": agentID,
					"task_id":  task.ID,
				}).Debug("skipping already processed task")
				atomic.AddInt64(&successCount, 1)
				return
			}

			// 尝试分发任务
			if err := d.DispatchTaskToAgent(agentID, task, requestScope); err != nil {
				atomic.AddInt64(&failedCount, 1)
				logger.GetLogger().WithError(err).WithFields(map[string]interface{}{
					"agent_id": agentID,
					"task_id":  task.ID,
				}).Warn("dispatch pending task failed")

				// 记录失败任务，便于后续重试或分析
				d.recordFailedDispatch(agentID, task.ID, err)
			} else {
				atomic.AddInt64(&successCount, 1)
				logger.GetLogger().WithFields(map[string]interface{}{
					"agent_id": agentID,
					"task_id":  task.ID,
				}).Debug("successfully dispatched pending task")
			}
		}(task)
	}

	// 等待所有任务处理完成
	done := make(chan struct{})
	go func() {
		wg.Wait()
		close(done)
	}()

	select {
	case <-done:
		// 正常完成
	case <-ctx.Done():
		logger.GetLogger().WithField("agent_id", agentID).Warn("pending tasks processing interrupted by timeout")
	}

	// 记录处理结果
	finalProcessedCount := atomic.LoadInt64(&processedCount)
	finalSuccessCount := atomic.LoadInt64(&successCount)
	finalFailedCount := atomic.LoadInt64(&failedCount)

	logger.GetLogger().WithFields(map[string]interface{}{
		"agent_id":        agentID,
		"total_tasks":     len(sortedTasks),
		"processed_count": finalProcessedCount,
		"success_count":   finalSuccessCount,
		"failed_count":    finalFailedCount,
		"success_rate":    fmt.Sprintf("%.1f%%", float64(finalSuccessCount)/float64(finalProcessedCount)*100),
	}).Info("completed processing pending tasks for agent")

	return nil
}

// sortTasksByPriority 按优先级对任务进行排序
func (d *Dispatcher) sortTasksByPriority(tasks []*api.TaskSpec) []*api.TaskSpec {
	sorted := make([]*api.TaskSpec, len(tasks))
	copy(sorted, tasks)

	// 简单的优先级排序：按任务类型和创建时间
	sort.Slice(sorted, func(i, j int) bool {
		// 关键任务优先
		if sorted[i].Type != sorted[j].Type {
			// 可以根据任务类型定义优先级
			return sorted[i].Type < sorted[j].Type
		}
		// 同类型任务按ID排序（近似时间顺序）
		return sorted[i].ID < sorted[j].ID
	})

	return sorted
}

// isTaskAlreadyProcessed 检查任务是否已被处理（简单的内存检查）
func (d *Dispatcher) isTaskAlreadyProcessed(agentID, taskID string) bool {
	// 这里可以实现更复杂的去重逻辑，比如检查Redis中的任务状态
	// 目前使用简单的内存检查（可以扩展为Redis检查）
	agentConn, exists := d.agentManager.Get(agentID)
	if !exists {
		return false
	}

	// 如果任务正在运行列表中，说明已被处理
	return agentConn.IsTaskRunning(taskID)
}

// recordFailedDispatch 记录分发失败的任务
func (d *Dispatcher) recordFailedDispatch(agentID, taskID string, err error) {
	// 这里可以实现失败任务的记录逻辑
	// 比如写入Redis便于后续分析，或触发告警
	logger.GetLogger().WithError(err).WithFields(map[string]interface{}{
		"agent_id": agentID,
		"task_id":  taskID,
		"error":    err.Error(),
	}).Debug("recorded failed task dispatch")
}
