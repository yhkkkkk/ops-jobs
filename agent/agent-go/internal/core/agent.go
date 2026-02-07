package core

import (
	"context"
	"fmt"
	"net/url"
	"sync"
	"sync/atomic"
	"time"

	"github.com/avast/retry-go/v4"
	"github.com/marusama/semaphore/v2"

	"ops-job-agent/internal/api"
	"ops-job-agent/internal/config"
	"ops-job-agent/internal/constants"
	"ops-job-agent/internal/errors"
	"ops-job-agent/internal/executor"
	"ops-job-agent/internal/httpclient"
	"ops-job-agent/internal/logger"
	"ops-job-agent/internal/metrics"
	"ops-job-agent/internal/system"
	wsclient "ops-job-agent/internal/websocket"
)

// HealthStatus Agent健康状态
type HealthStatus struct {
	Healthy bool     // 是否健康
	Issues  []string // 健康问题列表
}

// HeartbeatStats 心跳统计信息
type HeartbeatStats struct {
	TotalSent           int64     // 总发送心跳数
	TotalSucceeded      int64     // 总成功心跳数
	TotalFailed         int64     // 总失败心跳数
	ConsecutiveFailures int       // 连续失败次数
	LastSuccessTime     time.Time // 最后成功时间
	LastFailureTime     time.Time // 最后失败时间
	ReconnectCount      int64     // 重连次数
}

// Agent 是 Agent 进程的核心对象，负责注册、心跳、拉任务等
type Agent struct {
	cfg            *config.Config
	wsClient       *wsclient.Client // WebSocket 客户端（agent-server 模式）
	info           *AgentInfo
	system         SystemInfo
	ctx            context.Context
	cancel         context.CancelFunc
	wg             sync.WaitGroup
	started        bool
	executor       *executor.Executor
	scriptExecutor *executor.ScriptExecutor
	fileExecutor   *executor.FileTransferExecutor
	maxTaskTime    time.Duration                    // 全局最大任务执行时间
	taskSemaphore  semaphore.Semaphore              // 控制并发任务数
	runningTasks   map[string]*executor.RunningTask // 正在运行的任务映射
	tasksLock      sync.RWMutex                     // 任务映射锁
	wsURL          string
	outbox         *wsclient.FileOutbox // 本地文件持久化的 Outbox
	// completedTasks 用于幂等控制的最近已完成任务集合（LRU）
	completedTasks map[string]time.Time
	completedLock  sync.Mutex
	// runningTaskLocks 用于防止同一任务同时执行的锁集合
	runningTaskLocks map[string]*sync.Mutex
	runningLocksLock sync.RWMutex
	// registerMu 避免并发重注册
	registerMu sync.Mutex
	// heartbeatIntervalSec 支持运行时调整心跳间隔（秒），避免重启 Agent
	heartbeatIntervalSec int64
	// 心跳监控统计
	heartbeatStats HeartbeatStats
	heartbeatLock  sync.RWMutex
	// outboxFlushBatch 控制 WS outbox 每次冲刷的批量大小
	outboxFlushBatch int
}

func NewAgent(cfg *config.Config) *Agent {
	ctx, cancel := context.WithCancel(context.Background())

	// 创建执行器
	exec := executor.NewExecutor(cfg.Logging.LogDir)
	scriptExec := executor.NewScriptExecutor(exec, "")
	fileExec := executor.NewFileTransferExecutor(exec)

	// 创建任务信号量（控制并发数）
	maxConcurrent := cfg.Task.MaxConcurrentTasks
	if maxConcurrent <= 0 {
		maxConcurrent = constants.DefaultMaxConcurrentTasks
	}
	taskSemaphore := semaphore.New(maxConcurrent)

	// 设置全局最大任务执行时间
	maxTaskTime := 2 * time.Hour // 默认2小时
	if cfg.Task.MaxExecutionTimeSec > 0 {
		maxTaskTime = time.Duration(cfg.Task.MaxExecutionTimeSec) * time.Second
	}
	exec.SetMaxTaskTime(maxTaskTime)

	// Outbox 批量冲刷大小（可配置，默认 constants.OutboxFlushBatchSize）
	outboxBatch := cfg.Logging.LogBatchSize
	if outboxBatch <= 0 {
		outboxBatch = constants.OutboxFlushBatchSize
	}

	// 确定 outbox 文件存储目录
	outboxDir := ""
	logDir := cfg.Logging.LogDir
	if logDir != "" {
		outboxDir = logDir
	} else {
		// 使用默认目录
		outboxDir = "."
	}

	agent := &Agent{
		cfg:              cfg,
		system:           collectSystemInfo(),
		outbox:           wsclient.NewFileOutbox("placeholder", outboxDir, cfg.Connection.WSOutboxMaxSize), // Will be recreated after registration
		ctx:              ctx,
		cancel:           cancel,
		executor:         exec,
		scriptExecutor:   scriptExec,
		fileExecutor:     fileExec,
		taskSemaphore:    taskSemaphore,
		runningTasks:     make(map[string]*executor.RunningTask),
		completedTasks:   make(map[string]time.Time),
		runningTaskLocks: make(map[string]*sync.Mutex),
		maxTaskTime:      maxTaskTime,
	}

	// 存储配置化的 outbox 批量大小
	agent.outboxFlushBatch = outboxBatch

	// 初始化心跳间隔（秒），为后续动态刷新做准备
	hb := cfg.Task.HeartbeatInterval
	if hb <= 0 {
		hb = constants.DefaultHeartbeatIntervalSec
	}
	agent.heartbeatIntervalSec = int64(hb)

	wsClient := wsclient.NewClient(cfg.Connection.AgentServerURL, cfg.Identification.AgentToken, cfg.Connection.WSEnableCompression)
	wsClient.SetOnTask(agent.handleWebSocketTask)
	wsClient.SetOnCancel(agent.handleWebSocketCancel)
	wsClient.SetOnControl(agent.handleWebSocketControl)
	wsClient.SetOnUpgrade(agent.handleWebSocketUpgrade)
	wsClient.SetOnAuthError(agent.handleWSAuthError)
	agent.wsClient = wsClient

	return agent
}

// Start 注册自身，并启动后台协程
func (a *Agent) Start() error {
	if a.started {
		return nil
	}

	// 先注册自身，获取 agentID 等信息
	if err := a.register(); err != nil {
		return err
	}

	// 启动心跳循环
	a.wg.Add(1)
	go a.heartbeatLoop()

	// Agent-Server 模式：通过 WebSocket 与 Agent-Server 建立长链接
	if err := a.ensureWebSocketConnection(); err != nil {
		return err
	}

	// 启动独立的 WebSocket 重连循环（断线后自动尝试重连）
	if a.wsClient != nil && a.info != nil {
		a.wsClient.StartReconnectLoop(a.info.ID)
	}

	// 定期冲刷 WS outbox（若配置了刷写间隔）
	flushInterval := time.Duration(a.cfg.Logging.LogFlushInterval) * time.Millisecond
	if flushInterval > 0 {
		a.wg.Add(1)
		go func() {
			defer a.wg.Done()
			ticker := time.NewTicker(flushInterval)
			defer ticker.Stop()
			for {
				select {
				case <-a.ctx.Done():
					return
				case <-ticker.C:
					a.flushOutbox()
				}
			}
		}()
	}

	// 订阅配置变更（动态调整部分运行参数，如心跳间隔、日志级别）
	config.Subscribe(a.onConfigChanged)

	a.started = true
	return nil
}

// Stop 优雅关闭
func (a *Agent) Stop() {
	// 先停止重连循环
	if a.wsClient != nil {
		a.wsClient.StopReconnectLoop()
	}

	a.cancel()
	// HTTP Server 会在 ctx 取消后优雅退出
	// 断开 WebSocket 连接（agent-server 模式）
	if a.wsClient != nil {
		// 现阶段断开失败无需强制处理
		_ = a.wsClient.Disconnect()
	}
	// 关闭 Outbox
	if a.outbox != nil {
		a.outbox.Close()
	}
	a.wg.Wait()
}

// performHealthCheck 执行健康检查
func (a *Agent) performHealthCheck() *HealthStatus {
	health := &HealthStatus{
		Healthy: true,
		Issues:  []string{},
	}

	// 检查WebSocket连接状态
	if a.wsClient != nil && !a.wsClient.IsConnected() {
		health.Healthy = false
		health.Issues = append(health.Issues, "WebSocket connection lost")
	}

	return health
}

func (a *Agent) heartbeatLoop() {
	defer a.wg.Done()
	// 基础 ticker：1s，实际心跳间隔由 heartbeatIntervalSec 控制，支持运行时调整
	baseTicker := time.NewTicker(time.Second)
	defer baseTicker.Stop()

	var lastHeartbeat time.Time
	var reconnectBackoff time.Duration // 重连退避时间

	for {
		select {
		case <-a.ctx.Done():
			logger.GetLogger().Info("agent stopped")
			return
		case <-baseTicker.C:
			// 动态调整心跳间隔：连续失败时增加间隔，减少服务器负载
			baseIntervalSec := atomic.LoadInt64(&a.heartbeatIntervalSec)
			if baseIntervalSec <= 0 {
				baseIntervalSec = constants.DefaultHeartbeatIntervalSec
			}

			// 根据连续失败次数调整间隔（最多增加到5倍）
			a.heartbeatLock.RLock()
			consecutiveFailures := a.heartbeatStats.ConsecutiveFailures
			a.heartbeatLock.RUnlock()

			multiplier := 1 + (consecutiveFailures / 3) // 每3次失败增加1倍间隔
			if multiplier > 5 {
				multiplier = 5
			}
			intervalSec := baseIntervalSec * int64(multiplier)
			interval := time.Duration(intervalSec) * time.Second

			if !lastHeartbeat.IsZero() && time.Since(lastHeartbeat) < interval {
				continue
			}
			lastHeartbeat = time.Now()

			if a.info == nil {
				continue
			}

			// 检查是否需要重连退避
			if reconnectBackoff > 0 {
				if time.Since(a.getLastReconnectTime()) < reconnectBackoff {
					continue
				}
				reconnectBackoff = 0 // 重置退避
			}

			// 执行健康检查
			health := a.performHealthCheck()
			if !health.Healthy {
				logger.GetLogger().WithFields(map[string]interface{}{
					"issues": health.Issues,
				}).Warn("agent health check failed, disconnecting")

				// 主动断开WebSocket连接，触发快速状态更新
				if a.wsClient != nil && a.wsClient.IsConnected() {
					_ = a.wsClient.Disconnect()
				}
				continue
			}

			systemInfo := collectSystemInfo()
			a.system = systemInfo

			// Agent-Server 模式：通过 WebSocket 发送心跳
			if a.wsClient != nil {
				a.sendHeartbeatWithRetry(&systemInfo, &reconnectBackoff)
			}
		}
	}
}

// sendHeartbeatWithRetry 发送心跳并处理重试逻辑
func (a *Agent) sendHeartbeatWithRetry(systemInfo *SystemInfo, reconnectBackoff *time.Duration) {
	timestamp := time.Now().Unix()

	// 更新发送统计
	a.heartbeatLock.Lock()
	a.heartbeatStats.TotalSent++
	a.heartbeatLock.Unlock()

	// 发送心跳，支持重试
	maxRetries := 3
	var lastErr error

	for attempt := 1; attempt <= maxRetries; attempt++ {
		if !a.wsClient.IsConnected() {
			// 需要重连
			if err := a.wsClient.Connect(a.info.ID); err != nil {
				lastErr = err
				logger.GetLogger().WithError(err).WithField("attempt", attempt).Warn("websocket reconnect failed")

				// 记录重连统计
				a.heartbeatLock.Lock()
				a.heartbeatStats.ReconnectCount++
				a.heartbeatLock.Unlock()

				// 设置指数退避
				if attempt < maxRetries {
					*reconnectBackoff = time.Duration(attempt) * time.Second
					continue
				}
			} else {
				logger.GetLogger().WithField("attempt", attempt).Info("websocket reconnected successfully")
				// 重连成功，重置连续失败计数
				a.heartbeatLock.Lock()
				a.heartbeatStats.ConsecutiveFailures = 0
				a.heartbeatLock.Unlock()
			}
		}

		// 发送心跳
		if err := a.wsClient.SendHeartbeat(timestamp, systemInfo); err != nil {
			lastErr = err
			logger.GetLogger().WithError(err).WithField("attempt", attempt).Warn("websocket heartbeat failed")

			// 记录失败统计
			a.heartbeatLock.Lock()
			a.heartbeatStats.TotalFailed++
			a.heartbeatStats.ConsecutiveFailures++
			a.heartbeatStats.LastFailureTime = time.Now()
			a.heartbeatLock.Unlock()

			// 如果不是最后一次尝试，等待后重试
			if attempt < maxRetries {
				select {
				case <-time.After(time.Duration(attempt) * 500 * time.Millisecond):
					continue
				case <-a.ctx.Done():
					return
				}
			}
		} else {
			// 心跳成功
			logger.GetLogger().WithField("attempt", attempt).Debug("websocket heartbeat succeeded")

			// 记录成功统计
			a.heartbeatLock.Lock()
			a.heartbeatStats.TotalSucceeded++
			a.heartbeatStats.ConsecutiveFailures = 0
			a.heartbeatStats.LastSuccessTime = time.Now()
			a.heartbeatLock.Unlock()

			return
		}
	}

	// 所有重试都失败
	logger.GetLogger().WithError(lastErr).WithField("retries", maxRetries).Error("websocket heartbeat failed after all retries")
}

// getLastReconnectTime 获取最后重连时间（简化实现）
func (a *Agent) getLastReconnectTime() time.Time {
	a.heartbeatLock.RLock()
	defer a.heartbeatLock.RUnlock()
	return a.heartbeatStats.LastFailureTime // 近似使用最后失败时间
}

// executeTask 执行任务
func (a *Agent) executeTask(task *TaskSpec) {
	// 检查并跳过重复任务
	if a.checkAndSkipDuplicatedTask(task) {
		return
	}

	// 获取任务锁（防止同一任务同时执行）
	taskLock := a.getOrCreateTaskLock(task.ID)
	taskLock.Lock()
	defer func() {
		taskLock.Unlock()
		a.cleanupTaskLock(task.ID) // 清理锁
	}()

	// 获取信号量（控制并发）
	if err := a.taskSemaphore.Acquire(a.ctx, 1); err != nil {
		logger.GetLogger().WithError(err).Error("acquire semaphore failed")
		return
	}

	// 使用panic recovery确保信号量一定释放
	defer func() {
		if r := recover(); r != nil {
			logger.GetLogger().WithField("task_id", task.ID).WithField("panic", r).Error("task execution panic")
		}
		a.taskSemaphore.Release(1)
	}()

	logger.GetLogger().WithFields(map[string]interface{}{
		"task_id":   task.ID,
		"task_name": task.Name,
		"task_type": task.Type,
	}).Info("executing task")

	// 记录任务开始
	metrics.GetMetrics().RecordTaskStart()
	startTime := time.Now()

	// 创建日志回调函数
	logCallback := a.createLogCallback(task.ID)

	// 执行任务
	result, err := a.executeTaskByType(task, logCallback)

	// 处理执行错误
	if err != nil {
		logger.GetLogger().WithError(err).WithField("task_id", task.ID).Error("execute task error")
		result = &api.TaskResult{
			TaskID:     task.ID,
			Status:     constants.StatusFailed,
			ExitCode:   -1,
			StartedAt:  time.Now().Unix(),
			FinishedAt: time.Now().Unix(),
			ErrorMsg:   err.Error(),
			ErrorCode:  int(errors.GetErrorCode(err)),
		}
	}

	// 记录任务指标
	a.recordTaskMetrics(result, time.Since(startTime))

	// 上报结果
	a.reportTaskResult(result)

	// 记录任务已完成，用于后续幂等判断
	a.markTaskCompleted(task.ID)
}

// checkAndSkipDuplicatedTask 检查并跳过重复任务
func (a *Agent) checkAndSkipDuplicatedTask(task *TaskSpec) bool {
	// 首先检查是否已完成
	if a.isTaskCompleted(task.ID) {
		logger.GetLogger().WithFields(map[string]interface{}{
			"task_id": task.ID,
		}).Warn("skip duplicated task (already completed recently)")

		// 仍然上报一个标记为 cancelled 的结果，避免控制面长时间等待
		now := time.Now().Unix()
		result := &api.TaskResult{
			TaskID:     task.ID,
			Status:     constants.StatusCancelled,
			ExitCode:   -1,
			StartedAt:  now,
			FinishedAt: now,
			ErrorMsg:   constants.MsgTaskSkippedDuplicate,
		}
		a.reportTaskResult(result)
		return true
	}

	// 检查是否正在执行（防止同一任务同时执行）
	if a.isTaskRunning(task.ID) {
		logger.GetLogger().WithFields(map[string]interface{}{
			"task_id": task.ID,
		}).Warn("skip duplicated task (already running)")

		// 不上报结果，让控制面等待现有的执行完成
		return true
	}

	// 获取或创建任务锁
	taskLock := a.getOrCreateTaskLock(task.ID)

	// 尝试获取任务锁（非阻塞）
	if !taskLock.TryLock() {
		logger.GetLogger().WithFields(map[string]interface{}{
			"task_id": task.ID,
		}).Warn("skip duplicated task (lock already held)")

		// 不上报结果，让控制面等待现有的执行完成
		return true
	}

	// 成功获取锁，现在释放它（让executeTask重新获取）
	taskLock.Unlock()

	return false
}

// isTaskRunning 检查任务是否正在运行
func (a *Agent) isTaskRunning(taskID string) bool {
	a.tasksLock.RLock()
	defer a.tasksLock.RUnlock()
	_, exists := a.runningTasks[taskID]
	return exists
}

// getOrCreateTaskLock 获取或创建任务锁
func (a *Agent) getOrCreateTaskLock(taskID string) *sync.Mutex {
	a.runningLocksLock.Lock()
	defer a.runningLocksLock.Unlock()

	if lock, exists := a.runningTaskLocks[taskID]; exists {
		return lock
	}

	lock := &sync.Mutex{}
	a.runningTaskLocks[taskID] = lock
	return lock
}

// cleanupTaskLock 清理任务锁（在任务完成后调用）
func (a *Agent) cleanupTaskLock(taskID string) {
	a.runningLocksLock.Lock()
	defer a.runningLocksLock.Unlock()

	delete(a.runningTaskLocks, taskID)
}

// createLogCallback 创建日志回调函数
func (a *Agent) createLogCallback(taskID string) func(string) {
	return func(logLine string) {
		// 记录到本地日志
		logger.GetLogger().WithField("task_id", taskID).Info(logLine)

		// 通过 WebSocket 发送日志到 Agent-Server
		logEntry := api.LogEntry{
			Timestamp: time.Now().Unix(),
			Level:     "info",
			Content:   logLine,
			Stream:    constants.StreamStdout,
			TaskID:    taskID,
		}

		// 优先直发，断线则进入 outbox 本地缓冲
		if a.wsClient != nil && a.wsClient.IsConnected() {
			if err := a.wsClient.SendLogs(taskID, []api.LogEntry{logEntry}); err != nil {
				logger.GetLogger().WithError(err).Error("send log via websocket failed")
				if a.outbox != nil {
					a.outbox.Enqueue(wsclient.Message{
						Type:      constants.MessageTypeLog,
						Timestamp: time.Now().UnixMilli(),
						TaskID:    taskID,
						Logs:      []api.LogEntry{logEntry},
					})
				}
			}
			return
		}
		if a.outbox != nil {
			a.outbox.Enqueue(wsclient.Message{
				Type:      constants.MessageTypeLog,
				Timestamp: time.Now().UnixMilli(),
				TaskID:    taskID,
				Logs:      []api.LogEntry{logEntry},
			})
		}
	}
}

// executeTaskByType 根据任务类型执行任务
func (a *Agent) executeTaskByType(task *TaskSpec, logCallback func(string)) (*api.TaskResult, error) {
	// 任务上下文（文件传输需要可取消/超时）
	taskCtx := a.ctx
	var cancel context.CancelFunc

	// 启动任务状态跟踪协程（仅对脚本任务）
	var stopTracking chan struct{}
	if task.Type == constants.TaskTypeScript || task.Type == "" {
		stopTracking = make(chan struct{})
		go a.trackTaskStatus(task.ID, stopTracking)
		defer func() {
			if stopTracking != nil {
				close(stopTracking)
			}
		}()
	}

	// 文件传输纳入 runningTasks，支持取消/超时
	if task.Type == constants.TaskTypeFileTransfer {
		if task.TimeoutSec > 0 {
			taskCtx, cancel = context.WithTimeout(a.ctx, time.Duration(task.TimeoutSec)*time.Second)
		} else {
			taskCtx, cancel = context.WithCancel(a.ctx)
		}
		rt := &executor.RunningTask{
			TaskID:    task.ID,
			StartTime: time.Now(),
			Status:    constants.StatusRunning,
			Cancel:    cancel,
		}
		a.tasksLock.Lock()
		a.runningTasks[task.ID] = rt
		a.tasksLock.Unlock()
		defer func() {
			if cancel != nil {
				cancel()
			}
			a.tasksLock.Lock()
			delete(a.runningTasks, task.ID)
			a.tasksLock.Unlock()
		}()
	}

	// 根据任务类型选择执行器
	var result *api.TaskResult
	var err error
	switch task.Type {
	case constants.TaskTypeFileTransfer:
		// 如果任务未显式配置带宽限制且全局配置了带宽限制，则套用全局值（单位：MB/s）
		if task.FileTransfer != nil && task.FileTransfer.BandwidthLimit <= 0 && a.cfg.ResourceLimit.BandwidthLimit > 0 {
			task.FileTransfer.BandwidthLimit = a.cfg.ResourceLimit.BandwidthLimit
		}
		result, err = a.fileExecutor.ExecuteTransfer(taskCtx, task, logCallback)
	case constants.TaskTypeScript:
		result, err = a.scriptExecutor.ExecuteScript(a.ctx, task, logCallback)
	default:
		// 默认使用脚本执行器
		result, err = a.scriptExecutor.ExecuteScript(a.ctx, task, logCallback)
	}

	// 从运行任务映射中移除
	a.tasksLock.Lock()
	delete(a.runningTasks, task.ID)
	a.tasksLock.Unlock()

	return result, err
}

// recordTaskMetrics 记录任务指标
func (a *Agent) recordTaskMetrics(result *api.TaskResult, duration time.Duration) {
	switch result.Status {
	case constants.StatusSuccess:
		metrics.GetMetrics().RecordTaskSuccess(duration)
	case constants.StatusFailed:
		metrics.GetMetrics().RecordTaskFailed(duration)
	case constants.StatusCancelled:
		metrics.GetMetrics().RecordTaskCancelled(duration)
	}
}

// reportTaskResult 上报任务结果
func (a *Agent) reportTaskResult(result *api.TaskResult) {
	// 填充 storage_uri 风格的日志指针（默认指向 redis log stream 的末尾）
	if result != nil && result.LogPointer == "" && result.LogSize > 0 {
		result.LogPointer = fmt.Sprintf("redis:job_logs/%s@", result.TaskID)
	}

	// Agent-Server 模式：通过 WebSocket 发送结果
	if a.wsClient != nil && a.wsClient.IsConnected() {
		if err := a.wsClient.SendTaskResult(result); err != nil {
			logger.GetLogger().WithError(err).WithField("task_id", result.TaskID).Error("report result via websocket failed")
			if a.outbox != nil {
				a.outbox.Enqueue(wsclient.Message{
					Type:      constants.MessageTypeTaskResult,
					Timestamp: time.Now().UnixMilli(),
					TaskID:    result.TaskID,
					Result:    result,
				})
			}
		} else {
			logger.GetLogger().WithFields(map[string]interface{}{
				"task_id": result.TaskID,
				"status":  result.Status,
			}).Info("task completed")
		}
		return
	}
	// 断线期间先落到 outbox，等待重连后补传
	if a.outbox != nil {
		a.outbox.Enqueue(wsclient.Message{
			Type:      constants.MessageTypeTaskResult,
			Timestamp: time.Now().UnixMilli(),
			TaskID:    result.TaskID,
			Result:    result,
		})
	}
}

// isTaskCompleted 判断任务是否在最近已完成集合中（简易LRU）
func (a *Agent) isTaskCompleted(taskID string) bool {
	if taskID == "" {
		return false
	}
	a.completedLock.Lock()
	defer a.completedLock.Unlock()

	// 清理过期记录（超过5分钟的任务视为无效，以免集合无限增长）
	now := time.Now()
	const ttl = 5 * time.Minute
	for id, t := range a.completedTasks {
		if now.Sub(t) > ttl {
			delete(a.completedTasks, id)
		}
	}

	_, exists := a.completedTasks[taskID]
	return exists
}

// markTaskCompleted 将任务标记为已完成
func (a *Agent) markTaskCompleted(taskID string) {
	if taskID == "" {
		return
	}

	now := time.Now()

	a.completedLock.Lock()
	defer a.completedLock.Unlock()

	// 限制集合大小，最多保留 1000 个最近任务
	const maxSize = 1000
	if len(a.completedTasks) >= maxSize {
		// 清理过期记录（超过10分钟的任务）
		const ttl = 10 * time.Minute
		for id, completedTime := range a.completedTasks {
			if now.Sub(completedTime) > ttl {
				delete(a.completedTasks, id)
			}
		}

		// 如果仍然超过限制，删除最旧的记录
		if len(a.completedTasks) >= maxSize {
			oldestID := ""
			var oldestTime time.Time
			for id, t := range a.completedTasks {
				if oldestID == "" || t.Before(oldestTime) {
					oldestID = id
					oldestTime = t
				}
			}
			if oldestID != "" {
				delete(a.completedTasks, oldestID)
			}
		}
	}

	a.completedTasks[taskID] = now

	logger.GetLogger().WithFields(map[string]interface{}{
		"task_id":         taskID,
		"total_completed": len(a.completedTasks),
	}).Debug("task marked as completed")
}

// handleWSAuthError 在 WS 鉴权/不存在错误时尝试重注册，返回新 agentID
func (a *Agent) handleWSAuthError() (string, error) {
	if a.ctx.Err() != nil {
		return "", a.ctx.Err()
	}
	// 避免并发重注册
	a.registerMu.Lock()
	defer a.registerMu.Unlock()

	a.system = collectSystemInfo()
	if err := a.register(); err != nil {
		return "", err
	}
	if a.info == nil {
		return "", fmt.Errorf("agent info missing after re-register")
	}
	return a.info.ID, nil
}

// register 向 Agent-Server 注册自身
func (a *Agent) register() error {
	wasRegistered := a.info != nil
	info := AgentInfo{
		Name:   a.cfg.Identification.AgentName,
		System: &a.system,
		HostID: a.cfg.Identification.HostID,
	}

	// Agent-Server 模式：向 Agent-Server 注册
	httpURL, err := deriveAgentServerHTTPURL(a.cfg.Connection.AgentServerURL)
	if err != nil {
		return err
	}
	tempClient := httpclient.NewClient(httpURL, a.cfg.Identification.AgentToken)
	registered, err := tempClient.Register(a.ctx, info)
	if err != nil {
		return fmt.Errorf("register to agent-server failed: %w", err)
	}
	a.info = registered
	a.wsURL = registered.WSURL
	if a.wsURL == "" {
		a.wsURL = a.cfg.Connection.AgentServerURL
	}
	if a.wsClient != nil {
		a.wsClient.SetOverrideURL(a.wsURL)
	}
	logger.GetLogger().WithFields(map[string]interface{}{
		"agent_id":   a.info.ID,
		"agent_name": a.info.Name,
		"host_id":    a.cfg.Identification.HostID,
		"mode":       "agent-server",
	}).Info("agent registered to agent-server")

	// 首次注册时使用真实 agentID 创建 Outbox；重注册时保留旧 Outbox，避免丢失待补发消息
	if a.outbox == nil || !wasRegistered {
		if a.outbox != nil {
			a.outbox.Close() // 关闭旧的 Outbox（例如 placeholder）
		}
		// 确定 outbox 文件存储目录
		outboxDir := ""
		logDir := a.cfg.Logging.LogDir
		if logDir != "" {
			outboxDir = logDir
		} else {
			// 使用默认目录
			outboxDir = "."
		}
		a.outbox = wsclient.NewFileOutbox(a.info.ID, outboxDir, a.cfg.Connection.WSOutboxMaxSize)
	}

	return nil
}

func (a *Agent) ensureWebSocketConnection() error {
	if a.wsClient == nil {
		return fmt.Errorf("websocket client not initialized")
	}
	if a.info == nil {
		return fmt.Errorf("agent info missing, register before connecting websocket")
	}
	return a.connectWithBackoff()
}

// CancelTask 取消任务
func (a *Agent) CancelTask(taskID string) error {
	// 先尝试从 executor 取消
	if err := a.executor.CancelTask(taskID); err != nil {
		// 如果 executor 中没有，检查是否在跟踪映射中
		a.tasksLock.RLock()
		_, exists := a.runningTasks[taskID]
		a.tasksLock.RUnlock()

		if !exists {
			return fmt.Errorf("task %s not found", taskID)
		}
		// 如果任务在跟踪映射中但不在 executor 中，可能是文件传输任务
		// 文件传输任务通常很快完成，可能已经不在 executor 中了
		return fmt.Errorf("task %s cannot be cancelled (may have completed)", taskID)
	}
	return nil
}

// GetTaskStatus 获取任务状态
func (a *Agent) GetTaskStatus(taskID string) (*executor.RunningTask, bool) {
	// 先从 executor 获取
	if task, exists := a.executor.GetTaskStatus(taskID); exists {
		// 同时更新跟踪映射
		a.tasksLock.Lock()
		a.runningTasks[taskID] = task
		a.tasksLock.Unlock()
		return task, true
	}

	// 如果 executor 中没有，检查跟踪映射（可能是已完成但还未清理的任务）
	a.tasksLock.RLock()
	defer a.tasksLock.RUnlock()
	task, exists := a.runningTasks[taskID]
	return task, exists
}

// trackTaskStatus 跟踪任务状态，定期从 executor 获取最新状态
func (a *Agent) trackTaskStatus(taskID string, stopCh chan struct{}) {
	ticker := time.NewTicker(500 * time.Millisecond) // 每500ms检查一次
	defer ticker.Stop()

	for {
		select {
		case <-stopCh:
			return
		case <-a.ctx.Done():
			return
		case <-ticker.C:
			// 从 executor 获取任务状态
			if task, exists := a.executor.GetTaskStatus(taskID); exists {
				// 更新跟踪映射
				a.tasksLock.Lock()
				a.runningTasks[taskID] = task
				a.tasksLock.Unlock()
			} else {
				// 如果 executor 中不存在，说明任务已完成，停止跟踪
				return
			}
		}
	}
}

func collectSystemInfo() SystemInfo {
	// 使用 system 包收集更详细的系统信息
	return system.CollectSystemInfo()
}

func deriveAgentServerHTTPURL(raw string) (string, error) {
	if raw == "" {
		return "", fmt.Errorf("agent_server_url is empty")
	}
	u, err := url.Parse(raw)
	if err != nil {
		return "", fmt.Errorf("parse agent_server_url: %w", err)
	}
	switch u.Scheme {
	case "ws":
		u.Scheme = "http"
	case "wss":
		u.Scheme = "https"
	case "http", "https":
	default:
		return "", fmt.Errorf("unsupported scheme %q for agent_server_url", u.Scheme)
	}
	u.Path = ""
	u.RawQuery = ""
	u.Fragment = ""
	return u.String(), nil
}

func (a *Agent) connectWithBackoff() error {
	primary := a.wsURL
	if primary == "" {
		primary = a.cfg.Connection.AgentServerURL
	}
	var endpoints []string
	if primary != "" {
		endpoints = append(endpoints, primary)
	}
	if a.cfg.Connection.AgentServerBackup != "" {
		endpoints = append(endpoints, a.cfg.Connection.AgentServerBackup)
	}
	if len(endpoints) == 0 {
		return fmt.Errorf("no agent server endpoints configured")
	}

	initial := time.Duration(a.cfg.Connection.WSBackoffInitialMs) * time.Millisecond
	if initial <= 0 {
		initial = time.Duration(constants.WSBackoffInitialMs) * time.Millisecond
	}
	maxDelay := time.Duration(a.cfg.Connection.WSBackoffMaxMs) * time.Millisecond
	if maxDelay <= 0 {
		maxDelay = time.Duration(constants.WSBackoffMaxMs) * time.Millisecond
	}
	attempts := a.cfg.Connection.WSMaxRetries
	if attempts <= 0 {
		attempts = constants.WSMaxRetries
	}

	var idx int
	err := retry.Do(
		func() error {
			ep := endpoints[idx%len(endpoints)]
			idx++
			a.wsClient.SetOverrideURL(ep)
			if err := a.wsClient.Connect(a.info.ID); err != nil {
				logger.GetLogger().WithFields(map[string]interface{}{
					"endpoint": ep,
				}).Warn("websocket connect failed")
				return err
			}
			a.flushOutbox()
			return nil
		},
		retry.Attempts(uint(attempts)),
		retry.Delay(initial),
		retry.MaxDelay(maxDelay),
		retry.DelayType(retry.BackOffDelay),
		retry.LastErrorOnly(true),
		retry.Context(a.ctx),
	)
	return err
}

func (a *Agent) flushOutbox() {
	if a.wsClient == nil || !a.wsClient.IsConnected() || a.outbox == nil {
		return
	}

	// 小批量冲刷，避免一次性写太多导致阻塞
	batchSize := a.outboxFlushBatch
	if batchSize <= 0 {
		batchSize = constants.OutboxFlushBatchSize
	}
	for {
		batch := a.outbox.Drain(batchSize)
		if len(batch) == 0 {
			return
		}
		for i := range batch {
			msg := batch[i]
			if err := a.wsClient.SendReliable(&msg); err != nil {
				// 发送失败：回滚到 outbox（保持顺序）
				a.outbox.Enqueue(msg)
				return
			}
		}
	}
}

// onConfigChanged 处理配置变更事件（由 config.Subscribe 调用）。
// 仅应用安全可热更新的字段，避免影响已有连接和任务流。
func (a *Agent) onConfigChanged(newCfg *config.Config) {
	if newCfg == nil {
		return
	}

	// 动态调整心跳间隔
	if hb := newCfg.Task.HeartbeatInterval; hb > 0 {
		old := atomic.LoadInt64(&a.heartbeatIntervalSec)
		if int64(hb) != old {
			atomic.StoreInt64(&a.heartbeatIntervalSec, int64(hb))
			logger.GetLogger().WithField("heartbeat_interval", hb).Info("heartbeat interval updated from config")
		}
	}

	// 动态调整日志级别
	if newCfg.Logging.LogLevel != "" {
		logger.SetLevel(newCfg.Logging.LogLevel)
	}
}
