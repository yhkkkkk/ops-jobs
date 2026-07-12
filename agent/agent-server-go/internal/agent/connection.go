package agent

import (
	serrors "ops-job-agent-server/internal/errors"
	"sync"
	"time"

	"ops-job-agent-server/internal/constants"
	"ops-job-agent-server/internal/websocket"
	"ops-job-agent-server/pkg/api"

	gorillaWs "github.com/gorilla/websocket"
)

// Connection Agent 连接封装
type Connection struct {
	ID                string
	Name              string
	Token             string
	Conn              *gorillaWs.Conn
	Status            string // active/inactive
	LastHeartbeat     time.Time
	Labels            map[string]string
	System            *api.SystemInfo
	TaskQueue         chan *api.TaskSpec
	LogBuffer         chan *api.LogEntry
	HostID            int // 控制面主机ID，用于建立映射关系
	runningTasks      map[string]*api.TaskSpec
	mu                sync.RWMutex
	writeMu           sync.Mutex
	ackStore          *websocket.AckStore // 持久化去重存储
	closed            bool
	taskQueueLoopOnce sync.Once
	logBufferLoopOnce sync.Once
}

// ConnectionSnapshot is an immutable view of mutable Agent connection metadata.
type ConnectionSnapshot struct {
	ID            string
	Name          string
	Status        string
	LastHeartbeat time.Time
	Labels        map[string]string
	System        *api.SystemInfo
	HostID        int
	Connected     bool
}

// Snapshot copies mutable connection state while holding the connection lock.
func (c *Connection) Snapshot() ConnectionSnapshot {
	if c == nil {
		return ConnectionSnapshot{}
	}

	c.mu.RLock()
	defer c.mu.RUnlock()

	snapshot := ConnectionSnapshot{
		ID:            c.ID,
		Name:          c.Name,
		Status:        c.Status,
		LastHeartbeat: c.LastHeartbeat,
		Labels:        cloneLabels(c.Labels),
		System:        cloneSystemInfo(c.System),
		HostID:        c.HostID,
		Connected:     !c.closed && c.Conn != nil,
	}
	return snapshot
}

// IsActive reports whether the Agent has an active WebSocket connection.
func (c *Connection) IsActive() bool {
	if c == nil {
		return false
	}
	c.mu.RLock()
	defer c.mu.RUnlock()
	return !c.closed && c.Status == constants.StatusActive && c.Conn != nil
}

func cloneLabels(labels map[string]string) map[string]string {
	if labels == nil {
		return nil
	}
	result := make(map[string]string, len(labels))
	for key, value := range labels {
		result[key] = value
	}
	return result
}

func cloneSystemInfo(system *api.SystemInfo) *api.SystemInfo {
	if system == nil {
		return nil
	}
	result := *system
	result.IPs = append([]string(nil), system.IPs...)
	result.LoadAvg = append([]float64(nil), system.LoadAvg...)
	if system.DiskUsage != nil {
		result.DiskUsage = make(map[string]float64, len(system.DiskUsage))
		for key, value := range system.DiskUsage {
			result.DiskUsage[key] = value
		}
	}
	return &result
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
	c.Status = constants.StatusInactive
	c.runningTasks = make(map[string]*api.TaskSpec)
	close(c.TaskQueue)
	close(c.LogBuffer)
	if c.Conn == nil {
		return nil
	}
	return c.Conn.Close()
}

// WriteJSON serializes every Gorilla WebSocket write for this Agent connection.
func (c *Connection) WriteJSON(value interface{}) error {
	c.mu.RLock()
	defer c.mu.RUnlock()
	if c.closed || c.Conn == nil {
		return serrors.ErrAgentConnectionClosed
	}

	c.writeMu.Lock()
	defer c.writeMu.Unlock()
	return c.Conn.WriteJSON(value)
}

// SendTask 发送任务到 Agent
func (c *Connection) SendTask(task *api.TaskSpec) error {

	msg := api.WebSocketMessage{
		Type: constants.MessageTypeTask,
		Task: task,
	}
	return c.WriteJSON(msg)
}

// SendTasks 批量发送任务到 Agent
func (c *Connection) SendTasks(tasks []*api.TaskSpec) error {
	if len(tasks) == 0 {
		return nil
	}

	// 批量发送消息
	msg := api.WebSocketMessage{
		Type:  constants.MessageTypeTasksBatch,
		Tasks: tasks,
	}
	return c.WriteJSON(msg)
}

// SendCancelTask 发送取消任务消息
func (c *Connection) SendCancelTask(taskID string) error {

	msg := api.WebSocketMessage{
		Type:   constants.MessageTypeCancelTask,
		TaskID: taskID,
	}
	return c.WriteJSON(msg)
}

// SendCancelTasks 批量发送取消任务消息
func (c *Connection) SendCancelTasks(taskIDs []string) error {
	if len(taskIDs) == 0 {
		return nil
	}

	// 批量取消
	msg := api.WebSocketMessage{
		Type:    constants.MessageTypeCancelTasksBatch,
		TaskIDs: taskIDs,
	}
	return c.WriteJSON(msg)
}

// SendControl 发送控制消息（start/stop/restart）到 Agent
func (c *Connection) SendControl(action, reason string) error {

	msg := api.WebSocketMessage{
		Type: constants.MessageTypeControl,
		Payload: map[string]interface{}{
			"action": action,
			"reason": reason,
		},
	}
	return c.WriteJSON(msg)
}

// SendUpgrade 发送升级消息到 Agent
func (c *Connection) SendUpgrade(targetVersion, downloadURL, md5Hash, sha256Hash string) error {

	msg := api.WebSocketMessage{
		Type: constants.MessageTypeUpgrade,
		Payload: map[string]interface{}{
			"target_version": targetVersion,
			"download_url":   downloadURL,
			"md5_hash":       md5Hash,
			"sha256_hash":    sha256Hash,
		},
	}
	return c.WriteJSON(msg)
}

// AddRunningTask 注册一个正在运行的任务
func (c *Connection) AddRunningTask(task *api.TaskSpec) {
	if task == nil || task.ID == "" {
		return
	}
	c.mu.Lock()
	defer c.mu.Unlock()
	// 保存副本以避免外部修改
	taskCopy := *task
	c.runningTasks[task.ID] = &taskCopy
}

// RemoveRunningTask 从运行任务注册表中移除任务
func (c *Connection) RemoveRunningTask(taskID string) {
	if taskID == "" {
		return
	}
	c.mu.Lock()
	defer c.mu.Unlock()
	delete(c.runningTasks, taskID)
}

// IsTaskRunning 检查任务是否已注册为正在运行
func (c *Connection) IsTaskRunning(taskID string) bool {
	if taskID == "" {
		return false
	}
	c.mu.RLock()
	defer c.mu.RUnlock()
	_, exists := c.runningTasks[taskID]
	return exists
}

// GetRunningTasks 返回正在运行任务的副本以避免外部修改
func (c *Connection) GetRunningTasks() []api.TaskSpec {
	c.mu.RLock()
	defer c.mu.RUnlock()
	result := make([]api.TaskSpec, 0, len(c.runningTasks))
	for _, t := range c.runningTasks {
		if t == nil {
			continue
		}
		// 复制值以脱离内部 map
		copyVal := *t
		result = append(result, copyVal)
	}
	return result
}

// MarkDisconnected 标记连接断开但保留状态，供重连使用
func (c *Connection) MarkDisconnected() {
	c.mu.Lock()
	defer c.mu.Unlock()
	if c.closed {
		return
	}
	c.Status = constants.StatusInactive
	c.LastHeartbeat = time.Now()
	c.Conn = nil
}

// EnsureTaskQueueLoopStarted 确保任务队列处理协程只启动一次。
func (c *Connection) EnsureTaskQueueLoopStarted(start func()) {
	if start == nil {
		return
	}
	c.taskQueueLoopOnce.Do(start)
}

// EnsureLogBufferLoopStarted 确保日志缓冲处理协程只启动一次。
func (c *Connection) EnsureLogBufferLoopStarted(start func()) {
	if start == nil {
		return
	}
	c.logBufferLoopOnce.Do(start)
}
