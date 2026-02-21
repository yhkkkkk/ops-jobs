package server

import (
	"context"
	"fmt"
	"net/http"
	"time"

	"ops-job-agent-server/internal/agent"
	"ops-job-agent-server/internal/config"
	logstream "ops-job-agent-server/internal/log"
	"ops-job-agent-server/internal/logger"
	"ops-job-agent-server/internal/metrics"
	redisPkg "ops-job-agent-server/internal/redis"
	"ops-job-agent-server/internal/task"

	"github.com/redis/go-redis/v9"

	"github.com/gin-gonic/gin"
	"github.com/gorilla/websocket"
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
	cfg                 *config.Config
	engine              *gin.Engine
	httpServer          *http.Server
	upgrader            websocket.Upgrader // WebSocket Upgrader
	agentManager        *agent.Manager
	taskDispatcher      *task.Dispatcher
	pendingTaskStore    *task.PendingTaskStore // 待处理任务持久化存储
	logStream           LogSink
	resultStream        ResultSink
	statusStream        StatusSink
	taskStatsAggregator *metrics.TaskStatsAggregator // 任务统计聚合器
}

// New 创建服务器
func New(cfg *config.Config) (*Server, error) {
	gin.SetMode(gin.ReleaseMode)

	engine := gin.New()
	engine.Use(gin.Recovery())
	engine.Use(gin.Logger())

	// 创建 WebSocket Upgrader
	upgrader := createUpgrader(cfg)

	// 创建redis连接池管理器
	var redisClient *redis.Client
	if cfg.Redis.Enabled {
		poolMgr := redisPkg.NewPoolManager(&cfg.Redis)
		client, err := poolMgr.GetClient()
		if err != nil {
			logger.GetLogger().WithError(err).Warn("failed to create redis connection pool, ackstore will be disabled")
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
	var logStream LogSink
	if cfg.LogStream.Enabled {
		if redisClient == nil {
			return nil, fmt.Errorf("log stream enabled but redis client not available")
		}
		var err error
		writer, err := logstream.NewStreamWriter(redisClient, cfg)
		if err != nil {
			return nil, fmt.Errorf("create log stream writer: %w", err)
		}
		if writer != nil {
			logStream = &logStreamAdapter{writer}
		}
	}

	// 创建结果流写入器
	var resultStream ResultSink
	if cfg.ResultStream.Enabled {
		if redisClient == nil {
			return nil, fmt.Errorf("result stream enabled but redis client not available")
		}
		var err error
		writer, err := logstream.NewResultStreamWriter(redisClient, cfg)
		if err != nil {
			return nil, fmt.Errorf("create result stream writer: %w", err)
		}
		if writer != nil {
			resultStream = &resultStreamAdapter{writer}
		}
	}

	// 创建状态流写入器
	var statusStream StatusSink
	if cfg.StatusStream.Enabled {
		if redisClient == nil {
			return nil, fmt.Errorf("status stream enabled but redis client not available")
		}
		var err error
		writer, err := logstream.NewStatusStreamWriter(redisClient, cfg)
		if err != nil {
			return nil, fmt.Errorf("create status stream writer: %w", err)
		}
		if writer != nil {
			statusStream = &statusStreamAdapter{writer}
		}
	}

	// 创建任务统计聚合器
	var taskStatsAggregator *metrics.TaskStatsAggregator
	if cfg.TaskStatsStream.Enabled {
		var err error
		taskStatsAggregator, err = metrics.NewTaskStatsAggregator(redisClient, cfg)
		if err != nil {
			return nil, fmt.Errorf("create task stats aggregator: %w", err)
		}
	}

	s := &Server{
		cfg:                 cfg,
		upgrader:            upgrader,
		engine:              engine,
		agentManager:        agentMgr,
		taskDispatcher:      taskDispatcher,
		pendingTaskStore:    pendingTaskStore,
		logStream:           logStream,
		resultStream:        resultStream,
		statusStream:        statusStream,
		taskStatsAggregator: taskStatsAggregator,
	}

	s.setupRoutes()

	return s, nil
}

// Start 启动服务器
func (s *Server) Start() error {
	// 启动清理非活跃连接的goroutine
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
