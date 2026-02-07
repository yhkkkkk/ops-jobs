package server

import (
	"bytes"
	"context"
	"encoding/json"
	"fmt"
	"net/http"
	"net/http/httptest"
	"sync"
	"testing"
	"time"

	"ops-job-agent-server/internal/agent"
	"ops-job-agent-server/internal/config"
	"ops-job-agent-server/internal/constants"
	"ops-job-agent-server/internal/task"
	"ops-job-agent-server/pkg/api"

	gorillaWs "github.com/gorilla/websocket"
)

// fake sinks for test injection
type fakeLogStream struct {
	entries []map[string]interface{}
}

func (f *fakeLogStream) PushLogsByExecutionID(ctx context.Context, executionID string, entries []map[string]interface{}) error {
	f.entries = append(f.entries, entries...)
	return nil
}

type fakeResultStream struct {
	results []*api.TaskResult
}

func (f *fakeResultStream) PushResult(ctx context.Context, agentID string, r *api.TaskResult) error {
	f.results = append(f.results, r)
	return nil
}

type fakeStatusStream struct {
	mu      sync.Mutex
	entries []map[string]interface{}
}

func (f *fakeStatusStream) PushStatus(ctx context.Context, fields map[string]interface{}) error {
	f.mu.Lock()
	defer f.mu.Unlock()
	if fields == nil {
		fields = map[string]interface{}{}
	}
	f.entries = append(f.entries, fields)
	return nil
}

// TestTaskDispatchLogResultFlow: dispatch -> log/result -> ACK path using injected sinks.
func TestTaskDispatchLogResultFlow(t *testing.T) {
	cfg := &config.Config{}
	cfg.LogStream.Enabled = true
	cfg.ResultStream.Enabled = true

	agentMgr := agent.NewManager(5, 5*time.Second, cfg, nil)
	pending := task.NewPendingTaskStore(nil)
	s := newTestServerForE2E(cfg, agentMgr, pending)
	s.logStream = &fakeLogStream{}
	s.resultStream = &fakeResultStream{}
	s.statusStream = &fakeStatusStream{}

	// register agent
	_, agentID, err := agentMgr.Register("a1", "tok", nil, nil, 0)
	if err != nil {
		t.Fatalf("register: %v", err)
	}

	// start HTTP server
	ts := newTestHTTPServer(s)
	defer ts.Close()

	// mock agent client
	wsURL := "ws" + ts.URL[len("http"):] + "/ws/agent/" + agentID
	header := http.Header{}
	header.Set(constants.HeaderSecWebSocketProtocol, "agent-token,tok")
	dialer := gorillaWs.Dialer{}
	conn, _, err := dialer.Dial(wsURL, header)
	if err != nil {
		t.Fatalf("dial ws: %v", err)
	}
	defer conn.Close()

	// wait until server side connection established
	waitDeadline := time.Now().Add(2 * time.Second)
	for {
		c, ok := agentMgr.Get(agentID)
		if ok && c != nil && c.Conn != nil {
			break
		}
		if time.Now().After(waitDeadline) {
			t.Fatalf("timeout waiting for server connection")
		}
		time.Sleep(20 * time.Millisecond)
	}

	done := make(chan struct{})
	errCh := make(chan error, 1)
	taskID := "exec1_step1_host1_rand"
	logID := fmt.Sprintf("log-%d", time.Now().UnixNano())
	resID := fmt.Sprintf("res-%d", time.Now().UnixNano())
	go func() {
		defer close(done)
		hb := api.WebSocketMessage{
			Type:      constants.MessageTypeHeartbeat,
			MessageID: "hb1",
		}
		if err := conn.WriteJSON(hb); err != nil {
			errCh <- err
			return
		}

		// 防止永久阻塞
		_ = conn.SetReadDeadline(time.Now().Add(2 * time.Second))
		var recv api.WebSocketMessage
		if err := conn.ReadJSON(&recv); err != nil {
			errCh <- err
			return
		}
		_ = conn.SetReadDeadline(time.Time{})

		logMsg := api.WebSocketMessage{
			Type:      constants.MessageTypeLog,
			MessageID: logID,
			TaskID:    taskID,
			Logs: []api.LogEntry{
				{TaskID: taskID, Content: "hello", Stream: constants.StreamStdout, Timestamp: time.Now().UnixMilli()},
			},
		}
		if err := conn.WriteJSON(logMsg); err != nil {
			errCh <- err
			return
		}

		resMsg := api.WebSocketMessage{
			Type:      constants.MessageTypeTaskResult,
			MessageID: resID,
			TaskID:    taskID,
			Result: &api.TaskResult{
				TaskID: taskID,
				Status: "success",
			},
		}
		if err := conn.WriteJSON(resMsg); err != nil {
			errCh <- err
			return
		}
	}()

	taskSpec := api.TaskSpec{ID: taskID, Type: "script"}
	if err := s.taskDispatcher.DispatchTaskToAgent(agentID, &taskSpec); err != nil {
		t.Fatalf("dispatch: %v", err)
	}

	// 等待日志/结果写入
	deadline := time.Now().Add(2 * time.Second)
	for {
		select {
		case err := <-errCh:
			t.Fatalf("agent write/read error: %v", err)
		default:
		}
		logSink := s.logStream.(*fakeLogStream)
		resultSink := s.resultStream.(*fakeResultStream)
		statusSink := s.statusStream.(*fakeStatusStream)
		if len(logSink.entries) >= 1 && len(resultSink.results) >= 1 {
			if logSink.entries[0]["content"] != "hello" {
				t.Fatalf("logs not captured: %+v", logSink.entries)
			}
			if resultSink.results[0].TaskID != taskSpec.ID || resultSink.results[0].Status != "success" {
				t.Fatalf("result not captured: %+v", resultSink.results)
			}
			statusSink.mu.Lock()
			statusCount := len(statusSink.entries)
			statusSink.mu.Unlock()
			if statusCount == 0 {
				t.Fatalf("status not captured")
			}
			break
		}
		if time.Now().After(deadline) {
			t.Fatalf("timeout waiting for log/result")
		}
		time.Sleep(20 * time.Millisecond)
	}
}

// TestTaskBatchDispatchE2E: batch task push from control plane -> agent receives tasks batch.
func TestTaskBatchDispatchE2E(t *testing.T) {
	cfg := &config.Config{}
	agentMgr := agent.NewManager(5, 5*time.Second, cfg, nil)
	pending := task.NewPendingTaskStore(nil)
	s := newTestServerForE2E(cfg, agentMgr, pending)

	_, agentID, err := agentMgr.Register("batch-agent", "tok", nil, nil, 0)
	if err != nil {
		t.Fatalf("register: %v", err)
	}

	ts := newTestHTTPServer(s)
	defer ts.Close()

	wsURL := "ws" + ts.URL[len("http"):] + "/ws/agent/" + agentID
	header := http.Header{}
	header.Set(constants.HeaderSecWebSocketProtocol, "agent-token,tok")
	conn, _, err := gorillaWs.DefaultDialer.Dial(wsURL, header)
	if err != nil {
		t.Fatalf("dial ws: %v", err)
	}
	defer conn.Close()

	// send a heartbeat to ensure server loop active
	_ = conn.WriteJSON(api.WebSocketMessage{Type: constants.MessageTypeHeartbeat, MessageID: "hb-batch"})

	taskA := api.TaskSpec{ID: "task-batch-1", Type: "script"}
	taskB := api.TaskSpec{ID: "task-batch-2", Type: "script"}
	body, _ := json.Marshal([]api.TaskSpec{taskA, taskB})

	req, err := http.NewRequest(http.MethodPost, ts.URL+"/api/agents/"+agentID+"/tasks/batch", bytes.NewReader(body))
	if err != nil {
		t.Fatalf("new request: %v", err)
	}
	req.Header.Set("Content-Type", "application/json")
	resp, err := http.DefaultClient.Do(req)
	if err != nil {
		t.Fatalf("post batch: %v", err)
	}
	resp.Body.Close()
	if resp.StatusCode != http.StatusOK {
		t.Fatalf("unexpected status: %d", resp.StatusCode)
	}

	_ = conn.SetReadDeadline(time.Now().Add(2 * time.Second))
	var recv api.WebSocketMessage
	if err := conn.ReadJSON(&recv); err != nil {
		t.Fatalf("read ws: %v", err)
	}
	if recv.Type != constants.MessageTypeTasksBatch {
		t.Fatalf("expected tasks_batch, got %s", recv.Type)
	}
	if len(recv.Tasks) != 2 {
		t.Fatalf("expected 2 tasks, got %d", len(recv.Tasks))
	}
}

// TestPendingTaskRestoreE2E: pending store task restored on agent reconnect.
func TestPendingTaskRestoreE2E(t *testing.T) {
	cfg := &config.Config{}
	agentMgr := agent.NewManager(5, 5*time.Second, cfg, nil)
	pending := task.NewPendingTaskStore(nil)
	s := newTestServerForE2E(cfg, agentMgr, pending)

	_, agentID, err := agentMgr.Register("pending-agent", "tok", nil, nil, 0)
	if err != nil {
		t.Fatalf("register: %v", err)
	}

	taskID := "pending-task-1"
	if err := pending.SavePending(agentID, &api.TaskSpec{ID: taskID, Type: "script"}, 2); err != nil {
		t.Fatalf("save pending: %v", err)
	}

	ts := newTestHTTPServer(s)
	defer ts.Close()

	wsURL := "ws" + ts.URL[len("http"):] + "/ws/agent/" + agentID
	header := http.Header{}
	header.Set(constants.HeaderSecWebSocketProtocol, "agent-token,tok")
	conn, _, err := gorillaWs.DefaultDialer.Dial(wsURL, header)
	if err != nil {
		t.Fatalf("dial ws: %v", err)
	}
	defer conn.Close()

	_ = conn.WriteJSON(api.WebSocketMessage{Type: constants.MessageTypeHeartbeat, MessageID: "hb-pending"})

	_ = conn.SetReadDeadline(time.Now().Add(2 * time.Second))
	var recv api.WebSocketMessage
	if err := conn.ReadJSON(&recv); err != nil {
		t.Fatalf("read ws: %v", err)
	}
	if recv.Type != constants.MessageTypeTask {
		t.Fatalf("expected task, got %s", recv.Type)
	}
	if recv.Task == nil || recv.Task.ID != taskID {
		t.Fatalf("unexpected task payload: %+v", recv.Task)
	}

	// pending store should be cleared after dispatch
	deadline := time.Now().Add(2 * time.Second)
	for {
		list, _ := pending.GetAgentPendingTasks(agentID)
		if len(list) == 0 {
			break
		}
		if time.Now().After(deadline) {
			t.Fatalf("pending tasks not cleared")
		}
		time.Sleep(20 * time.Millisecond)
	}
}

// TestDuplicateMessageIDDedupE2E: same message_id should only be applied once.
func TestDuplicateMessageIDDedupE2E(t *testing.T) {
	cfg := &config.Config{}
	cfg.LogStream.Enabled = true
	cfg.ResultStream.Enabled = false

	agentMgr := agent.NewManager(5, 5*time.Second, cfg, nil)
	pending := task.NewPendingTaskStore(nil)
	s := newTestServerForE2E(cfg, agentMgr, pending)
	logSink := &fakeLogStream{}
	s.logStream = logSink

	_, agentID, err := agentMgr.Register("dup-agent", "tok", nil, nil, 0)
	if err != nil {
		t.Fatalf("register: %v", err)
	}

	ts := newTestHTTPServer(s)
	defer ts.Close()

	wsURL := "ws" + ts.URL[len("http"):] + "/ws/agent/" + agentID
	header := http.Header{}
	header.Set(constants.HeaderSecWebSocketProtocol, "agent-token,tok")
	conn, _, err := gorillaWs.DefaultDialer.Dial(wsURL, header)
	if err != nil {
		t.Fatalf("dial ws: %v", err)
	}
	defer conn.Close()

	taskID := "exec1_step1_host1_rand"
	msgID := fmt.Sprintf("dup-%d", time.Now().UnixNano())
	logMsg := api.WebSocketMessage{
		Type:      constants.MessageTypeLog,
		MessageID: msgID,
		TaskID:    taskID,
		Logs: []api.LogEntry{
			{TaskID: taskID, Content: "dup", Stream: constants.StreamStdout, Timestamp: time.Now().UnixMilli()},
		},
	}
	if err := conn.WriteJSON(logMsg); err != nil {
		t.Fatalf("write log: %v", err)
	}
	if err := conn.WriteJSON(logMsg); err != nil {
		t.Fatalf("write log dup: %v", err)
	}

	deadline := time.Now().Add(2 * time.Second)
	for {
		if len(logSink.entries) >= 1 {
			break
		}
		if time.Now().After(deadline) {
			t.Fatalf("timeout waiting for log entries")
		}
		time.Sleep(20 * time.Millisecond)
	}
	time.Sleep(100 * time.Millisecond)
	if len(logSink.entries) != 1 {
		t.Fatalf("expected 1 log entry after dedup, got %d", len(logSink.entries))
	}
}

// TestCancelTaskOnlineE2E: cancel request should send websocket cancel message.
func TestCancelTaskOnlineE2E(t *testing.T) {
	cfg := &config.Config{}
	agentMgr := agent.NewManager(5, 5*time.Second, cfg, nil)
	pending := task.NewPendingTaskStore(nil)
	s := newTestServerForE2E(cfg, agentMgr, pending)

	_, agentID, err := agentMgr.Register("cancel-agent", "tok", nil, nil, 0)
	if err != nil {
		t.Fatalf("register: %v", err)
	}

	ts := newTestHTTPServer(s)
	defer ts.Close()

	wsURL := "ws" + ts.URL[len("http"):] + "/ws/agent/" + agentID
	header := http.Header{}
	header.Set(constants.HeaderSecWebSocketProtocol, "agent-token,tok")
	conn, _, err := gorillaWs.DefaultDialer.Dial(wsURL, header)
	if err != nil {
		t.Fatalf("dial ws: %v", err)
	}
	defer conn.Close()

	// send a heartbeat to ensure handler loop active
	_ = conn.WriteJSON(api.WebSocketMessage{Type: constants.MessageTypeHeartbeat, MessageID: "hb-cancel"})

	taskID := "task-cancel-1"
	req, err := http.NewRequest(http.MethodPost, ts.URL+"/api/agents/"+agentID+"/tasks/"+taskID+"/cancel", nil)
	if err != nil {
		t.Fatalf("new request: %v", err)
	}
	resp, err := http.DefaultClient.Do(req)
	if err != nil {
		t.Fatalf("post cancel: %v", err)
	}
	resp.Body.Close()
	if resp.StatusCode != http.StatusOK {
		t.Fatalf("unexpected status: %d", resp.StatusCode)
	}

	_ = conn.SetReadDeadline(time.Now().Add(2 * time.Second))
	var msg api.WebSocketMessage
	if err := conn.ReadJSON(&msg); err != nil {
		t.Fatalf("read ws: %v", err)
	}
	if msg.Type != constants.MessageTypeCancelTask {
		t.Fatalf("expected cancel task message, got %s", msg.Type)
	}
	if msg.TaskID != taskID {
		t.Fatalf("expected task id %s, got %s", taskID, msg.TaskID)
	}
}

// TestCancelTaskOfflinePendingE2E: cancel should remove pending task when agent offline.
func TestCancelTaskOfflinePendingE2E(t *testing.T) {
	cfg := &config.Config{}
	agentMgr := agent.NewManager(5, 5*time.Second, cfg, nil)
	pending := task.NewPendingTaskStore(nil)
	s := newTestServerForE2E(cfg, agentMgr, pending)

	_, agentID, err := agentMgr.Register("pending-cancel-agent", "tok", nil, nil, 0)
	if err != nil {
		t.Fatalf("register: %v", err)
	}

	taskID := "pending-cancel-1"
	if err := pending.SavePending(agentID, &api.TaskSpec{ID: taskID, Type: "script"}, 1); err != nil {
		t.Fatalf("save pending: %v", err)
	}

	ts := newTestHTTPServer(s)
	defer ts.Close()

	req, err := http.NewRequest(http.MethodPost, ts.URL+"/api/agents/"+agentID+"/tasks/"+taskID+"/cancel", nil)
	if err != nil {
		t.Fatalf("new request: %v", err)
	}
	resp, err := http.DefaultClient.Do(req)
	if err != nil {
		t.Fatalf("post cancel: %v", err)
	}
	resp.Body.Close()
	if resp.StatusCode != http.StatusOK {
		t.Fatalf("unexpected status: %d", resp.StatusCode)
	}

	if p, _ := pending.GetPending(agentID, taskID); p != nil {
		t.Fatalf("pending task should be deleted after cancel")
	}
}

// TestHandleTaskQueueIncrementsRetryOnSendFailure: send failure should increment retry count.
func TestHandleTaskQueueIncrementsRetryOnSendFailure(t *testing.T) {
	cfg := &config.Config{}
	agentMgr := agent.NewManager(5, 5*time.Second, cfg, nil)
	pending := task.NewPendingTaskStore(nil)
	s := newTestServerForE2E(cfg, agentMgr, pending)

	wsSrv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		up := gorillaWs.Upgrader{CheckOrigin: func(r *http.Request) bool { return true }}
		c, err := up.Upgrade(w, r, nil)
		if err != nil {
			return
		}
		_ = c.Close()
	}))
	defer wsSrv.Close()

	wsURL := "ws" + wsSrv.URL[len("http"):]
	wsConn, _, err := gorillaWs.DefaultDialer.Dial(wsURL, nil)
	if err != nil {
		t.Fatalf("dial ws: %v", err)
	}
	_ = wsConn.Close()

	conn := &agent.Connection{
		ID:        "agent-retry",
		Conn:      wsConn,
		Status:    constants.StatusActive,
		TaskQueue: make(chan *api.TaskSpec, 1),
		LogBuffer: make(chan *api.LogEntry, 1),
	}

	taskSpec := &api.TaskSpec{ID: "task-retry-1", Type: "script"}
	if err := pending.SavePending(conn.ID, taskSpec, 2); err != nil {
		t.Fatalf("save pending: %v", err)
	}

	go s.handleTaskQueue(conn)
	conn.TaskQueue <- taskSpec
	close(conn.TaskQueue)

	deadline := time.Now().Add(1 * time.Second)
	for {
		p, _ := pending.GetPending(conn.ID, taskSpec.ID)
		if p != nil && p.RetryCount >= 1 {
			break
		}
		if time.Now().After(deadline) {
			t.Fatalf("expected retry count increment")
		}
		time.Sleep(10 * time.Millisecond)
	}
}
