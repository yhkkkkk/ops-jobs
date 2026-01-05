package executor

import (
	"context"
	"encoding/base64"
	"fmt"
	"io"
	"os"
	"unicode/utf8"

	"ops-job-agent/internal/api"
	"ops-job-agent/internal/constants"
	"ops-job-agent/internal/errors"
)

// FilePreviewExecutor 负责文件预览读取
type FilePreviewExecutor struct {
	executor *Executor
}

// NewFilePreviewExecutor 创建文件预览执行器
func NewFilePreviewExecutor(executor *Executor) *FilePreviewExecutor {
	return &FilePreviewExecutor{executor: executor}
}

// ExecutePreview 执行文件预览任务（读取小段内容）
func (p *FilePreviewExecutor) ExecutePreview(ctx context.Context, task *api.TaskSpec, logCallback func(string)) (*api.TaskResult, error) {
	if task.FilePreview == nil {
		return nil, fmt.Errorf("file_preview spec required")
	}
	fp := task.FilePreview
	if fp.RemotePath == "" {
		return setResultFailed(&api.TaskResult{TaskID: task.ID}, int(errors.ErrCodeInvalidParam), "remote_path required"), nil
	}

	maxBytes := fp.MaxBytes
	if maxBytes <= 0 || maxBytes > constants.DefaultMaxPreviewBytes {
		maxBytes = constants.DefaultMaxPreviewBytes
	}

	file, err := os.Open(fp.RemotePath)
	if err != nil {
		return setResultFailed(&api.TaskResult{TaskID: task.ID}, int(errors.ErrCodeFileReadError), fmt.Sprintf("open file failed: %v", err)), nil
	}
	defer file.Close()

	info, err := file.Stat()
	if err != nil {
		return setResultFailed(&api.TaskResult{TaskID: task.ID}, int(errors.ErrCodeFileReadError), fmt.Sprintf("stat file failed: %v", err)), nil
	}
	size := info.Size()

	start := int64(0)
	switch fp.Mode {
	case "tail":
		if size > maxBytes {
			start = size - maxBytes
		}
	case "range":
		if fp.Offset > 0 {
			start = fp.Offset
		}
	default: // head or empty
		if fp.Offset > 0 {
			start = fp.Offset
		}
	}

	if start > 0 {
		if _, err := file.Seek(start, io.SeekStart); err != nil {
			return setResultFailed(&api.TaskResult{TaskID: task.ID}, int(errors.ErrCodeFileReadError), fmt.Sprintf("seek file failed: %v", err)), nil
		}
	}

	reader := io.LimitReader(file, maxBytes)
	buf, err := io.ReadAll(reader)
	if err != nil {
		return setResultFailed(&api.TaskResult{TaskID: task.ID}, int(errors.ErrCodeFileReadError), fmt.Sprintf("read file failed: %v", err)), nil
	}

	isTruncated := start+int64(len(buf)) < size

	encoding := fp.Encoding
	if encoding == "" {
		encoding = "utf-8"
	}

	content := ""
	if utf8.Valid(buf) && encoding == "utf-8" {
		content = string(buf)
	} else {
		encoding = "base64"
		content = base64.StdEncoding.EncodeToString(buf)
	}

	result := &api.TaskResult{
		TaskID:     task.ID,
		Status:     constants.StatusSuccess,
		ExitCode:   0,
		StartedAt:  info.ModTime().Unix(), // 粗略填充
		FinishedAt: info.ModTime().Unix(),
		FilePreviewResult: &api.FilePreviewResult{
			Content:     content,
			Encoding:    encoding,
			Size:        size,
			IsTruncated: isTruncated,
			Channel:     "agent_preview",
		},
	}
	return result, nil
}
