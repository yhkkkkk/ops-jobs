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
	Scope         string // 多租户隔离：Agent所属的scope（从控制面获取或配置）
	HostID        int    // 控制面主机ID，用于建立映射关系
	runningTasks  map[string]*api.TaskSpec
	mu            sync.RWMutex
	ackStore      map[string]time.Time
	ackMu         sync.Mutex
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
		// runningTasks tracks tasks that were dispatched to this agent; guarded by mu.
		runningTasks: make(map[string]*api.TaskSpec),
		ackStore:     make(map[string]time.Time),
	}
}

// SeenMessage 记录并检查 message_id 幂等，返回是否已见过
func (c *Connection) SeenMessage(id string, ttl time.Duration, max int) bool {
	if id == "" {
		return false
	}
	if ttl <= 0 {
		ttl = 10 * time.Minute
	}
	if max <= 0 {
		max = 5000
	}
	now := time.Now()
	c.ackMu.Lock()
	defer c.ackMu.Unlock()
	if t, ok := c.ackStore[id]; ok {
		if now.Sub(t) < ttl {
			return true
		}
		delete(c.ackStore, id)
	}
	if len(c.ackStore) >= max {
		for k, t := range c.ackStore {
			if now.Sub(t) > ttl {
				delete(c.ackStore, k)
			}
			if len(c.ackStore) < max {
				break
			}
		}
		// 简单裁剪
		for len(c.ackStore) > max {
			for k := range c.ackStore {
				delete(c.ackStore, k)
				break
			}
		}
	}
	c.ackStore[id] = now
	return false
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
	c.runningTasks = make(map[string]*api.TaskSpec)
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

// SendTasks 批量发送任务到 Agent
func (c *Connection) SendTasks(tasks []*api.TaskSpec) error {
	if len(tasks) == 0 {
		return nil
	}

	c.mu.RLock()
	defer c.mu.RUnlock()
	if c.closed {
		return ErrConnectionClosed
	}

	// 批量发送消息
	msg := api.WebSocketMessage{
		Type:  "tasks_batch",
		Tasks: tasks,
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

// SendCancelTasks 批量发送取消任务消息
func (c *Connection) SendCancelTasks(taskIDs []string) error {
	if len(taskIDs) == 0 {
		return nil
	}

	c.mu.RLock()
	defer c.mu.RUnlock()
	if c.closed {
		return ErrConnectionClosed
	}

	// 批量取消
	msg := api.WebSocketMessage{
		Type:    "cancel_tasks_batch",
		TaskIDs: taskIDs,
	}
	return c.Conn.WriteJSON(msg)
}

// GetScope 返回连接的scope
func (c *Connection) GetScope() string {
	c.mu.RLock()
	defer c.mu.RUnlock()
	return c.Scope
}

// AddRunningTask registers a task as running for this connection (thread-safe).
func (c *Connection) AddRunningTask(task *api.TaskSpec) {
	if task == nil || task.ID == "" {
		return
	}
	c.mu.Lock()
	defer c.mu.Unlock()
	// store a copy to avoid external mutation
	taskCopy := *task
	c.runningTasks[task.ID] = &taskCopy
}

// RemoveRunningTask removes a task from the running registry.
func (c *Connection) RemoveRunningTask(taskID string) {
	if taskID == "" {
		return
	}
	c.mu.Lock()
	defer c.mu.Unlock()
	delete(c.runningTasks, taskID)
}

// IsTaskRunning reports whether the task is registered as running.
func (c *Connection) IsTaskRunning(taskID string) bool {
	if taskID == "" {
		return false
	}
	c.mu.RLock()
	defer c.mu.RUnlock()
	_, exists := c.runningTasks[taskID]
	return exists
}

// GetRunningTasks returns a copy of running tasks to avoid external mutation.
func (c *Connection) GetRunningTasks() []api.TaskSpec {
	c.mu.RLock()
	defer c.mu.RUnlock()
	result := make([]api.TaskSpec, 0, len(c.runningTasks))
	for _, t := range c.runningTasks {
		if t == nil {
			continue
		}
		// copy value to detach from internal map
		copyVal := *t
		result = append(result, copyVal)
	}
	return result
}
