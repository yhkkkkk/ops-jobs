package metrics

import (
	"net/http"
	"time"

	"ops-job-agent-server/internal/agent"
	"ops-job-agent-server/internal/config"
	"ops-job-agent-server/internal/logger"
	"ops-job-agent-server/internal/task"

	"github.com/gin-gonic/gin"
	"github.com/spf13/cast"
)

// HandleOverview 暴露最小可观测指标，便于控制面/监控系统抓取。
// 注：不引入 Prometheus 依赖，后续如需可再扩展为 /metrics(prometheus)。
func HandleOverview(c *gin.Context, agentMgr *agent.Manager, cfg *config.Config, tq *task.TaskQueue) {
	now := time.Now()

	agents := agentMgr.List()
	online := 0
	for _, a := range agents {
		if a.IsAlive(cfg.Agent.HeartbeatTimeout) {
			online++
		}
	}

	resp := gin.H{
		"now_unix_ms":        now.UnixMilli(),
		"agents_total":       len(agents),
		"agents_online":      online,
		"agents_offline":     len(agents) - online,
		"asynq_enabled":      tq != nil,
		"controlplane_scope": cfg.ControlPlane.Scope,
	}

	if tq != nil {
		if stats, err := tq.GetTaskStats(); err == nil {
			resp["queues"] = stats
		} else {
			resp["queues_error"] = err.Error()
		}
	}

	c.JSON(http.StatusOK, resp)
}

// HandleQueueStats 返回任务队列统计信息。
func HandleQueueStats(c *gin.Context, tq *task.TaskQueue) {
	if tq == nil {
		c.JSON(http.StatusServiceUnavailable, gin.H{
			"error": "asynq not enabled",
		})
		return
	}

	stats, err := tq.GetTaskStats()
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

// HandleDeadLetterTasks 返回死信队列（归档任务）列表
func HandleDeadLetterTasks(c *gin.Context, tq *task.TaskQueue) {
	if tq == nil {
		c.JSON(http.StatusServiceUnavailable, gin.H{
			"error": "asynq not enabled",
		})
		return
	}

	queueName := c.DefaultQuery("queue", task.QueueDefault)
	page := 1
	pageSize := 20

	if p := c.Query("page"); p != "" {
		parsed := cast.ToInt(p)
		if parsed > 0 {
			page = parsed
		}
	}
	if ps := c.Query("page_size"); ps != "" {
		parsed := cast.ToInt(ps)
		if parsed > 0 && parsed <= 100 {
			pageSize = parsed
		}
	}

	tasks, total, err := tq.GetDeadLetterTasks(queueName, page, pageSize)
	if err != nil {
		logger.GetLogger().WithError(err).Error("get dead letter tasks failed")
		c.JSON(http.StatusInternalServerError, gin.H{
			"error": err.Error(),
		})
		return
	}

	c.JSON(http.StatusOK, gin.H{
		"queue":      queueName,
		"tasks":      tasks,
		"total":      total,
		"page":       page,
		"page_size":  pageSize,
		"total_page": (total + pageSize - 1) / pageSize,
	})
}
