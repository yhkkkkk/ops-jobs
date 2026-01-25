package server

import (
	"bytes"
	"context"
	"crypto/hmac"
	"errors"
	"fmt"
	"io"
	"net/http"
	"strings"
	"time"

	"github.com/bytedance/sonic"
	"github.com/tidwall/gjson"

	"ops-job-agent-server/internal/agent"
	"ops-job-agent-server/internal/auth"
	"ops-job-agent-server/internal/config"
	"ops-job-agent-server/internal/constants"
	logstream "ops-job-agent-server/internal/log"
	"ops-job-agent-server/internal/logger"
	"ops-job-agent-server/internal/metrics"
	redisPkg "ops-job-agent-server/internal/redis"
	"ops-job-agent-server/internal/task"
	"ops-job-agent-server/pkg/api"

	"github.com/avast/retry-go/v4"
	"github.com/redis/go-redis/v9"

	"github.com/gin-gonic/gin"
	"github.com/gorilla/websocket"
	"github.com/spf13/cast"
)

const (
	ackCacheTTL = 10 * time.Minute
	ackCacheMax = 5000
)

var (
	errInvalidTaskID        = errors.New("invalid task_id format")
	errLogStreamUnavailable = errors.New("log stream unavailable")
	errLogStreamWriteFailed = errors.New("log stream write failed")
)

// createUpgrader 根据配置创建 WebSocket Upgrader
func createUpgrader(cfg *config.Config) websocket.Upgrader {
	checkOrigin := func(r *http.Request) bool {
		// 如果配置了允许的来源列表，检查请求来源
		if len(cfg.WebSocket.AllowedOrigins) > 0 {
			origin := r.Header.Get("Origin")
			for _, allowed := range cfg.WebSocket.AllowedOrigins {
				if origin == allowed {
					return true
				}
			}
			return false
		}
		// 否则允许所有来源（开发环境）
		return true
	}

	return websocket.Upgrader{
		CheckOrigin:       checkOrigin,
		HandshakeTimeout:  cfg.WebSocket.HandshakeTimeout,
		ReadBufferSize:    cfg.WebSocket.ReadBufferSize,
		WriteBufferSize:   cfg.WebSocket.WriteBufferSize,
		EnableCompression: cfg.WebSocket.EnableCompression,
	}
}

// Server Agent-Server 服务器
type Server struct {
	cfg              *config.Config
	engine           *gin.Engine
	httpServer       *http.Server
	upgrader         websocket.Upgrader // WebSocket Upgrader
	agentManager     *agent.Manager
	taskDispatcher   *task.Dispatcher
	pendingTaskStore *task.PendingTaskStore // 待处理任务持久化存储
	logStream        *logstream.StreamWriter
	resultStream     *logstream.ResultStreamWriter
	statusStream     *logstream.StatusStreamWriter
}

// New 创建服务器
func New(cfg *config.Config) (*Server, error) {
	gin.SetMode(gin.ReleaseMode)

	engine := gin.New()
	engine.Use(gin.Recovery())
	engine.Use(gin.Logger())

	// 创建 WebSocket Upgrader
	upgrader := createUpgrader(cfg)

	// 创建Redis连接池管理器
	var redisClient *redis.Client
	if cfg.Redis.Enabled {
		poolMgr := redisPkg.NewPoolManager(&cfg.Redis)
		client, err := poolMgr.GetClient()
		if err != nil {
			logger.GetLogger().WithError(err).Warn("Failed to create Redis connection pool, AckStore will be disabled")
		} else {
			redisClient = client
		}
	}

	// 创建 Agent 管理器
	agentMgr := agent.NewManager(
		cfg.Agent.MaxConnections,
		cfg.Agent.HeartbeatTimeout,
		cfg,
		redisClient,
	)

	// 创建 PendingTaskStore（用于无状态架构的任务持久化）
	pendingTaskStore := task.NewPendingTaskStore(redisClient)

	// 创建任务分发器
	taskDispatcher := task.NewDispatcher(agentMgr, pendingTaskStore)

	// 创建日志流写入器
	var logStream *logstream.StreamWriter
	if cfg.LogStream.Enabled {
		if redisClient == nil {
			return nil, fmt.Errorf("log stream enabled but redis client not available")
		}
		var err error
		logStream, err = logstream.NewStreamWriter(redisClient, cfg)
		if err != nil {
			return nil, fmt.Errorf("create log stream writer: %w", err)
		}
	}

	// 创建结果流写入器
	var resultStream *logstream.ResultStreamWriter
	if cfg.ResultStream.Enabled {
		if redisClient == nil {
			return nil, fmt.Errorf("result stream enabled but redis client not available")
		}
		var err error
		resultStream, err = logstream.NewResultStreamWriter(redisClient, cfg)
		if err != nil {
			return nil, fmt.Errorf("create result stream writer: %w", err)
		}
	}

	// 创建状态流写入器
	var statusStream *logstream.StatusStreamWriter
	if cfg.StatusStream.Enabled {
		if redisClient == nil {
			return nil, fmt.Errorf("status stream enabled but redis client not available")
		}
		var err error
		statusStream, err = logstream.NewStatusStreamWriter(redisClient, cfg)
		if err != nil {
			return nil, fmt.Errorf("create status stream writer: %w", err)
		}
	}

	s := &Server{
		cfg:              cfg,
		upgrader:         upgrader,
		engine:           engine,
		agentManager:     agentMgr,
		taskDispatcher:   taskDispatcher,
		pendingTaskStore: pendingTaskStore,
		logStream:        logStream,
		resultStream:     resultStream,
		statusStream:     statusStream,
	}

	s.setupRoutes()

	return s, nil
}

// setupRoutes 设置路由
func (s *Server) setupRoutes() {
	s.setupAgentIngressRoutes()
	s.setupControlPlaneIngressRoutes()
	s.setupWebSocketRoutes()
}

func (s *Server) setupAgentIngressRoutes() {
	api := s.engine.Group("/api")
	{
		// Agent 注册（Agent-Server 模式下，Agent 先注册拿到 ws_url）
		api.POST("/agents/register", s.handleRegister)
	}
}

func (s *Server) setupControlPlaneIngressRoutes() {
	api := s.engine.Group("/api")

	// 控制面入站：可选的 HMAC 签名校验
	if s.cfg.Auth.RequireSignature && s.cfg.Auth.SharedSecret != "" {
		api.Use(s.requireSignature())
	}

	{
		// Agent 列表
		api.GET("/agents", s.handleListAgents)
		// Agent 详情
		api.GET("/agents/:id", s.handleGetAgent)
		// 控制面推送任务到指定 Agent
		api.POST("/agents/:id/tasks", s.handlePushTask)
		// 批量推送任务到指定 Agent
		api.POST("/agents/:id/tasks/batch", s.handlePushTasksBatch)
		// 取消指定 Agent 的任务
		api.POST("/agents/:id/tasks/:task_id/cancel", s.handleCancelTask)
		// 批量取消指定 Agent 的任务
		api.POST("/agents/:id/tasks/cancel/batch", s.handleCancelTasksBatch)
		// 控制指定 Agent（start/stop/restart）
		api.POST("/agents/:id/control", s.handleAgentControl)
		// 升级指定 Agent
		api.POST("/agents/:id/upgrade", s.handleAgentUpgrade)
		// 观测指标（JSON）
		api.GET("/metrics", func(c *gin.Context) {
			metrics.HandleOverview(c, s.agentManager, s.cfg)
		})
		// Agent-Server 自我控制
		api.POST("/self/control", s.handleSelfControl)
		// Agent-Server 自我升级
		api.POST("/self/upgrade", s.handleSelfUpgrade)
	}
}

func (s *Server) setupWebSocketRoutes() {
	// WebSocket 连接（Agent 入站）
	s.engine.GET("/ws/agent/:id", s.handleWebSocket)
}

// Start 启动服务器
func (s *Server) Start() error {
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
					go s.pushStatus(context.Background(), a, constants.StatusOffline, nil)
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
		"host_id":        conn.HostID,
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

	// 从心跳 payload 中提取系统资源监控数据
	// payload 格式: {"timestamp": int64, "system": SystemInfo}
	if payload != nil {
		// 将payload转换为JSON字符串用于gjson解析
		payloadJSON, err := sonic.Marshal(payload)
		if err != nil {
			logger.GetLogger().WithError(err).WithField("agent_id", conn.ID).Warn("failed to marshal payload for gjson parsing")
		} else {
			systemData := make(map[string]interface{})

			// 使用gjson高效提取系统信息
			systemResult := gjson.GetBytes(payloadJSON, "system")
			if systemResult.Exists() {
				// CPU 使用率
				if cpuUsage := gjson.GetBytes(payloadJSON, "system.cpu_usage"); cpuUsage.Exists() {
					systemData["cpu_usage"] = cpuUsage.Value()
				}

				// 内存信息 - 控制面期望格式: memory: {total, used, usage}
				memoryInfo := make(map[string]interface{})
				if memUsage := gjson.GetBytes(payloadJSON, "system.memory_usage"); memUsage.Exists() {
					memoryInfo["usage"] = memUsage.Value()
				}
				if memTotal := gjson.GetBytes(payloadJSON, "system.memory_total"); memTotal.Exists() {
					memoryInfo["total"] = memTotal.Value()
				}
				if memUsed := gjson.GetBytes(payloadJSON, "system.memory_used"); memUsed.Exists() {
					memoryInfo["used"] = memUsed.Value()
				}
				if len(memoryInfo) > 0 {
					systemData["memory"] = memoryInfo
				}

				// 磁盘使用率
				if diskUsage := gjson.GetBytes(payloadJSON, "system.disk_usage"); diskUsage.Exists() {
					systemData["disk"] = diskUsage.Value()
				}

				// 负载信息 - 控制面期望格式: load_avg: {1m, 5m, 15m}
				loadAvgResult := gjson.GetBytes(payloadJSON, "system.load_avg")
				if loadAvgResult.Exists() && loadAvgResult.IsArray() {
					loadArr := loadAvgResult.Array()
					if len(loadArr) >= 3 {
						systemData["load_avg"] = map[string]interface{}{
							"1m":  loadArr[0].Value(),
							"5m":  loadArr[1].Value(),
							"15m": loadArr[2].Value(),
						}
					}
				}

				// 系统运行时间
				if uptime := gjson.GetBytes(payloadJSON, "system.uptime"); uptime.Exists() {
					systemData["uptime"] = uptime.Value()
				}
			}

			// 将 system 数据写入 Redis
			if len(systemData) > 0 {
				fields["system"] = systemData
			}
		}
	}

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

	conn, agentID, err := s.agentManager.Register(req.Name, req.Token, req.Labels, req.System, req.HostID)
	if err != nil {
		if err == agent.ErrMaxConnections {
			c.JSON(http.StatusServiceUnavailable, gin.H{"error": "max connections reached"})
			return
		}
		c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}

	// 通知控制面 Agent 已上线（通过状态流）
	if s.statusStream != nil {
		statusFields := map[string]interface{}{
			"agent_id":   agentID,
			"agent_name": req.Name,
			"host_id":    req.HostID,
			"status":     constants.StatusActive,
			"event":      "registered",
			"labels":     req.Labels,
		}
		if req.System != nil {
			if systemJSON, err := sonic.Marshal(req.System); err == nil {
				statusFields["system"] = string(systemJSON)
			}
		}
		if err := s.statusStream.PushStatus(c.Request.Context(), statusFields); err != nil {
			logger.GetLogger().WithError(err).WithField("agent_id", agentID).Warn("push registration status to stream failed")
		}
	}

	wsURL := fmt.Sprintf("ws://%s:%d/ws/agent/%s?token=%s",
		s.cfg.Server.Host, s.cfg.Server.Port, agentID, conn.Token)

	c.JSON(http.StatusOK, api.RegisterResponse{
		ID:     agentID,
		Name:   req.Name,
		Status: constants.StatusActive,
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
		"status":   constants.StatusDispatched,
	})
}

// handlePushTasksBatch 批量推送任务到指定 Agent
func (s *Server) handlePushTasksBatch(c *gin.Context) {
	agentID := c.Param("id")

	var taskSpecs []api.TaskSpec
	if err := c.ShouldBindJSON(&taskSpecs); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": err.Error()})
		return
	}

	if len(taskSpecs) == 0 {
		c.JSON(http.StatusBadRequest, gin.H{"error": "tasks array is empty"})
		return
	}

	// 获取 Agent 连接
	conn, exists := s.agentManager.Get(agentID)
	if !exists {
		c.JSON(http.StatusNotFound, gin.H{"error": "agent not found"})
		return
	}

	// 检查 scope（已移除，此检查不再需要）

	// 转换为指针数组
	taskPtrs := make([]*api.TaskSpec, len(taskSpecs))
	for i := range taskSpecs {
		taskPtrs[i] = &taskSpecs[i]
	}

	// 批量发送任务
	if err := conn.SendTasks(taskPtrs); err != nil {
		if err == agent.ErrConnectionClosed {
			c.JSON(http.StatusServiceUnavailable, gin.H{"error": "agent connection closed"})
			return
		}
		c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}

	// 记录所有任务为运行状态
	for _, task := range taskPtrs {
		conn.AddRunningTask(task)
	}

	taskIDs := make([]string, len(taskSpecs))
	for i, task := range taskSpecs {
		taskIDs[i] = task.ID
	}

	logger.GetLogger().WithFields(map[string]interface{}{
		"agent_id":   agentID,
		"task_count": len(taskSpecs),
		"task_ids":   taskIDs,
	}).Info("batch tasks pushed to agent")

	c.JSON(http.StatusOK, gin.H{
		"task_ids": taskIDs,
		"agent_id": agentID,
		"status":   constants.StatusDispatched,
		"count":    len(taskSpecs),
	})
}

// handleCancelTask 处理取消任务请求
// 支持两种情况：
// 1. Agent 在线：通过 WebSocket 发送取消消息
// 2. Agent 离线：从 pendingTaskStore 中删除任务
func (s *Server) handleCancelTask(c *gin.Context) {
	agentID := c.Param("id")
	taskID := c.Param("task_id")

	conn, exists := s.agentManager.Get(agentID)
	if !exists {
		// Agent 不存在，尝试从 pendingTaskStore 中删除任务
		if s.pendingTaskStore != nil {
			if err := s.cancelTaskFromQueue(agentID, taskID); err != nil {
				c.JSON(http.StatusNotFound, gin.H{"error": "agent not found and task not found in pending store"})
				return
			}
			c.JSON(http.StatusOK, gin.H{
				"task_id":  taskID,
				"agent_id": agentID,
				"status":   constants.StatusCancelled,
				"source":   "pending_store",
			})
			return
		}
		c.JSON(http.StatusNotFound, gin.H{"error": "agent not found"})
		return
	}

	// Agent 在线，尝试通过 WebSocket 发送取消消息
	if conn.Status == constants.StatusActive && conn.Conn != nil {
		if err := conn.SendCancelTask(taskID); err != nil {
			logger.GetLogger().WithError(err).WithFields(map[string]interface{}{
				"agent_id": agentID,
				"task_id":  taskID,
			}).Error("send cancel task message failed")
			// WebSocket 发送失败，尝试从 pendingTaskStore 中删除
			if s.pendingTaskStore != nil {
				if err := s.cancelTaskFromQueue(agentID, taskID); err == nil {
					c.JSON(http.StatusOK, gin.H{
						"task_id":  taskID,
						"agent_id": agentID,
						"status":   constants.StatusCancelled,
						"source":   "pending_store",
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
			"status":   constants.StatusCancelled,
			"source":   "websocket",
		})
		return
	}

	// Agent 连接不活跃，尝试从 pendingTaskStore 中删除
	if s.pendingTaskStore != nil {
		if err := s.cancelTaskFromQueue(agentID, taskID); err != nil {
			c.JSON(http.StatusServiceUnavailable, gin.H{"error": "agent connection is not active and task not found in pending store"})
			return
		}
		c.JSON(http.StatusOK, gin.H{
			"task_id":  taskID,
			"agent_id": agentID,
			"status":   constants.StatusCancelled,
			"source":   "pending_store",
		})
		return
	}

	c.JSON(http.StatusServiceUnavailable, gin.H{"error": "agent connection is not active"})
}

// handleCancelTasksBatch 批量取消任务
func (s *Server) handleCancelTasksBatch(c *gin.Context) {
	agentID := c.Param("id")

	var req struct {
		TaskIDs []string `json:"task_ids"`
	}
	if err := c.ShouldBindJSON(&req); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": err.Error()})
		return
	}

	if len(req.TaskIDs) == 0 {
		c.JSON(http.StatusBadRequest, gin.H{"error": "task_ids array is empty"})
		return
	}

	conn, exists := s.agentManager.Get(agentID)
	if !exists {
		c.JSON(http.StatusNotFound, gin.H{"error": "agent not found"})
		return
	}

	results := make([]map[string]interface{}, 0, len(req.TaskIDs))
	successCount := 0
	failedCount := 0

	// Agent 在线，通过 WebSocket 批量发送取消消息
	if conn.Status == constants.StatusActive && conn.Conn != nil {
		if err := conn.SendCancelTasks(req.TaskIDs); err != nil {
			logger.GetLogger().WithError(err).WithFields(map[string]interface{}{
				"agent_id":   agentID,
				"task_count": len(req.TaskIDs),
			}).Error("send cancel tasks batch message failed")

			// WebSocket 发送失败，逐个尝试从 pendingTaskStore 中删除
			if s.pendingTaskStore != nil {
				for _, taskID := range req.TaskIDs {
					if err := s.cancelTaskFromQueue(agentID, taskID); err == nil {
						results = append(results, map[string]interface{}{
							"task_id": taskID,
							"status":  constants.StatusCancelled,
							"source":  "pending_store",
						})
						successCount++
					} else {
						results = append(results, map[string]interface{}{
							"task_id": taskID,
							"status":  "failed",
							"error":   err.Error(),
						})
						failedCount++
					}
				}
			} else {
				c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
				return
			}
		} else {
			// WebSocket 批量发送成功
			for _, taskID := range req.TaskIDs {
				results = append(results, map[string]interface{}{
					"task_id": taskID,
					"status":  constants.StatusCancelled,
					"source":  "websocket",
				})
				successCount++
			}
		}
	} else {
		// Agent 离线，尝试从 pendingTaskStore 中逐个删除
		if s.pendingTaskStore != nil {
			for _, taskID := range req.TaskIDs {
				if err := s.cancelTaskFromQueue(agentID, taskID); err == nil {
					results = append(results, map[string]interface{}{
						"task_id": taskID,
						"status":  constants.StatusCancelled,
						"source":  "pending_store",
					})
					successCount++
				} else {
					results = append(results, map[string]interface{}{
						"task_id": taskID,
						"status":  "failed",
						"error":   err.Error(),
					})
					failedCount++
				}
			}
		} else {
			c.JSON(http.StatusServiceUnavailable, gin.H{"error": "agent connection is not active"})
			return
		}
	}

	logger.GetLogger().WithFields(map[string]interface{}{
		"agent_id":      agentID,
		"task_count":    len(req.TaskIDs),
		"success_count": successCount,
		"failed_count":  failedCount,
	}).Info("batch cancel tasks completed")

	c.JSON(http.StatusOK, gin.H{
		"agent_id":      agentID,
		"task_count":    len(req.TaskIDs),
		"success_count": successCount,
		"failed_count":  failedCount,
		"results":       results,
	})
}

// cancelTaskFromQueue 从待处理任务存储中取消任务
func (s *Server) cancelTaskFromQueue(agentID, taskID string) error {
	if s.pendingTaskStore == nil {
		return fmt.Errorf("pending task store not enabled")
	}

	// 直接从 pendingTaskStore 删除任务
	if err := s.pendingTaskStore.Delete(agentID, taskID); err != nil {
		logger.GetLogger().WithError(err).WithFields(map[string]interface{}{
			"agent_id": agentID,
			"task_id":  taskID,
		}).Warn("task not found in pending store")
		return fmt.Errorf("task not found in pending store")
	}

	logger.GetLogger().WithFields(map[string]interface{}{
		"agent_id": agentID,
		"task_id":  taskID,
	}).Info("task cancelled from pending store")

	return nil
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
	ws, err := s.upgrader.Upgrade(c.Writer, c.Request, nil)
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

		tsStr := c.GetHeader(auth.HeaderTimestamp)
		sig := c.GetHeader(auth.HeaderSignature)
		if tsStr == "" || sig == "" {
			c.AbortWithStatusJSON(http.StatusForbidden, gin.H{"error": "missing signature headers"})
			return
		}
		ts, err := cast.ToInt64E(tsStr)
		if err != nil {
			c.AbortWithStatusJSON(http.StatusForbidden, gin.H{"error": "invalid timestamp"})
			return
		}
		now := time.Now().Unix()
		if auth.AbsInt64(now-ts) > int64(clockSkew.Seconds()) {
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

		// 使用真实 URL.Path（而不是gin的FullPath路由模板），保证控制面计算签名稳定一致
		path := c.Request.URL.Path
		expected := auth.ComputeHMAC(secret, c.Request.Method, path, tsStr, bodyBytes)
		if !hmac.Equal([]byte(expected), []byte(sig)) {
			c.AbortWithStatusJSON(http.StatusForbidden, gin.H{"error": "invalid signature"})
			return
		}

		c.Next()
	}
}

// handleWebSocketMessages 处理 WebSocket 消息
func (s *Server) handleWebSocketMessages(conn *agent.Connection) {
	defer func() {
		// Agent断开连接时单次推送离线状态
		go s.pushStatus(context.Background(), conn, constants.StatusOffline, map[string]interface{}{
			"disconnect_reason": "websocket_closed",
			"disconnect_time":   time.Now().Unix(),
		})

		s.agentManager.Remove(conn.ID)
		logger.GetLogger().WithField("agent_id", conn.ID).Info("websocket disconnected")
	}()

	// 启动任务队列处理
	go s.handleTaskQueue(conn)

	for {
		var msg api.WebSocketMessage
		if err := conn.Conn.ReadJSON(&msg); err != nil {
			if websocket.IsUnexpectedCloseError(err, websocket.CloseGoingAway, websocket.CloseAbnormalClosure) {
				logger.GetLogger().WithError(err).Error("websocket read error")
			}
			break
		}

		switch msg.Type {
		case constants.MessageTypeHeartbeat:
			conn.UpdateHeartbeat()
			// 写入状态流：online
			go s.pushStatus(context.Background(), conn, constants.StatusOnline, msg.Payload)

		case constants.MessageTypeTaskResult:
			if msg.MessageID == "" {
				logger.GetLogger().WithField("agent_id", conn.ID).Warn("task_result missing message_id, dropped")
				continue
			}
			if conn.SeenMessage(msg.MessageID, ackCacheTTL, ackCacheMax) {
				s.sendAck(conn, msg.MessageID)
				continue
			}
			if msg.Result == nil {
				logger.GetLogger().WithField("message_id", msg.MessageID).Warn("task_result missing payload")
				continue
			}
			if err := s.pushResult(context.Background(), conn.ID, msg.Result); err != nil {
				logger.GetLogger().WithError(err).WithFields(map[string]interface{}{
					"agent_id":   conn.ID,
					"message_id": msg.MessageID,
					"task_id":    msg.TaskID,
				}).Warn("push result failed, waiting for retry")
				continue
			}
			s.sendAck(conn, msg.MessageID)

		case constants.MessageTypeLog:
			if msg.MessageID == "" {
				logger.GetLogger().WithField("agent_id", conn.ID).Warn("log message missing message_id, dropped")
				continue
			}
			if msg.TaskID == "" {
				logger.GetLogger().WithFields(map[string]interface{}{
					"agent_id":   conn.ID,
					"message_id": msg.MessageID,
				}).Warn("log message missing task_id, ack to avoid retry")
				s.sendAck(conn, msg.MessageID)
				continue
			}
			if conn.SeenMessage(msg.MessageID, ackCacheTTL, ackCacheMax) {
				s.sendAck(conn, msg.MessageID)
				continue
			}
			if len(msg.Logs) == 0 {
				logger.GetLogger().WithFields(map[string]interface{}{
					"agent_id":   conn.ID,
					"message_id": msg.MessageID,
				}).Warn("log message empty, ack to avoid retry")
				s.sendAck(conn, msg.MessageID)
				continue
			}
			for i := range msg.Logs {
				if msg.TaskID != "" {
					msg.Logs[i].TaskID = msg.TaskID
				}
			}
			if err := s.pushLogs(context.Background(), conn.ID, msg.TaskID, msg.Logs); err != nil {
				switch {
				case errors.Is(err, errInvalidTaskID):
					// 非法 task_id，直接 ACK 避免重复重试
					s.sendAck(conn, msg.MessageID)
					continue
				case errors.Is(err, errLogStreamUnavailable), errors.Is(err, errLogStreamWriteFailed):
					// 日志流不可用或写入失败：记录告警并 ACK（选择丢弃以避免 pending/outbox 占满）
					logger.GetLogger().WithError(err).WithFields(map[string]interface{}{
						"agent_id":   conn.ID,
						"message_id": msg.MessageID,
						"task_id":    msg.TaskID,
						"log_count":  len(msg.Logs),
					}).Warn("log stream unavailable, ack and drop logs to avoid retry storm")
					s.sendAck(conn, msg.MessageID)
					continue
				default:
					logger.GetLogger().WithError(err).WithFields(map[string]interface{}{
						"agent_id":   conn.ID,
						"message_id": msg.MessageID,
						"task_id":    msg.TaskID,
						"log_count":  len(msg.Logs),
					}).Warn("push logs failed, waiting for retry")
					continue
				}
			}
			s.sendAck(conn, msg.MessageID)
		}
	}
}

func (s *Server) sendAck(conn *agent.Connection, messageID string) {
	if conn == nil || messageID == "" {
		return
	}
	ack := api.WebSocketMessage{
		Type:  constants.MessageTypeAck,
		AckID: messageID,
	}
	if err := conn.Conn.WriteJSON(ack); err != nil {
		logger.GetLogger().WithError(err).WithFields(map[string]interface{}{
			"agent_id":   conn.ID,
			"message_id": messageID,
		}).Warn("send websocket ack failed")
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
	// 日志缓冲区大小限制，避免内存溢出
	const MaxLogBufferSize = 1000 // 最大缓冲日志条数
	var totalBuffered int         // 当前缓冲的总日志条数

	ticker := time.NewTicker(2 * time.Second)
	defer ticker.Stop()

	// 按 task_id 分组日志
	taskLogs := make(map[string][]api.LogEntry)
	for {
		select {
		case logEntry, ok := <-conn.LogBuffer:
			if !ok {
				// 通道关闭（Agent断线），优雅地处理剩余日志
				s.handleAgentDisconnectLogs(conn.ID, taskLogs, totalBuffered)
				return
			}

			// 从日志条目中获取 task_id
			taskID := logEntry.TaskID
			if taskID == "" {
				taskID = "unknown"
			}

			// 检查总缓冲大小限制
			if totalBuffered >= MaxLogBufferSize {
				logger.GetLogger().WithFields(map[string]interface{}{
					"agent_id": conn.ID,
					"task_id":  taskID,
				}).Warn("log buffer full, dropping old logs")

				// 丢弃最旧的日志：优先丢弃其他任务的日志，保留当前任务
				if s.evictOldLogs(taskLogs, &totalBuffered, taskID) {
					// 如果还是满了，丢弃当前日志
					continue
				}
			}

			taskLogs[taskID] = append(taskLogs[taskID], *logEntry)
			totalBuffered++

			// 批量发送（每个任务达到 50 条日志时）
			if len(taskLogs[taskID]) >= 50 {
				if err := s.pushLogs(context.Background(), conn.ID, taskID, taskLogs[taskID]); err != nil {
					logger.GetLogger().WithError(err).WithFields(map[string]interface{}{
						"agent_id": conn.ID,
						"task_id":  taskID,
					}).Warn("push logs failed (buffer flush)")
				}
				totalBuffered -= len(taskLogs[taskID])
				taskLogs[taskID] = taskLogs[taskID][:0]
			}

		case <-ticker.C:
			// 定时发送所有任务的日志
			for taskID, logs := range taskLogs {
				if len(logs) > 0 {
					if err := s.pushLogs(context.Background(), conn.ID, taskID, logs); err != nil {
						logger.GetLogger().WithError(err).WithFields(map[string]interface{}{
							"agent_id": conn.ID,
							"task_id":  taskID,
						}).Warn("push logs failed (tick flush)")
					}
					taskLogs[taskID] = logs[:0]
				}
			}
		}
	}
}

// pushLogs 优先写入 Redis Stream（如配置启用），否则仅记录告警；返回错误用于上层重试/统计
func (s *Server) pushLogs(ctx context.Context, agentID, taskID string, logs []api.LogEntry) error {
	if len(logs) == 0 {
		return nil
	}

	// 解析task_id提取execution_id和其他组件
	// task_id格式: {execution_id}_{step_id}_{host_id}_{random}
	executionID, stepID, hostID, ok := parseTaskID(taskID)
	if !ok {
		logger.GetLogger().WithFields(map[string]interface{}{
			"agent_id":  agentID,
			"task_id":   taskID,
			"log_count": len(logs),
			"message":   "invalid task_id format, log dropped",
		}).Warn("log message dropped due to invalid task_id")
		return errInvalidTaskID
	}

	// 尝试写入统一日志流
	if s.logStream != nil {
		// 按时间戳排序日志条目，确保顺序正确
		sortedLogs := make([]api.LogEntry, len(logs))
		copy(sortedLogs, logs)
		sortLogsByTimestamp(sortedLogs)

		entries := make([]map[string]interface{}, 0, len(sortedLogs))
		now := time.Now().UnixMilli()
		for _, l := range sortedLogs {
			entries = append(entries, map[string]interface{}{
				"task_id":      taskID,      // 保留完整task_id用于追踪
				"execution_id": executionID, // 新增：用于SSE按execution_id查询
				"step_id":      stepID,      // 新增：用于前端按步骤过滤
				"host_id":      hostID,      // 新增：用于前端按主机过滤
				"agent_id":     agentID,
				"timestamp":    l.Timestamp,
				"content":      l.Content,
				"log_type":     l.Stream, // 改为log_type，与控制面期望一致
				"received_at":  now,
			})
		}

		// 按execution_id写入，而不是task_id
		if err := s.logStream.PushLogsByExecutionID(ctx, executionID, entries); err != nil {
			logger.GetLogger().WithError(err).Warn("push logs to stream failed")
			return errLogStreamWriteFailed
		}
		return nil
	}

	// 不再常规回退 HTTP，失败仅记录告警
	logger.GetLogger().WithFields(map[string]interface{}{
		"agent_id":     agentID,
		"task_id":      taskID,
		"execution_id": executionID,
	}).Warn("log stream unavailable, log not delivered")
	return errLogStreamUnavailable
}

// parseTaskID 解析task_id，提取execution_id, step_id, host_id
// task_id格式: {execution_id}_{step_id}_{host_id}_{random}
func parseTaskID(taskID string) (executionID, stepID, hostID string, ok bool) {
	parts := strings.Split(taskID, "_")
	if len(parts) < 4 {
		return "", "", "", false
	}
	return parts[0], parts[1], parts[2], true
}

// pushResult 将任务结果写入结果流，失败可选回退 HTTP（当前仅记录错误，不回退）
func (s *Server) pushResult(ctx context.Context, agentID string, result *api.TaskResult) error {
	if result == nil {
		return nil
	}

	if s.resultStream != nil {
		if err := s.resultStream.PushResult(ctx, agentID, result); err != nil {
			logger.GetLogger().WithError(err).WithField("task_id", result.TaskID).Warn("push result to stream failed")
			return err
		}
		return nil
	}

	err := fmt.Errorf("result stream unavailable")
	logger.GetLogger().WithField("task_id", result.TaskID).Warn("result stream unavailable, result not delivered")
	return err
}

// sortLogsByTimestamp 按时间戳排序日志条目，确保日志顺序正确
func sortLogsByTimestamp(logs []api.LogEntry) {
	// 使用简单的冒泡排序，按时间戳升序排列
	for i := 0; i < len(logs)-1; i++ {
		for j := 0; j < len(logs)-1-i; j++ {
			if logs[j].Timestamp > logs[j+1].Timestamp {
				logs[j], logs[j+1] = logs[j+1], logs[j]
			}
		}
	}
}

// evictOldLogs 丢弃最旧的日志以释放缓冲区空间
// 返回true如果成功释放了空间，false如果没有更多日志可丢弃
func (s *Server) evictOldLogs(taskLogs map[string][]api.LogEntry, totalBuffered *int, currentTaskID string) bool {
	// 找到包含日志最多的任务（除了当前正在处理的）
	var maxTaskID string
	var maxCount int

	for taskID, logs := range taskLogs {
		if taskID == currentTaskID {
			continue // 跳过当前任务
		}
		if len(logs) > maxCount {
			maxCount = len(logs)
			maxTaskID = taskID
		}
	}

	if maxTaskID == "" || maxCount == 0 {
		return false // 没有日志可丢弃
	}

	// 丢弃该任务的一半日志
	evictCount := maxCount / 2
	if evictCount < 1 {
		evictCount = 1
	}

	logger.GetLogger().WithFields(map[string]interface{}{
		"task_id":     maxTaskID,
		"evict_count": evictCount,
		"remaining":   maxCount - evictCount,
	}).Warn("evicting old logs from buffer")

	// 保留最新的日志，丢弃最旧的
	taskLogs[maxTaskID] = taskLogs[maxTaskID][evictCount:]
	*totalBuffered -= evictCount

	return true
}

// handleAgentDisconnectLogs 处理Agent断线时的日志，确保日志完整性
func (s *Server) handleAgentDisconnectLogs(agentID string, taskLogs map[string][]api.LogEntry, totalBuffered int) {
	if len(taskLogs) == 0 {
		logger.GetLogger().WithField("agent_id", agentID).Debug("no buffered logs on agent disconnect")
		return
	}

	logger.GetLogger().WithFields(map[string]interface{}{
		"agent_id":       agentID,
		"buffered_tasks": len(taskLogs),
		"total_logs":     totalBuffered,
	}).Info("handling buffered logs on agent disconnect")

	// 设置超时上下文，确保不会无限等待
	ctx, cancel := context.WithTimeout(context.Background(), 30*time.Second)
	defer cancel()

	successCount := 0
	failedCount := 0
	totalPushedLogs := 0

	// 尝试推送所有缓冲的日志
	for taskID, logs := range taskLogs {
		if len(logs) == 0 {
			continue
		}

		// 对每个任务的日志按时间戳排序
		sortedLogs := make([]api.LogEntry, len(logs))
		copy(sortedLogs, logs)
		sortLogsByTimestamp(sortedLogs)

		err := retry.Do(
			func() error {
				return s.pushLogs(ctx, agentID, taskID, sortedLogs)
			},
			retry.Attempts(3),
			retry.Delay(500*time.Millisecond),
			retry.DelayType(retry.BackOffDelay),
			retry.Context(ctx),
		)
		if err != nil {
			logger.GetLogger().WithError(err).WithFields(map[string]interface{}{
				"agent_id":  agentID,
				"task_id":   taskID,
				"log_count": len(sortedLogs),
				"retries":   3,
			}).Error("permanently failed to push logs on agent disconnect")
			failedCount++
		} else {
			logger.GetLogger().WithFields(map[string]interface{}{
				"agent_id":  agentID,
				"task_id":   taskID,
				"log_count": len(sortedLogs),
			}).Debug("successfully pushed logs on disconnect")
			successCount++
			totalPushedLogs += len(sortedLogs)
		}

	}

	logger.GetLogger().WithFields(map[string]interface{}{
		"agent_id":      agentID,
		"tasks_total":   len(taskLogs),
		"tasks_success": successCount,
		"tasks_failed":  failedCount,
		"logs_pushed":   totalPushedLogs,
		"logs_total":    totalBuffered,
		"success_rate":  fmt.Sprintf("%.1f%%", float64(totalPushedLogs)/float64(totalBuffered)*100),
	}).Info("completed handling agent disconnect logs")
}
