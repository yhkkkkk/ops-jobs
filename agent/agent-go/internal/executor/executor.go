package executor

import (
	"context"
	"fmt"
	"io"
	"os"
	"os/exec"
	"os/user"
	"path/filepath"
	"runtime"
	"strings"
	"sync"
	"time"

	"ops-job-agent/internal/api"
	"ops-job-agent/internal/constants"
	"ops-job-agent/internal/errors"
	"ops-job-agent/internal/logger"
)

// Executor 负责执行任务
type Executor struct {
	tasks         map[string]*RunningTask
	tasksLock     sync.RWMutex
	logDir        string
	maxTaskTime   time.Duration // 全局最大任务执行时间
	monitorTicker *time.Ticker  // 监控定时器
	stopMonitor   chan struct{} // 停止监控信号
}

// RunningTask 正在运行的任务
type RunningTask struct {
	TaskID    string
	Command   *exec.Cmd
	Cancel    context.CancelFunc
	StartTime time.Time
	Status    string // pending/running/success/failed/cancelled
	LogBuffer strings.Builder
	LogLock   sync.Mutex
	WaitErr   error // 命令等待的错误
}

// NewExecutor 创建执行器
func NewExecutor(logDir string) *Executor {
	if logDir == "" {
		logDir = filepath.Join(os.TempDir(), "ops-job-agent", "logs")
	}
	os.MkdirAll(logDir, 0755)

	executor := &Executor{
		tasks:       make(map[string]*RunningTask),
		logDir:      logDir,
		maxTaskTime: 2 * time.Hour, // 默认最大执行时间2小时
		stopMonitor: make(chan struct{}),
	}

	// 启动任务监控goroutine
	go executor.monitorTasks()

	return executor
}

// SetMaxTaskTime 设置全局最大任务执行时间
func (e *Executor) SetMaxTaskTime(maxTime time.Duration) {
	e.tasksLock.Lock()
	e.maxTaskTime = maxTime
	e.tasksLock.Unlock()
}

// monitorTasks 监控运行中的任务，强制终止超时任务
func (e *Executor) monitorTasks() {
	ticker := time.NewTicker(30 * time.Second) // 每30秒检查一次
	defer ticker.Stop()

	for {
		select {
		case <-e.stopMonitor:
			return
		case <-ticker.C:
			e.checkAndTerminateTimeoutTasks()
		}
	}
}

// checkAndTerminateTimeoutTasks 检查并终止超时的任务
func (e *Executor) checkAndTerminateTimeoutTasks() {
	e.tasksLock.Lock()
	defer e.tasksLock.Unlock()

	now := time.Now()
	terminatedCount := 0

	for taskID, task := range e.tasks {
		if task.Status != constants.StatusRunning {
			continue
		}

		runtime := now.Sub(task.StartTime)

		// 检查是否超过全局最大执行时间
		if runtime > e.maxTaskTime {
			logger.GetLogger().WithFields(map[string]interface{}{
				"task_id":    taskID,
				"runtime":    runtime.String(),
				"max_time":   e.maxTaskTime.String(),
				"start_time": task.StartTime.Format(time.RFC3339),
			}).Warn("task exceeded global maximum execution time, terminating")

			// 强制终止任务
			if task.Cancel != nil {
				task.Cancel()
			}

			// 如果进程还在运行，强制kill
			// 注意：这里我们标记状态，实际的进程终止由waitForCommand处理
			task.Status = constants.StatusFailed

			terminatedCount++
		}
	}

	if terminatedCount > 0 {
		logger.GetLogger().WithField("terminated_count", terminatedCount).Info("terminated timeout tasks in monitoring cycle")
	}
}

// Stop 停止执行器
func (e *Executor) Stop() {
	close(e.stopMonitor)

	e.tasksLock.Lock()
	defer e.tasksLock.Unlock()

	// 取消所有正在运行的任务
	for _, task := range e.tasks {
		if task.Cancel != nil {
			task.Cancel()
		}
	}
}

// ExecuteTask 执行任务
func (e *Executor) ExecuteTask(ctx context.Context, task *api.TaskSpec, logCallback func(string)) (*api.TaskResult, error) {
	// 设置任务上下文
	taskCtx, cancel, runningTask := e.setupTaskContext(ctx, task)
	defer cancel()
	defer func() {
		e.tasksLock.Lock()
		delete(e.tasks, task.ID)
		e.tasksLock.Unlock()
	}()

	// 构建并配置命令
	cmd, logFile, err := e.prepareCommand(taskCtx, task, runningTask)
	if err != nil {
		return e.buildErrorResult(task.ID, runningTask.StartTime, err.Error()), nil
	}
	defer logFile.Close()

	// 启动命令并处理输出
	if err := e.startCommand(cmd, task.ID, logFile, runningTask, logCallback); err != nil {
		runningTask.Status = constants.StatusFailed
		return e.buildErrorResult(task.ID, runningTask.StartTime, err.Error()), nil
	}

	// 等待命令完成
	result := e.waitForCommand(taskCtx, cmd, runningTask)
	if result != nil {
		return result, nil
	}

	// 构建任务结果（正常完成）
	finishedAt := time.Now()
	return e.buildTaskResult(task.ID, runningTask, finishedAt, runningTask.WaitErr), nil
}

// setupTaskContext 设置任务上下文
func (e *Executor) setupTaskContext(ctx context.Context, task *api.TaskSpec) (context.Context, context.CancelFunc, *RunningTask) {
	taskCtx, cancel := context.WithCancel(ctx)
	if task.TimeoutSec > 0 {
		taskCtx, cancel = context.WithTimeout(taskCtx, time.Duration(task.TimeoutSec)*time.Second)
	}

	runningTask := &RunningTask{
		TaskID:    task.ID,
		StartTime: time.Now(),
		Status:    constants.StatusPending,
		Cancel:    cancel,
	}
	e.tasksLock.Lock()
	e.tasks[task.ID] = runningTask
	e.tasksLock.Unlock()

	return taskCtx, cancel, runningTask
}

// prepareCommand 准备命令
func (e *Executor) prepareCommand(ctx context.Context, task *api.TaskSpec, runningTask *RunningTask) (*exec.Cmd, *os.File, error) {
	// 构建命令
	cmd, err := buildCommand(ctx, task)
	if err != nil {
		return nil, nil, err
	}

	// 设置环境变量
	cmd.Env = os.Environ()
	for k, v := range task.Env {
		cmd.Env = append(cmd.Env, fmt.Sprintf("%s=%s", k, v))
	}

	// 设置工作目录
	if task.WorkDir != "" {
		cmd.Dir = task.WorkDir
	} else {
		if wd, wdErr := os.Getwd(); wdErr == nil {
			cmd.Dir = wd
		}
	}

	// 创建日志文件
	logFile, err := e.createLogFile(task.ID)
	if err != nil {
		return nil, nil, fmt.Errorf("create log file failed: %w", err)
	}

	return cmd, logFile, nil
}

// startCommand 启动命令
func (e *Executor) startCommand(cmd *exec.Cmd, taskID string, logFile *os.File, runningTask *RunningTask, logCallback func(string)) error {
	// 创建管道用于实时读取输出
	stdoutPipe, err := cmd.StdoutPipe()
	if err != nil {
		return fmt.Errorf("create stdout pipe failed: %w", err)
	}

	stderrPipe, err := cmd.StderrPipe()
	if err != nil {
		return fmt.Errorf("create stderr pipe failed: %w", err)
	}

	// 创建多写入器：同时写入日志文件和缓冲区
	multiWriter := io.MultiWriter(logFile, &runningTask.LogBuffer)

	// 启动命令
	runningTask.Status = constants.StatusRunning
	if err := cmd.Start(); err != nil {
		return err
	}

	runningTask.Command = cmd

	// 实时读取输出（stdout 和 stderr）
	go e.streamOutput(taskID, stdoutPipe, multiWriter, logCallback, constants.StreamStdout)
	go e.streamOutput(taskID, stderrPipe, multiWriter, logCallback, constants.StreamStderr)

	return nil
}

// waitForCommand 等待命令完成，如果被取消或超时则返回结果，否则返回 nil
func (e *Executor) waitForCommand(taskCtx context.Context, cmd *exec.Cmd, runningTask *RunningTask) *api.TaskResult {
	doneCh := make(chan error, 1)
	go func() {
		doneCh <- cmd.Wait()
	}()

	select {
	case <-taskCtx.Done():
		return e.handleContextDone(taskCtx, cmd, runningTask, doneCh)
	case waitErr := <-doneCh:
		// 正常完成，返回 nil 让调用者构建结果
		runningTask.WaitErr = waitErr
		return nil
	}
}

// handleContextDone 处理上下文取消
func (e *Executor) handleContextDone(taskCtx context.Context, cmd *exec.Cmd, runningTask *RunningTask, doneCh chan error) *api.TaskResult {
	finishedAt := time.Now()
	if taskCtx.Err() == context.Canceled {
		// 任务被取消
		if cmd.Process != nil {
			cmd.Process.Signal(os.Interrupt)
			time.Sleep(100 * time.Millisecond)
			if cmd.ProcessState == nil || !cmd.ProcessState.Exited() {
				cmd.Process.Kill()
			}
		}
		<-doneCh
		runningTask.Status = constants.StatusCancelled
		return e.buildTaskResult(runningTask.TaskID, runningTask, finishedAt, nil)
	}
	// 超时
	if cmd.Process != nil {
		cmd.Process.Kill()
	}
	<-doneCh
	runningTask.Status = constants.StatusFailed
	return e.buildTaskResult(runningTask.TaskID, runningTask, finishedAt, nil)
}

// buildTaskResult 构建任务结果
func (e *Executor) buildTaskResult(taskID string, runningTask *RunningTask, finishedAt time.Time, waitErr error) *api.TaskResult {
	// 如果状态已经是 cancelled 或 failed（由 handleContextDone 设置），直接使用
	if runningTask.Status == constants.StatusCancelled {
		runningTask.LogLock.Lock()
		logContent := runningTask.LogBuffer.String()
		runningTask.LogLock.Unlock()
		return &api.TaskResult{
			TaskID:     taskID,
			Status:     constants.StatusCancelled,
			ExitCode:   -1,
			Log:        logContent,
			StartedAt:  runningTask.StartTime.Unix(),
			FinishedAt: finishedAt.Unix(),
			ErrorMsg:   constants.MsgTaskCancelled,
			ErrorCode:  int(errors.ErrCodeProcessKilled),
		}
	}

	// 获取退出码和错误码
	exitCode := 0
	errorCode := 0
	errorMsg := getErrorMsg(waitErr)
	if waitErr != nil {
		if exitError, ok := waitErr.(*exec.ExitError); ok {
			exitCode = exitError.ExitCode()
			if exitCode != 0 {
				errorCode = int(errors.ErrCodeExitCodeNonZero)
			}
		} else {
			exitCode = -1
			errorCode = int(errors.ErrCodeExecutionFailed)
		}
		if runningTask.Status != constants.StatusFailed {
			runningTask.Status = constants.StatusFailed
		}
	} else {
		runningTask.Status = constants.StatusSuccess
	}

	// 读取完整日志
	runningTask.LogLock.Lock()
	logContent := runningTask.LogBuffer.String()
	runningTask.LogLock.Unlock()

	return &api.TaskResult{
		TaskID:     taskID,
		Status:     runningTask.Status,
		ExitCode:   exitCode,
		Log:        logContent,
		LogSize:    int64(len(logContent)),
		StartedAt:  runningTask.StartTime.Unix(),
		FinishedAt: finishedAt.Unix(),
		ErrorMsg:   errorMsg,
		ErrorCode:  errorCode,
		LogPointer: fmt.Sprintf("redis:job_logs/%s@", taskID),
	}
}

// buildErrorResult 构建错误结果
func (e *Executor) buildErrorResult(taskID string, startTime time.Time, errorMsg string) *api.TaskResult {
	return &api.TaskResult{
		TaskID:     taskID,
		Status:     constants.StatusFailed,
		ExitCode:   -1,
		StartedAt:  startTime.Unix(),
		FinishedAt: time.Now().Unix(),
		ErrorMsg:   errorMsg,
	}
}

// buildCommand 根据 TaskSpec 构建具体要执行的 *exec.Cmd
// 支持多种脚本类型：
// - ScriptType 为空：保持兼容，复用历史行为（Linux: /bin/sh -c；Windows: cmd /c）
// - shell：显式 shell 脚本
// - powershell：Windows 下使用 powershell.exe；其它系统预留 pwsh（如已安装）
// - python：使用 python/python3 -c 执行脚本
// - js：使用 node -e 执行脚本
// 如果指定了 RunAs，会使用 su/sudo (Linux) 或 runas (Windows) 切换用户执行
func buildCommand(ctx context.Context, task *api.TaskSpec) (*exec.Cmd, error) {
	var baseCmd *exec.Cmd

	// 如果没有 Command，但提供了 Args，则直接按 Args 执行
	if task.Command == "" {
		if len(task.Args) == 0 {
			return nil, fmt.Errorf("task command is empty")
		}
		baseCmd = exec.CommandContext(ctx, task.Args[0], task.Args[1:]...)
	} else {
		scriptType := strings.ToLower(strings.TrimSpace(task.ScriptType))
		switch scriptType {
		case "", constants.ScriptTypeShell:
			// 兼容默认行为：Windows 用 cmd，Linux/其他用 /bin/sh
			if runtime.GOOS == constants.OSWindows {
				baseCmd = exec.CommandContext(ctx, "cmd", "/c", task.Command)
			} else {
				baseCmd = exec.CommandContext(ctx, "/bin/sh", "-c", task.Command)
			}

		case constants.ScriptTypePowerShell, constants.ScriptTypePwsh:
			if runtime.GOOS == constants.OSWindows {
				// Windows 上使用 powershell.exe
				baseCmd = exec.CommandContext(ctx,
					"powershell.exe",
					"-NoLogo",
					"-NonInteractive",
					"-ExecutionPolicy", "Bypass",
					"-Command", task.Command,
				)
			} else {
				// 非 Windows 环境，优先尝试 pwsh（PowerShell Core）
				baseCmd = exec.CommandContext(ctx,
					"pwsh",
					"-NoLogo",
					"-NonInteractive",
					"-Command", task.Command,
				)
			}

		case constants.ScriptTypePython, constants.ScriptTypePy:
			// 通过 python/python3 解释执行
			pythonExe := "python3"
			if runtime.GOOS == "windows" {
				pythonExe = "python"
			}
			baseCmd = exec.CommandContext(ctx, pythonExe, "-c", task.Command)

		case constants.ScriptTypeJS, constants.ScriptTypeNode:
			// 通过 node -e 执行 JS 代码
			baseCmd = exec.CommandContext(ctx, "node", "-e", task.Command)

		default:
			// 未知脚本类型，回退到原有行为
			if runtime.GOOS == "windows" {
				baseCmd = exec.CommandContext(ctx, "cmd", "/c", task.Command)
			} else {
				baseCmd = exec.CommandContext(ctx, "/bin/sh", "-c", task.Command)
			}
		}
	}

	// 如果指定了 run_as，需要切换用户执行
	if task.RunAs != "" {
		// 获取当前用户
		currentUser, err := user.Current()
		currentUsername := ""
		if err == nil {
			currentUsername = currentUser.Username
		} else {
			// 如果获取失败，尝试从环境变量获取
			currentUsername = os.Getenv("USER")
		}

		// 如果目标用户与当前用户相同，不需要切换
		if currentUsername == task.RunAs {
			return baseCmd, nil
		}

		if runtime.GOOS == constants.OSWindows {
			// Windows: 使用 runas 切换用户
			// 注意：runas 需要密码，这里使用 /savecred 选项（需要管理员权限）
			// 或者使用计划任务的方式，但更简单的方式是使用 PowerShell 的 Start-Process -Credential
			// 由于 runas 需要交互式输入密码，这里先尝试使用 PowerShell 的 Start-Process
			// 如果失败，则记录错误
			// 将命令和参数转换为字符串
			cmdStr := baseCmd.Path
			if len(baseCmd.Args) > 1 {
				// 转义参数中的引号
				escapedArgs := make([]string, len(baseCmd.Args[1:]))
				for i, arg := range baseCmd.Args[1:] {
					escapedArgs[i] = fmt.Sprintf(`"%s"`, strings.ReplaceAll(arg, `"`, `\"`))
				}
				cmdStr += " " + strings.Join(escapedArgs, " ")
			}
			psScript := fmt.Sprintf(`$cred = Get-Credential -UserName "%s" -Message "Enter password"; Start-Process -FilePath "%s" -ArgumentList %s -Credential $cred -NoNewWindow -Wait`,
				task.RunAs, baseCmd.Path, strings.Join(baseCmd.Args[1:], ","))
			return exec.CommandContext(ctx, "powershell.exe", "-NoLogo", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-Command", psScript), nil
		} else {
			// Linux/Unix: 使用 sudo 或 su 切换用户
			// 检查当前用户是否为 root
			isRoot := false
			if currentUser != nil {
				isRoot = currentUser.Uid == "0"
			} else {
				// 如果无法获取用户信息，尝试检查 euid
				isRoot = os.Geteuid() == 0
			}

			if isRoot {
				// 如果是 root，使用 su - username -c "command"
				// 将原始命令和参数组合成字符串
				cmdStr := baseCmd.Path
				if len(baseCmd.Args) > 1 {
					// 转义参数，确保特殊字符正确处理
					escapedArgs := make([]string, len(baseCmd.Args[1:]))
					for i, arg := range baseCmd.Args[1:] {
						// 转义单引号，并用单引号包裹
						escapedArg := strings.ReplaceAll(arg, "'", "'\"'\"'")
						escapedArgs[i] = "'" + escapedArg + "'"
					}
					cmdStr += " " + strings.Join(escapedArgs, " ")
				}
				suArgs := []string{"-", task.RunAs, "-c", cmdStr}
				return exec.CommandContext(ctx, "su", suArgs...), nil
			} else {
				// 如果不是 root，尝试使用 sudo
				// sudo -u username command args...
				originalArgs := baseCmd.Args
				sudoArgs := append([]string{"-u", task.RunAs}, originalArgs...)
				return exec.CommandContext(ctx, "sudo", sudoArgs...), nil
			}
		}
	}

	return baseCmd, nil
}

// streamOutput 实时流式读取输出
func (e *Executor) streamOutput(taskID string, pipe io.ReadCloser, writer io.Writer, callback func(string), streamType string) {
	defer func() {
		_ = pipe.Close()
	}()

	// 使用缓冲区读取，避免频繁调用回调
	buf := make([]byte, constants.LogBufferSize)
	lineBuffer := make([]byte, 0, constants.LineBufferSize)

	for {
		n, err := pipe.Read(buf)
		if n > 0 {
			// 写入到日志文件和缓冲区
			if writer != nil {
				writer.Write(buf[:n])
			}

			// 处理行缓冲，按行回调
			data := buf[:n]
			for _, b := range data {
				lineBuffer = append(lineBuffer, b)
				if b == '\n' {
					// 找到完整的一行
					line := strings.TrimRight(string(lineBuffer), "\r\n")
					if line != "" {
						// 实时回调
						if callback != nil {
							callback(line)
						}
					}
					lineBuffer = lineBuffer[:0]
				}
			}
		}

		if err != nil {
			if err != io.EOF {
				// 读取错误，记录但不中断
				if callback != nil {
					callback(fmt.Sprintf("[%s stream error] %v", streamType, err))
				}
			}
			break
		}
	}

	// 处理剩余的不完整行
	if len(lineBuffer) > 0 {
		line := strings.TrimRight(string(lineBuffer), "\r\n")
		if line != "" && callback != nil {
			callback(line)
		}
	}
}

// CancelTask 取消任务
func (e *Executor) CancelTask(taskID string) error {
	e.tasksLock.RLock()
	task, exists := e.tasks[taskID]
	e.tasksLock.RUnlock()

	if !exists {
		return fmt.Errorf("task %s not found", taskID)
	}

	if task.Status != constants.StatusRunning {
		return fmt.Errorf("task %s is not running", taskID)
	}

	task.Cancel()
	task.Status = constants.StatusCancelled
	return nil
}

// GetTaskStatus 获取任务状态
func (e *Executor) GetTaskStatus(taskID string) (*RunningTask, bool) {
	e.tasksLock.RLock()
	defer e.tasksLock.RUnlock()
	task, exists := e.tasks[taskID]
	return task, exists
}

// createLogFile 创建日志文件
func (e *Executor) createLogFile(taskID string) (*os.File, error) {
	logPath := filepath.Join(e.logDir, fmt.Sprintf(constants.TaskLogFilePattern, taskID, time.Now().Unix()))
	return os.Create(logPath)
}

// getErrorMsg 获取错误信息
func getErrorMsg(err error) string {
	if err == nil {
		return ""
	}
	return err.Error()
}

// GetCurrentUser 获取当前用户
func GetCurrentUser() string {
	u, err := user.Current()
	if err != nil {
		return "unknown"
	}
	return u.Username
}
