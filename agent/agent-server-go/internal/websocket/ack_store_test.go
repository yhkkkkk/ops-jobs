package websocket

import (
	"os"
	"path/filepath"
	"testing"
	"time"
)

// Test AckStore fallback (memory + file) when Redis is nil.
func TestAckStoreFallbackMemoryAndFile(t *testing.T) {
	// isolate temp file
	os.Setenv("TMPDIR", t.TempDir())

	store := NewAckStore(nil, "test-agentserver")

	// first seen should return false (not processed)
	if store.Seen("msg-1") {
		t.Fatalf("expected first Seen to be false")
	}
	// second time within TTL should be true
	if !store.Seen("msg-1") {
		t.Fatalf("expected Seen to be true on second call within TTL")
	}

	// file should exist
	path := filepath.Join(os.TempDir(), "ack_store_test-agentserver.log")
	if _, err := os.Stat(path); err != nil {
		t.Fatalf("expected fallback file to exist: %v", err)
	}

	// expire by adjusting ttl small and waiting
	store.ttl = time.Second
	time.Sleep(1100 * time.Millisecond)
	if store.Seen("msg-1") {
		t.Fatalf("expected Seen to be false after TTL expiration")
	}
}
