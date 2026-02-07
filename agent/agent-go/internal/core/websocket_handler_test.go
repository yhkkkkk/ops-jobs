package core

import (
	"context"
	"testing"

	"ops-job-agent/internal/constants"
)

func TestPerformUpgradeRejectsNonHTTPS(t *testing.T) {
	a := &Agent{}
	called := false

	oldDownload := downloadFileFn
	downloadFileFn = func(ctx context.Context, url, dest string) error {
		called = true
		return nil
	}
	t.Cleanup(func() { downloadFileFn = oldDownload })

	a.performUpgrade("v1", "http://example.com/agent", "", "sha256")
	if called {
		t.Fatalf("expected download not called for non-https url")
	}
}

func TestPerformUpgradeRequiresSHA256(t *testing.T) {
	a := &Agent{}
	called := false

	oldDownload := downloadFileFn
	downloadFileFn = func(ctx context.Context, url, dest string) error {
		called = true
		return nil
	}
	t.Cleanup(func() { downloadFileFn = oldDownload })

	a.performUpgrade("v1", "https://example.com/agent", "", "")
	if called {
		t.Fatalf("expected download not called when sha256 missing")
	}
}

func TestControlCommandForOS(t *testing.T) {
	name, args, ok := controlCommandForOS("linux", constants.ControlActionRestart)
	if !ok || name != "systemctl" {
		t.Fatalf("expected systemctl for linux restart, got %v %v %v", name, args, ok)
	}
	if len(args) != 2 || args[0] != "restart" || args[1] != "agent" {
		t.Fatalf("unexpected args for linux restart: %v", args)
	}

	name, args, ok = controlCommandForOS("windows", constants.ControlActionStop)
	if !ok || name != "powershell" {
		t.Fatalf("expected powershell for windows stop, got %v %v %v", name, args, ok)
	}
	if len(args) < 2 || args[0] != "-Command" {
		t.Fatalf("unexpected args for windows stop: %v", args)
	}

	_, _, ok = controlCommandForOS("plan9", constants.ControlActionRestart)
	if ok {
		t.Fatalf("expected unsupported platform to return ok=false")
	}
}
