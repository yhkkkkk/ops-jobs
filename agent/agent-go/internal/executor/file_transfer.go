package executor

import (
	"bytes"
	"context"
	"crypto/sha256"
	"fmt"
	"io"
	"net/http"
	"os"
	"path/filepath"
	"time"

	"golang.org/x/time/rate"

	"ops-job-agent/internal/api"
	"ops-job-agent/internal/errors"
	"ops-job-agent/internal/metrics"
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
		return setResultFailed(result, int(errors.ErrCodeFileWriteError), fmt.Sprintf("create remote directory failed: %v", err)), nil
	}

	// 写入文件：支持从 content 或本地路径读取，并通过 rate limiter 控制写速
	var reader io.Reader
	if len(task.FileTransfer.Content) > 0 {
		reader = bytes.NewReader(task.FileTransfer.Content)
	} else if task.FileTransfer.LocalPath != "" {
		// 从本地文件读取为流
		fileReader, err := os.Open(task.FileTransfer.LocalPath)
		if err != nil {
			return setResultFailed(result, int(errors.ErrCodeFileReadError), fmt.Sprintf("read local file failed: %v", err)), nil
		}
		defer fileReader.Close()
		reader = fileReader
	} else {
		return setResultFailed(result, int(errors.ErrCodeInvalidParam), "no file content or local path provided"), nil
	}

	// 创建目标文件并写入（支持限速）
	file, err := os.Create(remotePath)
	if err != nil {
		return setResultFailed(result, int(errors.ErrCodeFileWriteError), fmt.Sprintf("create remote file failed: %v", err)), nil
	}
	defer file.Close()

	bandwidthLimit := task.FileTransfer.BandwidthLimit // MB/s
	if bandwidthLimit > 0 {
		logCallback(fmt.Sprintf("Uploading with bandwidth limit: %d MB/s", bandwidthLimit))
		if _, err := rateLimitedCopy(ctx, file, reader, int64(bandwidthLimit)*1024*1024); err != nil {
			return setResultFailed(result, int(errors.ErrCodeFileWriteError), fmt.Sprintf("write remote file failed: %v", err)), nil
		}
	} else {
		if _, err := io.Copy(file, reader); err != nil {
			return setResultFailed(result, int(errors.ErrCodeFileWriteError), fmt.Sprintf("write remote file failed: %v", err)), nil
		}
	}

	logCallback(fmt.Sprintf("File uploaded successfully: %s", remotePath))
	return setResultSuccess(result, fmt.Sprintf("Uploaded to %s", remotePath), 0), nil
}

// downloadFile 下载文件
func (f *FileTransferExecutor) downloadFile(ctx context.Context, task *api.TaskSpec, result *api.TaskResult, logCallback func(string)) (*api.TaskResult, error) {
	downloadStartTime := time.Now()
	remotePath := task.FileTransfer.RemotePath
	if remotePath == "" {
		return nil, fmt.Errorf("remote path is required for download")
	}

	// If a presigned download URL is provided, download from URL instead of reading remotePath locally
	if task.FileTransfer.DownloadURL != "" {
		return f.downloadFromURL(ctx, task, result, logCallback)
	}

	localPath := task.FileTransfer.LocalPath
	if localPath == "" {
		localPath = filepath.Base(remotePath)
	}

	// 确保本地目录存在
	localDir := filepath.Dir(localPath)
	if localDir != "." && localDir != "" {
		if err := os.MkdirAll(localDir, 0755); err != nil {
			return setResultFailed(result, int(errors.ErrCodeFileWriteError), fmt.Sprintf("create local directory failed: %v", err)), nil
		}
	}

	// 打开远程文件并按需限速写入到本地路径
	srcFile, err := os.Open(remotePath)
	if err != nil {
		return setResultFailed(result, int(errors.ErrCodeFileReadError), fmt.Sprintf("read remote file failed: %v", err)), nil
	}
	defer srcFile.Close()

	dstFile, err := os.Create(localPath)
	if err != nil {
		return setResultFailed(result, int(errors.ErrCodeFileWriteError), fmt.Sprintf("create local file failed: %v", err)), nil
	}
	defer dstFile.Close()

	bandwidthLimit := task.FileTransfer.BandwidthLimit // KB/s
	var written int64
	if bandwidthLimit > 0 {
		written, err = rateLimitedCopy(ctx, dstFile, srcFile, int64(bandwidthLimit)*1024)
	} else {
		written, err = io.Copy(dstFile, srcFile)
	}
	if err != nil {
		return setResultFailed(result, int(errors.ErrCodeFileWriteError), fmt.Sprintf("write local file failed: %v", err)), nil
	}

	logCallback(fmt.Sprintf("File downloaded successfully: %s -> %s (%d bytes)", remotePath, localPath, written))

	// 记录网络传输指标
	transferDuration := time.Since(downloadStartTime)
	metrics.GetMetrics().RecordNetworkTransfer(written, transferDuration)

	return setResultSuccess(result, fmt.Sprintf("Downloaded %d bytes from %s to %s", written, remotePath, localPath), 0), nil
}

// downloadFromURL 下载 presigned URL 内容到 remotePath（remotePath: 目标文件路径在主机上）
func (f *FileTransferExecutor) downloadFromURL(ctx context.Context, task *api.TaskSpec, result *api.TaskResult, logCallback func(string)) (*api.TaskResult, error) {
	downloadStartTime := time.Now()
	downloadURL := task.FileTransfer.DownloadURL
	if downloadURL == "" {
		return setResultFailed(result, int(errors.ErrCodeInvalidParam), "download_url is empty"), nil
	}

	remotePath := task.FileTransfer.RemotePath
	if remotePath == "" {
		return setResultFailed(result, int(errors.ErrCodeInvalidParam), "remote_path required"), nil
	}

	// 确保目标目录存在
	remoteDir := filepath.Dir(remotePath)
	if err := os.MkdirAll(remoteDir, 0755); err != nil {
		return setResultFailed(result, int(errors.ErrCodeFileWriteError), fmt.Sprintf("create remote directory failed: %v", err)), nil
	}

	// HTTP client with timeout
	timeout := time.Duration(task.FileTransfer.BandwidthLimit) * time.Second
	// bandwidthLimit may be 0; use request timeout from FileTransfer.LocalPath? fallback to 300s
	if timeout == 0 {
		timeout = 300 * time.Second
	}
	httpClient := &http.Client{
		Timeout: timeout,
	}

	// Build request
	req, err := http.NewRequestWithContext(ctx, "GET", downloadURL, nil)
	if err != nil {
		return setResultFailed(result, int(errors.ErrCodeNetworkError), fmt.Sprintf("create request failed: %v", err)), nil
	}
	// add optional auth headers
	for k, v := range task.FileTransfer.AuthHeaders {
		req.Header.Set(k, v)
	}

	// Try up to 3 attempts
	var resp *http.Response
	for attempt := 0; attempt < 3; attempt++ {
		resp, err = httpClient.Do(req)
		if err == nil && resp.StatusCode >= 200 && resp.StatusCode < 300 {
			break
		}
		if resp != nil {
			resp.Body.Close()
		}
		// backoff
		time.Sleep(time.Duration(attempt+1) * time.Second)
	}
	if err != nil {
		return setResultFailed(result, int(errors.ErrCodeNetworkError), fmt.Sprintf("download failed: %v", err)), nil
	}
	defer resp.Body.Close()

	// write to temp file first
	tmpPath := remotePath + ".tmp"
	tmpFile, err := os.Create(tmpPath)
	if err != nil {
		return setResultFailed(result, int(errors.ErrCodeFileWriteError), fmt.Sprintf("create temp file failed: %v", err)), nil
	}
	defer tmpFile.Close()

	// Determine bandwidthLimit bytes/s from MB/s if set
	var written int64
	if task.FileTransfer.BandwidthLimit > 0 {
		bytesPerSec := int64(task.FileTransfer.BandwidthLimit) * 1024 * 1024
		written, err = rateLimitedCopy(ctx, tmpFile, resp.Body, bytesPerSec)
	} else {
		written, err = io.Copy(tmpFile, resp.Body)
	}
	if err != nil {
		return setResultFailed(result, int(errors.ErrCodeFileWriteError), fmt.Sprintf("write temp file failed: %v", err)), nil
	}

	// 校验 checksum if provided
	if task.FileTransfer.Checksum != "" {
		if _, err := tmpFile.Seek(0, io.SeekStart); err != nil {
			return setResultFailed(result, int(errors.ErrCodeFileReadError), fmt.Sprintf("seek tmp file failed: %v", err)), nil
		}
		h := sha256.New()
		if _, err := io.Copy(h, tmpFile); err != nil {
			return setResultFailed(result, int(errors.ErrCodeFileReadError), fmt.Sprintf("compute checksum failed: %v", err)), nil
		}
		sum := fmt.Sprintf("%x", h.Sum(nil))
		if sum != task.FileTransfer.Checksum {
			return setResultFailed(result, int(errors.ErrCodeFileTransferFailed), fmt.Sprintf("checksum mismatch: expected %s got %s", task.FileTransfer.Checksum, sum)), nil
		}
	}

	// move tmp to final path
	if err := os.Rename(tmpPath, remotePath); err != nil {
		return setResultFailed(result, int(errors.ErrCodeFileWriteError), fmt.Sprintf("move temp file failed: %v", err)), nil
	}

	logCallback(fmt.Sprintf("File downloaded from URL successfully: %s -> %s (%d bytes)", downloadURL, remotePath, written))

	// record metrics
	transferDuration := time.Since(downloadStartTime)
	metrics.GetMetrics().RecordNetworkTransfer(written, transferDuration)

	return setResultSuccess(result, fmt.Sprintf("Downloaded %d bytes from %s to %s", written, downloadURL, remotePath), 0), nil
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

// rateLimitedCopy 从 src 复制到 dst，限制速率（bytesPerSec），ctx 用于取消/超时
func rateLimitedCopy(ctx context.Context, dst io.Writer, src io.Reader, bytesPerSec int64) (int64, error) {
	if bytesPerSec <= 0 {
		return io.Copy(dst, src)
	}

	limiter := rate.NewLimiter(rate.Limit(bytesPerSec), int(bytesPerSec)) // burst = bytesPerSec
	buf := make([]byte, 32*1024)
	var total int64
	for {
		n, rerr := src.Read(buf)
		if n > 0 {
			// 等待对应的令牌
			if err := limiter.WaitN(ctx, n); err != nil {
				return total, err
			}
			wn, werr := dst.Write(buf[:n])
			total += int64(wn)
			if werr != nil {
				return total, werr
			}
			if wn != n {
				return total, io.ErrShortWrite
			}
		}
		if rerr == io.EOF {
			break
		}
		if rerr != nil {
			return total, rerr
		}
	}
	return total, nil
}

// setResultFailed 统一设置失败结果
func setResultFailed(result *api.TaskResult, errCode int, errMsg string) *api.TaskResult {
	result.Status = "failed"
	result.ErrorCode = errCode
	result.ErrorMsg = errMsg
	result.FinishedAt = time.Now().Unix()
	return result
}

// setResultSuccess 统一设置成功结果
func setResultSuccess(result *api.TaskResult, logMsg string, exitCode int) *api.TaskResult {
	result.Status = "success"
	result.ExitCode = exitCode
	result.FinishedAt = time.Now().Unix()
	result.Log = logMsg
	return result
}
