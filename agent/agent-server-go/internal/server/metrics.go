package server

import (
	"net/http"
	"time"

	"github.com/gin-gonic/gin"
)

// handleMetrics 暴露最小可观测指标（JSON），便于控制面/监控系统抓取
// 注：不引入 Prometheus 依赖，后续如需可再扩展为 /metrics(prometheus)。
func (s *Server) handleMetrics(c *gin.Context) {
	now := time.Now()

	agents := s.agentManager.List()
	online := 0
	for _, a := range agents {
		if a.IsAlive(s.cfg.Agent.HeartbeatTimeout) {
			online++
		}
	}

	resp := gin.H{
		"now_unix_ms":        now.UnixMilli(),
		"agents_total":       len(agents),
		"agents_online":      online,
		"agents_offline":     len(agents) - online,
		"asynq_enabled":      s.taskQueue != nil,
		"controlplane_scope": s.cfg.ControlPlane.Scope,
	}

	if s.taskQueue != nil {
		if stats, err := s.taskQueue.GetTaskStats(); err == nil {
			resp["queues"] = stats
		} else {
			resp["queues_error"] = err.Error()
		}
	}

	c.JSON(http.StatusOK, resp)
}


