package agent

import (
	serrors "ops-job-agent-server/internal/errors"
	"sync"
	"time"

	"ops-job-agent-server/internal/config"
	"ops-job-agent-server/internal/constants"
	"ops-job-agent-server/internal/logger"
	"ops-job-agent-server/internal/websocket"
	"ops-job-agent-server/pkg/api"

	"github.com/google/uuid"
	gorillaWs "github.com/gorilla/websocket"
	"github.com/redis/go-redis/v9"
)

// Manager Agent 连接管理器
type Manager struct {
	agents           map[string]*Connection
	agentsByToken    map[string]*Connection
	mu               sync.RWMutex
	maxConns         int
	heartbeatTimeout time.Duration
	config           *config.Config
	redisClient      *redis.Client // redis连接池客户端
}

// NewManager 创建 Agent 管理器
func NewManager(maxConns int, heartbeatTimeout time.Duration, cfg *config.Config, redisClient *redis.Client) *Manager {
	return &Manager{
		agents:           make(map[string]*Connection),
		agentsByToken:    make(map[string]*Connection),
		maxConns:         maxConns,
		heartbeatTimeout: heartbeatTimeout,
		config:           cfg,
		redisClient:      redisClient,
	}
}

// Register 注册 Agent
func (m *Manager) Register(name, token string, labels map[string]string, system *api.SystemInfo, hostID int) (*Connection, string, error) {
	m.mu.Lock()
	defer m.mu.Unlock()

	// 检查连接数限制
	if len(m.agents) >= m.maxConns {
		return nil, "", serrors.ErrMaxConnectionsReached
	}

	// 生成 Agent ID
	agentID := uuid.New().String()

	// 如果提供了 token，检查是否已存在
	if token != "" {
		if conn, exists := m.agentsByToken[token]; exists {
			// 更新现有连接
			conn.mu.Lock()
			conn.Name = name
			conn.Labels = labels
			conn.System = system
			conn.UpdateHeartbeat()
			conn.mu.Unlock()
			return conn, conn.ID, nil
		}
	} else {
		// 生成新的 token
		token = uuid.New().String()
	}

	// 创建持久化 AckStore
	ackStore := websocket.NewAckStore(m.redisClient, "agent-server") // 使用Redis客户端

	// 创建新连接（注意：这里还没有 WebSocket 连接，需要后续通过 Connect 方法设置）
	conn := &Connection{
		ID:           agentID,
		Name:         name,
		Token:        token,
		Status:       "active",
		Labels:       labels,
		System:       system,
		TaskQueue:    make(chan *api.TaskSpec, 100),
		LogBuffer:    make(chan *api.LogEntry, 1000),
		HostID:       hostID,
		runningTasks: make(map[string]*api.TaskSpec),
		ackStore:     ackStore,
	}

	m.agents[agentID] = conn
	m.agentsByToken[token] = conn

	logger.GetLogger().WithFields(map[string]interface{}{
		"agent_id":   agentID,
		"agent_name": name,
	}).Info("agent registered")

	return conn, agentID, nil
}

// Connect 建立 WebSocket 连接
func (m *Manager) Connect(agentID, token string, conn *gorillaWs.Conn) (*Connection, error) {
	m.mu.Lock()
	defer m.mu.Unlock()

	agent, exists := m.agents[agentID]
	if !exists {
		return nil, serrors.ErrAgentNotFound
	}

	// 验证 token
	if agent.Token != token {
		return nil, serrors.ErrInvalidToken
	}

	// 设置 WebSocket 连接
	agent.mu.Lock()
	agent.Conn = conn
	agent.LastHeartbeat = time.Now()
	agent.Status = constants.StatusActive
	agent.mu.Unlock()

	logger.GetLogger().WithFields(map[string]interface{}{
		"agent_id": agentID,
	}).Info("agent connected")

	return agent, nil
}

// Get 获取 Agent 连接
func (m *Manager) Get(agentID string) (*Connection, bool) {
	m.mu.RLock()
	defer m.mu.RUnlock()
	conn, exists := m.agents[agentID]
	return conn, exists
}

// GetByToken 通过 token 获取 Agent 连接
func (m *Manager) GetByToken(token string) (*Connection, bool) {
	m.mu.RLock()
	defer m.mu.RUnlock()
	conn, exists := m.agentsByToken[token]
	return conn, exists
}

// Remove 移除 Agent
func (m *Manager) Remove(agentID string) error {
	m.mu.Lock()
	defer m.mu.Unlock()

	agent, exists := m.agents[agentID]
	if !exists {
		return serrors.ErrAgentNotFound
	}

	// 关闭连接
	_ = agent.Close()

	// 从映射中移除
	delete(m.agents, agentID)
	delete(m.agentsByToken, agent.Token)

	logger.GetLogger().WithFields(map[string]interface{}{
		"agent_id": agentID,
	}).Info("agent removed")

	return nil
}

// List 列出所有 Agent
func (m *Manager) List() []*Connection {
	m.mu.RLock()
	defer m.mu.RUnlock()

	agents := make([]*Connection, 0, len(m.agents))
	for _, agent := range m.agents {
		agents = append(agents, agent)
	}
	return agents
}

// CleanupInactive 清理非活跃连接
func (m *Manager) CleanupInactive() {
	m.mu.Lock()
	defer m.mu.Unlock()

	for agentID, agent := range m.agents {
		if !agent.IsAlive(m.heartbeatTimeout) {
			logger.GetLogger().WithFields(map[string]interface{}{
				"agent_id": agentID,
			}).Warn("removing inactive agent")
			_ = agent.Close()
			delete(m.agents, agentID)
			delete(m.agentsByToken, agent.Token)
		}
	}
}

// Count 返回当前连接数
func (m *Manager) Count() int {
	m.mu.RLock()
	defer m.mu.RUnlock()
	return len(m.agents)
}
