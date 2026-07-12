package agent

import (
	"testing"

	"time"

	serrors "ops-job-agent-server/internal/errors"
	"ops-job-agent-server/pkg/api"
)

func TestWriteJSONRejectsClosedConnection(t *testing.T) {
	connection := &Connection{closed: true}
	if err := connection.WriteJSON(api.WebSocketMessage{}); err != serrors.ErrAgentConnectionClosed {
		t.Fatalf("WriteJSON error = %v, want %v", err, serrors.ErrAgentConnectionClosed)
	}
}

func TestConnectionSnapshotCopiesMutableMetadata(t *testing.T) {
	connection := &Connection{
		ID:            "agent-1",
		Name:          "edge-1",
		HostID:        42,
		Status:        "active",
		LastHeartbeat: time.Unix(100, 0),
		Labels:        map[string]string{"zone": "a"},
		System:        &api.SystemInfo{Hostname: "edge-1", IPs: []string{"10.0.0.1"}},
	}

	snapshot := connection.Snapshot()
	snapshot.Labels["zone"] = "b"
	snapshot.System.IPs[0] = "10.0.0.2"

	if connection.Labels["zone"] != "a" {
		t.Fatalf("snapshot mutated connection labels")
	}
	if connection.System.IPs[0] != "10.0.0.1" {
		t.Fatalf("snapshot mutated connection system info")
	}
}
