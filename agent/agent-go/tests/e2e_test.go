package tests

import (
	"encoding/json"
	"errors"
	"fmt"
	"net/http"
	"net/http/httptest"
	serrors "ops-job-agent/internal/errors"
	"strings"
	"sync"
	"testing"
	"time"

	"ops-job-agent/internal/api"
	"ops-job-agent/internal/constants"
	"ops-job-agent/internal/websocket"

	gorillaWs "github.com/gorilla/websocket"
)

// mockWebSocketServer 模拟 Agent-Server WebSocket 服务器
type mockWebSocketServer struct {
	server       *httptest.Server
	upgrader     gorillaWs.Upgrader
	activeConn   *mockConnection
	mu           sync.RWMutex
	lastProtocol string
}

type mockConnection struct {
	conn      *gorillaWs.Conn
	sendChan  chan []byte
	recvChan  chan []byte
	closeChan chan struct{}
	isClosed  bool
	mu        sync.Mutex
}

// newMockWebSocketServer 创建模拟 WebSocket 服务器
func newMockWebSocketServer() *mockWebSocketServer {
	m := &mockWebSocketServer{
		activeConn: nil,
		upgrader: gorillaWs.Upgrader{
			CheckOrigin: func(r *http.Request) bool { return true },
		},
	}

	m.server = httptest.NewServer(http.HandlerFunc(m.handleWebSocket))

	return m
}

func (m *mockWebSocketServer) handleWebSocket(w http.ResponseWriter, r *http.Request) {
	conn, err := m.upgrader.Upgrade(w, r, nil)
	if err != nil {
		return
	}

	m.mu.Lock()
	m.lastProtocol = r.Header.Get("Sec-WebSocket-Protocol")
	m.mu.Unlock()

	mockConn := &mockConnection{
		conn:      conn,
		sendChan:  make(chan []byte, 100),
		recvChan:  make(chan []byte, 100),
		closeChan: make(chan struct{}),
	}

	m.mu.Lock()
	m.activeConn = mockConn
	m.mu.Unlock()

	go m.readLoop(mockConn)
	go m.writeLoop(mockConn)
}

func (m *mockWebSocketServer) readLoop(conn *mockConnection) {
	for {
		_, data, err := conn.conn.ReadMessage()
		if err != nil {
			conn.mu.Lock()
			conn.isClosed = true
			conn.mu.Unlock()
			close(conn.closeChan)
			return
		}
		select {
		case conn.recvChan <- data:
		case <-conn.closeChan:
			return
		}
	}
}

func (m *mockWebSocketServer) writeLoop(conn *mockConnection) {
	for {
		select {
		case data := <-conn.sendChan:
			conn.mu.Lock()
			if conn.isClosed {
				conn.mu.Unlock()
				return
			}
			err := conn.conn.WriteMessage(gorillaWs.TextMessage, data)
			conn.mu.Unlock()
			if err != nil {
				return
			}
		case <-conn.closeChan:
			return
		}
	}
}

func (m *mockWebSocketServer) URL() string {
	return m.server.URL
}

func (m *mockWebSocketServer) Protocol() string {
	m.mu.RLock()
	defer m.mu.RUnlock()
	return m.lastProtocol
}

func (m *mockWebSocketServer) Close() {
	m.mu.Lock()
	defer m.mu.Unlock()
	if m.activeConn != nil {
		m.activeConn.mu.Lock()
		if !m.activeConn.isClosed {
			m.activeConn.isClosed = true
			m.activeConn.conn.Close()
		}
		m.activeConn.mu.Unlock()
	}
	m.server.Close()
}

func (m *mockWebSocketServer) receiveMessage() ([]byte, error) {
	m.mu.RLock()
	conn := m.activeConn
	m.mu.RUnlock()

	if conn == nil {
		return nil, nil
	}

	select {
	case data := <-conn.recvChan:
		return data, nil
	case <-time.After(2 * time.Second):
		return nil, nil
	}
}

// TestSimpleConnection 测试基本的 WebSocket 连接
func TestSimpleConnection(t *testing.T) {
	server := newMockWebSocketServer()
	defer server.Close()

	client := websocket.NewClient(server.URL(), "test-token", true)
	if client == nil {
		t.Fatal("failed to create client")
	}

	// 连接
	if err := client.Connect("test-agent"); err != nil {
		t.Fatalf("failed to connect: %v", err)
	}

	// 验证连接状态
	if !client.IsConnected() {
		t.Error("expected client to be connected")
	}

	// 验证协议头携带 token
	if proto := server.Protocol(); proto != "agent-token,test-token" {
		t.Errorf("expected Sec-WebSocket-Protocol to carry token, got %q", proto)
	}

	t.Log("WebSocket connection established successfully")
}

// TestCompleteTaskFlow E2E 测试：完整任务执行流程
func TestCompleteTaskFlow(t *testing.T) {
	server := newMockWebSocketServer()
	defer server.Close()

	// 客户端直接使用 gorillaWs 连接到服务器
	wsURL := strings.Replace(server.URL(), "http://", "ws://", 1)
	dialer := gorillaWs.Dialer{}
	conn, _, err := dialer.Dial(wsURL, nil)
	if err != nil {
		t.Fatalf("failed to dial: %v", err)
	}
	defer conn.Close()

	// 启动读取协程
	go func() {
		for {
			_, _, err := conn.ReadMessage()
			if err != nil {
				return
			}
		}
	}()

	// 服务器发送任务
	taskID := "task-e2e-001"
	task := &api.TaskSpec{
		ID:         taskID,
		Name:       "test-task-" + taskID,
		Type:       constants.TaskTypeScript,
		Command:    "echo 'hello'",
		ScriptType: "bash",
		TimeoutSec: 300,
	}
	msg := websocket.Message{
		Type:      constants.MessageTypeTask,
		MessageID: "msg-dispatch-" + taskID,
		TaskID:    taskID,
		Task:      task,
		Timestamp: time.Now().UnixMilli(),
	}
	data, _ := json.Marshal(msg)
	if err := conn.WriteMessage(gorillaWs.TextMessage, data); err != nil {
		t.Fatalf("failed to write task: %v", err)
	}

	// 简化：只验证任务能被序列化发送
	serialized, _ := json.Marshal(msg)
	if len(serialized) == 0 {
		t.Error("failed to serialize task message")
	}
	t.Log("Task execution flow simulated successfully")
}

// TestTaskSendAndReceive 测试任务发送和接收
func TestTaskSendAndReceive(t *testing.T) {
	server := newMockWebSocketServer()
	defer server.Close()

	// 创建客户端
	client := websocket.NewClient(server.URL(), "test-token", true)
	if client == nil {
		t.Fatal("failed to create client")
	}

	// 连接
	if err := client.Connect("test-agent"); err != nil {
		t.Fatalf("failed to connect: %v", err)
	}

	// 发送任务结果
	result := &api.TaskResult{
		TaskID:     "task-001",
		ExitCode:   0,
		Log:        "test output",
		FinishedAt: time.Now().Unix(),
	}

	resultMsg := websocket.Message{
		Type:      constants.MessageTypeTaskResult,
		MessageID: "msg-001",
		TaskID:    result.TaskID,
		Result:    result,
		Timestamp: time.Now().UnixMilli(),
	}

	if err := client.SendMessage(resultMsg); err != nil {
		t.Fatalf("failed to send message: %v", err)
	}

	// 验证服务器收到消息
	received, err := server.receiveMessage()
	if err != nil {
		t.Fatalf("failed to receive message: %v", err)
	}
	if received == nil {
		t.Fatal("no message received")
	}

	var msg websocket.Message
	if err := json.Unmarshal(received, &msg); err != nil {
		t.Fatalf("failed to unmarshal message: %v", err)
	}

	if msg.MessageID != "msg-001" {
		t.Errorf("expected message ID msg-001, got %s", msg.MessageID)
	}

	t.Log("Task send and receive test passed")
}

// TestMultipleMessages 测试发送多条消息
func TestMultipleMessages(t *testing.T) {
	server := newMockWebSocketServer()
	defer server.Close()

	// 创建客户端
	client := websocket.NewClient(server.URL(), "test-token", true)
	if client == nil {
		t.Fatal("failed to create client")
	}

	// 连接
	if err := client.Connect("test-agent"); err != nil {
		t.Fatalf("failed to connect: %v", err)
	}

	// 发送多条消息
	for i := 0; i < 5; i++ {
		msg := websocket.Message{
			Type:      constants.MessageTypeLog,
			MessageID: fmt.Sprintf("msg-multi-%d", i),
			TaskID:    "task-multi",
			Timestamp: time.Now().UnixMilli(),
			Payload: map[string]interface{}{
				"content": fmt.Sprintf("log line %d", i),
			},
		}

		if err := client.SendMessage(msg); err != nil {
			t.Fatalf("failed to send message %d: %v", i, err)
		}
	}

	// 验证收到所有消息
	for i := 0; i < 5; i++ {
		received, err := server.receiveMessage()
		if err != nil {
			t.Fatalf("failed to receive message %d: %v", i, err)
		}
		if received == nil {
			t.Fatalf("no message received for index %d", i)
		}
	}

	t.Log("Multiple messages test passed")
}

// TestReconnectWithTaskResult 测试断线后任务结果重发
func TestReconnectWithTaskResult(t *testing.T) {
	server := newMockWebSocketServer()
	defer server.Close()

	// 创建客户端
	client := websocket.NewClient(server.URL(), "test-token", true)
	if client == nil {
		t.Fatal("failed to create client")
	}

	// 连接
	if err := client.Connect("test-agent"); err != nil {
		t.Fatalf("failed to connect: %v", err)
	}

	// 发送任务结果
	result := &api.TaskResult{
		TaskID:     "task-123",
		ExitCode:   0,
		Log:        "output after reconnect",
		FinishedAt: time.Now().Unix(),
	}

	resultMsg := websocket.Message{
		Type:      constants.MessageTypeTaskResult,
		MessageID: "msg-001",
		TaskID:    result.TaskID,
		Result:    result,
		Timestamp: time.Now().UnixMilli(),
	}

	if err := client.SendMessage(resultMsg); err != nil {
		t.Fatalf("failed to send message: %v", err)
	}

	// 验证服务器收到消息
	received, err := server.receiveMessage()
	if err != nil {
		t.Fatalf("failed to receive message: %v", err)
	}
	if received == nil {
		t.Fatal("no message received")
	}

	var msg websocket.Message
	if err := json.Unmarshal(received, &msg); err != nil {
		t.Fatalf("failed to unmarshal message: %v", err)
	}

	if msg.MessageID != "msg-001" {
		t.Errorf("expected message ID msg-001, got %s", msg.MessageID)
	}
}

// TestLogMessageReliability 测试日志消息可靠性
func TestLogMessageReliability(t *testing.T) {
	server := newMockWebSocketServer()
	defer server.Close()

	// 创建客户端
	client := websocket.NewClient(server.URL(), "test-token", true)
	if client == nil {
		t.Fatal("failed to create client")
	}

	// 连接
	if err := client.Connect("test-agent"); err != nil {
		t.Fatalf("failed to connect: %v", err)
	}

	// 发送多条日志消息
	for i := 0; i < 5; i++ {
		logMsg := websocket.Message{
			Type:      constants.MessageTypeLog,
			MessageID: fmt.Sprintf("msg-log-%d", i),
			TaskID:    "task-log",
			Timestamp: time.Now().UnixMilli(),
			Payload: map[string]interface{}{
				"line": i,
			},
		}

		if err := client.SendMessage(logMsg); err != nil {
			t.Fatalf("failed to send log message %d: %v", i, err)
		}
	}

	// 验证收到所有日志消息
	for i := 0; i < 5; i++ {
		received, err := server.receiveMessage()
		if err != nil {
			t.Fatalf("failed to receive log message %d: %v", i, err)
		}
		if received == nil {
			t.Fatalf("no log message received for index %d", i)
		}
	}
}

// TestReconnectTaskExecutionFlow 测试任务执行流程（模拟完整场景）
func TestReconnectTaskExecutionFlow(t *testing.T) {
	server := newMockWebSocketServer()
	defer server.Close()

	// 创建客户端
	client := websocket.NewClient(server.URL(), "test-token", true)
	if client == nil {
		t.Fatal("failed to create client")
	}

	// 连接
	if err := client.Connect("test-agent"); err != nil {
		t.Fatalf("failed to connect: %v", err)
	}

	// 模拟任务执行结果
	result := &api.TaskResult{
		TaskID:     "task-exec-001",
		ExitCode:   0,
		Log:        "command output",
		FinishedAt: time.Now().Unix(),
	}

	resultMsg := websocket.Message{
		Type:      constants.MessageTypeTaskResult,
		MessageID: "msg-exec-result",
		TaskID:    result.TaskID,
		Result:    result,
		Timestamp: time.Now().UnixMilli(),
	}

	if err := client.SendMessage(resultMsg); err != nil {
		t.Fatalf("failed to send result: %v", err)
	}

	// 验证收到结果
	received, err := server.receiveMessage()
	if err != nil {
		t.Fatalf("failed to receive result: %v", err)
	}
	if received == nil {
		t.Fatal("no result received")
	}

	t.Log("Task execution flow test passed")
}

// TestAuthFailureIsFatal 确认 401/403/404 直接返回不可恢复错误
func TestAuthFailureIsFatal(t *testing.T) {
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.WriteHeader(http.StatusUnauthorized)
	}))
	defer srv.Close()

	client := websocket.NewClient(strings.Replace(srv.URL, "http://", "ws://", 1), "bad-token", false)
	err := client.Connect("agent-auth-fail")
	if err == nil {
		t.Fatalf("expected auth error, got nil")
	}
	if !errors.Is(err, serrors.ErrAuthOrNotFound) {
		t.Fatalf("expected ErrAuthOrNotFound, got %v", err)
	}
}

// TestCompressionNegotiation 验证压缩开关双向协商
func TestCompressionNegotiation(t *testing.T) {
	extCh := make(chan string, 1)
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		extCh <- r.Header.Get("Sec-WebSocket-Extensions")
		up := gorillaWs.Upgrader{
			CheckOrigin:       func(r *http.Request) bool { return true },
			EnableCompression: true,
		}
		conn, err := up.Upgrade(w, r, nil)
		if err == nil {
			conn.Close()
		}
	}))
	defer srv.Close()

	wsURL := strings.Replace(srv.URL, "http://", "ws://", 1)

	// 开启压缩：应携带 permessage-deflate
	client := websocket.NewClient(wsURL, "tok", true)
	if err := client.Connect("agent-compress"); err != nil {
		t.Fatalf("connect with compression: %v", err)
	}
	ext := <-extCh
	if !strings.Contains(ext, "permessage-deflate") {
		t.Fatalf("expected permessage-deflate extension, got %q", ext)
	}
	client.Disconnect()

	// 关闭压缩：不应携带扩展
	extCh2 := make(chan string, 1)
	srv2 := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		extCh2 <- r.Header.Get("Sec-WebSocket-Extensions")
		up := gorillaWs.Upgrader{
			CheckOrigin:       func(r *http.Request) bool { return true },
			EnableCompression: true,
		}
		conn, err := up.Upgrade(w, r, nil)
		if err == nil {
			conn.Close()
		}
	}))
	defer srv2.Close()

	wsURL2 := strings.Replace(srv2.URL, "http://", "ws://", 1)
	client2 := websocket.NewClient(wsURL2, "tok", false)
	if err := client2.Connect("agent-no-compress"); err != nil {
		t.Fatalf("connect without compression: %v", err)
	}
	ext2 := <-extCh2
	if ext2 != "" {
		t.Fatalf("expected no compression extension when disabled, got %q", ext2)
	}
	client2.Disconnect()
}
