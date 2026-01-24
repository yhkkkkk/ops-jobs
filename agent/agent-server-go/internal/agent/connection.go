package agent

import (
	"sync"
	"time"

	"ops-job-agent-server/internal/websocket"
	"ops-job-agent-server/pkg/api"

	gorillaWs "github.com/gorilla/websocket"
)

// Connection Agent 连接封装
type Connection struct {
	ID            string
	Name          string
	Token         string
	Conn          *gorillaWs.Conn
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
	ackStore      *websocket.AckStore // 持久化去重存储
	closed        bool
}

// NewConnection 创建新的 Agent 连接
func NewConnection(id, name, token string, conn *gorillaWs.Conn) *Connection {
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
	}
}

// SeenMessage 记录并检查 message_id 幂等，返回是否已见过
func (c *Connection) SeenMessage(id string, ttl time.Duration, max int) bool {
	if id == "" {
		return false
	}

	// 使用持久化 AckStore
	return c.ackStore.Seen(id)
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

// SendControl 发送控制消息到 Agent
func (c *Connection) SendControl(action, reason string) error {
	c.mu.RLock()
	defer c.mu.RUnlock()
	if c.closed {
		return ErrConnectionClosed
	}

	msg := api.WebSocketMessage{
		Type: "control",
		Payload: map[string]interface{}{
			"action": action,
			"reason": reason,
		},
	}
	return c.Conn.WriteJSON(msg)
}

// SendUpgrade 发送升级消息到 Agent
func (c *Connection) SendUpgrade(targetVersion, downloadURL, md5Hash, sha256Hash string) error {
	c.mu.RLock()
	defer c.mu.RUnlock()
	if c.closed {
		return ErrConnectionClosed
	}

	msg := api.WebSocketMessage{
		Type: "upgrade",
		Payload: map[string]interface{}{
			"target_version": targetVersion,
			"download_url":   downloadURL,
			"md5_hash":       md5Hash,
			"sha256_hash":    sha256Hash,
		},
	}
	return c.Conn.WriteJSON(msg)
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
