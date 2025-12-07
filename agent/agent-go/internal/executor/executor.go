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
	"ops-job-agent/internal/errors"
)

// Executor 负责执行任务
type Executor struct {
	tasks     map[string]*RunningTask
	tasksLock sync.RWMutex
	logDir    string
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
}

// NewExecutor 创建执行器
func NewExecutor(logDir string) *Executor {
	if logDir == "" {
		logDir = filepath.Join(os.TempDir(), "ops-job-agent", "logs")
	}
	os.MkdirAll(logDir, 0755)
	return &Executor{
		tasks:  make(map[string]*RunningTask),
		logDir: logDir,
	}
}

// ExecuteTask 执行任务
func (e *Executor) ExecuteTask(ctx context.Context, task *api.TaskSpec, logCallback func(string)) (*api.TaskResult, error) {
	var err error
	
	// 创建任务上下文，支持取消
	taskCtx, cancel := context.WithCancel(ctx)
	defer cancel()

	// 设置超时
	if task.TimeoutSec > 0 {
		taskCtx, cancel = context.WithTimeout(taskCtx, time.Duration(task.TimeoutSec)*time.Second)
		defer cancel()
	}

	// 创建运行任务记录
	runningTask := &RunningTask{
		TaskID:    task.ID,
		StartTime: time.Now(),
		Status:    "pending",
		Cancel:    cancel,
	}
	e.tasksLock.Lock()
	e.tasks[task.ID] = runningTask
	e.tasksLock.Unlock()

	defer func() {
		e.tasksLock.Lock()
		delete(e.tasks, task.ID)
		e.tasksLock.Unlock()
	}()

	// 构建命令
	var cmd *exec.Cmd
	var shell string
	var args []string

	switch {
	case task.Command != "":
		// 根据操作系统选择 shell
		if runtime.GOOS == "windows" {
			shell = "cmd"
			args = []string{"/c", task.Command}
		} else {
			shell = "/bin/sh"
			args = []string{"-c", task.Command}
		}
		cmd = exec.CommandContext(taskCtx, shell, args...)
	default:
		// 使用 Command 和 Args
		if len(task.Args) == 0 {
			return nil, fmt.Errorf("task command is empty")
		}
		cmd = exec.CommandContext(taskCtx, task.Args[0], task.Args[1:]...)
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
	var logFile *os.File
	logFile, err = e.createLogFile(task.ID)
	if err != nil {
		return nil, fmt.Errorf("create log file failed: %w", err)
	}
	defer logFile.Close()

	// 创建管道用于实时读取输出
	stdoutPipe, err := cmd.StdoutPipe()
	if err != nil {
		runningTask.Status = "failed"
		return &api.TaskResult{
			TaskID:     task.ID,
			Status:     "failed",
			ExitCode:   -1,
			StartedAt:  runningTask.StartTime.Unix(),
			FinishedAt: time.Now().Unix(),
			ErrorMsg:   fmt.Sprintf("create stdout pipe failed: %v", err),
		}, nil
	}

	stderrPipe, err := cmd.StderrPipe()
	if err != nil {
		runningTask.Status = "failed"
		return &api.TaskResult{
			TaskID:     task.ID,
			Status:     "failed",
			ExitCode:   -1,
			StartedAt:  runningTask.StartTime.Unix(),
			FinishedAt: time.Now().Unix(),
			ErrorMsg:   fmt.Sprintf("create stderr pipe failed: %v", err),
		}, nil
	}

	// 创建多写入器：同时写入日志文件和缓冲区
	multiWriter := io.MultiWriter(logFile, &runningTask.LogBuffer)

	// 启动命令
	runningTask.Status = "running"
	if err := cmd.Start(); err != nil {
		runningTask.Status = "failed"
		return &api.TaskResult{
			TaskID:     task.ID,
			Status:     "failed",
			ExitCode:   -1,
			StartedAt:  runningTask.StartTime.Unix(),
			FinishedAt: time.Now().Unix(),
			ErrorMsg:   err.Error(),
		}, nil
	}

	runningTask.Command = cmd

	// 实时读取输出（stdout 和 stderr）
	go e.streamOutput(task.ID, stdoutPipe, multiWriter, logCallback, "stdout")
	go e.streamOutput(task.ID, stderrPipe, multiWriter, logCallback, "stderr")

	// 等待命令完成（在单独的 goroutine 中，以便可以响应取消）
	doneCh := make(chan error, 1)
	go func() {
		doneCh <- cmd.Wait()
	}()

	var finishedAt time.Time
	var waitErr error

	// 等待命令完成或取消
	select {
	case <-taskCtx.Done():
		// 任务被取消
		if taskCtx.Err() == context.Canceled {
			// 尝试终止进程
			if cmd.Process != nil {
				// 先尝试优雅终止
				cmd.Process.Signal(os.Interrupt)
				// 等待一小段时间让进程有机会清理
				time.Sleep(100 * time.Millisecond)
				// 如果还在运行，强制终止
				if cmd.ProcessState == nil || !cmd.ProcessState.Exited() {
					cmd.Process.Kill()
				}
			}
			// 等待 Wait 返回
			<-doneCh
			finishedAt = time.Now()
			runningTask.Status = "cancelled"
			return &api.TaskResult{
				TaskID:     task.ID,
				Status:     "cancelled",
				ExitCode:   -1,
				StartedAt:  runningTask.StartTime.Unix(),
				FinishedAt: finishedAt.Unix(),
				ErrorMsg:   "task cancelled",
				ErrorCode:  int(errors.ErrCodeProcessKilled),
			}, nil
		}
		// 超时
		if taskCtx.Err() == context.DeadlineExceeded {
			// 超时，终止进程
			if cmd.Process != nil {
				cmd.Process.Kill()
			}
			<-doneCh
			finishedAt = time.Now()
			runningTask.Status = "failed"
			return &api.TaskResult{
				TaskID:     task.ID,
				Status:     "failed",
				ExitCode:   -1,
				StartedAt:  runningTask.StartTime.Unix(),
				FinishedAt: finishedAt.Unix(),
				ErrorMsg:   "task timeout",
				ErrorCode:  int(errors.ErrCodeTimeout),
			}, nil
		}
		case waitErr = <-doneCh:
		// 命令正常完成
		finishedAt = time.Now()
		err = waitErr
	}

	// 获取退出码和错误码
	exitCode := 0
	errorCode := 0
	if err != nil {
		if exitError, ok := err.(*exec.ExitError); ok {
			exitCode = exitError.ExitCode()
			if exitCode != 0 {
				errorCode = int(errors.ErrCodeExitCodeNonZero)
			}
		} else {
			exitCode = -1
			errorCode = int(errors.ErrCodeExecutionFailed)
		}
		runningTask.Status = "failed"
	} else {
		runningTask.Status = "success"
	}

	// 读取完整日志
	runningTask.LogLock.Lock()
	logContent := runningTask.LogBuffer.String()
	runningTask.LogLock.Unlock()

	return &api.TaskResult{
		TaskID:     task.ID,
		Status:     runningTask.Status,
		ExitCode:   exitCode,
		Log:        logContent,
		StartedAt:  runningTask.StartTime.Unix(),
		FinishedAt: finishedAt.Unix(),
		ErrorMsg:   getErrorMsg(err),
		ErrorCode:  errorCode,
	}, nil
}

// streamOutput 实时流式读取输出
func (e *Executor) streamOutput(taskID string, pipe io.ReadCloser, writer io.Writer, callback func(string), streamType string) {
	defer pipe.Close()

	// 使用缓冲区读取，避免频繁调用回调
	buf := make([]byte, 4096)
	lineBuffer := make([]byte, 0, 1024)

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

	if task.Status != "running" {
		return fmt.Errorf("task %s is not running", taskID)
	}

	task.Cancel()
	task.Status = "cancelled"
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
	logPath := filepath.Join(e.logDir, fmt.Sprintf("task_%s_%d.log", taskID, time.Now().Unix()))
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

