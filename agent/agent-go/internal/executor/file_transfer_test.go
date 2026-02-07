package executor

import (
	"bytes"
	"context"
	"crypto/sha256"
	"fmt"
	"io"
	"net/http"
	"net/http/httptest"
	"os"
	"path/filepath"
	"testing"
	"time"

	"ops-job-agent/internal/api"
	"ops-job-agent/internal/constants"
	"ops-job-agent/internal/errors"
)

// helper to create temp executor and cleanup
func newTempExecutor(t *testing.T) (*Executor, string) {
	dir := t.TempDir()
	exec := NewExecutor(dir)
	return exec, dir
}

func TestFileTransferRetryThenSuccess(t *testing.T) {
	var count int
	payload := []byte("retry-ok")
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		count++
		if count < 3 {
			w.WriteHeader(http.StatusInternalServerError)
			return
		}
		w.Write(payload)
	}))
	defer srv.Close()

	exec, _ := newTempExecutor(t)
	ftExec := NewFileTransferExecutor(exec)
	out := filepath.Join(t.TempDir(), "retry.bin")
	task := &api.TaskSpec{
		ID: "task-retry",
		FileTransfer: &api.FileTransferSpec{
			DownloadURL: srv.URL,
			RemotePath:  out,
		},
	}

	res, err := ftExec.ExecuteTransfer(context.Background(), task, func(string) {})
	if err != nil {
		t.Fatalf("execute transfer: %v", err)
	}
	if res.Status != constants.StatusSuccess {
		t.Fatalf("expected success after retries, got %s (%s)", res.Status, res.ErrorMsg)
	}
	if count < 3 {
		t.Fatalf("expected retries, count=%d", count)
	}
	data, err := os.ReadFile(out)
	if err != nil {
		t.Fatalf("read output: %v", err)
	}
	if string(data) != string(payload) {
		t.Fatalf("payload mismatch")
	}
}

func TestFileTransferMissingURL(t *testing.T) {
	exec, _ := newTempExecutor(t)
	ftExec := NewFileTransferExecutor(exec)

	task := &api.TaskSpec{
		ID: "task-missing-url",
		FileTransfer: &api.FileTransferSpec{
			DownloadURL: "",
			RemotePath:  filepath.Join(t.TempDir(), "out.txt"),
		},
	}

	res, err := ftExec.ExecuteTransfer(context.Background(), task, func(string) {})
	if err == nil {
		t.Fatalf("expected error for missing download_url")
	}
	if res != nil {
		t.Fatalf("expected nil result on validation error")
	}
}

func TestFileTransferChecksumMismatch(t *testing.T) {
	// start a test server serving known content
	body := []byte("hello-world")
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.Write(body)
	}))
	defer srv.Close()

	exec, _ := newTempExecutor(t)
	ftExec := NewFileTransferExecutor(exec)

	tmpOut := filepath.Join(t.TempDir(), "out.txt")

	task := &api.TaskSpec{
		ID: "task-bad-checksum",
		FileTransfer: &api.FileTransferSpec{
			DownloadURL: srv.URL,
			RemotePath:  tmpOut,
			Checksum:    fmt.Sprintf("%x", sha256.Sum256([]byte("different"))), // mismatch
		},
	}

	res, err := ftExec.ExecuteTransfer(context.Background(), task, func(string) {})
	if err != nil {
		t.Fatalf("execute transfer error: %v", err)
	}
	if res.Status != constants.StatusFailed {
		t.Fatalf("expected failed status, got %s", res.Status)
	}
	if res.ErrorCode != int(errors.ErrCodeFileTransferFailed) {
		t.Fatalf("expected ErrCodeFileTransferFailed, got %d", res.ErrorCode)
	}

	// ensure file was cleaned up (tmp renamed should not exist because checksum failed)
	if _, statErr := os.Stat(tmpOut); statErr == nil {
		t.Fatalf("expected output file not to exist on checksum failure")
	}
}

// Test rateLimitedCopy cancels on context deadline
func TestRateLimitedCopyContextCancel(t *testing.T) {
	ctx, cancel := context.WithTimeout(context.Background(), 5*time.Millisecond)
	defer cancel()

	// reader returns a large chunk to force WaitN with big n
	r := io.NopCloser(&largeChunkReader{})
	dst := &countWriter{}

	_, err := rateLimitedCopy(ctx, dst, r, 1) // bytesPerSec=1 => burst=1, big n should block
	if err == nil {
		t.Fatalf("expected context error due to limiter wait")
	}
}

// TestFileTransferSuccessWithLimit 验证成功下载+限速
func TestFileTransferSuccessWithLimit(t *testing.T) {
	payload := bytes.Repeat([]byte("x"), 1024) // 1KB
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.Write(payload)
	}))
	defer srv.Close()

	exec, _ := newTempExecutor(t)
	ftExec := NewFileTransferExecutor(exec)
	out := filepath.Join(t.TempDir(), "ok.bin")
	task := &api.TaskSpec{
		ID: "task-ok",
		FileTransfer: &api.FileTransferSpec{
			DownloadURL:    srv.URL,
			RemotePath:     out,
			BandwidthLimit: 1, // 1MB/s，足够小以触发限速逻辑
		},
	}
	res, err := ftExec.ExecuteTransfer(context.Background(), task, func(string) {})
	if err != nil {
		t.Fatalf("execute transfer: %v", err)
	}
	if res.Status != constants.StatusSuccess {
		t.Fatalf("expected success, got %s (%s)", res.Status, res.ErrorMsg)
	}
	data, err := os.ReadFile(out)
	if err != nil {
		t.Fatalf("read output: %v", err)
	}
	if len(data) != len(payload) {
		t.Fatalf("output size %d, want %d", len(data), len(payload))
	}
}

// TestFileTransferContextTimeoutErrorCode ensures ctx timeout maps to network error code
func TestFileTransferContextTimeoutErrorCode(t *testing.T) {
	chunk := bytes.Repeat([]byte("x"), 32*1024)
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		flusher, _ := w.(http.Flusher)
		for i := 0; i < 3; i++ {
			_, _ = w.Write(chunk)
			if flusher != nil {
				flusher.Flush()
			}
			time.Sleep(30 * time.Millisecond)
		}
	}))
	defer srv.Close()

	exec, _ := newTempExecutor(t)
	ftExec := NewFileTransferExecutor(exec)
	out := filepath.Join(t.TempDir(), "timeout.bin")
	task := &api.TaskSpec{
		ID: "task-timeout",
		FileTransfer: &api.FileTransferSpec{
			DownloadURL: srv.URL,
			RemotePath:  out,
		},
	}

	ctx, cancel := context.WithTimeout(context.Background(), 20*time.Millisecond)
	defer cancel()

	res, err := ftExec.ExecuteTransfer(ctx, task, func(string) {})
	if err != nil {
		t.Fatalf("execute transfer error: %v", err)
	}
	if res.Status != constants.StatusFailed {
		t.Fatalf("expected failed status, got %s", res.Status)
	}
	if res.ErrorCode != int(errors.ErrCodeNetworkError) {
		t.Fatalf("expected ErrCodeNetworkError, got %d (%s)", res.ErrorCode, res.ErrorMsg)
	}
}

type countWriter struct {
	total int
}

func (w *countWriter) Write(p []byte) (int, error) {
	w.total += len(p)
	return len(p), nil
}

type slowReader struct {
	chunks int
	delay  int64 // nanoseconds
}

func (r *slowReader) Read(p []byte) (int, error) {
	if r.chunks == 0 {
		return 0, io.EOF
	}
	r.chunks--
	time.Sleep(time.Duration(r.delay))
	p[0] = 'a'
	return 1, nil
}

type largeChunkReader struct{}

func (r *largeChunkReader) Read(p []byte) (int, error) {
	for i := range p {
		p[i] = 'b'
	}
	return len(p), nil
}
