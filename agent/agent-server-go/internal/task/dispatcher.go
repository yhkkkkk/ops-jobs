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
	ctx          context.Context
	cancel       context.CancelFunc
	wg           sync.WaitGroup
	interval     time.Duration
}

// NewDispatcher 创建任务分发器
func NewDispatcher(agentMgr *agent.Manager, cpClient *controlplane.Client, interval time.Duration) *Dispatcher {
	ctx, cancel := context.WithCancel(context.Background())
	return &Dispatcher{
		agentManager: agentMgr,
		cpClient:     cpClient,
		ctx:          ctx,
		cancel:       cancel,
		interval:     interval,
	}
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
			// 任务队列满，记录警告
			logger.GetLogger().WithFields(map[string]interface{}{
				"agent_id": agentConn.ID,
				"task_id":  task.ID,
			}).Warn("task queue full, dropping task")
		}
	}
}

// DispatchTaskToAgent 直接分发任务到指定 Agent（用于控制面主动推送）
func (d *Dispatcher) DispatchTaskToAgent(agentID string, task *api.TaskSpec) error {
	agentConn, exists := d.agentManager.Get(agentID)
	if !exists {
		return agent.ErrAgentNotFound
	}

	if agentConn.Status != "active" || agentConn.Conn == nil {
		return agent.ErrConnectionClosed
	}

	select {
	case agentConn.TaskQueue <- task:
		logger.GetLogger().WithFields(map[string]interface{}{
			"agent_id": agentID,
			"task_id":  task.ID,
		}).Info("task dispatched to agent")
		return nil
	default:
		return agent.ErrConnectionClosed
	}
}

