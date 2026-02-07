package task

import (
	"testing"
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
