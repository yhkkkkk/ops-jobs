package websocket

import (
	"context"
	"fmt"
	"net/url"
	"sync"
	"time"

	"ops-job-agent/internal/api"
	"ops-job-agent/internal/logger"

	"github.com/gorilla/websocket"
)

// Client WebSocket 客户端，用于连接 Agent-Server
type Client struct {
	url         string
	token       string
	overrideURL string
	conn        *websocket.Conn
	connMu      sync.RWMutex
	connected   bool
	ctx         context.Context
	cancel      context.CancelFunc
	wg          sync.WaitGroup
	// 消息通道
	taskChan   chan *api.TaskSpec
	resultChan chan *api.TaskResult
	logChan    chan []api.LogEntry
	// 回调函数
	onTask   func(*api.TaskSpec)
	onCancel func(string)
}

// SendMessage 发送一条协议消息（用于 outbox 冲刷等场景）
func (c *Client) SendMessage(msg Message) error {
	return c.writeMessage(msg)
}

// NewClient 创建 WebSocket 客户端
func NewClient(serverURL, token string) *Client {
	ctx, cancel := context.WithCancel(context.Background())
	return &Client{
		url:        serverURL,
		token:      token,
		ctx:        ctx,
		cancel:     cancel,
		taskChan:   make(chan *api.TaskSpec, 100),
		resultChan: make(chan *api.TaskResult, 100),
		logChan:    make(chan []api.LogEntry, 100),
	}
}

// Connect 连接到 Agent-Server
func (c *Client) Connect(agentID string) error {
	wsURL, err := c.connectionURL(agentID)
	if err != nil {
		return err
	}

	// 连接 WebSocket
	dialer := websocket.Dialer{
		HandshakeTimeout: 10 * time.Second,
	}

	conn, _, err := dialer.Dial(wsURL, nil)
	if err != nil {
		return fmt.Errorf("dial websocket failed: %w", err)
	}

	c.connMu.Lock()
	c.conn = conn
	c.connected = true
	c.connMu.Unlock()

	logger.GetLogger().WithFields(map[string]interface{}{
		"url": wsURL,
	}).Info("websocket connected")

	// 启动消息处理
	c.wg.Add(2)
	go c.readLoop()
	go c.writeLoop()

	return nil
}

// Disconnect 断开连接
func (c *Client) Disconnect() error {
	c.cancel()

	c.connMu.Lock()
	if c.conn != nil {
		c.conn.Close()
		c.conn = nil
	}
	c.connected = false
	c.connMu.Unlock()

	c.wg.Wait()
	return nil
}

// IsConnected 检查是否已连接
func (c *Client) IsConnected() bool {
	c.connMu.RLock()
	defer c.connMu.RUnlock()
	return c.connected && c.conn != nil
}

// SetOnTask 设置任务接收回调
func (c *Client) SetOnTask(fn func(*api.TaskSpec)) {
	c.onTask = fn
}

// SetOnCancel 设置任务取消回调
func (c *Client) SetOnCancel(fn func(string)) {
	c.onCancel = fn
}

// SetOverrideURL 指定完整的 WebSocket 连接地址（用于 Agent-Server 返回的 ws_url）
func (c *Client) SetOverrideURL(u string) {
	c.connMu.Lock()
	defer c.connMu.Unlock()
	c.overrideURL = u
}

// SendHeartbeat 发送心跳
func (c *Client) SendHeartbeat(timestamp int64, system *api.SystemInfo) error {
	msg := Message{
		Type:      "heartbeat",
		Timestamp: time.Now().UnixMilli(),
		Payload: map[string]interface{}{
			"timestamp": timestamp,
			"system":    system,
		},
	}
	return c.writeMessage(msg)
}

// SendTaskResult 发送任务结果
func (c *Client) SendTaskResult(result *api.TaskResult) error {
	msg := Message{
		Type:      "task_result",
		Timestamp: time.Now().UnixMilli(),
		TaskID:    result.TaskID,
		Result:    result,
	}
	return c.writeMessage(msg)
}

// SendLogs 发送日志
func (c *Client) SendLogs(taskID string, logs []api.LogEntry) error {
	msg := Message{
		Type:      "log",
		Timestamp: time.Now().UnixMilli(),
		TaskID:    taskID,
		Logs:      logs,
	}
	return c.writeMessage(msg)
}

// readLoop 读取消息循环
func (c *Client) readLoop() {
	defer c.wg.Done()

	for {
		select {
		case <-c.ctx.Done():
			return
		default:
			c.connMu.RLock()
			conn := c.conn
			c.connMu.RUnlock()

			if conn == nil {
				return
			}

			// 设置读取超时
			conn.SetReadDeadline(time.Now().Add(60 * time.Second))

			var msg Message
			if err := conn.ReadJSON(&msg); err != nil {
				if websocket.IsUnexpectedCloseError(err, websocket.CloseGoingAway, websocket.CloseAbnormalClosure) {
					logger.GetLogger().WithError(err).Error("websocket read error")
				}
				c.connMu.Lock()
				c.connected = false
				c.connMu.Unlock()
				return
			}

			c.handleMessage(msg)
		}
	}
}

// writeLoop 写入消息循环
func (c *Client) writeLoop() {
	defer c.wg.Done()

	ticker := time.NewTicker(30 * time.Second)
	defer ticker.Stop()

	for {
		select {
		case <-c.ctx.Done():
			return
		case task := <-c.taskChan:
			// 任务已通过回调处理，这里不需要处理
			_ = task
		case result := <-c.resultChan:
			if err := c.SendTaskResult(result); err != nil {
				logger.GetLogger().WithError(err).Error("send task result failed")
			}
		case logs := <-c.logChan:
			// 日志已通过 SendLogs 直接发送，这里不需要处理
			_ = logs
		case <-ticker.C:
			// 定期发送心跳（如果需要）
		}
	}
}

// handleMessage 处理接收到的消息
func (c *Client) handleMessage(msg Message) {
	switch msg.Type {
	case "task":
		if msg.Task == nil {
			return
		}
		if c.onTask != nil {
			c.onTask(msg.Task)
		}
	case "cancel_task":
		if msg.TaskID == "" {
			return
		}
		if c.onCancel != nil {
			c.onCancel(msg.TaskID)
		}
	}
}

// writeMessage 写入消息
func (c *Client) writeMessage(msg interface{}) error {
	c.connMu.RLock()
	conn := c.conn
	c.connMu.RUnlock()

	if conn == nil {
		return fmt.Errorf("websocket not connected")
	}

	conn.SetWriteDeadline(time.Now().Add(10 * time.Second))
	return conn.WriteJSON(msg)
}

func (c *Client) connectionURL(agentID string) (string, error) {
	c.connMu.RLock()
	override := c.overrideURL
	c.connMu.RUnlock()

	if override != "" {
		return override, nil
	}

	u, err := url.Parse(c.url)
	if err != nil {
		return "", fmt.Errorf("parse url failed: %w", err)
	}

	switch u.Scheme {
	case "http":
		u.Scheme = "ws"
	case "https":
		u.Scheme = "wss"
	case "ws", "wss":
	default:
		return "", fmt.Errorf("unsupported websocket scheme %q", u.Scheme)
	}

	u.Path = fmt.Sprintf("/ws/agent/%s", agentID)
	q := u.Query()
	q.Set("token", c.token)
	u.RawQuery = q.Encode()
	return u.String(), nil
}
