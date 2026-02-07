package websocket

import (
	"context"
	"errors"
	"fmt"
	"net/http"
	"net/url"
	"sync"
	"time"

	"github.com/avast/retry-go/v4"
	"github.com/google/uuid"
	"github.com/gorilla/websocket"

	"ops-job-agent/internal/api"
	"ops-job-agent/internal/constants"
	serrors "ops-job-agent/internal/errors"
	"ops-job-agent/internal/logger"
)

type connEvent string

const (
	connEventConnected    connEvent = "connected"
	connEventDisconnected connEvent = "disconnected"
	connEventEnqueued     connEvent = "enqueued"
)

type connEventMessage struct {
	kind   connEvent
	reason string
}

type pendingMessage struct {
	msg       Message
	retries   int
	nextRetry time.Time
	lastSent  time.Time
}

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
	// pending ACK
	pending          map[string]*pendingMessage
	pendingMu        sync.Mutex
	retryInterval    time.Duration
	maxRetryInterval time.Duration
	pendingTTL       time.Duration
	pendingMax       int
	// 重连状态
	reconnectMu       sync.Mutex
	reconnectAgentID  string
	reconnectInterval time.Duration
	reconnecting      bool
	reconnectMax      int
	reconnectCancel   context.CancelFunc
	// 连接事件
	events chan connEventMessage
	// 重连触发信号
	reconnectCh chan struct{}
	// 压缩开关
	enableCompression bool
	// 回调函数
	onTask      func(*api.TaskSpec)
	onCancel    func(string)
	onControl   func(map[string]interface{})
	onUpgrade   func(map[string]interface{})
	onAuthError func() (string, error)
}

// SendMessage 发送一条协议消息（用于 outbox 冲刷等场景）
func (c *Client) SendMessage(msg Message) error {
	return c.writeMessage(msg)
}

// TaskChan 返回任务通道
func (c *Client) TaskChan() <-chan *api.TaskSpec {
	return c.taskChan
}

// NewClient 创建 WebSocket 客户端
func NewClient(serverURL, token string, enableCompression bool) *Client {
	ctx, cancel := context.WithCancel(context.Background())
	client := &Client{
		url:               serverURL,
		token:             token,
		ctx:               ctx,
		cancel:            cancel,
		taskChan:          make(chan *api.TaskSpec, 100),
		resultChan:        make(chan *api.TaskResult, 100),
		logChan:           make(chan []api.LogEntry, 100),
		pending:           make(map[string]*pendingMessage),
		retryInterval:     constants.WSDefaultRetryInterval,
		maxRetryInterval:  constants.WSMaxRetryInterval,
		pendingTTL:        constants.WSPendingTTL,
		pendingMax:        constants.WSPendingMax,
		reconnectInterval: constants.WSDefaultReconnectInterval,
		events:            make(chan connEventMessage, 8),
		reconnectCh:       make(chan struct{}, 1),
		enableCompression: enableCompression,
	}
	go client.retryPendingLoop()
	go client.eventLoop()
	return client
}

// Connect 连接到 Agent-Server
func (c *Client) Connect(agentID string) error {
	wsURL, err := c.connectionURL(agentID)
	if err != nil {
		return err
	}

	// 连接 WebSocket，使用 Sec-WebSocket-Protocol 头部传递 token（更安全，不暴露在 URL 中）
	dialer := websocket.Dialer{
		HandshakeTimeout:  10 * time.Second,
		EnableCompression: c.enableCompression,
	}

	// 使用 Sec-WebSocket-Protocol 头部传递认证 token
	headers := http.Header{
		constants.HeaderSecWebSocketProtocol: []string{"agent-token," + c.token},
	}

	conn, resp, err := dialer.Dial(wsURL, headers)
	if err != nil {
		if resp != nil {
			switch resp.StatusCode {
			case http.StatusUnauthorized, http.StatusForbidden, http.StatusNotFound:
				return serrors.ErrAuthOrNotFound
			}
		}
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
	c.emitEvent(connEventConnected, "connected")

	return nil
}

// Disconnect 断开连接
func (c *Client) Disconnect() error {
	// 先停止重连循环
	c.reconnectMu.Lock()
	c.reconnecting = false
	c.reconnectMu.Unlock()

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

// StartReconnectLoop 启动独立的重连循环（断线后自动尝试重连）
// 事件驱动：只有收到断线/触发事件时才开始一次重连序列，不做轮询。
// 重连序列由 retry-go 托管：失败后按退避间隔重试；成功后立即退出序列。
// 互斥保证：同一时刻只允许一条重连序列进行中；StopReconnectLoop 会取消当前序列。
func (c *Client) StartReconnectLoop(agentID string) {
	c.reconnectMu.Lock()
	if c.reconnecting {
		c.reconnectAgentID = agentID
		c.reconnectMu.Unlock()
		return
	}
	c.reconnecting = true
	c.reconnectAgentID = agentID
	c.reconnectMu.Unlock()

	c.wg.Add(1)
	go func() {
		defer c.wg.Done()

		for {
			select {
			case <-c.ctx.Done():
				c.stopReconnectAttempt()
				logger.GetLogger().Info("reconnect loop stopped due to context cancelled")
				return
			case <-c.reconnectCh:
				// 事件驱动入口：只在断线/触发信号到来时进入重连序列。
				agentID, maxAttempts, ok := c.snapshotReconnect()
				if !ok {
					return
				}
				if c.IsConnected() {
					continue
				}
				// 保证同一时刻仅有一条重连序列在进行。
				retryCtx, ok := c.startReconnectAttempt()
				if !ok {
					continue
				}
				logger.GetLogger().Warn("websocket disconnected, attempting to reconnect...")
				// retry-go 负责退避与最大重试次数；成功则返回 nil。
				err := c.reconnectOnce(retryCtx, agentID, maxAttempts)
				c.finishReconnectAttempt()
				if !c.isReconnectEnabled() {
					return
				}
				if err == nil {
					continue
				}
				if errors.Is(err, context.Canceled) || errors.Is(err, context.DeadlineExceeded) {
					return
				}
				if maxAttempts > 0 {
					logger.GetLogger().WithFields(map[string]interface{}{
						"attempts": maxAttempts,
					}).Warn("reconnect stopped after max attempts")
					c.StopReconnectLoop()
					return
				}
				// 不可恢复错误（例如鉴权失败且无法重注册）直接停止循环。
				if !retry.IsRecoverable(err) {
					logger.GetLogger().WithError(err).Warn("reconnect stopped due to unrecoverable error")
					c.StopReconnectLoop()
					return
				}
			}
		}
	}()

	c.triggerReconnect()
}

// StopReconnectLoop 停止重连循环
func (c *Client) StopReconnectLoop() {
	c.reconnectMu.Lock()
	c.reconnecting = false
	cancel := c.reconnectCancel
	c.reconnectCancel = nil
	c.reconnectMu.Unlock()
	if cancel != nil {
		cancel()
	}
	c.triggerReconnect()
}

func (c *Client) snapshotReconnect() (string, int, bool) {
	c.reconnectMu.Lock()
	defer c.reconnectMu.Unlock()
	if !c.reconnecting {
		return "", 0, false
	}
	return c.reconnectAgentID, c.reconnectMax, true
}

func (c *Client) isReconnectEnabled() bool {
	c.reconnectMu.Lock()
	defer c.reconnectMu.Unlock()
	return c.reconnecting
}

func (c *Client) startReconnectAttempt() (context.Context, bool) {
	c.reconnectMu.Lock()
	defer c.reconnectMu.Unlock()
	if !c.reconnecting {
		return nil, false
	}
	if c.reconnectCancel != nil {
		return nil, false
	}
	ctx, cancel := context.WithCancel(c.ctx)
	c.reconnectCancel = cancel
	return ctx, true
}

func (c *Client) finishReconnectAttempt() {
	c.reconnectMu.Lock()
	cancel := c.reconnectCancel
	c.reconnectCancel = nil
	c.reconnectMu.Unlock()
	if cancel != nil {
		cancel()
	}
}

func (c *Client) stopReconnectAttempt() {
	c.reconnectMu.Lock()
	cancel := c.reconnectCancel
	c.reconnectCancel = nil
	c.reconnectMu.Unlock()
	if cancel != nil {
		cancel()
	}
}

func (c *Client) backoffDelay(attempts int) time.Duration {
	base := c.reconnectInterval
	if base <= 0 {
		base = constants.WSDefaultReconnectInterval
	}
	maxDelay := c.maxRetryInterval
	if maxDelay <= 0 {
		maxDelay = constants.WSMaxRetryInterval
	}
	shift := attempts - 1
	if shift < 0 {
		shift = 0
	}
	if shift > 30 {
		shift = 30
	}
	delay := base * time.Duration(1<<uint(shift))
	if delay > maxDelay {
		delay = maxDelay
	}
	return delay
}

func (c *Client) reconnectOnce(ctx context.Context, agentID string, maxAttempts int) error {
	attempts := uint(0)
	if maxAttempts > 0 {
		attempts = uint(maxAttempts)
	}

	err := retry.Do(
		func() error {
			if c.IsConnected() {
				return nil
			}
			if err := c.Connect(agentID); err != nil {
				// 鉴权/不存在：说明旧的 agentID 失效（控制面或 server 重启/丢状态），
				// 需要重新注册拿到新 agentID 后立即重试连接。
				if errors.Is(err, serrors.ErrAuthOrNotFound) {
					if c.onAuthError == nil {
						return retry.Unrecoverable(err)
					}
					newID, regErr := c.onAuthError()
					if regErr != nil || newID == "" {
						if regErr == nil {
							regErr = err
						}
						logger.GetLogger().WithError(regErr).Warn("re-register failed, stop reconnect")
						return retry.Unrecoverable(regErr)
					}
					c.reconnectMu.Lock()
					c.reconnectAgentID = newID
					c.reconnectMu.Unlock()
					agentID = newID
					logger.GetLogger().WithField("agent_id", newID).Info("re-registered after auth error, will reconnect")
					return serrors.ErrReconnectAuthRetry
				}
				return err
			}
			return nil
		},
		retry.Context(ctx),
		retry.Attempts(attempts),
		retry.RetryIf(func(err error) bool {
			if err == nil {
				return false
			}
			if errors.Is(err, context.Canceled) || errors.Is(err, context.DeadlineExceeded) {
				return false
			}
			return true
		}),
		retry.DelayType(func(n uint, err error, _ *retry.Config) time.Duration {
			if errors.Is(err, serrors.ErrReconnectAuthRetry) {
				return 0
			}
			attempt := int(n)
			if attempt < 1 {
				attempt = 1
			}
			return c.backoffDelay(attempt)
		}),
		retry.OnRetry(func(n uint, err error) {
			logger.GetLogger().WithError(err).WithField("attempt", n).Warn("reconnect failed, will retry")
		}),
	)

	if err == nil {
		logger.GetLogger().Info("reconnected successfully")
	}
	return err
}

// SetReconnectMaxAttempts 设置重连最大尝试次数（<=0 表示无限）
func (c *Client) SetReconnectMaxAttempts(attempts int) {
	c.reconnectMu.Lock()
	c.reconnectMax = attempts
	c.reconnectMu.Unlock()
}

// SetOnTask 设置任务接收回调
func (c *Client) SetOnTask(fn func(*api.TaskSpec)) {
	c.onTask = fn
}

// SetOnCancel 设置任务取消回调
func (c *Client) SetOnCancel(fn func(string)) {
	c.onCancel = fn
}

// SetOnControl 设置控制消息回调
func (c *Client) SetOnControl(fn func(map[string]interface{})) {
	c.onControl = fn
}

// SetOnUpgrade 设置升级消息回调
func (c *Client) SetOnUpgrade(fn func(map[string]interface{})) {
	c.onUpgrade = fn
}

// SetOnAuthError 设置鉴权/不存在错误回调（用于重注册）
func (c *Client) SetOnAuthError(fn func() (string, error)) {
	c.onAuthError = fn
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
		Type:      constants.MessageTypeHeartbeat,
		Timestamp: time.Now().UnixMilli(),
		Payload: map[string]interface{}{
			"timestamp": timestamp,
			"system":    system,
		},
	}
	return c.writeMessage(msg)
}

// SendTaskResult 发送任务结果（可靠投递）
func (c *Client) SendTaskResult(result *api.TaskResult) error {
	msg := Message{
		Type:      constants.MessageTypeTaskResult,
		Timestamp: time.Now().UnixMilli(),
		TaskID:    result.TaskID,
		Result:    result,
	}
	return c.SendReliable(&msg)
}

// SendLogs 发送日志（可靠投递）
func (c *Client) SendLogs(taskID string, logs []api.LogEntry) error {
	msg := Message{
		Type:      constants.MessageTypeLog,
		Timestamp: time.Now().UnixMilli(),
		TaskID:    taskID,
		Logs:      logs,
	}
	return c.SendReliable(&msg)
}

// SendReliable 带 ACK 的可靠发送
func (c *Client) SendReliable(msg *Message) error {
	if msg == nil {
		return fmt.Errorf("websocket message is nil")
	}
	c.ensureMessageID(msg)
	c.addPending(*msg)
	if err := c.writeMessage(*msg); err != nil {
		return err
	}
	return nil
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
				c.emitEvent(connEventDisconnected, "read error")
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
	case constants.MessageTypeTask:
		if msg.Task == nil {
			return
		}
		if c.onTask != nil {
			c.onTask(msg.Task)
		}
	case constants.MessageTypeTasksBatch:
		// 批量任务处理
		if len(msg.Tasks) == 0 {
			return
		}
		if c.onTask != nil {
			for _, task := range msg.Tasks {
				if task != nil {
					c.onTask(task)
				}
			}
		}
	case constants.MessageTypeCancelTask:
		if msg.TaskID == "" {
			return
		}
		if c.onCancel != nil {
			c.onCancel(msg.TaskID)
		}
	case constants.MessageTypeCancelTasksBatch:
		// 批量取消任务处理
		if len(msg.TaskIDs) == 0 {
			return
		}
		if c.onCancel != nil {
			for _, taskID := range msg.TaskIDs {
				if taskID != "" {
					c.onCancel(taskID)
				}
			}
		}
	case constants.MessageTypeAck:
		if msg.AckID != "" {
			c.removePending(msg.AckID)
		}
	case constants.MessageTypeControl:
		if msg.Payload != nil && c.onControl != nil {
			c.onControl(msg.Payload)
		}
	case constants.MessageTypeUpgrade:
		if msg.Payload != nil && c.onUpgrade != nil {
			c.onUpgrade(msg.Payload)
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
	// 注意：token 不再放在 URL 中，而是通过 Sec-WebSocket-Protocol 头部传递
	return u.String(), nil
}

func (c *Client) ensureMessageID(msg *Message) {
	if msg == nil {
		return
	}
	if msg.MessageID == "" {
		msg.MessageID = uuid.NewString()
	}
}

func (c *Client) addPending(msg Message) {
	if msg.MessageID == "" {
		return
	}
	now := time.Now()
	c.pendingMu.Lock()
	defer c.pendingMu.Unlock()

	c.gcPendingLocked(now)
	if existing, ok := c.pending[msg.MessageID]; ok {
		existing.msg = msg
		existing.lastSent = now
		existing.nextRetry = now.Add(c.retryInterval)
		return
	}

	if len(c.pending) >= c.pendingMax {
		c.evictOldestLocked(now)
	}

	c.pending[msg.MessageID] = &pendingMessage{
		msg:       msg,
		retries:   0,
		nextRetry: now.Add(c.retryInterval),
		lastSent:  now,
	}
	c.emitEvent(connEventEnqueued, "pending enqueued")
}

func (c *Client) removePending(id string) {
	if id == "" {
		return
	}
	c.pendingMu.Lock()
	defer c.pendingMu.Unlock()
	delete(c.pending, id)
}

func (c *Client) retryPendingLoop() {
	ticker := time.NewTicker(c.retryInterval)
	defer ticker.Stop()
	for {
		select {
		case <-c.ctx.Done():
			return
		case <-ticker.C:
			c.retryPendingOnce()
		}
	}
}

func (c *Client) retryPendingOnce() {
	now := time.Now()
	c.pendingMu.Lock()
	c.gcPendingLocked(now)
	snapshot := make(map[string]*pendingMessage, len(c.pending))
	for k, v := range c.pending {
		snapshot[k] = v
	}
	c.pendingMu.Unlock()

	if !c.IsConnected() {
		return
	}

	for id, pm := range snapshot {
		if pm == nil || pm.msg.MessageID == "" {
			continue
		}
		if now.Before(pm.nextRetry) {
			continue
		}
		if err := c.writeMessage(pm.msg); err != nil {
			logger.GetLogger().WithError(err).WithField("message_id", id).Warn("websocket send retry failed")
			c.updateNextRetry(id, pm, now)
			continue
		}
		c.updateNextRetry(id, pm, now)
	}
}

func (c *Client) updateNextRetry(id string, pm *pendingMessage, now time.Time) {
	delay := c.retryInterval * (1 << pm.retries)
	if delay > c.maxRetryInterval {
		delay = c.maxRetryInterval
	}
	pm.retries++
	pm.lastSent = now
	pm.nextRetry = now.Add(delay)

	if pm.retries >= constants.WSMaxRetryAttempts {
		c.pendingMu.Lock()
		delete(c.pending, id)
		c.pendingMu.Unlock()
		logger.GetLogger().WithFields(map[string]interface{}{
			"message_id": id,
			"retries":    pm.retries,
		}).Warn("drop pending websocket message after max retries without ACK")
		return
	}

	c.pendingMu.Lock()
	if _, ok := c.pending[id]; ok {
		c.pending[id] = pm
	}
	c.pendingMu.Unlock()
}

func (c *Client) gcPendingLocked(now time.Time) {
	if c.pendingTTL <= 0 {
		return
	}
	for id, pm := range c.pending {
		if pm == nil {
			delete(c.pending, id)
			continue
		}
		if now.Sub(pm.lastSent) > c.pendingTTL {
			delete(c.pending, id)
			logger.GetLogger().WithFields(map[string]interface{}{
				"message_id": id,
			}).Warn("drop stale pending websocket message")
		}
	}
}

func (c *Client) evictOldestLocked(now time.Time) {
	var oldestID string
	var oldest time.Time
	for id, pm := range c.pending {
		if pm == nil {
			oldestID = id
			break
		}
		if oldestID == "" || pm.lastSent.Before(oldest) {
			oldestID = id
			oldest = pm.lastSent
		}
	}
	if oldestID != "" {
		delete(c.pending, oldestID)
		logger.GetLogger().WithFields(map[string]interface{}{
			"message_id": oldestID,
		}).Warn("evict pending websocket message to respect capacity")
	}
}

func (c *Client) emitEvent(kind connEvent, reason string) {
	select {
	case c.events <- connEventMessage{kind: kind, reason: reason}:
	default:
	}
}

func (c *Client) triggerReconnect() {
	select {
	case c.reconnectCh <- struct{}{}:
	default:
	}
}

func (c *Client) eventLoop() {
	for {
		select {
		case <-c.ctx.Done():
			return
		case ev := <-c.events:
			switch ev.kind {
			case connEventConnected, connEventEnqueued:
				c.retryPendingOnce()
			case connEventDisconnected:
				c.triggerReconnect()
			default:
			}
		}
	}
}
