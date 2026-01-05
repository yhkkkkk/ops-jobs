package executor

import (
	"context"
	"fmt"
	"os"
	"os/exec"
	"path/filepath"
	"runtime"
	"strings"
	"time"

	"ops-job-agent/internal/api"
	"ops-job-agent/internal/constants"
)

// ScriptExecutor 专门处理脚本执行（支持 shell/python/powershell）
type ScriptExecutor struct {
	executor *Executor
	tempDir  string
}

// NewScriptExecutor 创建脚本执行器
func NewScriptExecutor(executor *Executor, tempDir string) *ScriptExecutor {
	if tempDir == "" {
		tempDir = filepath.Join(os.TempDir(), "ops-job-agent", "scripts")
	}
	os.MkdirAll(tempDir, 0755)
	return &ScriptExecutor{
		executor: executor,
		tempDir:  tempDir,
	}
}

// ExecuteScript 执行脚本
func (s *ScriptExecutor) ExecuteScript(ctx context.Context, task *api.TaskSpec, logCallback func(string)) (*api.TaskResult, error) {
	// 如果 Command 是脚本内容，需要先写入文件
	if task.Command != "" && !isExecutableCommand(task.Command) {
		return s.executeScriptContent(ctx, task, logCallback)
	}

	// 直接执行命令
	return s.executor.ExecuteTask(ctx, task, logCallback)
}

// executeScriptContent 执行脚本内容
func (s *ScriptExecutor) executeScriptContent(ctx context.Context, task *api.TaskSpec, logCallback func(string)) (*api.TaskResult, error) {
	// 检测脚本类型
	scriptType := detectScriptType(task.Command)

	// 创建临时脚本文件
	scriptFile, err := s.createScriptFile(task.ID, scriptType, task.Command)
	if err != nil {
		return nil, fmt.Errorf("create script file failed: %w", err)
	}
	defer os.Remove(scriptFile)

	// 设置执行权限（Unix）
	if runtime.GOOS != constants.OSWindows {
		os.Chmod(scriptFile, 0755)
	}

	// 构建执行命令
	var cmd *exec.Cmd
	switch scriptType {
	case constants.ScriptTypePython:
		cmd = exec.CommandContext(ctx, "python3", scriptFile)
		if cmd.Path == "" {
			// 尝试 python
			cmd = exec.CommandContext(ctx, "python", scriptFile)
		}
	case constants.ScriptTypePowerShell:
		if runtime.GOOS == constants.OSWindows {
			cmd = exec.CommandContext(ctx, "powershell", "-ExecutionPolicy", "Bypass", "-File", scriptFile)
		} else {
			// Linux/Mac 上尝试 pwsh
			cmd = exec.CommandContext(ctx, "pwsh", "-File", scriptFile)
		}
	case constants.ScriptTypeShell, constants.ScriptTypeBash:
		if runtime.GOOS == constants.OSWindows {
			// Windows 上使用 Git Bash 或 WSL
			cmd = exec.CommandContext(ctx, "bash", scriptFile)
		} else {
			cmd = exec.CommandContext(ctx, "/bin/bash", scriptFile)
		}
	default:
		// 默认使用 sh
		if runtime.GOOS == constants.OSWindows {
			cmd = exec.CommandContext(ctx, "sh", scriptFile)
		} else {
			cmd = exec.CommandContext(ctx, "/bin/sh", scriptFile)
		}
	}

	// 设置环境变量
	cmd.Env = os.Environ()
	for k, v := range task.Env {
		cmd.Env = append(cmd.Env, fmt.Sprintf("%s=%s", k, v))
	}

	// 创建新的任务规范
	newTask := &api.TaskSpec{
		ID:         task.ID,
		Name:       task.Name,
		Command:    "",
		Args:       cmd.Args,
		Env:        task.Env,
		TimeoutSec: task.TimeoutSec,
	}

	// 使用 executor 执行
	return s.executor.ExecuteTask(ctx, newTask, logCallback)
}

// createScriptFile 创建脚本文件
func (s *ScriptExecutor) createScriptFile(taskID, scriptType, content string) (string, error) {
	var ext string
	switch scriptType {
	case constants.ScriptTypePython:
		ext = constants.ScriptExtPy
	case constants.ScriptTypePowerShell:
		ext = constants.ScriptExtPs1
	case constants.ScriptTypeShell, constants.ScriptTypeBash:
		ext = constants.ScriptExtSh
	default:
		ext = constants.ScriptExtSh
	}

	scriptPath := filepath.Join(s.tempDir, fmt.Sprintf("script_%s_%d%s", taskID, time.Now().Unix(), ext))
	return scriptPath, os.WriteFile(scriptPath, []byte(content), 0644)
}

// detectScriptType 检测脚本类型
func detectScriptType(content string) string {
	content = strings.TrimSpace(content)

	// 检查 shebang
	if strings.HasPrefix(content, "#!") {
		shebang := strings.ToLower(content[:strings.Index(content, "\n")])
		if strings.Contains(shebang, constants.ScriptTypePython) {
			return constants.ScriptTypePython
		}
		if strings.Contains(shebang, constants.ScriptTypeBash) {
			return constants.ScriptTypeBash
		}
		if strings.Contains(shebang, "sh") {
			return constants.ScriptTypeShell
		}
		if strings.Contains(shebang, constants.ScriptTypePowerShell) || strings.Contains(shebang, constants.ScriptTypePwsh) {
			return constants.ScriptTypePowerShell
		}
	}

	// 检查文件扩展名（如果内容包含路径）
	if strings.Contains(content, constants.ScriptExtPy) {
		return constants.ScriptTypePython
	}
	if strings.Contains(content, constants.ScriptExtPs1) {
		return constants.ScriptTypePowerShell
	}

	// 检查 Python 特征
	if strings.Contains(content, "import ") || strings.Contains(content, "def ") || strings.Contains(content, "print(") {
		return constants.ScriptTypePython
	}

	// 检查 PowerShell 特征
	if strings.Contains(content, "$") && strings.Contains(content, "Get-") {
		return constants.ScriptTypePowerShell
	}

	// 默认 shell
	return constants.ScriptTypeShell
}

// isExecutableCommand 判断是否是可直接执行的命令
func isExecutableCommand(cmd string) bool {
	cmd = strings.TrimSpace(cmd)
	// 简单的命令（不包含换行符，且不是脚本内容）
	if !strings.Contains(cmd, "\n") && len(cmd) < 100 {
		return true
	}
	return false
}
