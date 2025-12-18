package server

import (
	"bytes"
	"context"
	"crypto/hmac"
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"strconv"
	"time"

	"ops-job-agent-server/internal/agent"
	"ops-job-agent-server/internal/config"
	"ops-job-agent-server/internal/controlplane"
	logstream "ops-job-agent-server/internal/log"
	"ops-job-agent-server/internal/logger"
	"ops-job-agent-server/internal/task"
	"ops-job-agent-server/pkg/api"

	"github.com/gin-gonic/gin"
	"github.com/gorilla/websocket"
	"github.com/hibiken/asynq"
)

var upgrader = websocket.Upgrader{
	CheckOrigin: func(r *http.Request) bool {
		return true // 允许跨域，生产环境应该限制
	},
}

// Server Agent-Server 服务器
type Server struct {
	cfg            *config.Config
	engine         *gin.Engine
	httpServer     *http.Server
	agentManager   *agent.Manager
	cpClient       *controlplane.Client
	taskDispatcher *task.Dispatcher
	taskQueue      *task.TaskQueue
	logStream      *logstream.StreamWriter
	resultStream   *logstream.ResultStreamWriter
	statusStream   *logstream.StatusStreamWriter
}

// New 创建服务器
func New(cfg *config.Config) (*Server, error) {
	gin.SetMode(gin.ReleaseMode)
	engine := gin.New()
	engine.Use(gin.Recovery())
	engine.Use(gin.Logger())

	// 创建 Agent 管理器
	agentMgr := agent.NewManager(
		cfg.Agent.MaxConnections,
		cfg.Agent.HeartbeatTimeout,
	)

	// 创建控制面客户端
	cpClient := controlplane.NewClient(cfg.ControlPlane.URL, cfg.ControlPlane.Token, cfg.ControlPlane.Scope, cfg.ControlPlane.Timeout)

	// 创建任务队列（如果启用）
	var taskQueue *task.TaskQueue
	asynqEnabled := cfg.Asynq.Enabled && cfg.Redis.Enabled
	if asynqEnabled {
		var err error
		taskQueue, err = task.NewTaskQueue(cfg.Redis.Addr, cfg.Redis.Password, cfg.Redis.DB)
		if err != nil {
			return nil, fmt.Errorf("create task queue: %w", err)
		}
		logger.GetLogger().Info("asynq task queue initialized")
	}

	// 创建任务分发器（
	taskDispatcher := task.NewDispatcher(agentMgr, cpClient, taskQueue, asynqEnabled)

	// 创建日志流写入器
	logStream, err := logstream.NewStreamWriter(cfg)
	if err != nil {
		return nil, fmt.Errorf("create log stream writer: %w", err)
	}

	// 创建结果流写入器
	resultStream, err := logstream.NewResultStreamWriter(cfg)
	if err != nil {
		return nil, fmt.Errorf("create result stream writer: %w", err)
	}

	// 创建状态流写入器
	statusStream, err := logstream.NewStatusStreamWriter(cfg)
	if err != nil {
		return nil, fmt.Errorf("create status stream writer: %w", err)
	}

	s := &Server{
		cfg:            cfg,
		engine:         engine,
		agentManager:   agentMgr,
		cpClient:       cpClient,
		taskDispatcher: taskDispatcher,
		taskQueue:      taskQueue,
		logStream:      logStream,
		resultStream:   resultStream,
		statusStream:   statusStream,
	}

	s.setupRoutes()

	return s, nil
}

// setupRoutes 设置路由
func (s *Server) setupRoutes() {
	api := s.engine.Group("/api")
	if s.cfg.Auth.RequireSignature && s.cfg.Auth.SharedSecret != "" {
		api.Use(s.requireSignature())
	}
	{
		// Agent 注册
		api.POST("/agents/register", s.handleRegister)
		// Agent 列表
		api.GET("/agents", s.requireScope(), s.handleListAgents)
		// Agent 详情
		api.GET("/agents/:id", s.requireScope(), s.handleGetAgent)
		// 控制面推送任务到指定 Agent
		api.POST("/agents/:id/tasks", s.requireScope(), s.handlePushTask)
		// 取消指定 Agent 的任务
		api.POST("/agents/:id/tasks/:task_id/cancel", s.requireScope(), s.handleCancelTask)
		// 任务队列统计信息
		api.GET("/stats/queues", s.requireScope(), s.handleGetStats)
	}

	// WebSocket 连接
	s.engine.GET("/ws/agent/:id", s.handleWebSocket)
}

// Start 启动服务器
func (s *Server) Start() error {
	// 启动任务分发器
	s.taskDispatcher.Start()

	// 启动asynq服务器（如果启用）
	if s.taskQueue != nil {
		go func() {
			if err := s.taskQueue.Start(); err != nil {
				logger.GetLogger().WithError(err).Error("asynq server error")
			}
		}()
		logger.GetLogger().Info("asynq server started")
	}

	// 启动清理非活跃连接的 goroutine
	go s.cleanupLoop()

	addr := fmt.Sprintf("%s:%d", s.cfg.Server.Host, s.cfg.Server.Port)
	s.httpServer = &http.Server{
		Addr:         addr,
		Handler:      s.engine,
		ReadTimeout:  s.cfg.Server.ReadTimeout,
		WriteTimeout: s.cfg.Server.WriteTimeout,
	}

	logger.GetLogger().WithField("addr", addr).Info("server started")
	return s.httpServer.ListenAndServe()
}

// Stop 停止服务器
func (s *Server) Stop() {
	// 停止任务分发器
	s.taskDispatcher.Stop()

	// 停止asynq服务器（如果启用）
	if s.taskQueue != nil {
		s.taskQueue.Stop()
	}

	ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
	defer cancel()

	if err := s.httpServer.Shutdown(ctx); err != nil {
		logger.GetLogger().WithError(err).Error("server shutdown error")
	}
}

// cleanupLoop 定期清理非活跃连接
func (s *Server) cleanupLoop() {
	ticker := time.NewTicker(30 * time.Second)
	defer ticker.Stop()

	for {
		select {
		case <-ticker.C:
			// 清理非活跃连接，并为变为离线的连接写一条 offline 状态
			agents := s.agentManager.List()
			s.agentManager.CleanupInactive()
			for _, a := range agents {
				if !a.IsAlive(s.cfg.Agent.HeartbeatTimeout) {
					go s.pushStatus(context.Background(), a, "offline", nil)
				}
			}
		}
	}
}

// pushStatus 将 Agent 在线状态写入状态流
func (s *Server) pushStatus(ctx context.Context, conn *agent.Connection, status string, payload map[string]interface{}) {
	if s.statusStream == nil || conn == nil {
		return
	}

	fields := map[string]interface{}{
		"agent_id":       conn.ID,
		"agent_name":     conn.Name,
		"status":         status,
		"last_heartbeat": conn.LastHeartbeat.UnixMilli(),
	}

	// 从 SystemInfo / payload 中提取补充信息
	if conn.System != nil {
		if conn.System.Hostname != "" {
			fields["hostname"] = conn.System.Hostname
		}
		if conn.System.OS != "" {
			fields["os"] = conn.System.OS
		}
		if conn.System.Arch != "" {
			fields["arch"] = conn.System.Arch
		}
	}

	_ = payload // 预留：如需从心跳 payload 中提取更多信息

	if err := s.statusStream.PushStatus(ctx, fields); err != nil {
		logger.GetLogger().WithError(err).WithField("agent_id", conn.ID).Warn("push status to stream failed")
	}
}

// handleRegister 处理 Agent 注册
func (s *Server) handleRegister(c *gin.Context) {
	var req api.RegisterRequest
	if err := c.ShouldBindJSON(&req); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": err.Error()})
		return
	}

	conn, agentID, err := s.agentManager.Register(req.Name, req.Token, req.Labels, req.System)
	if err != nil {
		if err == agent.ErrMaxConnections {
			c.JSON(http.StatusServiceUnavailable, gin.H{"error": "max connections reached"})
			return
		}
		c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}

	wsURL := fmt.Sprintf("ws://%s:%d/ws/agent/%s?token=%s",
		s.cfg.Server.Host, s.cfg.Server.Port, agentID, conn.Token)

	c.JSON(http.StatusOK, api.RegisterResponse{
		ID:     agentID,
		Name:   req.Name,
		Status: "active",
		WSURL:  wsURL,
	})
}

// handleListAgents 列出所有 Agent
func (s *Server) handleListAgents(c *gin.Context) {
	agents := s.agentManager.List()
	result := make([]map[string]interface{}, 0, len(agents))
	for _, agent := range agents {
		result = append(result, map[string]interface{}{
			"id":             agent.ID,
			"name":           agent.Name,
			"status":         agent.Status,
			"last_heartbeat": agent.LastHeartbeat,
		})
	}
	c.JSON(http.StatusOK, gin.H{"agents": result})
}

// handleGetAgent 获取 Agent 详情
func (s *Server) handleGetAgent(c *gin.Context) {
	agentID := c.Param("id")
	conn, exists := s.agentManager.Get(agentID)
	if !exists {
		c.JSON(http.StatusNotFound, gin.H{"error": "agent not found"})
		return
	}

	c.JSON(http.StatusOK, gin.H{
		"id":             conn.ID,
		"name":           conn.Name,
		"status":         conn.Status,
		"last_heartbeat": conn.LastHeartbeat,
		"labels":         conn.Labels,
		"system":         conn.System,
	})
}

// handlePushTask 处理控制面推送的任务
func (s *Server) handlePushTask(c *gin.Context) {
	agentID := c.Param("id")

	var taskSpec api.TaskSpec
	if err := c.ShouldBindJSON(&taskSpec); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": err.Error()})
		return
	}

	if err := s.taskDispatcher.DispatchTaskToAgent(agentID, &taskSpec); err != nil {
		if err == agent.ErrAgentNotFound {
			c.JSON(http.StatusNotFound, gin.H{"error": "agent not found"})
			return
		}
		if err == agent.ErrConnectionClosed {
			c.JSON(http.StatusServiceUnavailable, gin.H{"error": "agent connection closed"})
			return
		}
		c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}

	c.JSON(http.StatusOK, gin.H{
		"task_id":  taskSpec.ID,
		"agent_id": agentID,
		"status":   "dispatched",
	})
}

// handleCancelTask 处理取消任务请求
// 支持两种情况：
// 1. Agent 在线：通过 WebSocket 发送取消消息
// 2. Agent 离线：从 asynq 队列中删除任务
func (s *Server) handleCancelTask(c *gin.Context) {
	agentID := c.Param("id")
	taskID := c.Param("task_id")

	conn, exists := s.agentManager.Get(agentID)
	if !exists {
		// Agent 不存在，尝试从队列中删除任务
		if s.taskQueue != nil {
			if err := s.cancelTaskFromQueue(agentID, taskID); err != nil {
				c.JSON(http.StatusNotFound, gin.H{"error": "agent not found and task not found in queue"})
				return
			}
			c.JSON(http.StatusOK, gin.H{
				"task_id":  taskID,
				"agent_id": agentID,
				"status":   "cancelled",
				"source":   "queue",
			})
			return
		}
		c.JSON(http.StatusNotFound, gin.H{"error": "agent not found"})
		return
	}

	// Agent 在线，尝试通过 WebSocket 发送取消消息
	if conn.Status == "active" && conn.Conn != nil {
	if err := conn.SendCancelTask(taskID); err != nil {
		logger.GetLogger().WithError(err).WithFields(map[string]interface{}{
			"agent_id": agentID,
			"task_id":  taskID,
		}).Error("send cancel task message failed")
			// WebSocket 发送失败，尝试从队列中删除
			if s.taskQueue != nil {
				if err := s.cancelTaskFromQueue(agentID, taskID); err == nil {
					c.JSON(http.StatusOK, gin.H{
						"task_id":  taskID,
						"agent_id": agentID,
						"status":   "cancelled",
						"source":   "queue",
					})
					return
				}
			}
		c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}

	logger.GetLogger().WithFields(map[string]interface{}{
		"agent_id": agentID,
		"task_id":  taskID,
		}).Info("cancel task request sent to agent via websocket")

	c.JSON(http.StatusOK, gin.H{
		"task_id":  taskID,
		"agent_id": agentID,
		"status":   "cancelled",
			"source":   "websocket",
	})
		return
	}

	// Agent 连接不活跃，尝试从队列中删除
	if s.taskQueue != nil {
		if err := s.cancelTaskFromQueue(agentID, taskID); err != nil {
			c.JSON(http.StatusServiceUnavailable, gin.H{"error": "agent connection is not active and task not found in queue"})
			return
		}
		c.JSON(http.StatusOK, gin.H{
			"task_id":  taskID,
			"agent_id": agentID,
			"status":   "cancelled",
			"source":   "queue",
		})
		return
	}

	c.JSON(http.StatusServiceUnavailable, gin.H{"error": "agent connection is not active"})
}

// cancelTaskFromQueue 从队列中取消任务
// 需要先查询任务找到 asynq 的 taskID，然后删除
func (s *Server) cancelTaskFromQueue(agentID, taskID string) error {
	if s.taskQueue == nil {
		return fmt.Errorf("task queue not enabled")
	}

	// 查询所有队列，找到匹配的任务
	queues := []string{task.QueueCritical, task.QueueDefault, task.QueueLow}
	states := []string{"pending", "active", "retry", "scheduled"}

	for _, queueName := range queues {
		inspector := asynq.NewInspector(s.taskQueue.GetRedisOpt())
		defer inspector.Close()

		for _, state := range states {
			// 查询该状态的任务
			var taskInfos []*asynq.TaskInfo
			var err error

			switch state {
			case "pending":
				taskInfos, err = inspector.ListPendingTasks(queueName, asynq.PageSize(100), asynq.Page(1))
			case "active":
				taskInfos, err = inspector.ListActiveTasks(queueName, asynq.PageSize(100), asynq.Page(1))
			case "retry":
				taskInfos, err = inspector.ListRetryTasks(queueName, asynq.PageSize(100), asynq.Page(1))
			case "scheduled":
				taskInfos, err = inspector.ListScheduledTasks(queueName, asynq.PageSize(100), asynq.Page(1))
			default:
				continue
			}

			if err != nil {
				continue
			}

			// 遍历任务，找到匹配的
			for _, taskInfo := range taskInfos {
				// 解析任务负载
				var payload task.TaskPayload
				if err := json.Unmarshal(taskInfo.Payload, &payload); err != nil {
					continue
				}

				// 检查是否匹配 agentID 和 taskID
				if payload.AgentID == agentID && payload.Task != nil && payload.Task.ID == taskID {
					// 找到匹配的任务，删除它
					if err := inspector.DeleteTask(queueName, taskInfo.ID); err != nil {
						logger.GetLogger().WithError(err).WithFields(map[string]interface{}{
							"agent_id":    agentID,
							"task_id":     taskID,
							"asynq_id":    taskInfo.ID,
							"queue":       queueName,
							"state":       state,
						}).Error("delete task from queue failed")
						return err
					}

					logger.GetLogger().WithFields(map[string]interface{}{
						"agent_id": agentID,
						"task_id":  taskID,
						"asynq_id": taskInfo.ID,
						"queue":    queueName,
						"state":    state,
					}).Info("task cancelled from queue")
					return nil
				}
			}
		}
	}

	return fmt.Errorf("task not found in any queue")
}

// handleWebSocket 处理 WebSocket 连接
func (s *Server) handleWebSocket(c *gin.Context) {
	agentID := c.Param("id")
	token := c.Query("token")

	// 获取 Agent 连接
	conn, exists := s.agentManager.Get(agentID)
	if !exists {
		c.JSON(http.StatusNotFound, gin.H{"error": "agent not found"})
		return
	}

	// 验证 token
	if conn.Token != token {
		c.JSON(http.StatusUnauthorized, gin.H{"error": "invalid token"})
		return
	}

	// 升级为 WebSocket
	ws, err := upgrader.Upgrade(c.Writer, c.Request, nil)
	if err != nil {
		logger.GetLogger().WithError(err).Error("websocket upgrade failed")
		return
	}
	defer ws.Close()

	// 建立连接
	agentConn, err := s.agentManager.Connect(agentID, token, ws)
	if err != nil {
		logger.GetLogger().WithError(err).Error("connect agent failed")
		return
	}

	logger.GetLogger().WithFields(map[string]interface{}{
		"agent_id": agentID,
	}).Info("websocket connected")

	// Agent上线时，处理待处理任务
	if s.taskDispatcher != nil {
		go func() {
			if err := s.taskDispatcher.ProcessPendingTasksForAgent(agentID); err != nil {
				logger.GetLogger().WithError(err).WithField("agent_id", agentID).Error("process pending tasks failed")
			}
		}()
	}

	// 启动消息处理
	s.handleWebSocketMessages(agentConn)
}

// requireScope 校验来自控制面的请求是否符合配置的 scope，用于多租户/作用域隔离
func (s *Server) requireScope() gin.HandlerFunc {
	expected := s.cfg.ControlPlane.Scope
	return func(c *gin.Context) {
		if expected == "" {
			c.Next()
			return
		}
		scope := c.GetHeader("X-Scope")
		if scope == "" {
			c.AbortWithStatusJSON(http.StatusForbidden, gin.H{"error": "missing X-Scope"})
			return
		}
		if scope != expected {
			c.AbortWithStatusJSON(http.StatusForbidden, gin.H{"error": "invalid scope"})
			return
		}
		c.Next()
	}
}

// requireSignature 校验 HMAC 时间窗签名：X-Timestamp + X-Signature
func (s *Server) requireSignature() gin.HandlerFunc {
	secret := s.cfg.Auth.SharedSecret
	clockSkew := s.cfg.Auth.ClockSkew
	if clockSkew <= 0 {
		clockSkew = 5 * time.Minute
	}
	return func(c *gin.Context) {
		if secret == "" {
			c.Next()
			return
		}

		tsStr := c.GetHeader("X-Timestamp")
		sig := c.GetHeader("X-Signature")
		if tsStr == "" || sig == "" {
			c.AbortWithStatusJSON(http.StatusForbidden, gin.H{"error": "missing signature headers"})
			return
		}
		ts, err := strconv.ParseInt(tsStr, 10, 64)
		if err != nil {
			c.AbortWithStatusJSON(http.StatusForbidden, gin.H{"error": "invalid timestamp"})
			return
		}
		now := time.Now().Unix()
		if absInt64(now-ts) > int64(clockSkew.Seconds()) {
			c.AbortWithStatusJSON(http.StatusForbidden, gin.H{"error": "timestamp skew too large"})
			return
		}

		bodyBytes, err := c.GetRawData()
		if err != nil {
			c.AbortWithStatusJSON(http.StatusForbidden, gin.H{"error": "failed to read body"})
			return
		}
		// 读过 body 之后需要恢复
		c.Request.Body = io.NopCloser(bytes.NewBuffer(bodyBytes))

		path := c.FullPath()
		if path == "" {
			path = c.Request.URL.Path
		}
		expected := computeHMAC(secret, c.Request.Method, path, tsStr, bodyBytes)
		if !hmac.Equal([]byte(expected), []byte(sig)) {
			c.AbortWithStatusJSON(http.StatusForbidden, gin.H{"error": "invalid signature"})
			return
		}

		c.Next()
	}
}

func computeHMAC(secret, method, path, ts string, body []byte) string {
	mac := hmac.New(sha256.New, []byte(secret))
	// message = timestamp + "\n" + method + "\n" + path + "\n" + body
	mac.Write([]byte(ts))
	mac.Write([]byte("\n"))
	mac.Write([]byte(method))
	mac.Write([]byte("\n"))
	mac.Write([]byte(path))
	mac.Write([]byte("\n"))
	mac.Write(body)
	return hex.EncodeToString(mac.Sum(nil))
}

func absInt64(v int64) int64 {
	if v < 0 {
		return -v
	}
	return v
}

// handleWebSocketMessages 处理 WebSocket 消息
func (s *Server) handleWebSocketMessages(conn *agent.Connection) {
	defer func() {
		s.agentManager.Remove(conn.ID)
		logger.GetLogger().WithField("agent_id", conn.ID).Info("websocket disconnected")
	}()

	// 启动 goroutine 处理任务队列
	go s.handleTaskQueue(conn)

	// 启动 goroutine 处理日志缓冲
	go s.handleLogBuffer(conn)

	// 读取消息
	for {
		var msg api.WebSocketMessage
		if err := conn.Conn.ReadJSON(&msg); err != nil {
			if websocket.IsUnexpectedCloseError(err, websocket.CloseGoingAway, websocket.CloseAbnormalClosure) {
				logger.GetLogger().WithError(err).Error("websocket read error")
			}
			break
		}

		switch msg.Type {
		case "heartbeat":
			conn.UpdateHeartbeat()
			// 写入状态流：online
			go s.pushStatus(context.Background(), conn, "online", msg.Payload)

		case "task_result":
			// 优先写入结果流，失败再回退 HTTP
			if msg.Result != nil {
				go s.pushResult(context.Background(), conn.ID, msg.Result)
			}

		case "log":
			// 将日志添加到缓冲区
			if msg.Logs != nil {
				for i := range msg.Logs {
					// 设置 task_id（如果消息中包含）
					if msg.TaskID != "" {
						msg.Logs[i].TaskID = msg.TaskID
					}
					select {
					case conn.LogBuffer <- &msg.Logs[i]:
					default:
						// 缓冲区满，丢弃日志
					}
				}
			}
		}
	}
}

// handleTaskQueue 处理任务队列
func (s *Server) handleTaskQueue(conn *agent.Connection) {
	for task := range conn.TaskQueue {
		if err := conn.SendTask(task); err != nil {
			logger.GetLogger().WithError(err).WithField("task_id", task.ID).Error("send task failed")
		}
	}
}

// handleLogBuffer 处理日志缓冲
func (s *Server) handleLogBuffer(conn *agent.Connection) {
	ticker := time.NewTicker(2 * time.Second)
	defer ticker.Stop()

	// 按 task_id 分组日志
	taskLogs := make(map[string][]api.LogEntry)
	for {
		select {
		case logEntry, ok := <-conn.LogBuffer:
			if !ok {
				// 通道关闭，发送剩余日志
				for taskID, logs := range taskLogs {
					if len(logs) > 0 {
						s.pushLogs(context.Background(), conn.ID, taskID, logs)
					}
				}
				return
			}

			// 从日志条目中获取 task_id
			taskID := logEntry.TaskID
			if taskID == "" {
				taskID = "unknown"
			}

			taskLogs[taskID] = append(taskLogs[taskID], *logEntry)

			// 批量发送（每个任务达到 50 条日志时）
			if len(taskLogs[taskID]) >= 50 {
				s.pushLogs(context.Background(), conn.ID, taskID, taskLogs[taskID])
				taskLogs[taskID] = taskLogs[taskID][:0]
			}

		case <-ticker.C:
			// 定时发送所有任务的日志
			for taskID, logs := range taskLogs {
				if len(logs) > 0 {
					s.pushLogs(context.Background(), conn.ID, taskID, logs)
					taskLogs[taskID] = logs[:0]
				}
			}
		}
	}
}

// pushLogs 优先写入 Redis Stream（如配置启用），否则回退到控制面 HTTP
func (s *Server) pushLogs(ctx context.Context, agentID, taskID string, logs []api.LogEntry) {
	if len(logs) == 0 {
		return
	}

	// 尝试写入统一日志流
	if s.logStream != nil {
		entries := make([]map[string]interface{}, 0, len(logs))
		now := time.Now().UnixMilli()
		for _, l := range logs {
			entries = append(entries, map[string]interface{}{
				"task_id":     taskID,
				"agent_id":    agentID,
				"timestamp":   l.Timestamp,
				"content":     l.Content,
				"stream":      l.Stream,
				"received_at": now,
			})
		}
		if err := s.logStream.PushLogs(ctx, entries); err != nil {
			logger.GetLogger().WithError(err).Warn("push logs to stream failed")
		} else {
			return
		}
	}

	// 不再常规回退 HTTP，失败仅记录告警
	logger.GetLogger().WithFields(map[string]interface{}{
		"agent_id": agentID,
		"task_id":  taskID,
	}).Warn("log stream unavailable, log not delivered")
}

// pushResult 将任务结果写入结果流，失败可选回退 HTTP（当前仅记录错误，不回退）
func (s *Server) pushResult(ctx context.Context, agentID string, result *api.TaskResult) {
	if result == nil {
		return
	}

	if s.resultStream != nil {
		if err := s.resultStream.PushResult(ctx, agentID, result); err != nil {
			logger.GetLogger().WithError(err).WithField("task_id", result.TaskID).Warn("push result to stream failed")
		} else {
			return
		}
	}

	// 不再常规回退 HTTP，失败仅记录告警。如需回退，可在此调用 cpClient.ReportTaskResult
	logger.GetLogger().WithField("task_id", result.TaskID).Warn("result stream unavailable, result not delivered")
}
