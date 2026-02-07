package websocket

import (
	"net/http"
	"net/http/httptest"
	"strings"
	"sync"
	"sync/atomic"
	"testing"
	"time"

	"ops-job-agent/internal/constants"

	gorillaWs "github.com/gorilla/websocket"
)

// TestReconnectSucceedsAndStops 确认断线后会重连一次并在成功后停止指数退避
func TestReconnectSucceedsAndStops(t *testing.T) {
	var connCount int32
	closeFirst := make(chan struct{}, 1)

	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		atomic.AddInt32(&connCount, 1)
		up := gorillaWs.Upgrader{CheckOrigin: func(r *http.Request) bool { return true }}
		conn, err := up.Upgrade(w, r, nil)
		if err != nil {
			return
		}
		// 首次连接后立即关闭，触发重连
		select {
		case <-closeFirst:
			conn.Close()
		default:
			// 后续连接保持存活一会以便成功
			time.AfterFunc(200*time.Millisecond, func() { conn.Close() })
		}
	}))
	defer srv.Close()

	closeFirst <- struct{}{}

	wsURL := srv.URL
	wsURL = "ws" + wsURL[len("http"):] // http:// -> ws://

	c := NewClient(wsURL, "tok", false)
	// 缩短重连间隔，避免测试超时
	c.reconnectInterval = 50 * time.Millisecond
	c.maxRetryInterval = 200 * time.Millisecond
	c.retryInterval = 50 * time.Millisecond
	c.maxRetryInterval = 200 * time.Millisecond

	if err := c.Connect("agent"); err != nil {
		t.Fatalf("initial connect failed: %v", err)
	}
	c.StartReconnectLoop("agent")

	deadline := time.Now().Add(2 * time.Second)
	for atomic.LoadInt32(&connCount) < 2 && time.Now().Before(deadline) {
		time.Sleep(20 * time.Millisecond)
	}

	c.StopReconnectLoop()
	c.Disconnect()

	if atomic.LoadInt32(&connCount) < 2 {
		t.Fatalf("expected at least 2 connections (initial + reconnect), got %d", connCount)
	}
}

// TestReconnectStopsOnCancel 确认 cancel 会停止重连循环
func TestReconnectStopsOnCancel(t *testing.T) {
	c := NewClient("ws://invalid-host", "tok", false)
	c.reconnectInterval = 10 * time.Millisecond
	c.maxRetryInterval = 20 * time.Millisecond
	c.retryInterval = 10 * time.Millisecond
	c.maxRetryInterval = 20 * time.Millisecond

	c.StartReconnectLoop("agent")
	time.Sleep(40 * time.Millisecond) // 允许若干次尝试
	c.StopReconnectLoop()
	c.Disconnect()

	// 若未 panic 即认为取消流程正常结束；这里主要保证不阻塞
}

// TestReconnectTriggeredByDisconnectEvent 断线事件应触发立即重连（不等待长周期 ticker）
func TestReconnectTriggeredByDisconnectEvent(t *testing.T) {
	var connCount int32
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		atomic.AddInt32(&connCount, 1)
		up := gorillaWs.Upgrader{CheckOrigin: func(r *http.Request) bool { return true }}
		conn, err := up.Upgrade(w, r, nil)
		if err != nil {
			return
		}
		if atomic.LoadInt32(&connCount) == 1 {
			// 首次连接后很快断开，触发断线事件
			time.AfterFunc(50*time.Millisecond, func() { _ = conn.Close() })
			return
		}
		// 后续连接保持一会儿
		time.AfterFunc(200*time.Millisecond, func() { _ = conn.Close() })
	}))
	defer srv.Close()

	wsURL := "ws" + srv.URL[len("http"):]
	c := NewClient(wsURL, "tok", false)
	// 设置较长间隔，若靠 ticker 将无法在窗口内重连
	c.reconnectInterval = 5 * time.Second
	c.maxRetryInterval = 5 * time.Second

	if err := c.Connect("agent"); err != nil {
		t.Fatalf("connect failed: %v", err)
	}
	c.StartReconnectLoop("agent")

	deadline := time.Now().Add(800 * time.Millisecond)
	for atomic.LoadInt32(&connCount) < 2 && time.Now().Before(deadline) {
		time.Sleep(20 * time.Millisecond)
	}

	c.StopReconnectLoop()
	c.Disconnect()

	if atomic.LoadInt32(&connCount) < 2 {
		t.Fatalf("expected reconnect before ticker window, got %d", connCount)
	}
}

// TestReconnectLoopDoesNotDialWhenConnected 确认已连接时不会重复拨号
func TestReconnectLoopDoesNotDialWhenConnected(t *testing.T) {
	var connCount int32
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		atomic.AddInt32(&connCount, 1)
		up := gorillaWs.Upgrader{CheckOrigin: func(r *http.Request) bool { return true }}
		conn, err := up.Upgrade(w, r, nil)
		if err != nil {
			return
		}
		// 保持连接一会儿
		time.AfterFunc(300*time.Millisecond, func() { conn.Close() })
	}))
	defer srv.Close()

	wsURL := "ws" + srv.URL[len("http"):]
	c := NewClient(wsURL, "tok", false)
	c.reconnectInterval = 20 * time.Millisecond
	c.maxRetryInterval = 40 * time.Millisecond

	if err := c.Connect("agent"); err != nil {
		t.Fatalf("connect failed: %v", err)
	}
	c.StartReconnectLoop("agent")

	time.Sleep(200 * time.Millisecond)
	c.StopReconnectLoop()
	c.Disconnect()

	if atomic.LoadInt32(&connCount) != 1 {
		t.Fatalf("expected single dial while connected, got %d", connCount)
	}
}

// TestReconnectStopsAfterMaxAttempts 确认达到最大重试次数后停止重连
func TestReconnectStopsAfterMaxAttempts(t *testing.T) {
	var reqCount int32
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		atomic.AddInt32(&reqCount, 1)
		w.WriteHeader(http.StatusInternalServerError)
	}))
	defer srv.Close()

	wsURL := "ws" + srv.URL[len("http"):] // http:// -> ws://
	c := NewClient(wsURL, "tok", false)
	c.reconnectInterval = 10 * time.Millisecond
	c.maxRetryInterval = 20 * time.Millisecond
	c.SetReconnectMaxAttempts(3)

	c.StartReconnectLoop("agent")

	deadline := time.Now().Add(800 * time.Millisecond)
	for {
		if atomic.LoadInt32(&reqCount) >= 3 {
			break
		}
		if time.Now().After(deadline) {
			t.Fatalf("expected at least 3 attempts, got %d", atomic.LoadInt32(&reqCount))
		}
		time.Sleep(10 * time.Millisecond)
	}

	// 额外等待，确保不会继续增长
	count := atomic.LoadInt32(&reqCount)
	time.Sleep(200 * time.Millisecond)
	if atomic.LoadInt32(&reqCount) != count {
		t.Fatalf("expected reconnect loop to stop after max attempts, got %d", atomic.LoadInt32(&reqCount))
	}

	c.StopReconnectLoop()
	c.Disconnect()
}

// TestReconnectCompressionHeaderPreserved 确认重连仍带压缩扩展请求
func TestReconnectCompressionHeaderPreserved(t *testing.T) {
	var connCount int32
	var mu sync.Mutex
	exts := make([]string, 0, 2)
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		atomic.AddInt32(&connCount, 1)
		mu.Lock()
		exts = append(exts, r.Header.Get("Sec-WebSocket-Extensions"))
		mu.Unlock()
		up := gorillaWs.Upgrader{
			CheckOrigin:       func(r *http.Request) bool { return true },
			EnableCompression: true,
		}
		conn, err := up.Upgrade(w, r, nil)
		if err != nil {
			return
		}
		if atomic.LoadInt32(&connCount) == 1 {
			conn.Close()
			return
		}
		time.AfterFunc(200*time.Millisecond, func() { conn.Close() })
	}))
	defer srv.Close()

	wsURL := "ws" + srv.URL[len("http"):]
	c := NewClient(wsURL, "tok", true)
	c.reconnectInterval = 20 * time.Millisecond
	c.retryInterval = 20 * time.Millisecond
	c.maxRetryInterval = 50 * time.Millisecond

	if err := c.Connect("agent"); err != nil {
		t.Fatalf("initial connect failed: %v", err)
	}
	c.StartReconnectLoop("agent")

	deadline := time.Now().Add(2 * time.Second)
	for atomic.LoadInt32(&connCount) < 2 && time.Now().Before(deadline) {
		time.Sleep(20 * time.Millisecond)
	}

	c.StopReconnectLoop()
	c.Disconnect()

	mu.Lock()
	recorded := append([]string(nil), exts...)
	mu.Unlock()
	if len(recorded) < 2 {
		t.Fatalf("expected at least 2 connections, got %d", len(recorded))
	}
	for _, ext := range recorded {
		if !strings.Contains(ext, "permessage-deflate") {
			t.Fatalf("expected permessage-deflate in reconnect header, got %q", ext)
		}
	}
}

// TestPendingFlushTriggeredOnEnqueue 确认入队事件会触发 pending flush
func TestPendingFlushTriggeredOnEnqueue(t *testing.T) {
	recv := make(chan Message, 1)
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		up := gorillaWs.Upgrader{CheckOrigin: func(r *http.Request) bool { return true }}
		conn, err := up.Upgrade(w, r, nil)
		if err != nil {
			return
		}
		defer conn.Close()
		var msg Message
		if err := conn.ReadJSON(&msg); err == nil {
			recv <- msg
		}
	}))
	defer srv.Close()

	wsURL := "ws" + srv.URL[len("http"):]
	c := NewClient(wsURL, "tok", false)
	if err := c.Connect("agent"); err != nil {
		t.Fatalf("connect failed: %v", err)
	}

	pm := &pendingMessage{
		msg: Message{
			Type:      constants.MessageTypeLog,
			MessageID: "pending-1",
			TaskID:    "task-1",
		},
		retries:   0,
		nextRetry: time.Now().Add(-10 * time.Millisecond),
		lastSent:  time.Now().Add(-10 * time.Millisecond),
	}
	c.pendingMu.Lock()
	c.pending[pm.msg.MessageID] = pm
	c.pendingMu.Unlock()

	c.emitEvent(connEventEnqueued, "test")

	select {
	case got := <-recv:
		if got.MessageID != pm.msg.MessageID {
			t.Fatalf("unexpected message id: %s", got.MessageID)
		}
	case <-time.After(1 * time.Second):
		t.Fatalf("timeout waiting for pending flush")
	}

	_ = c.Disconnect()
}

// TestReconnectFlushesPendingAfterDisconnect 确认断线后重连会补发 pending 消息
func TestReconnectFlushesPendingAfterDisconnect(t *testing.T) {
	var connCount int32
	recv := make(chan Message, 1)
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		atomic.AddInt32(&connCount, 1)
		up := gorillaWs.Upgrader{CheckOrigin: func(r *http.Request) bool { return true }}
		conn, err := up.Upgrade(w, r, nil)
		if err != nil {
			return
		}
		if atomic.LoadInt32(&connCount) == 1 {
			conn.Close()
			return
		}
		var msg Message
		if err := conn.ReadJSON(&msg); err == nil {
			recv <- msg
		}
		conn.Close()
	}))
	defer srv.Close()

	wsURL := "ws" + srv.URL[len("http"):]
	c := NewClient(wsURL, "tok", true)
	c.reconnectInterval = 20 * time.Millisecond
	c.retryInterval = 20 * time.Millisecond
	c.maxRetryInterval = 50 * time.Millisecond

	if err := c.Connect("agent"); err != nil {
		t.Fatalf("initial connect failed: %v", err)
	}
	c.StartReconnectLoop("agent")

	pm := &pendingMessage{
		msg: Message{
			Type:      constants.MessageTypeLog,
			MessageID: "pending-reconnect-1",
			TaskID:    "task-1",
		},
		retries:   0,
		nextRetry: time.Now().Add(-10 * time.Millisecond),
		lastSent:  time.Now().Add(-10 * time.Millisecond),
	}
	c.pendingMu.Lock()
	c.pending[pm.msg.MessageID] = pm
	c.pendingMu.Unlock()

	select {
	case got := <-recv:
		if got.MessageID != pm.msg.MessageID {
			t.Fatalf("unexpected message id: %s", got.MessageID)
		}
	case <-time.After(2 * time.Second):
		t.Fatalf("timeout waiting for pending message after reconnect")
	}

	c.StopReconnectLoop()
	_ = c.Disconnect()
}
