package agent

import (
	"testing"
	"time"

	"ops-job-agent-server/internal/config"

	"github.com/google/uuid"
)

func TestRegisterRequiresStableAgentUID(t *testing.T) {
	manager := NewManager(5, time.Second, &config.Config{}, nil)

	if _, _, err := manager.Register("agent", "token", nil, nil, 1, ""); err == nil {
		t.Fatal("registration without agent_uid must fail")
	}
	if _, _, err := manager.Register("agent", "", nil, nil, 1, uuid.NewString()); err == nil {
		t.Fatal("registration without token must fail")
	}
}

func TestRegisterUsesStableAgentUIDAcrossReconnects(t *testing.T) {
	manager := NewManager(5, time.Second, &config.Config{}, nil)
	agentUID := uuid.NewString()

	first, firstID, err := manager.Register("agent", "token", nil, nil, 1, agentUID)
	if err != nil {
		t.Fatalf("first registration: %v", err)
	}
	if firstID != agentUID || first.ID != agentUID {
		t.Fatalf("registration identity = %q, want %q", firstID, agentUID)
	}

	second, secondID, err := manager.Register("agent-renamed", "token", nil, nil, 1, agentUID)
	if err != nil {
		t.Fatalf("reconnect registration: %v", err)
	}
	if secondID != agentUID || second != first {
		t.Fatalf("reconnect must reuse connection for %q", agentUID)
	}

	if _, _, err := manager.Register("agent", "token", nil, nil, 1, uuid.NewString()); err == nil {
		t.Fatal("a token must not be allowed to change agent_uid")
	}
}
