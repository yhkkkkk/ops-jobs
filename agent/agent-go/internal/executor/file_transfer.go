package executor

import (
	"context"
	"crypto/sha256"
	stderrors "errors"
	"fmt"
	"io"
	"os"
	"path/filepath"
	"time"

	"github.com/avast/retry-go/v4"
	"github.com/go-resty/resty/v2"
	"golang.org/x/time/rate"

	"ops-job-agent/internal/api"
	"ops-job-agent/internal/constants"
	"ops-job-agent/internal/errors"
	"ops-job-agent/internal/metrics"
)

// FileTransferExecutor 文件传输执行器（artifact 上传：Agent 从 download_url 拉取并写入 remote_path）
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
		return nil, fmt.Errorf("文件传输配置为空")
	}
	if task.FileTransfer.DownloadURL == "" {
		return nil, fmt.Errorf("download_url required")
	}
	if task.FileTransfer.RemotePath == "" {
		return nil, fmt.Errorf("remote_path required")
	}

	startTime := time.Now()
	result := &api.TaskResult{
		TaskID:    task.ID,
		Status:    constants.StatusRunning,
		StartedAt: startTime.Unix(),
	}

	return f.downloadFromURL(ctx, task, result, logCallback)
}

// downloadFromURL 下载 presigned URL 内容到 remotePath（remotePath: 目标文件路径在主机上）
func (f *FileTransferExecutor) downloadFromURL(ctx context.Context, task *api.TaskSpec, result *api.TaskResult, logCallback func(string)) (*api.TaskResult, error) {
	downloadStartTime := time.Now()
	ft := task.FileTransfer
	downloadURL := ft.DownloadURL
	if downloadURL == "" {
		return setResultFailed(result, int(errors.ErrCodeInvalidParam), "download_url 不能为空"), nil
	}

	remotePath := ft.RemotePath
	if remotePath == "" {
		return setResultFailed(result, int(errors.ErrCodeInvalidParam), "remote_path 不能为空"), nil
	}

	// 确保目标目录存在
	if err := ensureDir(remotePath); err != nil {
		return setResultFailed(result, int(errors.ErrCodeFileWriteError), fmt.Sprintf("create remote directory failed: %v", err)), nil
	}

	// 构造 resty 客户端（使用重试库控制重试）
	timeout := time.Duration(constants.DefaultDownloadTimeoutS) * time.Second
	client := resty.New().
		SetTimeout(timeout).
		SetDoNotParseResponse(true)

	var resp *resty.Response
	err := retry.Do(
		func() error {
			r := client.R().SetContext(ctx).SetDoNotParseResponse(true)
			for k, v := range ft.AuthHeaders {
				r.SetHeader(k, v)
			}
			res, reqErr := r.Get(downloadURL)
			if reqErr != nil {
				return reqErr
			}
			if res.StatusCode() < 200 || res.StatusCode() >= 300 {
				return fmt.Errorf("HTTP 状态码异常: %d", res.StatusCode())
			}
			resp = res
			return nil
		},
		retry.Attempts(constants.DownloadRetryCount),
	)
	if err != nil {
		return setResultFailed(result, int(errors.ErrCodeNetworkError), fmt.Sprintf("下载失败: %v", err)), nil
	}
	if resp != nil && resp.RawBody() != nil {
		defer resp.RawBody().Close()
	}

	// 先写临时文件
	tmpPath := remotePath + ".tmp"
	tmpFile, err := os.Create(tmpPath)
	if err != nil {
		return setResultFailed(result, int(errors.ErrCodeFileWriteError), fmt.Sprintf("创建临时文件失败: %v", err)), nil
	}
	defer func() {
		if tmpFile != nil {
			tmpFile.Close()
		}
	}()

	// 若设置，将MB/s转换为字节/秒的带宽限制
	var written int64
	bodyReader := resp.RawBody()
	bytesPerSec := int64(ft.BandwidthLimit) * 1024 * 1024
	written, err = rateLimitedCopy(ctx, tmpFile, bodyReader, bytesPerSec)
	if err != nil {
		if ctx.Err() != nil || stderrors.Is(err, context.DeadlineExceeded) || stderrors.Is(err, context.Canceled) {
			return setResultFailed(result, int(errors.ErrCodeNetworkError), fmt.Sprintf("下载超时: %v", err)), nil
		}
		return setResultFailed(result, int(errors.ErrCodeFileWriteError), fmt.Sprintf("写入临时文件失败: %v", err)), nil
	}

	// 校验 checksum（如提供）
	if ft.Checksum != "" {
		if _, err := tmpFile.Seek(0, io.SeekStart); err != nil {
			return setResultFailed(result, int(errors.ErrCodeFileReadError), fmt.Sprintf("定位临时文件失败: %v", err)), nil
		}
		h := sha256.New()
		if _, err := io.Copy(h, tmpFile); err != nil {
			return setResultFailed(result, int(errors.ErrCodeFileReadError), fmt.Sprintf("计算校验失败: %v", err)), nil
		}
		sum := fmt.Sprintf("%x", h.Sum(nil))
		if sum != ft.Checksum {
			return setResultFailed(result, int(errors.ErrCodeFileTransferFailed), fmt.Sprintf("校验不一致: 期望 %s 实际 %s", ft.Checksum, sum)), nil
		}
	}

	// 关闭句柄再移动，兼容 Windows
	if err := tmpFile.Close(); err != nil {
		return setResultFailed(result, int(errors.ErrCodeFileWriteError), fmt.Sprintf("关闭临时文件失败: %v", err)), nil
	}
	tmpFile = nil

	if err := os.Rename(tmpPath, remotePath); err != nil {
		return setResultFailed(result, int(errors.ErrCodeFileWriteError), fmt.Sprintf("移动临时文件失败: %v", err)), nil
	}

	logCallback(fmt.Sprintf("文件下载成功: %s -> %s (%d 字节)", downloadURL, remotePath, written))

	// 记录网络传输指标
	transferDuration := time.Since(downloadStartTime)
	metrics.GetMetrics().RecordNetworkTransfer(written, transferDuration)

	return setResultSuccess(result, fmt.Sprintf("已从 %s 下载 %d 字节到 %s", downloadURL, written, remotePath), 0), nil
}

// rateLimitedCopy 从 src 复制到 dst，限制速率（bytesPerSec），ctx 用于取消/超时（bytesPerSec<=0 只检查 ctx）
func rateLimitedCopy(ctx context.Context, dst io.Writer, src io.Reader, bytesPerSec int64) (int64, error) {
	var limiter *rate.Limiter
	if bytesPerSec > 0 {
		limiter = rate.NewLimiter(rate.Limit(bytesPerSec), int(bytesPerSec)) // burst = bytesPerSec
	}
	buf := make([]byte, constants.RateLimitBufSize)
	var total int64
	for {
		n, rerr := src.Read(buf)
		if n > 0 {
			if limiter != nil {
				if err := limiter.WaitN(ctx, n); err != nil {
					return total, err
				}
			} else {
				select {
				case <-ctx.Done():
					return total, ctx.Err()
				default:
				}
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
	result.Status = constants.StatusFailed
	result.ErrorCode = errCode
	result.ErrorMsg = errMsg
	result.FinishedAt = time.Now().Unix()
	result.LogPointer = fmt.Sprintf("redis:job_logs/%s@", result.TaskID)
	return result
}

// setResultSuccess 统一设置成功结果
func setResultSuccess(result *api.TaskResult, logMsg string, exitCode int) *api.TaskResult {
	result.Status = constants.StatusSuccess
	result.ExitCode = exitCode
	result.FinishedAt = time.Now().Unix()
	result.Log = logMsg
	result.LogSize = int64(len(logMsg))
	result.LogPointer = fmt.Sprintf("redis:job_logs/%s@", result.TaskID)
	return result
}

// ensureDir 创建 remotePath 父目录
func ensureDir(remotePath string) error {
	dir := filepath.Dir(remotePath)
	if dir == "" || dir == "." || dir == "/" {
		return nil
	}
	return os.MkdirAll(dir, 0755)
}
