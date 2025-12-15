package server

import (
	"bytes"
	"context"
	"crypto/hmac"
	"crypto/sha256"
	"encoding/hex"
	"fmt"
	"io"
	"net/http"
	"strconv"
	"time"

	"ops-job-agent-server/internal/agent"
	"ops-job-agent-server/internal/config"
	"ops-job-agent-server/internal/controlplane"
	"ops-job-agent-server/internal/logger"
	"ops-job-agent-server/internal/task"
	"ops-job-agent-server/pkg/api"

	"github.com/gin-gonic/gin"
	"github.com/gorilla/websocket"
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

	// 创建任务分发器
	taskDispatcher := task.NewDispatcher(agentMgr, cpClient, taskQueue, 5*time.Second, asynqEnabled)

	s := &Server{
		cfg:            cfg,
		engine:         engine,
		agentManager:   agentMgr,
		cpClient:       cpClient,
		taskDispatcher: taskDispatcher,
		taskQueue:      taskQueue,
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
			s.agentManager.CleanupInactive()
		}
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

	// 注册到控制面
	agentInfo := &api.AgentInfo{
		ID:     agentID,
		Name:   req.Name,
		Token:  conn.Token,
		Labels: req.Labels,
		System: req.System,
		Status: "active",
	}
	if err := s.cpClient.RegisterAgent(context.Background(), agentInfo); err != nil {
		logger.GetLogger().WithError(err).Error("register agent to control plane failed")
		// 不返回错误，允许 Agent 先连接
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
func (s *Server) handleCancelTask(c *gin.Context) {
	agentID := c.Param("id")
	taskID := c.Param("task_id")

	conn, exists := s.agentManager.Get(agentID)
	if !exists {
		c.JSON(http.StatusNotFound, gin.H{"error": "agent not found"})
		return
	}

	if conn.Status != "active" || conn.Conn == nil {
		c.JSON(http.StatusServiceUnavailable, gin.H{"error": "agent connection is not active"})
		return
	}

	// 通过 WebSocket 发送取消任务消息
	if err := conn.SendCancelTask(taskID); err != nil {
		logger.GetLogger().WithError(err).WithFields(map[string]interface{}{
			"agent_id": agentID,
			"task_id":  taskID,
		}).Error("send cancel task message failed")
		c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}

	logger.GetLogger().WithFields(map[string]interface{}{
		"agent_id": agentID,
		"task_id":  taskID,
	}).Info("cancel task request sent to agent")

	c.JSON(http.StatusOK, gin.H{
		"task_id":  taskID,
		"agent_id": agentID,
		"status":   "cancelled",
	})
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
			// 转发心跳到控制面（可选）
			if msg.Payload != nil {
				// 从 payload 中提取系统信息
				if timestamp, ok := msg.Payload["timestamp"].(float64); ok {
					hb := &api.HeartbeatPayload{
						Timestamp: int64(timestamp),
					}
					if systemMap, ok := msg.Payload["system"].(map[string]interface{}); ok && len(systemMap) > 0 {
						// 简化处理，实际应该完整解析 SystemInfo
						hb.System = &api.SystemInfo{}
						_ = systemMap // 避免未使用变量警告
					}
					go s.cpClient.SendHeartbeat(context.Background(), conn.ID, hb)
				}
			}

		case "task_result":
			// 转发任务结果到控制面
			if msg.Result != nil {
				go s.cpClient.ReportTaskResult(context.Background(), conn.ID, msg.Result)
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
						s.cpClient.PushLogs(context.Background(), conn.ID, taskID, logs)
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
				s.cpClient.PushLogs(context.Background(), conn.ID, taskID, taskLogs[taskID])
				taskLogs[taskID] = taskLogs[taskID][:0]
			}

		case <-ticker.C:
			// 定时发送所有任务的日志
			for taskID, logs := range taskLogs {
				if len(logs) > 0 {
					s.cpClient.PushLogs(context.Background(), conn.ID, taskID, logs)
					taskLogs[taskID] = logs[:0]
				}
			}
		}
	}
}
