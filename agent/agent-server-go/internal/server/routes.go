package server

import (
	"ops-job-agent-server/internal/metrics"

	"github.com/gin-gonic/gin"
)

// setupRoutes 设置路由
func (s *Server) setupRoutes() {
	s.setupAgentIngressRoutes()
	s.setupControlPlaneIngressRoutes()
	s.setupWebSocketRoutes()
	setupIntegrationRoutes(s)
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
