package task

import (
	"testing"
	"time"

	"ops-job-agent-server/internal/agent"
	"ops-job-agent-server/internal/config"
	"ops-job-agent-server/pkg/api"

	gorillaWs "github.com/gorilla/websocket"
)

// helper 创建一个在线的 Agent 连接
func newOnlineAgent(t *testing.T, mgr *agent.Manager) (*agent.Connection, string) {
	conn, agentID, err := mgr.Register("agent-test", "tok", nil, nil, 0)
	if err != nil {
		t.Fatalf("register agent: %v", err)
	}
	conn.Conn = &gorillaWs.Conn{} // 非 nil 视为在线
	conn.Status = "active"        // 标记在线
	conn.UpdateHeartbeat()        // 初始化心跳
	return conn, agentID
}

func TestDispatchOnlineSavesPendingAndQueuesTask(t *testing.T) {
	mgr := agent.NewManager(5, time.Second, &config.Config{}, nil)
	conn, agentID := newOnlineAgent(t, mgr)

	store := NewPendingTaskStore(nil) // 内存模式
	dispatcher := NewDispatcher(mgr, store)

	taskSpec := &api.TaskSpec{ID: "task-1", Name: "n1", Type: "script"}

	if err := dispatcher.DispatchTaskToAgent(agentID, taskSpec); err != nil {
		t.Fatalf("dispatch: %v", err)
	}

	select {
	case got := <-conn.TaskQueue:
		if got.ID != "task-1" {
			t.Fatalf("queued task id = %s, want task-1", got.ID)
		}
	default:
		t.Fatalf("task not queued to agent")
	}

	if p, _ := store.GetPending(agentID, "task-1"); p == nil {
		t.Fatalf("pending store missing task")
	}
}

func TestProcessPendingSkipsAckedTasks(t *testing.T) {
	mgr := agent.NewManager(5, time.Second, &config.Config{}, nil)
	conn, agentID := newOnlineAgent(t, mgr)

	store := NewPendingTaskStore(nil)
	dispatcher := NewDispatcher(mgr, store)

	taskSpec := &api.TaskSpec{ID: "task-ack", Name: "n", Type: "script"}
	if err := store.SavePending(agentID, taskSpec, 1); err != nil {
		t.Fatalf("save pending: %v", err)
	}
	store.MarkAcked(agentID, taskSpec.ID)

	if err := dispatcher.ProcessPendingTasksForAgent(agentID); err != nil {
		t.Fatalf("process pending: %v", err)
	}

	select {
	case got := <-conn.TaskQueue:
		t.Fatalf("expected no dispatch for acked task, got %v", got.ID)
	default:
	}
}

func TestProcessPendingResendsUnacked(t *testing.T) {
	mgr := agent.NewManager(5, time.Second, &config.Config{}, nil)
	conn, agentID := newOnlineAgent(t, mgr)

	store := NewPendingTaskStore(nil)
	dispatcher := NewDispatcher(mgr, store)

	taskSpec := &api.TaskSpec{ID: "task-send", Name: "n", Type: "script"}
	if err := store.SavePending(agentID, taskSpec, 1); err != nil {
		t.Fatalf("save pending: %v", err)
	}

	if err := dispatcher.ProcessPendingTasksForAgent(agentID); err != nil {
		t.Fatalf("process pending: %v", err)
	}

	select {
	case got := <-conn.TaskQueue:
		if got.ID != taskSpec.ID {
			t.Fatalf("dispatched task id = %s, want %s", got.ID, taskSpec.ID)
		}
	default:
		t.Fatalf("expected task dispatched from pending")
	}
}

func TestProcessPendingSkipsRunningTask(t *testing.T) {
	mgr := agent.NewManager(5, time.Second, &config.Config{}, nil)
	conn, agentID := newOnlineAgent(t, mgr)

	store := NewPendingTaskStore(nil)
	dispatcher := NewDispatcher(mgr, store)

	taskSpec := &api.TaskSpec{ID: "task-running", Name: "n", Type: "script"}
	conn.AddRunningTask(taskSpec)

	if err := store.SavePending(agentID, taskSpec, 1); err != nil {
		t.Fatalf("save pending: %v", err)
	}

	if err := dispatcher.ProcessPendingTasksForAgent(agentID); err != nil {
		t.Fatalf("process pending: %v", err)
	}

	select {
	case got := <-conn.TaskQueue:
		t.Fatalf("expected no dispatch for running task, got %v", got.ID)
	default:
	}
	if p, _ := store.GetPending(agentID, taskSpec.ID); p != nil {
		t.Fatalf("pending task should be marked acked and removed")
	}
}
