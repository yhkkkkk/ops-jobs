package core

import (
	"context"
	"fmt"
	"net"
	"net/url"
	"sort"
	"sync"
	"time"

	"github.com/avast/retry-go/v4"
	"github.com/marusama/semaphore/v2"

	"ops-job-agent/internal/api"
	"ops-job-agent/internal/config"
	"ops-job-agent/internal/errors"
	"ops-job-agent/internal/executor"
	"ops-job-agent/internal/httpclient"
	"ops-job-agent/internal/logger"
	"ops-job-agent/internal/logstream"
	"ops-job-agent/internal/metrics"
	"ops-job-agent/internal/system"
	"ops-job-agent/internal/taskqueue"
	wsclient "ops-job-agent/internal/websocket"
)

// Agent 是 Agent 进程的核心对象，负责注册、心跳、拉任务等
type Agent struct {
	cfg            *config.Config
	client         *httpclient.Client   // HTTP 客户端（direct 模式）
	wsClient       *wsclient.Client     // WebSocket 客户端（agent-server 模式）
	taskQueue      *taskqueue.TaskQueue // asynq任务队列（可选）
	info           *AgentInfo
	system         SystemInfo
	ctx            context.Context
	cancel         context.CancelFunc
	wg             sync.WaitGroup
	started        bool
	executor       *executor.Executor
	scriptExecutor *executor.ScriptExecutor
	fileExecutor   *executor.FileTransferExecutor
	taskSemaphore  semaphore.Semaphore              // 控制并发任务数
	logStream      *logstream.LogStream             // 日志流管理器（direct 模式）
	runningTasks   map[string]*executor.RunningTask // 正在运行的任务映射
	tasksLock      sync.RWMutex                     // 任务映射锁
	wsURL          string
}

func NewAgent(cfg *config.Config) *Agent {
	ctx, cancel := context.WithCancel(context.Background())

	// 创建执行器
	exec := executor.NewExecutor(cfg.LogDir)
	scriptExec := executor.NewScriptExecutor(exec, "")
	fileExec := executor.NewFileTransferExecutor(exec)

	// 创建任务信号量（控制并发数）
	maxConcurrent := cfg.MaxConcurrentTasks
	if maxConcurrent <= 0 {
		maxConcurrent = 5
	}
	taskSemaphore := semaphore.New(maxConcurrent)

	// 创建 HTTP 客户端
	httpClient := httpclient.NewClient(cfg.ControlPlaneURL, cfg.AgentToken)

	// 创建日志流管理器（批量推送）
	batchSize := cfg.LogBatchSize
	if batchSize <= 0 {
		batchSize = 10
	}
	flushInterval := time.Duration(cfg.LogFlushInterval) * time.Millisecond
	if flushInterval <= 0 {
		flushInterval = 200 * time.Millisecond
	}
	logStream := logstream.NewLogStream(httpClient, "", batchSize, flushInterval)

	// 创建asynq任务队列（如果启用）
	var taskQueue *taskqueue.TaskQueue
	if cfg.Asynq.Enabled && cfg.Redis.Enabled {
		var err error
		taskQueue, err = taskqueue.NewTaskQueue(cfg)
		if err != nil {
			logger.GetLogger().WithError(err).Warn("create task queue failed, continuing without asynq")
		} else {
			logger.GetLogger().Info("asynq task queue initialized for agent")
		}
	}

	agent := &Agent{
		cfg:            cfg,
		client:         httpClient,
		taskQueue:      taskQueue,
		system:         collectSystemInfo(),
		ctx:            ctx,
		cancel:         cancel,
		executor:       exec,
		scriptExecutor: scriptExec,
		fileExecutor:   fileExec,
		taskSemaphore:  taskSemaphore,
		logStream:      logStream,
		runningTasks:   make(map[string]*executor.RunningTask),
	}

	if cfg.Mode == "agent-server" {
		wsClient := wsclient.NewClient(cfg.AgentServerURL, cfg.AgentToken)
		wsClient.SetOnTask(agent.handleWebSocketTask)
		wsClient.SetOnCancel(agent.handleWebSocketCancel)
		agent.wsClient = wsClient
	}

	return agent
}

// Start 注册自身，并启动后台协程
func (a *Agent) Start() error {
	if a.started {
		return nil
	}

	if err := a.register(); err != nil {
		return err
	}

	// 启动asynq任务队列服务器（如果启用）
	if a.taskQueue != nil {
		// 注册任务处理器
		a.taskQueue.RegisterHandler(func(ctx context.Context, task *api.TaskSpec) error {
			// 从队列中取出任务后，直接执行
			go a.executeTask(task)
			return nil
		})

		// 启动asynq服务器
		a.wg.Add(1)
		go func() {
			defer a.wg.Done()
			if err := a.taskQueue.Start(); err != nil {
				logger.GetLogger().WithError(err).Error("asynq server error")
			}
		}()

		// Agent上线时，处理待处理任务
		go a.processPendingTasksFromQueue()
	}

	a.wg.Add(1)
	go a.heartbeatLoop()

	if a.cfg.Mode == "direct" {
		a.wg.Add(1)
	go a.taskLoop()
	} else {
		if err := a.ensureWebSocketConnection(); err != nil {
			return err
		}
	}

	a.started = true
	return nil
}

// Stop 优雅关闭
func (a *Agent) Stop() {
	a.cancel()
	// 停止日志流（direct 模式）
	if a.logStream != nil {
		a.logStream.Stop()
	}
	// 断开 WebSocket 连接（agent-server 模式）
	if a.wsClient != nil {
		a.wsClient.Disconnect()
	}
	// 停止asynq任务队列（如果启用）
	if a.taskQueue != nil {
		a.taskQueue.Stop()
	}
	a.wg.Wait()
}

func (a *Agent) heartbeatLoop() {
	defer a.wg.Done()
	interval := time.Duration(a.cfg.HeartbeatInterval) * time.Second
	if interval == 0 {
		interval = 10 * time.Second
	}
	ticker := time.NewTicker(interval)
	defer ticker.Stop()

	// 系统指标更新 ticker（每30秒更新一次）
	metricsTicker := time.NewTicker(30 * time.Second)
	defer metricsTicker.Stop()

	for {
		select {
		case <-a.ctx.Done():
			logger.GetLogger().Info("agent stopped")
			return
		case <-metricsTicker.C:
			// 更新系统指标
			a.updateSystemMetrics()
		case <-ticker.C:
			if a.info == nil {
				continue
			}
			system := collectSystemInfo()
			a.system = system

			if a.cfg.Mode == "agent-server" {
				// Agent-Server 模式：通过 WebSocket 发送心跳
				if a.wsClient != nil && a.wsClient.IsConnected() {
					if err := a.wsClient.SendHeartbeat(time.Now().Unix(), &system); err != nil {
						logger.GetLogger().WithError(err).Error("websocket heartbeat failed")
						// 尝试重连
						if err := a.wsClient.Connect(a.info.ID); err != nil {
							logger.GetLogger().WithError(err).Error("websocket reconnect failed")
						}
					}
				}
			} else {
				// Direct 模式：通过 HTTP 发送心跳
				payload := HeartbeatPayload{
					Timestamp: time.Now().Unix(),
					System:    &system,
				}
				if err := a.client.Heartbeat(a.ctx, a.info.ID, payload); err != nil {
					logger.GetLogger().WithError(err).Error("heartbeat failed")
					// 心跳失败时尝试重新注册
					if err := a.register(); err != nil {
						logger.GetLogger().WithError(err).Error("re-register failed")
					}
				}
			}
		}
	}
}

// taskLoop 轮询控制面，拉取任务并执行
func (a *Agent) taskLoop() {
	defer a.wg.Done()
	interval := time.Duration(a.cfg.TaskPollInterval) * time.Second
	if interval == 0 {
		interval = 5 * time.Second
	}
	ticker := time.NewTicker(interval)
	defer ticker.Stop()
	for {
		select {
		case <-a.ctx.Done():
			return
		case <-ticker.C:
			if a.info == nil {
				continue
			}
			task, err := a.client.FetchTask(a.ctx, a.info.ID)
			if err != nil {
				logger.GetLogger().WithError(err).Error("fetch task error")
				continue
			}
			if task == nil {
				continue
			}
			logger.GetLogger().WithFields(map[string]interface{}{
				"task_id":   task.ID,
				"task_name": task.Name,
			}).Info("received task")
			// 异步执行任务
			go a.executeTask(task)
		}
	}
}

// executeTask 执行任务
func (a *Agent) executeTask(task *TaskSpec) {
	// 获取信号量（控制并发）
	if err := a.taskSemaphore.Acquire(a.ctx, 1); err != nil {
		logger.GetLogger().WithError(err).Error("acquire semaphore failed")
		return
	}
	defer a.taskSemaphore.Release(1)

	logger.GetLogger().WithFields(map[string]interface{}{
		"task_id":   task.ID,
		"task_name": task.Name,
		"task_type": task.Type,
	}).Info("executing task")

	// 记录任务开始
	metrics.GetMetrics().RecordTaskStart()
	startTime := time.Now()

	// 日志回调函数 - 根据模式选择推送方式
	logCallback := func(logLine string) {
		// 记录到本地日志
		logger.GetLogger().WithField("task_id", task.ID).Info(logLine)

		if a.cfg.Mode == "agent-server" {
			// Agent-Server 模式：通过 WebSocket 发送日志
			if a.wsClient != nil && a.wsClient.IsConnected() {
				logEntry := api.LogEntry{
					Timestamp: time.Now().Unix(),
					Content:   logLine,
					Stream:    "stdout",
					TaskID:    task.ID,
				}
				// 直接发送单条日志（Agent-Server 会批量聚合）
				if err := a.wsClient.SendLogs(task.ID, []api.LogEntry{logEntry}); err != nil {
					logger.GetLogger().WithError(err).Error("send log via websocket failed")
				}
			}
		} else {
			// Direct 模式：通过 HTTP 批量推送
			if a.logStream != nil && a.info != nil {
				a.logStream.PushLog(task.ID, logstream.LogEntry{
					Timestamp: time.Now().Unix(),
					Level:     "info",
					Content:   logLine,
				})
			}
		}
	}

	var result *TaskResult
	var err error

	// 启动任务状态跟踪协程（仅对脚本任务）
	var stopTracking chan struct{}
	if task.Type == "script" || task.Type == "" {
		stopTracking = make(chan struct{})
		go a.trackTaskStatus(task.ID, stopTracking)
	}

	// 根据任务类型选择执行器
	switch task.Type {
	case "file_transfer":
		result, err = a.fileExecutor.ExecuteTransfer(a.ctx, task, logCallback)
	case "script":
		result, err = a.scriptExecutor.ExecuteScript(a.ctx, task, logCallback)
	default:
		// 默认使用脚本执行器
		result, err = a.scriptExecutor.ExecuteScript(a.ctx, task, logCallback)
	}

	// 停止任务状态跟踪
	if stopTracking != nil {
		close(stopTracking)
	}

	// 从运行任务映射中移除
	a.tasksLock.Lock()
	delete(a.runningTasks, task.ID)
	a.tasksLock.Unlock()

	if err != nil {
		logger.GetLogger().WithError(err).WithField("task_id", task.ID).Error("execute task error")
		// 上报错误结果
		result = &api.TaskResult{
			TaskID:     task.ID,
			Status:     "failed",
			ExitCode:   -1,
			StartedAt:  time.Now().Unix(),
			FinishedAt: time.Now().Unix(),
			ErrorMsg:   err.Error(),
			ErrorCode:  int(errors.GetErrorCode(err)),
		}
	}

	// 记录任务完成
	duration := time.Since(startTime)
	switch result.Status {
	case "success":
		metrics.GetMetrics().RecordTaskSuccess(duration)
	case "failed":
		metrics.GetMetrics().RecordTaskFailed(duration)
	case "cancelled":
		metrics.GetMetrics().RecordTaskCancelled(duration)
	}

	// 上报结果
	if a.cfg.Mode == "agent-server" {
		// Agent-Server 模式：通过 WebSocket 发送结果
		if a.wsClient != nil && a.wsClient.IsConnected() {
			if err := a.wsClient.SendTaskResult(result); err != nil {
				logger.GetLogger().WithError(err).WithField("task_id", task.ID).Error("report result via websocket failed")
			} else {
				logger.GetLogger().WithFields(map[string]interface{}{
					"task_id": task.ID,
					"status":  result.Status,
				}).Info("task completed")
			}
		}
	} else {
		// Direct 模式：通过 HTTP 发送结果
		if err := a.client.ReportResult(a.ctx, a.info.ID, *result); err != nil {
			logger.GetLogger().WithError(err).WithField("task_id", task.ID).Error("report result error")
		} else {
			logger.GetLogger().WithFields(map[string]interface{}{
				"task_id": task.ID,
				"status":  result.Status,
			}).Info("task completed")
		}
		// 任务完成后，清理日志流缓冲区
		if a.logStream != nil {
			a.logStream.RemoveTask(task.ID)
		}
	}
}

// register 向控制面或 Agent-Server 注册自身
func (a *Agent) register() error {
	info := AgentInfo{
		Name:   a.cfg.AgentName,
		Labels: a.cfg.AgentLabels,
		System: &a.system,
	}

	if a.cfg.Mode == "agent-server" {
		// Agent-Server 模式：向 Agent-Server 注册
		httpURL, err := deriveAgentServerHTTPURL(a.cfg.AgentServerURL)
		if err != nil {
			return err
		}
		tempClient := httpclient.NewClient(httpURL, a.cfg.AgentToken)
		registered, err := tempClient.Register(a.ctx, info)
		if err != nil {
			return fmt.Errorf("register to agent-server failed: %w", err)
		}
		a.info = registered
		a.wsURL = registered.WSURL
		if a.wsURL == "" {
			a.wsURL = a.cfg.AgentServerURL
		}
		if a.wsClient != nil {
			a.wsClient.SetOverrideURL(a.wsURL)
		}
		logger.GetLogger().WithFields(map[string]interface{}{
			"agent_id":   a.info.ID,
			"agent_name": a.info.Name,
			"mode":       "agent-server",
		}).Info("agent registered to agent-server")
	} else {
		// Direct 模式：向控制面注册
		registered, err := a.client.Register(a.ctx, info)
		if err != nil {
			return err
		}
		a.info = registered
		// 更新日志流的 agent ID
		if a.logStream != nil {
			// 重新创建日志流以更新 agent ID
			a.logStream.Stop()
			batchSize := a.cfg.LogBatchSize
			if batchSize <= 0 {
				batchSize = 10
			}
			flushInterval := time.Duration(a.cfg.LogFlushInterval) * time.Millisecond
			if flushInterval <= 0 {
				flushInterval = 200 * time.Millisecond
			}
			a.logStream = logstream.NewLogStream(a.client, a.info.ID, batchSize, flushInterval)
		}
		logger.GetLogger().WithFields(map[string]interface{}{
			"agent_id":   a.info.ID,
			"agent_name": a.info.Name,
			"mode":       "direct",
		}).Info("agent registered to control plane")
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

// updateSystemMetrics 更新系统指标
func (a *Agent) updateSystemMetrics() {
	systemInfo := system.CollectSystemInfo()
	metrics.GetMetrics().UpdateSystemMetrics(systemInfo.CPUUsage, systemInfo.MemoryUsage)
}

// CancelTask 取消任务 - 实现 TaskService 接口
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

// GetTaskStatus 获取任务状态 - 实现 TaskService 接口
func (a *Agent) GetTaskStatus(taskID string) (*executor.RunningTask, bool) {
	// 先从 executor 获取（这是最准确的）
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

// processPendingTasksFromQueue 从asynq队列拉取待处理任务并执行
// 在Agent上线时调用，处理离线期间积累的任务
func (a *Agent) processPendingTasksFromQueue() {
	if a.taskQueue == nil || a.info == nil {
		return
	}

	// 等待Agent注册完成
	time.Sleep(2 * time.Second)

	// 从队列中拉取待处理任务（最多100个）
	tasks, err := a.taskQueue.ListPendingTasks(a.info.ID, 100)
	if err != nil {
		logger.GetLogger().WithError(err).Error("list pending tasks from queue failed")
		return
	}

	if len(tasks) == 0 {
		return
	}

	logger.GetLogger().WithFields(map[string]interface{}{
		"agent_id":   a.info.ID,
		"task_count": len(tasks),
	}).Info("processing pending tasks from asynq queue")

	// 执行每个任务
	for _, task := range tasks {
		go a.executeTask(task)
		// 避免同时启动太多任务，稍微延迟
		time.Sleep(100 * time.Millisecond)
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
		primary = a.cfg.AgentServerURL
	}
	endpoints := []string{}
	if primary != "" {
		endpoints = append(endpoints, primary)
	}
	if a.cfg.AgentServerBackup != "" {
		endpoints = append(endpoints, a.cfg.AgentServerBackup)
	}
	if len(endpoints) == 0 {
		return fmt.Errorf("no agent server endpoints configured")
	}

	initial := time.Duration(a.cfg.WSBackoffInitialMs) * time.Millisecond
	if initial <= 0 {
		initial = time.Second
	}
	max := time.Duration(a.cfg.WSBackoffMaxMs) * time.Millisecond
	if max <= 0 {
		max = 30 * time.Second
	}
	attempts := a.cfg.WSMaxRetries
	if attempts <= 0 {
		attempts = 6
	}

	var idx int
	return retry.Do(
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
			return nil
		},
		retry.Attempts(uint(attempts)),
		retry.Delay(initial),
		retry.MaxDelay(max),
		retry.DelayType(retry.BackOffDelay),
		retry.LastErrorOnly(true),
		retry.Context(a.ctx),
	)
}

func listIPs() []string {
	ifaces, err := net.Interfaces()
	if err != nil {
		return nil
	}
	seen := map[string]struct{}{}
	for _, iface := range ifaces {
		if (iface.Flags & net.FlagUp) == 0 {
			continue
		}
		addrs, err := iface.Addrs()
		if err != nil {
			continue
		}
		for _, addr := range addrs {
			ip, _, err := net.ParseCIDR(addr.String())
			if err != nil {
				continue
			}
			if ip == nil || ip.IsLoopback() {
				continue
			}
			seen[ip.String()] = struct{}{}
		}
	}
	ips := make([]string, 0, len(seen))
	for ip := range seen {
		ips = append(ips, ip)
	}
	sort.Strings(ips)
	return ips
}
