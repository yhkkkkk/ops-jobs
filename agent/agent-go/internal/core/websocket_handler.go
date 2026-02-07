package core

import (
	"context"
	"crypto/md5"
	"crypto/sha256"
	"encoding/hex"
	"fmt"
	"io"
	"net/http"
	"os"
	"os/exec"
	"runtime"
	"strings"
	"time"

	"ops-job-agent/internal/constants"
	"ops-job-agent/internal/logger"
)

var (
	execCommandFn  = exec.Command
	exitFn         = os.Exit
	sleepFn        = time.Sleep
	downloadFileFn = downloadFile
	verifySHA256Fn = verifySHA256
	osExecutableFn = os.Executable
	osRenameFn     = os.Rename
	osChmodFn      = os.Chmod
	osRemoveFn     = os.Remove
)

// handleWebSocketTask 处理从 WebSocket 接收的任务
func (a *Agent) handleWebSocketTask(task *TaskSpec) {
	logger.GetLogger().WithFields(map[string]interface{}{
		"task_id":   task.ID,
		"task_name": task.Name,
	}).Info("received task via websocket")

	// 异步执行任务
	go a.executeTask(task)
}

// handleWebSocketCancel 处理从 WebSocket 接收的取消任务请求
func (a *Agent) handleWebSocketCancel(taskID string) {
	logger.GetLogger().WithField("task_id", taskID).Info("received cancel task via websocket")

	// 取消任务
	if err := a.CancelTask(taskID); err != nil {
		logger.GetLogger().WithError(err).WithField("task_id", taskID).Error("cancel task failed")
	}
}

// handleWebSocketControl 处理从 WebSocket 接收的控制消息
func (a *Agent) handleWebSocketControl(payload map[string]interface{}) {
	action, _ := payload["action"].(string)
	reason, _ := payload["reason"].(string)

	logger.GetLogger().WithFields(map[string]interface{}{
		"action": action,
		"reason": reason,
	}).Warn("received control command")

	switch action {
	case constants.ControlActionRestart:
		go a.performRestart(reason)
	case constants.ControlActionStop:
		go a.performStop(reason)
	case constants.ControlActionStart:
		// start 通常不需要处理，因为 agent 已经在运行
		logger.GetLogger().Info("agent is already running, ignoring start command")
	default:
		logger.GetLogger().WithField("action", action).Warn("unknown control action")
	}
}

// handleWebSocketUpgrade 处理从 WebSocket 接收的升级消息
func (a *Agent) handleWebSocketUpgrade(payload map[string]interface{}) {
	targetVersion, _ := payload["target_version"].(string)
	downloadURL, _ := payload["download_url"].(string)
	md5Hash, _ := payload["md5_hash"].(string)
	sha256Hash, _ := payload["sha256_hash"].(string)

	logger.GetLogger().WithFields(map[string]interface{}{
		"target_version": targetVersion,
		"download_url":   downloadURL,
	}).Warn("received upgrade command")

	go a.performUpgrade(targetVersion, downloadURL, md5Hash, sha256Hash)
}

// performRestart 执行重启操作
func (a *Agent) performRestart(reason string) {
	logger.GetLogger().WithField("reason", reason).Info("restarting agent in 3 seconds")
	sleepFn(3 * time.Second)

	name, args, ok := controlCommandForOS(runtime.GOOS, constants.ControlActionRestart)
	if !ok {
		logger.GetLogger().WithField("os", runtime.GOOS).Warn("unsupported platform for restart, exiting process")
		exitFn(0)
		return
	}
	cmd := execCommandFn(name, args...)
	if err := cmd.Run(); err != nil {
		logger.GetLogger().WithError(err).Warn("restart command failed, exiting process")
		exitFn(0)
	}
}

// performStop 执行停止操作
func (a *Agent) performStop(reason string) {
	logger.GetLogger().WithField("reason", reason).Info("stopping agent in 3 seconds")
	sleepFn(3 * time.Second)

	name, args, ok := controlCommandForOS(runtime.GOOS, constants.ControlActionStop)
	if !ok {
		logger.GetLogger().WithField("os", runtime.GOOS).Warn("unsupported platform for stop, exiting process")
		exitFn(0)
		return
	}
	cmd := execCommandFn(name, args...)
	if err := cmd.Run(); err != nil {
		logger.GetLogger().WithError(err).Warn("stop command failed, exiting process")
		exitFn(0)
	}
}

// performUpgrade 执行升级操作
func (a *Agent) performUpgrade(targetVersion, downloadURL, md5Hash, sha256Hash string) {
	ctx, cancel := context.WithTimeout(context.Background(), 10*time.Minute)
	defer cancel()

	logger.GetLogger().Info("starting agent upgrade")

	if !strings.HasPrefix(downloadURL, "https://") {
		logger.GetLogger().WithField("download_url", downloadURL).Error("upgrade download_url must be https")
		return
	}
	if sha256Hash == "" {
		logger.GetLogger().Error("upgrade requires sha256 checksum")
		return
	}

	// 1. 下载新版本
	tmpFile := "/tmp/agent-new"
	if err := downloadFileFn(ctx, downloadURL, tmpFile); err != nil {
		logger.GetLogger().WithError(err).Error("download agent binary failed")
		return
	}
	defer osRemoveFn(tmpFile)

	logger.GetLogger().Info("agent binary downloaded")

	// 2. 验证校验和
	if err := verifySHA256Fn(tmpFile, sha256Hash); err != nil {
		logger.GetLogger().WithError(err).Error("sha256 verification failed")
		return
	}
	logger.GetLogger().Info("sha256 checksum verified")

	// 3. 获取当前可执行文件路径
	currentExe, err := osExecutableFn()
	if err != nil {
		logger.GetLogger().WithError(err).Error("get executable path failed")
		return
	}

	// 4. 备份当前版本
	backupFile := currentExe + ".bak"
	if err := osRenameFn(currentExe, backupFile); err != nil {
		logger.GetLogger().WithError(err).Error("backup current version failed")
		return
	}
	logger.GetLogger().WithField("backup", backupFile).Info("current version backed up")

	// 5. 替换可执行文件
	if err := osRenameFn(tmpFile, currentExe); err != nil {
		// 恢复备份
		osRenameFn(backupFile, currentExe)
		logger.GetLogger().WithError(err).Error("replace executable failed")
		return
	}

	// 6. 设置执行权限
	if err := osChmodFn(currentExe, 0755); err != nil {
		logger.GetLogger().WithError(err).Warn("failed to set executable permission")
	}

	logger.GetLogger().Info("agent binary replaced, restarting")

	// 7. 重启 agent
	sleepFn(1 * time.Second)
	name, args, ok := controlCommandForOS(runtime.GOOS, constants.ControlActionRestart)
	if !ok {
		logger.GetLogger().WithField("os", runtime.GOOS).Warn("unsupported platform for restart, exiting process")
		exitFn(0)
		return
	}
	cmd := execCommandFn(name, args...)
	if err := cmd.Run(); err != nil {
		logger.GetLogger().WithError(err).Warn("restart command failed, exiting process")
		exitFn(0)
	}
}

// controlCommandForOS 根据平台返回控制指令
func controlCommandForOS(goos, action string) (string, []string, bool) {
	switch goos {
	case "linux":
		switch action {
		case constants.ControlActionRestart:
			return "systemctl", []string{"restart", "agent"}, true
		case constants.ControlActionStop:
			return "systemctl", []string{"stop", "agent"}, true
		}
	case "windows":
		switch action {
		case constants.ControlActionRestart:
			return "powershell", []string{"-Command", "Restart-Service -Name agent"}, true
		case constants.ControlActionStop:
			return "powershell", []string{"-Command", "Stop-Service -Name agent"}, true
		}
	}
	return "", nil, false
}

// downloadFile 从 URL 下载文件到指定路径
func downloadFile(ctx context.Context, url, dest string) error {
	req, err := http.NewRequestWithContext(ctx, "GET", url, nil)
	if err != nil {
		return fmt.Errorf("create request: %w", err)
	}

	client := &http.Client{}
	resp, err := client.Do(req)
	if err != nil {
		return fmt.Errorf("download file: %w", err)
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK {
		return fmt.Errorf("download failed: HTTP %d", resp.StatusCode)
	}

	out, err := os.Create(dest)
	if err != nil {
		return fmt.Errorf("create file: %w", err)
	}
	defer out.Close()

	if _, err := io.Copy(out, resp.Body); err != nil {
		return fmt.Errorf("save file: %w", err)
	}

	return nil
}

// verifySHA256 验证文件的 SHA256 校验和
func verifySHA256(filePath, expectedHash string) error {
	file, err := os.Open(filePath)
	if err != nil {
		return fmt.Errorf("open file: %w", err)
	}
	defer file.Close()

	hash := sha256.New()
	if _, err := io.Copy(hash, file); err != nil {
		return fmt.Errorf("compute hash: %w", err)
	}

	actual := hex.EncodeToString(hash.Sum(nil))
	if actual != expectedHash {
		return fmt.Errorf("sha256 mismatch: expected %s, got %s", expectedHash, actual)
	}

	return nil
}

// verifyMD5 验证文件的 MD5 校验和
func verifyMD5(filePath, expectedHash string) error {
	file, err := os.Open(filePath)
	if err != nil {
		return fmt.Errorf("open file: %w", err)
	}
	defer file.Close()

	hash := md5.New()
	if _, err := io.Copy(hash, file); err != nil {
		return fmt.Errorf("compute hash: %w", err)
	}

	actual := hex.EncodeToString(hash.Sum(nil))
	if actual != expectedHash {
		return fmt.Errorf("md5 mismatch: expected %s, got %s", expectedHash, actual)
	}

	return nil
}
