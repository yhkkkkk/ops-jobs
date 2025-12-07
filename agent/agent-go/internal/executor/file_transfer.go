package executor

import (
	"context"
	"fmt"
	"io"
	"os"
	"path/filepath"
	"time"

	"ops-job-agent/internal/api"
	"ops-job-agent/internal/errors"
	"ops-job-agent/internal/metrics"
	"ops-job-agent/internal/resource"
)

// FileTransferExecutor 文件传输执行器
type FileTransferExecutor struct {
	executor *Executor
}

// NewFileTransferExecutor 创建文件传输执行器
func NewFileTransferExecutor(executor *Executor) *FileTransferExecutor {
	return &FileTransferExecutor{
		executor: executor,
	}
}

// ExecuteTransfer 执行文件传输
func (f *FileTransferExecutor) ExecuteTransfer(ctx context.Context, task *api.TaskSpec, logCallback func(string)) (*api.TaskResult, error) {
	if task.FileTransfer == nil {
		return nil, fmt.Errorf("file transfer spec is empty")
	}

	startTime := time.Now()
	result := &api.TaskResult{
		TaskID:    task.ID,
		Status:    "running",
		StartedAt: startTime.Unix(),
	}

	switch task.FileTransfer.Type {
	case "upload":
		return f.uploadFile(ctx, task, result, logCallback)
	case "download":
		return f.downloadFile(ctx, task, result, logCallback)
	default:
		return nil, fmt.Errorf("unsupported transfer type: %s", task.FileTransfer.Type)
	}
}

// uploadFile 上传文件
func (f *FileTransferExecutor) uploadFile(ctx context.Context, task *api.TaskSpec, result *api.TaskResult, logCallback func(string)) (*api.TaskResult, error) {
	remotePath := task.FileTransfer.RemotePath
	if remotePath == "" {
		return nil, fmt.Errorf("remote path is required for upload")
	}

	// 确保目标目录存在
	remoteDir := filepath.Dir(remotePath)
	if err := os.MkdirAll(remoteDir, 0755); err != nil {
		result.Status = "failed"
		result.ErrorCode = int(errors.ErrCodeFileWriteError)
		result.ErrorMsg = fmt.Sprintf("create remote directory failed: %v", err)
		result.FinishedAt = time.Now().Unix()
		return result, nil
	}

	// 写入文件
	var content []byte
	if len(task.FileTransfer.Content) > 0 {
		content = task.FileTransfer.Content
	} else if task.FileTransfer.LocalPath != "" {
		// 从本地文件读取
		var err error
		content, err = os.ReadFile(task.FileTransfer.LocalPath)
		if err != nil {
			result.Status = "failed"
			result.ErrorCode = int(errors.ErrCodeFileReadError)
			result.ErrorMsg = fmt.Sprintf("read local file failed: %v", err)
			result.FinishedAt = time.Now().Unix()
			return result, nil
		}
	} else {
		result.Status = "failed"
		result.ErrorCode = int(errors.ErrCodeInvalidParam)
		result.ErrorMsg = "no file content or local path provided"
		result.FinishedAt = time.Now().Unix()
		return result, nil
	}

	// 应用带宽限制（如果配置了）
	bandwidthLimit := task.FileTransfer.BandwidthLimit
	var writer io.Writer
	if bandwidthLimit > 0 {
		limiter := resource.NewBandwidthLimiter(bandwidthLimit)
		file, err := os.Create(remotePath)
		if err != nil {
			result.Status = "failed"
			result.ErrorCode = int(errors.ErrCodeFileWriteError)
			result.ErrorMsg = fmt.Sprintf("create remote file failed: %v", err)
			result.FinishedAt = time.Now().Unix()
			return result, nil
		}
		defer file.Close()
		writer = limiter.LimitWriter(file)
		logCallback(fmt.Sprintf("Uploading with bandwidth limit: %d KB/s", bandwidthLimit))
	} else {
		writer = nil // 直接写入，不使用限制器
	}

	// 写入远程文件
	if writer != nil {
		// 使用带宽限制写入
		if _, err := writer.Write(content); err != nil {
			result.Status = "failed"
			result.ErrorCode = int(errors.ErrCodeFileWriteError)
			result.ErrorMsg = fmt.Sprintf("write remote file failed: %v", err)
			result.FinishedAt = time.Now().Unix()
			return result, nil
		}
	} else {
		// 直接写入
		if err := os.WriteFile(remotePath, content, 0644); err != nil {
			result.Status = "failed"
			result.ErrorCode = int(errors.ErrCodeFileWriteError)
			result.ErrorMsg = fmt.Sprintf("write remote file failed: %v", err)
			result.FinishedAt = time.Now().Unix()
			return result, nil
		}
	}

	logCallback(fmt.Sprintf("File uploaded successfully: %s (%d bytes)", remotePath, len(content)))

	result.Status = "success"
	result.ExitCode = 0
	result.FinishedAt = time.Now().Unix()
	result.Log = fmt.Sprintf("Uploaded %d bytes to %s", len(content), remotePath)
	return result, nil
}

// downloadFile 下载文件
func (f *FileTransferExecutor) downloadFile(ctx context.Context, task *api.TaskSpec, result *api.TaskResult, logCallback func(string)) (*api.TaskResult, error) {
	downloadStartTime := time.Now()
	remotePath := task.FileTransfer.RemotePath
	if remotePath == "" {
		return nil, fmt.Errorf("remote path is required for download")
	}

	localPath := task.FileTransfer.LocalPath
	if localPath == "" {
		localPath = filepath.Base(remotePath)
	}

	// 确保本地目录存在
	localDir := filepath.Dir(localPath)
	if localDir != "." && localDir != "" {
		if err := os.MkdirAll(localDir, 0755); err != nil {
			result.Status = "failed"
			result.ErrorCode = int(errors.ErrCodeFileWriteError)
			result.ErrorMsg = fmt.Sprintf("create local directory failed: %v", err)
			result.FinishedAt = time.Now().Unix()
			return result, nil
		}
	}

	// 读取远程文件
	content, err := os.ReadFile(remotePath)
	if err != nil {
		result.Status = "failed"
		result.ErrorCode = int(errors.ErrCodeFileReadError)
		result.ErrorMsg = fmt.Sprintf("read remote file failed: %v", err)
		result.FinishedAt = time.Now().Unix()
		return result, nil
	}

	// 写入本地文件
	if err := os.WriteFile(localPath, content, 0644); err != nil {
		result.Status = "failed"
		result.ErrorCode = int(errors.ErrCodeFileWriteError)
		result.ErrorMsg = fmt.Sprintf("write local file failed: %v", err)
		result.FinishedAt = time.Now().Unix()
		return result, nil
	}

	logCallback(fmt.Sprintf("File downloaded successfully: %s -> %s (%d bytes)", remotePath, localPath, len(content)))

	// 记录网络传输指标
	transferDuration := time.Since(downloadStartTime)
	metrics.GetMetrics().RecordNetworkTransfer(int64(len(content)), transferDuration)

	result.Status = "success"
	result.ExitCode = 0
	result.FinishedAt = time.Now().Unix()
	result.Log = fmt.Sprintf("Downloaded %d bytes from %s to %s", len(content), remotePath, localPath)
	return result, nil
}

// CopyFile 复制文件（用于本地文件传输）
func CopyFile(src, dst string) error {
	sourceFile, err := os.Open(src)
	if err != nil {
		return err
	}
	defer sourceFile.Close()

	destFile, err := os.Create(dst)
	if err != nil {
		return err
	}
	defer destFile.Close()

	_, err = io.Copy(destFile, sourceFile)
	return err
}
