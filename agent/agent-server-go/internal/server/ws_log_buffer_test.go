package server

import (
	"reflect"
	"testing"

	"ops-job-agent-server/internal/agent"
	"ops-job-agent-server/internal/config"
	"ops-job-agent-server/pkg/api"
)

func TestWriteToLogBufferPreservesEachEntry(t *testing.T) {
	s := &Server{cfg: &config.Config{}}
	conn := &agent.Connection{
		ID:        "agent-1",
		LogBuffer: make(chan *api.LogEntry, 4),
	}

	s.writeToLogBuffer(conn, []api.LogEntry{
		{TaskID: "task-1", Content: "line1"},
		{TaskID: "task-1", Content: "line2"},
	})

	close(conn.LogBuffer)

	var got []string
	for entry := range conn.LogBuffer {
		if entry == nil {
			continue
		}
		got = append(got, entry.Content)
	}

	want := []string{"line1", "line2"}
	if !reflect.DeepEqual(got, want) {
		t.Fatalf("unexpected buffered logs, got=%v want=%v", got, want)
	}
}
