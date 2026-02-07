package server

import (
	"net/http/httptest"
	"time"

	"ops-job-agent-server/internal/agent"
	"ops-job-agent-server/internal/config"
	"ops-job-agent-server/internal/task"

	"github.com/gin-gonic/gin"
)

// newTestServerForE2E 构造测试用 Server（仅测试编译时可见）
func newTestServerForE2E(cfg *config.Config, mgr *agent.Manager, pending *task.PendingTaskStore) *Server {
	if cfg == nil {
		cfg = &config.Config{}
	}
	// 缩短日志缓冲刷新频率，避免测试卡住
	if cfg.LogStream.FlushInterval == 0 {
		cfg.LogStream.FlushInterval = 1
	}
	if cfg.LogStream.BatchSize == 0 {
		cfg.LogStream.BatchSize = 1
	}
	if cfg.LogStream.BufferSize == 0 {
		cfg.LogStream.BufferSize = 16
	}
	if cfg.Server.ReadTimeout == 0 {
		cfg.Server.ReadTimeout = 5 * time.Second
	}
	if cfg.Server.WriteTimeout == 0 {
		cfg.Server.WriteTimeout = 5 * time.Second
	}

	s := &Server{
		cfg:              cfg,
		upgrader:         createUpgrader(cfg),
		agentManager:     mgr,
		taskDispatcher:   task.NewDispatcher(mgr, pending),
		pendingTaskStore: pending,
	}
	s.engine = gin.New()
	s.engine.Use(gin.Recovery())
	s.setupRoutes()
	return s
}

// newTestHTTPServer 启动 httptest Server 并返回
func newTestHTTPServer(s *Server) *httptest.Server {
	return httptest.NewServer(s.engine)
}
