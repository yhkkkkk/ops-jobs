package websocket

import (
	"fmt"
	"testing"
	"time"
)

// Test FileOutbox bounded queue and Stats with writer enabled.
func TestFileOutboxBoundedWriter(t *testing.T) {
	dir := t.TempDir()
	outbox := NewFileOutbox("agent-test", dir, 50)

	// enqueue more than maxSize to trigger drop logic
	for i := 0; i < 200; i++ {
		msg := Message{
			MessageID: fmt.Sprintf("msg-%d", i),
			Type:      "log",
			Timestamp: time.Now().UnixMilli(),
		}
		outbox.Enqueue(msg)
	}

	queueLen, dropped := outbox.Stats()
	if queueLen > 50 {
		t.Fatalf("expected queue length <= maxSize, got %d", queueLen)
	}
	if dropped == 0 {
		t.Fatalf("expected some messages dropped when over capacity")
	}

	outbox.Close()
}
