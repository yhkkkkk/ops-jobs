package config

import "testing"

func TestValidateAgentServerURLRejectsRemotePlaintextWebSocket(t *testing.T) {
	if err := validateAgentServerURL("ws://agent-server.example.com/ws"); err == nil {
		t.Fatal("expected remote ws URL to be rejected")
	}
}

func TestValidateAgentServerURLAllowsLoopbackPlaintextWebSocket(t *testing.T) {
	if err := validateAgentServerURL("ws://127.0.0.1:8080/ws"); err != nil {
		t.Fatalf("expected loopback ws URL to be allowed: %v", err)
	}
}

func TestValidateAgentServerURLAllowsSecureWebSocket(t *testing.T) {
	if err := validateAgentServerURL("wss://agent-server.example.com/ws"); err != nil {
		t.Fatalf("expected wss URL to be allowed: %v", err)
	}
}
