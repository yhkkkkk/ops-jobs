package server

import "testing"

func TestExtractTokenFromProtocol(t *testing.T) {
	s := &Server{}
	token := s.extractTokenFromProtocol("agent-token,abc123")
	if token != "abc123" {
		t.Fatalf("expected abc123, got %q", token)
	}

	token2 := s.extractTokenFromProtocol("legacytoken")
	if token2 != "legacytoken" {
		t.Fatalf("expected fallback legacy token, got %q", token2)
	}
}
