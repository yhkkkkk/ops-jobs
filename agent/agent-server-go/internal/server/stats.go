package server

import (
	"net/http"

	"ops-job-agent-server/internal/logger"

	"github.com/gin-gonic/gin"
)

// handleGetStats 获取任务队列统计信息
func (s *Server) handleGetStats(c *gin.Context) {
	if s.taskQueue == nil {
		c.JSON(http.StatusServiceUnavailable, gin.H{
			"error": "asynq not enabled",
		})
		return
	}

	stats, err := s.taskQueue.GetTaskStats()
	if err != nil {
		logger.GetLogger().WithError(err).Error("get task stats failed")
		c.JSON(http.StatusInternalServerError, gin.H{
			"error": err.Error(),
		})
		return
	}

	c.JSON(http.StatusOK, gin.H{
		"queues": stats,
	})
}
