package server

import "testing"

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
