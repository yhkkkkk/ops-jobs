//go:build integration

package integration

import (
	"bytes"
	"context"
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"fmt"
	"io"
	"net"
	"net/http"
	"os"
	"os/exec"
	"path/filepath"
	"runtime"
	"strings"
	"testing"
	"time"

	"ops-job-agent-server/internal/auth"
	"ops-job-agent-server/internal/constants"

	"github.com/redis/go-redis/v9"
	"github.com/spf13/cast"
)

var (
	serverBin string
	agentBin  string
	tmpRoot   string
)

func TestMain(m *testing.M) {
	var err error
	tmpRoot, err = os.MkdirTemp("", "ops-job-itest-*")
	if err != nil {
		panic(err)
	}

	binExt := ""
	if runtime.GOOS == "windows" {
		binExt = ".exe"
	}
	serverBin = filepath.Join(tmpRoot, "agent-server-test"+binExt)
	agentBin = filepath.Join(tmpRoot, "agent-test"+binExt)

	serverRoot := filepath.Clean(filepath.Join("..", ".."))
	agentRoot := filepath.Clean(filepath.Join(serverRoot, "..", "agent-go"))

	if err := buildBinary(serverBin, serverRoot, "./cmd/server", []string{"-tags=integration"}); err != nil {
		panic(err)
	}
	if err := buildBinary(agentBin, agentRoot, "./cmd/agent", nil); err != nil {
		panic(err)
	}

	code := m.Run()
	_ = os.RemoveAll(tmpRoot)
	os.Exit(code)
}

func buildBinary(outPath, workDir, pkgPath string, extraArgs []string) error {
	args := []string{"build", "-o", outPath}
	if len(extraArgs) > 0 {
		args = append(args, extraArgs...)
	}
	args = append(args, pkgPath)

	cmd := exec.Command("go", args...)
	cmd.Stdout = os.Stdout
	cmd.Stderr = os.Stderr
	cmd.Dir = workDir
	return cmd.Run()
}

type testEnvOptions struct {
	serverCompression       bool
	agentCompression        bool
	requireSignature        bool
	sharedSecret            string
	serverHeartbeatTimeoutS int
	agentHeartbeatIntervalS int
	redisAddr               string
	enableStatusStream      bool
}

type testEnv struct {
	baseURL      string
	wsURL        string
	agentID      string
	secret       string
	serverCmd    *exec.Cmd
	agentCmd     *exec.Cmd
	serverOut    *bytes.Buffer
	agentOut     *bytes.Buffer
	serverCfgDir string
	agentCfgDir  string
	agentCfgPath string
}

func startServerAndAgent(t *testing.T, opts testEnvOptions) *testEnv {
	t.Helper()

	if opts.sharedSecret == "" && opts.requireSignature {
		opts.sharedSecret = "itest-secret"
	}
	if opts.serverHeartbeatTimeoutS <= 0 {
		opts.serverHeartbeatTimeoutS = 60
	}
	if opts.agentHeartbeatIntervalS <= 0 {
		opts.agentHeartbeatIntervalS = 1
	}
	redisEnabled := opts.redisAddr != ""

	port, err := freePort()
	if err != nil {
		t.Fatalf("free port: %v", err)
	}
	baseURL := fmt.Sprintf("http://127.0.0.1:%d", port)
	wsURL := fmt.Sprintf("ws://127.0.0.1:%d", port)

	serverCfgDir := filepath.Join(tmpRoot, fmt.Sprintf("server-cfg-%d", port))
	agentCfgDir := filepath.Join(tmpRoot, fmt.Sprintf("agent-cfg-%d", port))
	if err := os.MkdirAll(serverCfgDir, 0755); err != nil {
		t.Fatalf("mkdir server cfg: %v", err)
	}
	if err := os.MkdirAll(agentCfgDir, 0755); err != nil {
		t.Fatalf("mkdir agent cfg: %v", err)
	}

	statusStreamKey := "agent_status"
	serverCfg := fmt.Sprintf(`server:
  host: "127.0.0.1"
  port: %d
agent:
  heartbeat_timeout: "%ds"
logging:
  level: "info"
  dir: ""
log_stream:
  enabled: false
result_stream:
  enabled: false
status_stream:
  enabled: %t
  key: "%s"
redis:
  enabled: %t
  addr: "%s"
  password: ""
  db: 0
websocket:
  enable_compression: %t
auth:
  shared_secret: "%s"
  require_signature: %t
`, port, opts.serverHeartbeatTimeoutS, opts.enableStatusStream, statusStreamKey, redisEnabled, opts.redisAddr, opts.serverCompression, opts.sharedSecret, opts.requireSignature)
	if err := os.WriteFile(filepath.Join(serverCfgDir, "config.yaml"), []byte(serverCfg), 0644); err != nil {
		t.Fatalf("write server config: %v", err)
	}

	agentCfg := fmt.Sprintf(`connection:
  agent_server_url: "%s"
  ws_enable_compression: %t
identification:
  agent_name: "itest-agent"
  agent_token: "itest-token"
logging:
  log_dir: ""
task:
  heartbeat_interval: %d
`, wsURL, opts.agentCompression, opts.agentHeartbeatIntervalS)
	agentCfgPath := filepath.Join(agentCfgDir, "config.yaml")
	if err := os.WriteFile(agentCfgPath, []byte(agentCfg), 0644); err != nil {
		t.Fatalf("write agent config: %v", err)
	}

	serverOut := &bytes.Buffer{}
	serverCmd := exec.Command(serverBin, "start")
	serverCmd.Dir = serverCfgDir
	serverCmd.Env = append(os.Environ(), "AGENT_SERVER_INTEGRATION=1")
	serverCmd.Stdout = serverOut
	serverCmd.Stderr = serverOut
	if err := serverCmd.Start(); err != nil {
		t.Fatalf("start server: %v", err)
	}

	if err := waitForHTTP(baseURL+"/api/agents", 10*time.Second, opts.sharedSecret); err != nil {
		stopProcess(serverCmd)
		t.Fatalf("server not ready: %v\n%s", err, serverOut.String())
	}

	resetURL := baseURL + "/_test/reset"
	_, _ = http.Post(resetURL, "application/json", nil)

	if redisEnabled && opts.enableStatusStream {
		rdb := redis.NewClient(&redis.Options{
			Addr: opts.redisAddr,
		})
		ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
		_ = rdb.Del(ctx, statusStreamKey).Err()
		cancel()
		_ = rdb.Close()
	}

	agentOut := &bytes.Buffer{}
	agentCmd := exec.Command(agentBin, "start")
	agentCmd.Dir = agentCfgDir
	agentCmd.Env = append(os.Environ(), "AGENT_CONFIG_FILE="+agentCfgPath)
	agentCmd.Stdout = agentOut
	agentCmd.Stderr = agentOut
	if err := agentCmd.Start(); err != nil {
		stopProcess(serverCmd)
		t.Fatalf("start agent: %v", err)
	}

	agentID, err := waitForAgentID(baseURL+"/api/agents", 15*time.Second, opts.sharedSecret)
	if err != nil {
		stopProcess(agentCmd)
		stopProcess(serverCmd)
		t.Fatalf("agent not registered: %v\nagent log:\n%s", err, agentOut.String())
	}

	return &testEnv{
		baseURL:      baseURL,
		wsURL:        wsURL,
		agentID:      agentID,
		secret:       opts.sharedSecret,
		serverCmd:    serverCmd,
		agentCmd:     agentCmd,
		serverOut:    serverOut,
		agentOut:     agentOut,
		serverCfgDir: serverCfgDir,
		agentCfgDir:  agentCfgDir,
		agentCfgPath: agentCfgPath,
	}
}

func (e *testEnv) stop() {
	stopProcess(e.agentCmd)
	stopProcess(e.serverCmd)
}

func TestAgentServerIntegrationFlow(t *testing.T) {
	env := startServerAndAgent(t, testEnvOptions{
		serverCompression: true,
		agentCompression:  true,
	})
	defer env.stop()

	taskID := "exec1_step1_host1_rand"
	cmd, scriptType := scriptForOS()
	if err := dispatchTask(env.baseURL, env.agentID, taskID, cmd, scriptType, nil, env.secret); err != nil {
		t.Fatalf("dispatch task: %v\nserver log:\n%s\nagent log:\n%s", err, env.serverOut.String(), env.agentOut.String())
	}

	if err := waitForResult(env.baseURL+"/_test/results", taskID, 20*time.Second); err != nil {
		t.Fatalf("result not received: %v\nserver log:\n%s\nagent log:\n%s", err, env.serverOut.String(), env.agentOut.String())
	}
	if err := waitForLog(env.baseURL+"/_test/logs", taskID, 20*time.Second); err != nil {
		t.Fatalf("log not received: %v\nserver log:\n%s\nagent log:\n%s", err, env.serverOut.String(), env.agentOut.String())
	}
}

func TestAgentServerIntegrationRetryMarkedTask(t *testing.T) {
	env := startServerAndAgent(t, testEnvOptions{
		serverCompression: true,
		agentCompression:  true,
	})
	defer env.stop()

	firstID := "exec_retry_step1_host1_rand"
	cmdFail, scriptTypeFail := failureScriptForOS()
	firstExtra := map[string]interface{}{
		"execution_id": "exec-retry-1",
		"step_id":      "step-1",
		"host_id":      1,
		"is_retry":     false,
	}
	if err := dispatchTask(env.baseURL, env.agentID, firstID, cmdFail, scriptTypeFail, firstExtra, env.secret); err != nil {
		t.Fatalf("dispatch initial task: %v\nserver log:\n%s\nagent log:\n%s", err, env.serverOut.String(), env.agentOut.String())
	}
	if err := waitForResultStatus(env.baseURL+"/_test/results", firstID, "failed", 25*time.Second); err != nil {
		t.Fatalf("initial task not failed: %v\nserver log:\n%s\nagent log:\n%s", err, env.serverOut.String(), env.agentOut.String())
	}

	secondID := "exec_retry_step1_host1_rand_retry1"
	cmdOK, scriptTypeOK := scriptForOS()
	secondExtra := map[string]interface{}{
		"execution_id":   "exec-retry-2",
		"step_id":        "step-1",
		"host_id":        1,
		"is_retry":       true,
		"retry_count":    1,
		"parent_task_id": firstID,
	}
	if err := dispatchTask(env.baseURL, env.agentID, secondID, cmdOK, scriptTypeOK, secondExtra, env.secret); err != nil {
		t.Fatalf("dispatch retry task: %v\nserver log:\n%s\nagent log:\n%s", err, env.serverOut.String(), env.agentOut.String())
	}
	if err := waitForResultStatus(env.baseURL+"/_test/results", secondID, "success", 25*time.Second); err != nil {
		t.Fatalf("retry task not success: %v\nserver log:\n%s\nagent log:\n%s", err, env.serverOut.String(), env.agentOut.String())
	}
}

func TestAgentServerIntegrationCancelTask(t *testing.T) {
	env := startServerAndAgent(t, testEnvOptions{
		serverCompression: true,
		agentCompression:  true,
	})
	defer env.stop()

	taskID := "exec_cancel_step1_host1_rand"
	cmd, scriptType := longRunningScriptForOS()
	if err := dispatchTask(env.baseURL, env.agentID, taskID, cmd, scriptType, nil, env.secret); err != nil {
		t.Fatalf("dispatch task: %v\nserver log:\n%s\nagent log:\n%s", err, env.serverOut.String(), env.agentOut.String())
	}

	time.Sleep(1 * time.Second)
	if err := cancelTask(env.baseURL, env.agentID, taskID, env.secret); err != nil {
		t.Fatalf("cancel task: %v\nserver log:\n%s", err, env.serverOut.String())
	}

	if err := waitForResultStatus(env.baseURL+"/_test/results", taskID, constants.StatusCancelled, 20*time.Second); err != nil {
		t.Fatalf("cancel result not received: %v\nserver log:\n%s\nagent log:\n%s", err, env.serverOut.String(), env.agentOut.String())
	}
}

func TestAgentServerIntegrationPendingRecovery(t *testing.T) {
	env := startServerAndAgent(t, testEnvOptions{
		serverCompression: true,
		agentCompression:  true,
	})
	defer env.stop()

	if err := disconnectAgent(env.baseURL, env.agentID, 0); err != nil {
		t.Fatalf("disconnect agent: %v", err)
	}
	if err := waitForAgentStatus(env.baseURL+"/api/agents", env.agentID, constants.StatusInactive, 10*time.Second, env.secret); err != nil {
		t.Fatalf("agent not inactive: %v\nserver log:\n%s", err, env.serverOut.String())
	}

	taskID := "exec_pending_step1_host1_rand"
	cmd, scriptType := scriptForOS()
	if err := dispatchTask(env.baseURL, env.agentID, taskID, cmd, scriptType, nil, env.secret); err != nil {
		t.Fatalf("dispatch task while offline: %v\nserver log:\n%s", err, env.serverOut.String())
	}

	if err := waitForAgentStatus(env.baseURL+"/api/agents", env.agentID, constants.StatusActive, 20*time.Second, env.secret); err != nil {
		t.Fatalf("agent not reconnected: %v\nserver log:\n%s\nagent log:\n%s", err, env.serverOut.String(), env.agentOut.String())
	}

	if err := waitForResult(env.baseURL+"/_test/results", taskID, 25*time.Second); err != nil {
		t.Fatalf("pending task result not received: %v\nserver log:\n%s\nagent log:\n%s", err, env.serverOut.String(), env.agentOut.String())
	}
	if err := waitForLog(env.baseURL+"/_test/logs", taskID, 25*time.Second); err != nil {
		t.Fatalf("pending task log not received: %v\nserver log:\n%s\nagent log:\n%s", err, env.serverOut.String(), env.agentOut.String())
	}
}

func TestAgentServerIntegrationRetryMarkedPending(t *testing.T) {
	env := startServerAndAgent(t, testEnvOptions{
		serverCompression: true,
		agentCompression:  true,
	})
	defer env.stop()

	if err := disconnectAgent(env.baseURL, env.agentID, 0); err != nil {
		t.Fatalf("disconnect agent: %v", err)
	}
	if err := waitForAgentStatus(env.baseURL+"/api/agents", env.agentID, constants.StatusInactive, 10*time.Second, env.secret); err != nil {
		t.Fatalf("agent not inactive: %v\nserver log:\n%s", err, env.serverOut.String())
	}

	taskID := "exec_retry_pending_step1_host1_rand"
	cmd, scriptType := scriptForOS()
	extra := map[string]interface{}{
		"execution_id":   "exec-retry-pending",
		"step_id":        "step-1",
		"host_id":        1,
		"is_retry":       true,
		"retry_count":    1,
		"parent_task_id": "exec_retry_parent",
	}
	if err := dispatchTask(env.baseURL, env.agentID, taskID, cmd, scriptType, extra, env.secret); err != nil {
		t.Fatalf("dispatch retry task while offline: %v\nserver log:\n%s", err, env.serverOut.String())
	}

	if err := waitForAgentStatus(env.baseURL+"/api/agents", env.agentID, constants.StatusActive, 20*time.Second, env.secret); err != nil {
		t.Fatalf("agent not reconnected: %v\nserver log:\n%s\nagent log:\n%s", err, env.serverOut.String(), env.agentOut.String())
	}

	if err := waitForResult(env.baseURL+"/_test/results", taskID, 25*time.Second); err != nil {
		t.Fatalf("retry pending task result not received: %v\nserver log:\n%s\nagent log:\n%s", err, env.serverOut.String(), env.agentOut.String())
	}
	if err := waitForLog(env.baseURL+"/_test/logs", taskID, 25*time.Second); err != nil {
		t.Fatalf("retry pending task log not received: %v\nserver log:\n%s\nagent log:\n%s", err, env.serverOut.String(), env.agentOut.String())
	}
}

func TestAgentServerIntegrationFileTransfer(t *testing.T) {
	env := startServerAndAgent(t, testEnvOptions{
		serverCompression: true,
		agentCompression:  true,
	})
	defer env.stop()

	sourcePath := filepath.Join(tmpRoot, fmt.Sprintf("source-%d.txt", time.Now().UnixNano()))
	content := []byte("integration file transfer payload")
	if err := os.WriteFile(sourcePath, content, 0644); err != nil {
		t.Fatalf("write source file: %v", err)
	}
	defer os.Remove(sourcePath)

	fileServer := http.NewServeMux()
	fileServer.HandleFunc("/artifact", func(w http.ResponseWriter, r *http.Request) {
		f, err := os.Open(sourcePath)
		if err != nil {
			w.WriteHeader(http.StatusNotFound)
			return
		}
		defer f.Close()
		_, _ = io.Copy(w, f)
	})
	ln, err := net.Listen("tcp", "127.0.0.1:0")
	if err != nil {
		t.Fatalf("listen file server: %v", err)
	}
	fileHTTP := &http.Server{Handler: fileServer}
	go fileHTTP.Serve(ln)
	defer fileHTTP.Shutdown(context.Background())

	hash := sha256.Sum256(content)
	checksum := hex.EncodeToString(hash[:])
	downloadURL := fmt.Sprintf("http://%s/artifact", ln.Addr().String())
	targetPath := filepath.Join(env.agentCfgDir, "downloaded.txt")
	defer os.Remove(targetPath)

	extra := map[string]interface{}{
		"file_transfer": map[string]interface{}{
			"download_url":    downloadURL,
			"remote_path":     targetPath,
			"checksum":        checksum,
			"bandwidth_limit": 1,
		},
		"type": "file_transfer",
	}

	taskID := "exec_file_step1_host1_rand"
	cmd, scriptType := scriptForOS()
	if err := dispatchTask(env.baseURL, env.agentID, taskID, cmd, scriptType, extra, env.secret); err != nil {
		t.Fatalf("dispatch file transfer: %v\nserver log:\n%s", err, env.serverOut.String())
	}

	if err := waitForResultStatus(env.baseURL+"/_test/results", taskID, "success", 30*time.Second); err != nil {
		t.Fatalf("file transfer result missing: %v\nserver log:\n%s\nagent log:\n%s", err, env.serverOut.String(), env.agentOut.String())
	}

	got, err := os.ReadFile(targetPath)
	if err != nil {
		t.Fatalf("read target file: %v", err)
	}
	if !bytes.Equal(got, content) {
		t.Fatalf("file content mismatch: got %q", string(got))
	}
}

func TestAgentServerIntegrationSignedControlPlane(t *testing.T) {
	env := startServerAndAgent(t, testEnvOptions{
		serverCompression: true,
		agentCompression:  true,
		requireSignature:  true,
		sharedSecret:      "itest-secret",
	})
	defer env.stop()

	taskID := "exec_signed_step1_host1_rand"
	cmd, scriptType := scriptForOS()
	if err := dispatchTask(env.baseURL, env.agentID, taskID, cmd, scriptType, nil, env.secret); err != nil {
		t.Fatalf("dispatch signed task: %v\nserver log:\n%s\nagent log:\n%s", err, env.serverOut.String(), env.agentOut.String())
	}

	if err := waitForResult(env.baseURL+"/_test/results", taskID, 20*time.Second); err != nil {
		t.Fatalf("signed result not received: %v\nserver log:\n%s\nagent log:\n%s", err, env.serverOut.String(), env.agentOut.String())
	}
}

func TestAgentServerIntegrationCompressionDisabled(t *testing.T) {
	env := startServerAndAgent(t, testEnvOptions{
		serverCompression: false,
		agentCompression:  false,
	})
	defer env.stop()

	taskID := "exec_nocompress_step1_host1_rand"
	cmd, scriptType := scriptForOS()
	if err := dispatchTask(env.baseURL, env.agentID, taskID, cmd, scriptType, nil, env.secret); err != nil {
		t.Fatalf("dispatch task: %v\nserver log:\n%s\nagent log:\n%s", err, env.serverOut.String(), env.agentOut.String())
	}

	if err := waitForResult(env.baseURL+"/_test/results", taskID, 20*time.Second); err != nil {
		t.Fatalf("result not received: %v\nserver log:\n%s\nagent log:\n%s", err, env.serverOut.String(), env.agentOut.String())
	}
}

func TestAgentServerIntegrationOutboxReplay(t *testing.T) {
	env := startServerAndAgent(t, testEnvOptions{
		serverCompression: true,
		agentCompression:  true,
	})
	defer env.stop()

	taskID := "exec_outbox_step1_host1_rand"
	cmd, scriptType := progressScriptForOS()
	extra := map[string]interface{}{
		"timeout_sec": 60,
	}
	if err := dispatchTask(env.baseURL, env.agentID, taskID, cmd, scriptType, extra, env.secret); err != nil {
		t.Fatalf("dispatch task: %v\nserver log:\n%s\nagent log:\n%s", err, env.serverOut.String(), env.agentOut.String())
	}

	time.Sleep(1 * time.Second)
	if err := disconnectAgent(env.baseURL, env.agentID, 6000); err != nil {
		t.Fatalf("disconnect agent: %v", err)
	}
	if err := waitForAgentStatus(env.baseURL+"/api/agents", env.agentID, constants.StatusActive, 20*time.Second, env.secret); err != nil {
		t.Fatalf("agent not reconnected: %v\nserver log:\n%s\nagent log:\n%s", err, env.serverOut.String(), env.agentOut.String())
	}

	if err := waitForResult(env.baseURL+"/_test/results", taskID, 25*time.Second); err != nil {
		t.Fatalf("outbox result missing: %v\nserver log:\n%s\nagent log:\n%s", err, env.serverOut.String(), env.agentOut.String())
	}
	if err := waitForLog(env.baseURL+"/_test/logs", taskID, 25*time.Second); err != nil {
		t.Fatalf("outbox log missing: %v\nserver log:\n%s\nagent log:\n%s", err, env.serverOut.String(), env.agentOut.String())
	}
}

func TestAgentServerIntegrationRetryMarkedOutboxReplay(t *testing.T) {
	env := startServerAndAgent(t, testEnvOptions{
		serverCompression: true,
		agentCompression:  true,
	})
	defer env.stop()

	taskID := "exec_retry_outbox_step1_host1_rand"
	cmd, scriptType := progressScriptForOS()
	extra := map[string]interface{}{
		"timeout_sec": 60,
		"execution_id":   "exec-retry-outbox",
		"step_id":        "step-1",
		"host_id":        1,
		"is_retry":       true,
		"retry_count":    1,
		"parent_task_id": "exec_retry_outbox_parent",
	}
	if err := dispatchTask(env.baseURL, env.agentID, taskID, cmd, scriptType, extra, env.secret); err != nil {
		t.Fatalf("dispatch retry task: %v\nserver log:\n%s\nagent log:\n%s", err, env.serverOut.String(), env.agentOut.String())
	}

	time.Sleep(1 * time.Second)
	if err := disconnectAgent(env.baseURL, env.agentID, 6000); err != nil {
		t.Fatalf("disconnect agent: %v", err)
	}

	if err := waitForAgentStatus(env.baseURL+"/api/agents", env.agentID, constants.StatusActive, 20*time.Second, env.secret); err != nil {
		t.Fatalf("agent not reconnected: %v\nserver log:\n%s\nagent log:\n%s", err, env.serverOut.String(), env.agentOut.String())
	}

	if err := waitForResult(env.baseURL+"/_test/results", taskID, 30*time.Second); err != nil {
		t.Fatalf("retry outbox result missing: %v\nserver log:\n%s\nagent log:\n%s", err, env.serverOut.String(), env.agentOut.String())
	}
	if _, err := waitForLogsWithContent(env.baseURL+"/_test/logs", taskID, []string{"line1", "line5"}, 25*time.Second); err != nil {
		t.Fatalf("retry outbox logs missing: %v\nserver log:\n%s\nagent log:\n%s", err, env.serverOut.String(), env.agentOut.String())
	}
}

func TestAgentServerIntegrationLogResumeAfterDisconnect(t *testing.T) {
	env := startServerAndAgent(t, testEnvOptions{
		serverCompression: true,
		agentCompression:  true,
	})
	defer env.stop()

	taskID := "exec_logresume_step1_host1_rand"
	cmd, scriptType := progressScriptForOS()
	extra := map[string]interface{}{
		"timeout_sec": 60,
	}
	if err := dispatchTask(env.baseURL, env.agentID, taskID, cmd, scriptType, extra, env.secret); err != nil {
		t.Fatalf("dispatch task: %v\nserver log:\n%s\nagent log:\n%s", err, env.serverOut.String(), env.agentOut.String())
	}

	time.Sleep(1 * time.Second)
	if err := disconnectAgent(env.baseURL, env.agentID, 4000); err != nil {
		t.Fatalf("disconnect agent: %v", err)
	}

	if err := waitForAgentStatus(env.baseURL+"/api/agents", env.agentID, constants.StatusActive, 20*time.Second, env.secret); err != nil {
		t.Fatalf("agent not reconnected: %v\nserver log:\n%s\nagent log:\n%s", err, env.serverOut.String(), env.agentOut.String())
	}

	if err := waitForResult(env.baseURL+"/_test/results", taskID, 30*time.Second); err != nil {
		t.Fatalf("result not received: %v\nserver log:\n%s\nagent log:\n%s", err, env.serverOut.String(), env.agentOut.String())
	}

	logs, err := waitForLogsWithContent(env.baseURL+"/_test/logs", taskID, []string{"line1", "line5"}, 20*time.Second)
	if err != nil {
		t.Fatalf("log resume validation failed: %v\nserver log:\n%s\nagent log:\n%s", err, env.serverOut.String(), env.agentOut.String())
	}
	if len(logs) == 0 {
		t.Fatalf("expected logs after reconnect")
	}
}

func TestAgentServerIntegrationRetryMarkedLogResumeDetailed(t *testing.T) {
	env := startServerAndAgent(t, testEnvOptions{
		serverCompression: true,
		agentCompression:  true,
	})
	defer env.stop()

	taskID := "exec_retry_logresume_step1_host1_rand"
	cmd, scriptType := progressScriptForOS()
	extra := map[string]interface{}{
		"timeout_sec": 60,
		"execution_id":   "exec-retry-logresume",
		"step_id":        "step-1",
		"host_id":        1,
		"is_retry":       true,
		"retry_count":    1,
		"parent_task_id": "exec_retry_logresume_parent",
	}
	if err := dispatchTask(env.baseURL, env.agentID, taskID, cmd, scriptType, extra, env.secret); err != nil {
		t.Fatalf("dispatch retry task: %v\nserver log:\n%s\nagent log:\n%s", err, env.serverOut.String(), env.agentOut.String())
	}

	time.Sleep(1 * time.Second)
	if err := disconnectAgent(env.baseURL, env.agentID, 4000); err != nil {
		t.Fatalf("disconnect agent: %v", err)
	}

	if err := waitForAgentStatus(env.baseURL+"/api/agents", env.agentID, constants.StatusActive, 20*time.Second, env.secret); err != nil {
		t.Fatalf("agent not reconnected: %v\nserver log:\n%s\nagent log:\n%s", err, env.serverOut.String(), env.agentOut.String())
	}

	if err := waitForResult(env.baseURL+"/_test/results", taskID, 30*time.Second); err != nil {
		t.Fatalf("retry result not received: %v\nserver log:\n%s\nagent log:\n%s", err, env.serverOut.String(), env.agentOut.String())
	}

	logs, err := waitForLogsWithContent(env.baseURL+"/_test/logs", taskID, []string{"line1", "line5"}, 25*time.Second)
	if err != nil {
		t.Fatalf("retry log resume validation failed: %v\nserver log:\n%s\nagent log:\n%s", err, env.serverOut.String(), env.agentOut.String())
	}
	counts := countLogOccurrences(logs, "line")
	for i := 1; i <= 5; i++ {
		key := fmt.Sprintf("line%d", i)
		if counts[key] != 1 {
			t.Fatalf("unexpected retry log count for %s: %d", key, counts[key])
		}
	}
	tsByLine := extractLogTimestamps(logs, "line")
	for i := 2; i <= 5; i++ {
		prev := fmt.Sprintf("line%d", i-1)
		curr := fmt.Sprintf("line%d", i)
		if tsByLine[curr] <= tsByLine[prev] {
			t.Fatalf("retry timestamp order not preserved: %s=%d %s=%d", prev, tsByLine[prev], curr, tsByLine[curr])
		}
	}
}

func TestAgentServerIntegrationCompressionServerOnly(t *testing.T) {
	env := startServerAndAgent(t, testEnvOptions{
		serverCompression: true,
		agentCompression:  false,
	})
	defer env.stop()

	taskID := "exec_comp_server_only_step1_host1_rand"
	cmd, scriptType := scriptForOS()
	if err := dispatchTask(env.baseURL, env.agentID, taskID, cmd, scriptType, nil, env.secret); err != nil {
		t.Fatalf("dispatch task: %v\nserver log:\n%s\nagent log:\n%s", err, env.serverOut.String(), env.agentOut.String())
	}

	if err := waitForResult(env.baseURL+"/_test/results", taskID, 20*time.Second); err != nil {
		t.Fatalf("result not received: %v\nserver log:\n%s\nagent log:\n%s", err, env.serverOut.String(), env.agentOut.String())
	}
}

func TestAgentServerIntegrationRetryMarkedCompressionServerOnly(t *testing.T) {
	env := startServerAndAgent(t, testEnvOptions{
		serverCompression: true,
		agentCompression:  false,
	})
	defer env.stop()

	taskID := "exec_retry_comp_server_only_step1_host1_rand"
	cmd, scriptType := scriptForOS()
	extra := map[string]interface{}{
		"execution_id":   "exec-retry-comp-server-only",
		"step_id":        "step-1",
		"host_id":        1,
		"is_retry":       true,
		"retry_count":    1,
		"parent_task_id": "exec_retry_comp_server_only_parent",
	}
	if err := dispatchTask(env.baseURL, env.agentID, taskID, cmd, scriptType, extra, env.secret); err != nil {
		t.Fatalf("dispatch retry task: %v\nserver log:\n%s\nagent log:\n%s", err, env.serverOut.String(), env.agentOut.String())
	}

	if err := waitForResult(env.baseURL+"/_test/results", taskID, 20*time.Second); err != nil {
		t.Fatalf("retry result not received: %v\nserver log:\n%s\nagent log:\n%s", err, env.serverOut.String(), env.agentOut.String())
	}
}

func TestAgentServerIntegrationCompressionAgentOnly(t *testing.T) {
	env := startServerAndAgent(t, testEnvOptions{
		serverCompression: false,
		agentCompression:  true,
	})
	defer env.stop()

	taskID := "exec_comp_agent_only_step1_host1_rand"
	cmd, scriptType := scriptForOS()
	if err := dispatchTask(env.baseURL, env.agentID, taskID, cmd, scriptType, nil, env.secret); err != nil {
		t.Fatalf("dispatch task: %v\nserver log:\n%s\nagent log:\n%s", err, env.serverOut.String(), env.agentOut.String())
	}

	if err := waitForResult(env.baseURL+"/_test/results", taskID, 20*time.Second); err != nil {
		t.Fatalf("result not received: %v\nserver log:\n%s\nagent log:\n%s", err, env.serverOut.String(), env.agentOut.String())
	}
}

func TestAgentServerIntegrationRetryMarkedCompressionAgentOnly(t *testing.T) {
	env := startServerAndAgent(t, testEnvOptions{
		serverCompression: false,
		agentCompression:  true,
	})
	defer env.stop()

	taskID := "exec_retry_comp_agent_only_step1_host1_rand"
	cmd, scriptType := scriptForOS()
	extra := map[string]interface{}{
		"execution_id":   "exec-retry-comp-agent-only",
		"step_id":        "step-1",
		"host_id":        1,
		"is_retry":       true,
		"retry_count":    1,
		"parent_task_id": "exec_retry_comp_agent_only_parent",
	}
	if err := dispatchTask(env.baseURL, env.agentID, taskID, cmd, scriptType, extra, env.secret); err != nil {
		t.Fatalf("dispatch retry task: %v\nserver log:\n%s\nagent log:\n%s", err, env.serverOut.String(), env.agentOut.String())
	}

	if err := waitForResult(env.baseURL+"/_test/results", taskID, 20*time.Second); err != nil {
		t.Fatalf("retry result not received: %v\nserver log:\n%s\nagent log:\n%s", err, env.serverOut.String(), env.agentOut.String())
	}
}

func TestAgentServerIntegrationOutboxOrderAndDedup(t *testing.T) {
	env := startServerAndAgent(t, testEnvOptions{
		serverCompression: true,
		agentCompression:  true,
	})
	defer env.stop()

	taskID := "exec_outbox_order_step1_host1_rand"
	cmd, scriptType := progressScriptForOS()
	extra := map[string]interface{}{
		"timeout_sec": 60,
	}
	if err := dispatchTask(env.baseURL, env.agentID, taskID, cmd, scriptType, extra, env.secret); err != nil {
		t.Fatalf("dispatch task: %v\nserver log:\n%s\nagent log:\n%s", err, env.serverOut.String(), env.agentOut.String())
	}

	time.Sleep(1 * time.Second)
	if err := disconnectAgent(env.baseURL, env.agentID, 5000); err != nil {
		t.Fatalf("disconnect agent: %v", err)
	}

	if err := waitForResult(env.baseURL+"/_test/results", taskID, 30*time.Second); err != nil {
		t.Fatalf("result missing: %v\nserver log:\n%s\nagent log:\n%s", err, env.serverOut.String(), env.agentOut.String())
	}

	logs, err := waitForLogsWithContent(env.baseURL+"/_test/logs", taskID, []string{"line1", "line5"}, 25*time.Second)
	if err != nil {
		t.Fatalf("logs missing: %v\nserver log:\n%s\nagent log:\n%s", err, env.serverOut.String(), env.agentOut.String())
	}

	counts := countLogOccurrences(logs, "line")
	for i := 1; i <= 5; i++ {
		key := fmt.Sprintf("line%d", i)
		if counts[key] != 1 {
			t.Fatalf("unexpected log count for %s: %d", key, counts[key])
		}
	}
	tsByLine := extractLogTimestamps(logs, "line")
	for i := 1; i <= 5; i++ {
		key := fmt.Sprintf("line%d", i)
		if _, ok := tsByLine[key]; !ok {
			t.Fatalf("missing timestamp for %s", key)
		}
	}
	for i := 2; i <= 5; i++ {
		prev := fmt.Sprintf("line%d", i-1)
		curr := fmt.Sprintf("line%d", i)
		if tsByLine[curr] <= tsByLine[prev] {
			t.Fatalf("timestamp order not preserved: %s=%d %s=%d", prev, tsByLine[prev], curr, tsByLine[curr])
		}
	}
}

func TestAgentServerIntegrationNoDeliveryWhileBlocked(t *testing.T) {
	env := startServerAndAgent(t, testEnvOptions{
		serverCompression: true,
		agentCompression:  true,
	})
	defer env.stop()

	taskID := "exec_blocked_step1_host1_rand"
	cmd, scriptType := progressScriptForOS()
	extra := map[string]interface{}{
		"timeout_sec": 60,
	}
	if err := dispatchTask(env.baseURL, env.agentID, taskID, cmd, scriptType, extra, env.secret); err != nil {
		t.Fatalf("dispatch task: %v\nserver log:\n%s\nagent log:\n%s", err, env.serverOut.String(), env.agentOut.String())
	}

	time.Sleep(1 * time.Second)
	if err := disconnectAgent(env.baseURL, env.agentID, 5000); err != nil {
		t.Fatalf("disconnect agent: %v", err)
	}

	time.Sleep(1 * time.Second)
	logCount1, _ := countLogsForTask(env.baseURL+"/_test/logs", taskID)
	resultCount1, _ := countResultsForTask(env.baseURL+"/_test/results", taskID)

	time.Sleep(1 * time.Second)
	logCount2, _ := countLogsForTask(env.baseURL+"/_test/logs", taskID)
	resultCount2, _ := countResultsForTask(env.baseURL+"/_test/results", taskID)

	if logCount2 != logCount1 || resultCount2 != resultCount1 {
		t.Fatalf("unexpected delivery while blocked: logs %d->%d results %d->%d", logCount1, logCount2, resultCount1, resultCount2)
	}

	if err := waitForResult(env.baseURL+"/_test/results", taskID, 30*time.Second); err != nil {
		t.Fatalf("result not received: %v\nserver log:\n%s\nagent log:\n%s", err, env.serverOut.String(), env.agentOut.String())
	}
	if err := waitForLog(env.baseURL+"/_test/logs", taskID, 30*time.Second); err != nil {
		t.Fatalf("logs not received: %v\nserver log:\n%s\nagent log:\n%s", err, env.serverOut.String(), env.agentOut.String())
	}
}

func TestAgentServerIntegrationPendingPlusOutbox(t *testing.T) {
	env := startServerAndAgent(t, testEnvOptions{
		serverCompression: true,
		agentCompression:  true,
	})
	defer env.stop()

	runningID := "exec_combo_run_step1_host1_rand"
	cmd, scriptType := progressScriptForOS()
	extra := map[string]interface{}{
		"timeout_sec": 60,
	}
	if err := dispatchTask(env.baseURL, env.agentID, runningID, cmd, scriptType, extra, env.secret); err != nil {
		t.Fatalf("dispatch running task: %v\nserver log:\n%s\nagent log:\n%s", err, env.serverOut.String(), env.agentOut.String())
	}

	time.Sleep(1 * time.Second)
	if err := disconnectAgent(env.baseURL, env.agentID, 5000); err != nil {
		t.Fatalf("disconnect agent: %v", err)
	}

	pendingID1 := "exec_combo_pending1_step1_host1_rand"
	pendingID2 := "exec_combo_pending2_step1_host1_rand"
	shortCmd, shortType := scriptForOS()
	if err := dispatchTask(env.baseURL, env.agentID, pendingID1, shortCmd, shortType, nil, env.secret); err != nil {
		t.Fatalf("dispatch pending1: %v\nserver log:\n%s", err, env.serverOut.String())
	}
	if err := dispatchTask(env.baseURL, env.agentID, pendingID2, shortCmd, shortType, nil, env.secret); err != nil {
		t.Fatalf("dispatch pending2: %v\nserver log:\n%s", err, env.serverOut.String())
	}

	if err := waitForAgentStatus(env.baseURL+"/api/agents", env.agentID, constants.StatusActive, 25*time.Second, env.secret); err != nil {
		t.Fatalf("agent not reconnected: %v\nserver log:\n%s\nagent log:\n%s", err, env.serverOut.String(), env.agentOut.String())
	}

	for _, taskID := range []string{runningID, pendingID1, pendingID2} {
		if err := waitForResult(env.baseURL+"/_test/results", taskID, 30*time.Second); err != nil {
			t.Fatalf("result not received for %s: %v\nserver log:\n%s\nagent log:\n%s", taskID, err, env.serverOut.String(), env.agentOut.String())
		}
	}
}

func TestAgentServerIntegrationHeartbeatTimeoutOffline(t *testing.T) {
	env := startServerAndAgent(t, testEnvOptions{
		serverCompression:       true,
		agentCompression:        true,
		serverHeartbeatTimeoutS: 2,
		agentHeartbeatIntervalS: 1,
	})
	defer env.stop()

	if err := waitForAgentStatus(env.baseURL+"/api/agents", env.agentID, constants.StatusActive, 10*time.Second, env.secret); err != nil {
		t.Fatalf("agent not active: %v\nserver log:\n%s\nagent log:\n%s", err, env.serverOut.String(), env.agentOut.String())
	}

	stopProcess(env.agentCmd)
	env.agentCmd = nil

	if err := waitForAgentStatus(env.baseURL+"/api/agents", env.agentID, constants.StatusInactive, 10*time.Second, env.secret); err != nil {
		t.Fatalf("agent not inactive after heartbeat timeout: %v\nserver log:\n%s", err, env.serverOut.String())
	}
}

func TestAgentServerIntegrationStatusStreamRedis(t *testing.T) {
	redisAddr := os.Getenv("AGENT_SERVER_REDIS_ADDR")
	if redisAddr == "" {
		t.Skip("AGENT_SERVER_REDIS_ADDR not set; skipping status stream redis test")
	}
	redisPassword := os.Getenv("AGENT_SERVER_REDIS_PASSWORD")

	env := startServerAndAgent(t, testEnvOptions{
		serverCompression:  true,
		agentCompression:   true,
		redisAddr:          redisAddr,
		enableStatusStream: true,
	})
	defer env.stop()

	rdb := redis.NewClient(&redis.Options{
		Addr:     redisAddr,
		Password: redisPassword,
		DB:       0,
	})
	defer rdb.Close()

	key := "agent_status"
	deadline := time.Now().Add(10 * time.Second)
	for {
		ctx, cancel := context.WithTimeout(context.Background(), 2*time.Second)
		n, err := rdb.XLen(ctx, key).Result()
		cancel()
		if err == nil && n > 0 {
			return
		}
		if time.Now().After(deadline) {
			t.Fatalf("status stream empty or unreadable (key=%s, err=%v)", key, err)
		}
		time.Sleep(200 * time.Millisecond)
	}
}

func waitForHTTP(url string, timeout time.Duration, secret string) error {
	deadline := time.Now().Add(timeout)
	for {
		resp, err := doRequest(http.MethodGet, url, nil, secret)
		if err == nil {
			resp.Body.Close()
			if resp.StatusCode == http.StatusOK {
				return nil
			}
		}
		if time.Now().After(deadline) {
			return fmt.Errorf("timeout waiting for %s", url)
		}
		time.Sleep(200 * time.Millisecond)
	}
}

func waitForAgentID(url string, timeout time.Duration, secret string) (string, error) {
	deadline := time.Now().Add(timeout)
	for {
		resp, err := doRequest(http.MethodGet, url, nil, secret)
		if err == nil && resp.StatusCode == http.StatusOK {
			var payload struct {
				Agents []struct {
					ID     string `json:"id"`
					Status string `json:"status"`
				} `json:"agents"`
			}
			_ = json.NewDecoder(resp.Body).Decode(&payload)
			resp.Body.Close()
			if len(payload.Agents) > 0 && payload.Agents[0].ID != "" {
				return payload.Agents[0].ID, nil
			}
		} else if resp != nil {
			resp.Body.Close()
		}
		if time.Now().After(deadline) {
			return "", fmt.Errorf("timeout waiting for agent registration")
		}
		time.Sleep(300 * time.Millisecond)
	}
}

func waitForAgentStatus(url, agentID, status string, timeout time.Duration, secret string) error {
	deadline := time.Now().Add(timeout)
	for {
		resp, err := doRequest(http.MethodGet, url, nil, secret)
		if err == nil && resp.StatusCode == http.StatusOK {
			var payload struct {
				Agents []struct {
					ID     string `json:"id"`
					Status string `json:"status"`
				} `json:"agents"`
			}
			_ = json.NewDecoder(resp.Body).Decode(&payload)
			resp.Body.Close()
			for _, agent := range payload.Agents {
				if agent.ID == agentID && agent.Status == status {
					return nil
				}
			}
		} else if resp != nil {
			resp.Body.Close()
		}
		if time.Now().After(deadline) {
			return fmt.Errorf("timeout waiting for agent status %s", status)
		}
		time.Sleep(300 * time.Millisecond)
	}
}

func waitForResult(url, taskID string, timeout time.Duration) error {
	deadline := time.Now().Add(timeout)
	for {
		resp, err := http.Get(url)
		if err == nil && resp.StatusCode == http.StatusOK {
			var payload struct {
				Results []struct {
					TaskID string `json:"task_id"`
				} `json:"results"`
			}
			_ = json.NewDecoder(resp.Body).Decode(&payload)
			resp.Body.Close()
			for _, r := range payload.Results {
				if r.TaskID == taskID {
					return nil
				}
			}
		} else if resp != nil {
			resp.Body.Close()
		}
		if time.Now().After(deadline) {
			return fmt.Errorf("timeout waiting for result")
		}
		time.Sleep(300 * time.Millisecond)
	}
}

func waitForResultStatus(url, taskID, status string, timeout time.Duration) error {
	deadline := time.Now().Add(timeout)
	for {
		resp, err := http.Get(url)
		if err == nil && resp.StatusCode == http.StatusOK {
			var payload struct {
				Results []struct {
					TaskID string `json:"task_id"`
					Status string `json:"status"`
				} `json:"results"`
			}
			_ = json.NewDecoder(resp.Body).Decode(&payload)
			resp.Body.Close()
			for _, r := range payload.Results {
				if r.TaskID == taskID && r.Status == status {
					return nil
				}
			}
		} else if resp != nil {
			resp.Body.Close()
		}
		if time.Now().After(deadline) {
			return fmt.Errorf("timeout waiting for result status %s", status)
		}
		time.Sleep(300 * time.Millisecond)
	}
}

func waitForLog(url, taskID string, timeout time.Duration) error {
	deadline := time.Now().Add(timeout)
	for {
		resp, err := http.Get(url)
		if err == nil && resp.StatusCode == http.StatusOK {
			var payload struct {
				Logs []map[string]interface{} `json:"logs"`
			}
			_ = json.NewDecoder(resp.Body).Decode(&payload)
			resp.Body.Close()
			for _, l := range payload.Logs {
				if v, ok := l["task_id"].(string); ok && v == taskID {
					return nil
				}
			}
		} else if resp != nil {
			resp.Body.Close()
		}
		if time.Now().After(deadline) {
			return fmt.Errorf("timeout waiting for log")
		}
		time.Sleep(300 * time.Millisecond)
	}
}

func waitForLogsWithContent(url, taskID string, contents []string, timeout time.Duration) ([]map[string]interface{}, error) {
	deadline := time.Now().Add(timeout)
	for {
		logs, err := getLogsForTask(url, taskID)
		if err == nil && len(logs) > 0 {
			matched := true
			for _, content := range contents {
				if content == "" {
					continue
				}
				if !logsContainContent(logs, content) {
					matched = false
					break
				}
			}
			if matched {
				return logs, nil
			}
		}
		if time.Now().After(deadline) {
			return nil, fmt.Errorf("timeout waiting for logs content")
		}
		time.Sleep(300 * time.Millisecond)
	}
}

func getLogsForTask(url, taskID string) ([]map[string]interface{}, error) {
	resp, err := http.Get(url)
	if err != nil {
		return nil, err
	}
	defer resp.Body.Close()
	if resp.StatusCode != http.StatusOK {
		return nil, fmt.Errorf("unexpected status %d", resp.StatusCode)
	}
	var payload struct {
		Logs []map[string]interface{} `json:"logs"`
	}
	if err := json.NewDecoder(resp.Body).Decode(&payload); err != nil {
		return nil, err
	}
	out := make([]map[string]interface{}, 0, len(payload.Logs))
	for _, l := range payload.Logs {
		if v, ok := l["task_id"].(string); ok && v == taskID {
			out = append(out, l)
		}
	}
	return out, nil
}

func logsContainContent(logs []map[string]interface{}, want string) bool {
	for _, l := range logs {
		if v, ok := l["content"].(string); ok && strings.Contains(v, want) {
			return true
		}
	}
	return false
}

func countLogsForTask(url, taskID string) (int, error) {
	logs, err := getLogsForTask(url, taskID)
	if err != nil {
		return 0, err
	}
	return len(logs), nil
}

func countResultsForTask(url, taskID string) (int, error) {
	resp, err := http.Get(url)
	if err != nil {
		return 0, err
	}
	defer resp.Body.Close()
	if resp.StatusCode != http.StatusOK {
		return 0, fmt.Errorf("unexpected status %d", resp.StatusCode)
	}
	var payload struct {
		Results []struct {
			TaskID string `json:"task_id"`
		} `json:"results"`
	}
	if err := json.NewDecoder(resp.Body).Decode(&payload); err != nil {
		return 0, err
	}
	count := 0
	for _, r := range payload.Results {
		if r.TaskID == taskID {
			count++
		}
	}
	return count, nil
}

func countLogOccurrences(logs []map[string]interface{}, prefix string) map[string]int {
	counts := map[string]int{}
	for _, l := range logs {
		content, ok := l["content"].(string)
		if !ok {
			continue
		}
		if !strings.HasPrefix(content, prefix) {
			continue
		}
		counts[content]++
	}
	return counts
}

func extractLogTimestamps(logs []map[string]interface{}, prefix string) map[string]int64 {
	result := map[string]int64{}
	for _, l := range logs {
		content, ok := l["content"].(string)
		if !ok || !strings.HasPrefix(content, prefix) {
			continue
		}
		ts, ok := parseTimestamp(l["timestamp"])
		if !ok {
			continue
		}
		if _, exists := result[content]; !exists {
			result[content] = ts
		}
	}
	return result
}

func parseTimestamp(value interface{}) (int64, bool) {
	switch v := value.(type) {
	case int64:
		return v, true
	case int:
		return int64(v), true
	case float64:
		return int64(v), true
	case json.Number:
		n, err := v.Int64()
		if err != nil {
			return 0, false
		}
		return n, true
	default:
		return 0, false
	}
}

func dispatchTask(baseURL, agentID, taskID, cmd, scriptType string, extra map[string]interface{}, secret string) error {
	payload := map[string]interface{}{
		"id":          taskID,
		"name":        "itest-task",
		"type":        "script",
		"command":     cmd,
		"script_type": scriptType,
		"timeout_sec": 30,
	}
	for k, v := range extra {
		payload[k] = v
	}
	body, _ := json.Marshal(payload)
	resp, err := doRequest(http.MethodPost, fmt.Sprintf("%s/api/agents/%s/tasks", baseURL, agentID), body, secret)
	if err != nil {
		return err
	}
	defer resp.Body.Close()
	if resp.StatusCode != http.StatusOK {
		return fmt.Errorf("dispatch status %d", resp.StatusCode)
	}
	return nil
}

func cancelTask(baseURL, agentID, taskID, secret string) error {
	resp, err := doRequest(http.MethodPost, fmt.Sprintf("%s/api/agents/%s/tasks/%s/cancel", baseURL, agentID, taskID), nil, secret)
	if err != nil {
		return err
	}
	defer resp.Body.Close()
	if resp.StatusCode != http.StatusOK {
		return fmt.Errorf("cancel status %d", resp.StatusCode)
	}
	return nil
}

func disconnectAgent(baseURL, agentID string, blockMs int) error {
	url := fmt.Sprintf("%s/_test/agents/%s/disconnect", baseURL, agentID)
	if blockMs > 0 {
		url = fmt.Sprintf("%s?block_ms=%d", url, blockMs)
	}
	resp, err := http.Post(url, "application/json", nil)
	if err != nil {
		return err
	}
	defer resp.Body.Close()
	if resp.StatusCode != http.StatusOK {
		return fmt.Errorf("disconnect status %d", resp.StatusCode)
	}
	return nil
}

func doRequest(method, url string, body []byte, secret string) (*http.Response, error) {
	var reader io.Reader
	if body != nil {
		reader = bytes.NewReader(body)
	}
	req, err := http.NewRequest(method, url, reader)
	if err != nil {
		return nil, err
	}
	if body != nil {
		req.Header.Set("Content-Type", "application/json")
	}
	if secret != "" {
		ts := cast.ToString(time.Now().Unix())
		signBody := body
		if signBody == nil {
			signBody = []byte{}
		}
		sig := auth.ComputeHMAC(secret, method, req.URL.Path, ts, signBody)
		req.Header.Set(constants.HeaderTimestamp, ts)
		req.Header.Set(constants.HeaderSignature, sig)
	}
	return http.DefaultClient.Do(req)
}

func freePort() (int, error) {
	ln, err := net.Listen("tcp", "127.0.0.1:0")
	if err != nil {
		return 0, err
	}
	defer ln.Close()
	return ln.Addr().(*net.TCPAddr).Port, nil
}

func stopProcess(cmd *exec.Cmd) {
	if cmd == nil || cmd.Process == nil {
		return
	}
	_ = cmd.Process.Signal(os.Interrupt)
	ctx, cancel := context.WithTimeout(context.Background(), 2*time.Second)
	defer cancel()
	done := make(chan struct{})
	go func() {
		_ = cmd.Wait()
		close(done)
	}()
	select {
	case <-done:
	case <-ctx.Done():
		_ = cmd.Process.Kill()
	}
}

func scriptForOS() (string, string) {
	if runtime.GOOS == "windows" {
		return `Write-Output "hello"`, "powershell"
	}
	return "echo hello", "bash"
}

func longRunningScriptForOS() (string, string) {
	if runtime.GOOS == "windows" {
		return "Start-Sleep -Seconds 10", "powershell"
	}
	return "sleep 10", "bash"
}

func progressScriptForOS() (string, string) {
	if runtime.GOOS == "windows" {
		return `1..5 | ForEach-Object { Write-Output "line$($_)"; Start-Sleep -Seconds 1 }`, "powershell"
	}
	return "for i in 1 2 3 4 5; do echo line$i; sleep 1; done", "bash"
}

func failureScriptForOS() (string, string) {
	if runtime.GOOS == "windows" {
		return `Write-Output "fail"; exit 1`, "powershell"
	}
	return "echo fail; exit 1", "bash"
}
