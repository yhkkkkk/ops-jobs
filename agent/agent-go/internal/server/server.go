package server

import (
	"net/http"
	"time"

	"github.com/gin-gonic/gin"
	"ops-job-agent/internal/executor"
	"ops-job-agent/internal/logger"
	"ops-job-agent/internal/metrics"
)

// TaskService 任务服务接口，用于取消和查询任务
type TaskService interface {
	CancelTask(taskID string) error
	GetTaskStatus(taskID string) (*executor.RunningTask, bool)
}

type Server struct {
	engine      *gin.Engine
	addr        string
	taskService TaskService
}

// New 创建一个带基础路由的 Gin 服务
func New(addr string) *Server {
	r := gin.New()
	r.Use(gin.Recovery())
	r.Use(gin.Logger())

	s := &Server{
		engine: r,
		addr:   addr,
	}

	// 健康检查
	r.GET("/health", s.healthCheck)

	// 任务取消接口
	r.POST("/tasks/:taskId/cancel", s.cancelTask)

	// 获取任务状态
	r.GET("/tasks/:taskId/status", s.getTaskStatus)

	// 性能指标接口
	r.GET("/metrics", s.getMetrics)

	return s
}

// SetTaskService 设置任务服务
func (s *Server) SetTaskService(service TaskService) {
	s.taskService = service
}

// healthCheck 健康检查
func (s *Server) healthCheck(c *gin.Context) {
	c.JSON(http.StatusOK, gin.H{
		"status":    "ok",
		"timestamp": time.Now().Unix(),
	})
}

// cancelTask 取消任务
func (s *Server) cancelTask(c *gin.Context) {
	taskID := c.Param("taskId")
	if taskID == "" {
		c.JSON(http.StatusBadRequest, gin.H{
			"error": "task_id is required",
		})
		return
	}

	if s.taskService == nil {
		c.JSON(http.StatusServiceUnavailable, gin.H{
			"error": "task service not available",
		})
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

// getTaskStatus 获取任务状态
func (s *Server) getTaskStatus(c *gin.Context) {
	taskID := c.Param("taskId")
	if taskID == "" {
		c.JSON(http.StatusBadRequest, gin.H{
			"error": "task_id is required",
		})
		return
	}

	if s.taskService == nil {
		c.JSON(http.StatusServiceUnavailable, gin.H{
			"error": "task service not available",
		})
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
		"task_id":    task.TaskID,
		"status":     task.Status,
		"start_time": task.StartTime.Unix(),
		"duration_ms": duration,
		"log_size":   logSize,
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
		"metrics": stats,
		"timestamp": time.Now().Unix(),
	})
}

// Start 启动 HTTP 服务（阻塞）
func (s *Server) Start() error {
	logger.GetLogger().Infof("agent http server listening on %s", s.addr)
	return s.engine.Run(s.addr)
}
