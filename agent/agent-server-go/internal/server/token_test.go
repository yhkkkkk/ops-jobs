package server

import (
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"
	"time"

	"ops-job-agent-server/internal/agent"
	"ops-job-agent-server/internal/config"
	"ops-job-agent-server/internal/task"

	"github.com/google/uuid"
)

func TestExtractTokenFromProtocol(t *testing.T) {
	s := &Server{}
	token := s.extractTokenFromProtocol("agent-token,abc123")
	if token != "abc123" {
		t.Fatalf("expected abc123, got %q", token)
	}

	if token2 := s.extractTokenFromProtocol("legacytoken"); token2 != "" {
		t.Fatalf("bare legacy token must be rejected, got %q", token2)
	}
}

func TestRegisterAcceptsBearerTokenWithoutJSONToken(t *testing.T) {
	cfg := &config.Config{}
	manager := agent.NewManager(5, time.Second, cfg, nil)
	server := newTestServerForE2E(cfg, manager, task.NewPendingTaskStore(nil))

	body := `{"name":"e2e-agent","agent_uid":"` + uuid.NewString() + `"}`
	request := httptest.NewRequest(http.MethodPost, "/api/agents/register", strings.NewReader(body))
	request.Header.Set("Content-Type", "application/json")
	request.Header.Set("Authorization", "Bearer registration-token")
	recorder := httptest.NewRecorder()

	server.engine.ServeHTTP(recorder, request)

	if recorder.Code != http.StatusOK {
		t.Fatalf("register status = %d, want %d; body=%s", recorder.Code, http.StatusOK, recorder.Body.String())
	}
}

func TestNewRejectsUnsignedControlPlaneConfig(t *testing.T) {
	if _, err := New(&config.Config{}); err == nil {
		t.Fatal("server without shared secret and signature requirement must be rejected")
	}
}
