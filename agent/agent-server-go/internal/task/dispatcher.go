package task

import (
	"context"
	"fmt"
	serrors "ops-job-agent-server/internal/errors"
	"sort"
	"sync"
	"sync/atomic"
	"time"

	"ops-job-agent-server/internal/agent"
	"ops-job-agent-server/internal/logger"
	"ops-job-agent-server/pkg/api"

	"github.com/marusama/semaphore/v2"
)

// Dispatcher 任务分发器
type Dispatcher struct {
	agentManager     *agent.Manager
	pendingTaskStore *PendingTaskStore // 待处理任务持久化存储（唯一持久化方案）
}

// NewDispatcher 创建任务分发器（仅支持控制面主动推送，不再轮询拉取）
// pendingTaskStore 用于任务持久化和 ACK 跟踪（无状态架构核心组件）
func NewDispatcher(agentMgr *agent.Manager, pendingStore *PendingTaskStore) *Dispatcher {
	d := &Dispatcher{
		agentManager:     agentMgr,
		pendingTaskStore: pendingStore,
	}

	return d
}

// DispatchTaskToAgent 直接分发任务到指定 Agent（用于控制面主动推送）
// 实现混合模式：Agent在线时直接推送，离线时持久化到 pendingTaskStore
func (d *Dispatcher) DispatchTaskToAgent(agentID string, task *api.TaskSpec) error {
	agentConn, exists := d.agentManager.Get(agentID)
	if !exists {
		// Agent不存在，持久化到 pendingTaskStore（如果有）
		if d.pendingTaskStore != nil {
			if err := d.pendingTaskStore.SavePending(agentID, task, 3); err != nil {
				logger.GetLogger().WithError(err).WithFields(map[string]interface{}{
					"agent_id": agentID,
					"task_id":  task.ID,
				}).Error("save pending task failed")
				return err
			}
			logger.GetLogger().WithFields(map[string]interface{}{
				"agent_id": agentID,
				"task_id":  task.ID,
			}).Info("task saved to pending store (agent not found)")
			return nil
		}
		return serrors.ErrAgentNotFound
	}

	// 检查Agent是否在线
	if agentConn.Status != "active" || agentConn.Conn == nil {
		// Agent离线，持久化到 pendingTaskStore（如果有）
		if d.pendingTaskStore != nil {
			if err := d.pendingTaskStore.SavePending(agentID, task, 3); err != nil {
				logger.GetLogger().WithError(err).WithFields(map[string]interface{}{
					"agent_id": agentID,
					"task_id":  task.ID,
				}).Error("save pending task failed")
				return err
			}
			logger.GetLogger().WithFields(map[string]interface{}{
				"agent_id": agentID,
				"task_id":  task.ID,
			}).Info("task saved to pending store (agent offline)")
			return nil
		}
		return serrors.ErrAgentConnectionClosed
	}

	// Agent在线，先持久化到 pendingTaskStore（确保可靠性）
	if d.pendingTaskStore != nil {
		if err := d.pendingTaskStore.SavePending(agentID, task, 3); err != nil {
			logger.GetLogger().WithError(err).WithFields(map[string]interface{}{
				"agent_id": agentID,
				"task_id":  task.ID,
			}).Warn("failed to save pending task, continuing with push")
		}
	}

	// 尝试直接推送
	select {
	case agentConn.TaskQueue <- task:
		agentConn.AddRunningTask(task)
		logger.GetLogger().WithFields(map[string]interface{}{
			"agent_id": agentID,
			"task_id":  task.ID,
		}).Info("task dispatched to agent (direct push)")
		return nil
	default:
		// 任务队列满，持久化到 pendingTaskStore（如果有）
		if d.pendingTaskStore != nil {
			if err := d.pendingTaskStore.SavePending(agentID, task, 3); err != nil {
				logger.GetLogger().WithError(err).WithFields(map[string]interface{}{
					"agent_id": agentID,
					"task_id":  task.ID,
				}).Error("save pending task failed")
				return err
			}
			logger.GetLogger().WithFields(map[string]interface{}{
				"agent_id": agentID,
				"task_id":  task.ID,
			}).Warn("task saved to pending store (agent queue full)")
			return nil
		}
		return serrors.ErrAgentConnectionClosed
	}
}

// ProcessPendingTasksForAgent 处理指定Agent的待处理任务（Agent上线时调用）
// 从 PendingTaskStore 获取任务进行补发
func (d *Dispatcher) ProcessPendingTasksForAgent(agentID string) error {
	var tasks []*PendingTask
	var err error

	// 从 PendingTaskStore 获取
	if d.pendingTaskStore != nil {
		tasks, err = d.pendingTaskStore.GetAgentPendingTasks(agentID)
		if err != nil {
			logger.GetLogger().WithError(err).WithField("agent_id", agentID).Error("get pending tasks from store failed")
			return err
		}
	}

	if len(tasks) == 0 {
		return nil
	}

	logger.GetLogger().WithFields(map[string]interface{}{
		"agent_id":   agentID,
		"task_count": len(tasks),
	}).Info("processing pending tasks for agent")

	// 获取Agent连接信息
	_, exists := d.agentManager.Get(agentID)
	if !exists {
		logger.GetLogger().WithField("agent_id", agentID).Warn("agent connection not found, skipping pending tasks")
		return nil
	}

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

	for _, pTask := range sortedTasks {
		task := pTask.Task // 提取 TaskSpec
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
		go func(t *api.TaskSpec) {
			defer wg.Done()

			// 获取信号量，尊重上下文超时
			if err := sem.Acquire(ctx, 1); err != nil {
				return
			}
			defer sem.Release(1)

			atomic.AddInt64(&processedCount, 1)

			// 检查任务是否已被处理（去重检查）
			if d.isTaskAlreadyProcessed(agentID, t.ID) {
				logger.GetLogger().WithFields(map[string]interface{}{
					"agent_id": agentID,
					"task_id":  t.ID,
				}).Debug("skipping already processed task")
				atomic.AddInt64(&successCount, 1)
				// 从 pending store 中标记为 acked
				if d.pendingTaskStore != nil {
					d.pendingTaskStore.MarkAcked(agentID, t.ID)
				}
				return
			}

			// 持久化 ack 检查
			if d.pendingTaskStore != nil {
				if acked, _ := d.pendingTaskStore.HasAcked(agentID, t.ID); acked {
					logger.GetLogger().WithFields(map[string]interface{}{
						"agent_id": agentID,
						"task_id":  t.ID,
					}).Debug("skipping pending task already acked (persistent)")
					atomic.AddInt64(&successCount, 1)
					d.pendingTaskStore.MarkAcked(agentID, t.ID)
					return
				}
			}

			// 尝试分发任务
			if err := d.DispatchTaskToAgent(agentID, t); err != nil {
				atomic.AddInt64(&failedCount, 1)
				logger.GetLogger().WithError(err).WithFields(map[string]interface{}{
					"agent_id": agentID,
					"task_id":  t.ID,
				}).Warn("dispatch pending task failed")

				// 记录失败任务，便于后续重试或分析
				d.recordFailedDispatch(agentID, t.ID, err)
			} else {
				atomic.AddInt64(&successCount, 1)
				logger.GetLogger().WithFields(map[string]interface{}{
					"agent_id": agentID,
					"task_id":  t.ID,
				}).Debug("successfully dispatched pending task")
				if d.pendingTaskStore != nil {
					d.pendingTaskStore.MarkAcked(agentID, t.ID)
				}
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
func (d *Dispatcher) sortTasksByPriority(tasks []*PendingTask) []*PendingTask {
	sorted := make([]*PendingTask, len(tasks))
	copy(sorted, tasks)

	// 简单的优先级排序：按任务类型和创建时间
	sort.Slice(sorted, func(i, j int) bool {
		// 关键任务优先
		if sorted[i].Task.Type != sorted[j].Task.Type {
			// 可以根据任务类型定义优先级
			return sorted[i].Task.Type < sorted[j].Task.Type
		}
		// 同类型任务按ID排序（近似时间顺序）
		return sorted[i].Task.ID < sorted[j].Task.ID
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
