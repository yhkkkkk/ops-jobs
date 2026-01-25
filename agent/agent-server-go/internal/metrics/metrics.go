package metrics

import (
	"net/http"
	"time"

	"ops-job-agent-server/internal/agent"
	"ops-job-agent-server/internal/config"

	"github.com/gin-gonic/gin"
)

// HandleOverview 暴露最小可观测指标，便于控制面/监控系统抓取。
// 注：不引入 Prometheus 依赖，后续如需可再扩展为 /metrics(prometheus)。
func HandleOverview(c *gin.Context, agentMgr *agent.Manager, cfg *config.Config) {
	now := time.Now()

	agents := agentMgr.List()
	online := 0
	for _, a := range agents {
		if a.IsAlive(cfg.Agent.HeartbeatTimeout) {
			online++
		}
	}

	resp := gin.H{
		"now_unix_ms":    now.UnixMilli(),
		"agents_total":   len(agents),
		"agents_online":  online,
		"agents_offline": len(agents) - online,
	}

	c.JSON(http.StatusOK, resp)
}
