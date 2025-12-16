package server

import (
	"net"
	"net/http"
	"strings"
	"time"

	"github.com/gin-gonic/gin"

	"ops-job-agent/internal/api"
	"ops-job-agent/internal/executor"
	"ops-job-agent/internal/logger"
	"ops-job-agent/internal/metrics"
)

// TaskService 任务服务接口，用于接收/取消/查询任务
type TaskService interface {
	// SubmitTask 提交任务执行（通常内部会异步执行）
	SubmitTask(task *api.TaskSpec)
	// CancelTask 取消任务
	CancelTask(taskID string) error
	// GetTaskStatus 获取任务状态
	GetTaskStatus(taskID string) (*executor.RunningTask, bool)
}

// Server Agent 内置 HTTP 服务：
// - /api/tasks                 : 控制面直连推任务
// - /api/tasks/:taskId/cancel  : 控制面直连取消任务
// - /tasks/:taskId/status      : 本地/工具查询任务状态
// - /metrics                   : 指标
type Server struct {
	engine      *gin.Engine
	addr        string
	taskService TaskService
	authToken   string
}

// New 创建 HTTP Server
func New(addr, authToken string) *Server {
	if addr == "" {
		addr = ":8080"
	}

	r := gin.New()
	r.Use(gin.Recovery())
	r.Use(gin.Logger())

	s := &Server{
		engine:    r,
		addr:      addr,
		authToken: strings.TrimSpace(authToken),
	}

	// 健康检查
	r.GET("/health", s.healthCheck)

	// 本地管理接口：任务状态/取消（可选，保留原有路径）
	r.POST("/tasks/:taskId/cancel", s.cancelTask)
	r.GET("/tasks/:taskId/status", s.getTaskStatus)

	// 指标
	r.GET("/metrics", s.getMetrics)

	// 控制面直连 API（统一挂鉴权中间件）
	apiGroup := r.Group("/api")
	apiGroup.Use(s.authMiddleware())
	{
		apiGroup.POST("/tasks", s.handlePushTask)
		apiGroup.POST("/tasks/:taskId/cancel", s.handleCancelTaskAPI)
	}

	return s
}

// SetTaskService 设置任务服务，使 server 能够访问执行器
func (s *Server) SetTaskService(service TaskService) {
	s.taskService = service
}

// authMiddleware 统一鉴权：
// - 若 authToken 为空：仅允许本机回环地址访问
// - 若配置了 authToken：要求 Authorization: Bearer <token>
func (s *Server) authMiddleware() gin.HandlerFunc {
	return func(c *gin.Context) {
		// 未配置 token：仅允许 loopback
		if s.authToken == "" {
			host, _, err := net.SplitHostPort(c.Request.RemoteAddr)
			if err != nil {
				c.AbortWithStatusJSON(http.StatusUnauthorized, gin.H{"error": "unauthorized"})
				return
			}
			ip := net.ParseIP(host)
			if ip == nil || !ip.IsLoopback() {
				c.AbortWithStatusJSON(http.StatusUnauthorized, gin.H{"error": "unauthorized"})
				return
			}
			c.Next()
			return
		}

		auth := c.GetHeader("Authorization")
		if auth == "" {
			c.AbortWithStatusJSON(http.StatusUnauthorized, gin.H{"error": "missing authorization"})
			return
		}
		const prefix = "Bearer "
		if !strings.HasPrefix(auth, prefix) {
			c.AbortWithStatusJSON(http.StatusUnauthorized, gin.H{"error": "invalid authorization header"})
			return
		}
		token := strings.TrimSpace(strings.TrimPrefix(auth, prefix))
		if token == "" || token != s.authToken {
			c.AbortWithStatusJSON(http.StatusUnauthorized, gin.H{"error": "invalid token"})
			return
		}

		c.Next()
	}
}

// healthCheck 健康检查
func (s *Server) healthCheck(c *gin.Context) {
	c.JSON(http.StatusOK, gin.H{
		"status":    "ok",
		"timestamp": time.Now().Unix(),
	})
}

// handlePushTask 控制面直连推任务：POST /api/tasks
func (s *Server) handlePushTask(c *gin.Context) {
	if s.taskService == nil {
		c.JSON(http.StatusServiceUnavailable, gin.H{"error": "task service not available"})
		return
	}

	var task api.TaskSpec
	if err := c.ShouldBindJSON(&task); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": "invalid json body", "message": err.Error()})
		return
	}
	if task.ID == "" {
		c.JSON(http.StatusBadRequest, gin.H{"error": "task_id is required"})
		return
	}

	logger.GetLogger().WithFields(map[string]interface{}{
		"task_id":   task.ID,
		"task_name": task.Name,
		"type":      task.Type,
	}).Info("received task via http (direct mode)")

	s.taskService.SubmitTask(&task)

	c.JSON(http.StatusOK, gin.H{
		"task_id": task.ID,
		"status":  "accepted",
	})
}

// handleCancelTaskAPI 控制面直连取消：POST /api/tasks/:taskId/cancel
func (s *Server) handleCancelTaskAPI(c *gin.Context) {
	taskID := c.Param("taskId")
	if taskID == "" {
		c.JSON(http.StatusBadRequest, gin.H{"error": "task_id is required"})
		return
	}
	if s.taskService == nil {
		c.JSON(http.StatusServiceUnavailable, gin.H{"error": "task service not available"})
		return
	}

	if err := s.taskService.CancelTask(taskID); err != nil {
		logger.GetLogger().WithError(err).WithField("task_id", taskID).Error("cancel task via api failed")
		c.JSON(http.StatusBadRequest, gin.H{
			"error":   "cancel task failed",
			"message": err.Error(),
		})
		return
	}

	c.JSON(http.StatusOK, gin.H{
		"task_id": taskID,
		"status":  "cancelled",
	})
}

// cancelTask 本地管理接口：POST /tasks/:taskId/cancel
func (s *Server) cancelTask(c *gin.Context) {
	taskID := c.Param("taskId")
	if taskID == "" {
		c.JSON(http.StatusBadRequest, gin.H{"error": "task_id is required"})
		return
	}

	if s.taskService == nil {
		c.JSON(http.StatusServiceUnavailable, gin.H{"error": "task service not available"})
		return
	}

	err := s.taskService.CancelTask(taskID)
	if err != nil {
		logger.GetLogger().WithError(err).WithField("task_id", taskID).Error("cancel task failed")
		c.JSON(http.StatusInternalServerError, gin.H{
			"error":   "cancel task failed",
			"message": err.Error(),
		})
		return
	}

	c.JSON(http.StatusOK, gin.H{
		"task_id": taskID,
		"status":  "cancelled",
		"message": "task cancellation requested",
	})
}

// getTaskStatus 获取任务状态：GET /tasks/:taskId/status
func (s *Server) getTaskStatus(c *gin.Context) {
	taskID := c.Param("taskId")
	if taskID == "" {
		c.JSON(http.StatusBadRequest, gin.H{"error": "task_id is required"})
		return
	}

	if s.taskService == nil {
		c.JSON(http.StatusServiceUnavailable, gin.H{"error": "task service not available"})
		return
	}

	task, exists := s.taskService.GetTaskStatus(taskID)
	if !exists {
		c.JSON(http.StatusNotFound, gin.H{
			"task_id": taskID,
			"status":  "not_found",
			"message": "task not found",
		})
		return
	}

	// 计算运行时间
	var duration int64
	if !task.StartTime.IsZero() {
		duration = time.Since(task.StartTime).Milliseconds()
	}

	// 获取日志大小
	task.LogLock.Lock()
	logSize := int64(task.LogBuffer.Len())
	task.LogLock.Unlock()

	response := gin.H{
		"task_id":     task.TaskID,
		"status":      task.Status,
		"start_time":  task.StartTime.Unix(),
		"duration_ms": duration,
		"log_size":    logSize,
	}

	// 如果任务正在运行，添加进程信息
	if task.Command != nil && task.Command.Process != nil {
		response["pid"] = task.Command.Process.Pid
	}

	c.JSON(http.StatusOK, response)
}

// getMetrics 获取性能指标
func (s *Server) getMetrics(c *gin.Context) {
	stats := metrics.GetMetrics().GetStats()
	c.JSON(http.StatusOK, gin.H{
		"metrics":   stats,
		"timestamp": time.Now().Unix(),
	})
}

// Start 启动 HTTP 服务（阻塞）
func (s *Server) Start() error {
	logger.GetLogger().Infof("agent http server listening on %s", s.addr)
	return s.engine.Run(s.addr)
}
