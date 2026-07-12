package task

import (
	"testing"

	"ops-job-agent-server/pkg/api"
)

// Test HasAcked/MarkAcked behavior when Redis is nil (no panic, MarkAcked still succeeds).
func TestPendingStoreAckWithoutRedis(t *testing.T) {
	store := NewPendingTaskStore(nil)

	acked, err := store.HasAcked("agent-1", "task-1")
	if err != nil {
		t.Fatalf("HasAcked returned error: %v", err)
	}
	if acked {
		t.Fatalf("expected HasAcked to be false when no Redis and no record")
	}

	if err := store.MarkAcked("agent-1", "task-1"); err != nil {
		t.Fatalf("MarkAcked returned error: %v", err)
	}
}

func TestGetPendingReturnsSnapshot(t *testing.T) {
	store := NewPendingTaskStore(nil)
	if err := store.SavePending("agent-1", &api.TaskSpec{ID: "task-1"}, 3); err != nil {
		t.Fatalf("SavePending returned error: %v", err)
	}

	pending, err := store.GetPending("agent-1", "task-1")
	if err != nil {
		t.Fatalf("GetPending returned error: %v", err)
	}
	pending.RetryCount = 99

	fresh, err := store.GetPending("agent-1", "task-1")
	if err != nil {
		t.Fatalf("GetPending returned error: %v", err)
	}
	if fresh.RetryCount != 0 {
		t.Fatalf("GetPending leaked the cached task pointer: got retry count %d, want 0", fresh.RetryCount)
	}
}

func TestPendingStoreIsolatesTaskSpec(t *testing.T) {
	store := NewPendingTaskStore(nil)
	task := &api.TaskSpec{
		ID:      "task-1",
		Command: "echo original",
		Args:    []string{"first"},
		Env:     map[string]string{"MODE": "safe"},
		FileTransfer: &api.FileTransferSpec{
			AuthHeaders: map[string]string{"Authorization": "original"},
		},
	}
	if err := store.SavePending("agent-1", task, 3); err != nil {
		t.Fatalf("SavePending returned error: %v", err)
	}

	task.Command = "echo mutated"
	task.Args[0] = "mutated"
	task.Env["MODE"] = "mutated"
	task.FileTransfer.AuthHeaders["Authorization"] = "mutated"

	pending, err := store.GetPending("agent-1", "task-1")
	if err != nil {
		t.Fatalf("GetPending returned error: %v", err)
	}
	if pending.Task.Command != "echo original" || pending.Task.Args[0] != "first" || pending.Task.Env["MODE"] != "safe" || pending.Task.FileTransfer.AuthHeaders["Authorization"] != "original" {
		t.Fatalf("SavePending leaked the caller task: %+v", pending.Task)
	}

	pending.Task.Command = "echo snapshot-mutated"
	fresh, err := store.GetPending("agent-1", "task-1")
	if err != nil {
		t.Fatalf("GetPending returned error: %v", err)
	}
	if fresh.Task.Command != "echo original" {
		t.Fatalf("GetPending leaked the cached task: %+v", fresh.Task)
	}
}
