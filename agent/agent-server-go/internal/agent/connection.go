package agent

import (
	"sync"
	"time"

	"ops-job-agent-server/pkg/api"

	"github.com/gorilla/websocket"
)

// Connection Agent 连接封装
type Connection struct {
	ID            string
	Name          string
	Token         string
	Conn          *websocket.Conn
	Status        string // active/inactive
	LastHeartbeat time.Time
	Labels        map[string]string
	System        *api.SystemInfo
	TaskQueue     chan *api.TaskSpec
	LogBuffer     chan *api.LogEntry
	mu            sync.RWMutex
	closed        bool
}

// NewConnection 创建新的 Agent 连接
func NewConnection(id, name, token string, conn *websocket.Conn) *Connection {
	return &Connection{
		ID:        id,
		Name:      name,
		Token:     token,
		Conn:      conn,
		Status:    "active",
		TaskQueue: make(chan *api.TaskSpec, 100),
		LogBuffer: make(chan *api.LogEntry, 1000),
		Labels:    make(map[string]string),
	}
}

// UpdateHeartbeat 更新心跳时间
func (c *Connection) UpdateHeartbeat() {
	c.mu.Lock()
	defer c.mu.Unlock()
	c.LastHeartbeat = time.Now()
}

// IsAlive 检查连接是否存活
func (c *Connection) IsAlive(timeout time.Duration) bool {
	c.mu.RLock()
	defer c.mu.RUnlock()
	if c.closed {
		return false
	}
	return time.Since(c.LastHeartbeat) < timeout
}

// Close 关闭连接
func (c *Connection) Close() error {
	c.mu.Lock()
	defer c.mu.Unlock()
	if c.closed {
		return nil
	}
	c.closed = true
	c.Status = "inactive"
	close(c.TaskQueue)
	close(c.LogBuffer)
	return c.Conn.Close()
}

// SendTask 发送任务到 Agent
func (c *Connection) SendTask(task *api.TaskSpec) error {
	c.mu.RLock()
	defer c.mu.RUnlock()
	if c.closed {
		return ErrConnectionClosed
	}

	msg := api.WebSocketMessage{
		Type: "task",
		Task: task,
	}
	return c.Conn.WriteJSON(msg)
}

// SendCancelTask 发送取消任务消息
func (c *Connection) SendCancelTask(taskID string) error {
	c.mu.RLock()
	defer c.mu.RUnlock()
	if c.closed {
		return ErrConnectionClosed
	}

	msg := api.WebSocketMessage{
		Type:   "cancel_task",
		TaskID: taskID,
	}
	return c.Conn.WriteJSON(msg)
}
