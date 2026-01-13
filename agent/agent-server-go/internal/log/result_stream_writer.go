package log

import (
	"context"
	"fmt"
	"strconv"
	"strings"
	"time"

	"ops-job-agent-server/internal/config"
	"ops-job-agent-server/pkg/api"

	"github.com/redis/go-redis/v9"
)

// ResultStreamWriter 写任务结果到 Redis Stream
type ResultStreamWriter struct {
	client *redis.Client
	key    string
}

func NewResultStreamWriter(cfg *config.Config) (*ResultStreamWriter, error) {
	if !cfg.ResultStream.Enabled {
		return nil, nil
	}
	if !cfg.Redis.Enabled {
		return nil, fmt.Errorf("result stream enabled but redis disabled")
	}
	rdb, err := NewRedisClient(cfg)
	if err != nil {
		return nil, err
	}
	return &ResultStreamWriter{client: rdb, key: cfg.ResultStream.Key}, nil
}

func (w *ResultStreamWriter) PushResult(ctx context.Context, agentID string, result *api.TaskResult) error {
	if w == nil || w.client == nil || result == nil {
		return nil
	}
	logPointer := result.LogPointer
	if logPointer == "" && result.LogSize > 0 {
		logPointer = "redis:job_logs/" + result.TaskID + "@"
	}

	// 解析 task_id 提取 host_id
	// task_id 格式: {execution_id}_{step_id}_{host_id}_{random}
	hostID := extractHostID(result.TaskID)

	values := map[string]interface{}{
		"task_id":     result.TaskID,
		"agent_id":    agentID,
		"host_id":     hostID, // 添加 host_id 字段供控制面使用
		"status":      result.Status,
		"exit_code":   result.ExitCode,
		"error_msg":   result.ErrorMsg,
		"error_code":  result.ErrorCode,
		"started_at":  result.StartedAt,
		"finished_at": result.FinishedAt,
		"log_size":    result.LogSize,
		"log_pointer": logPointer,
		"received_at": time.Now().UnixMilli(),
	}
	if result.FilePreviewResult != nil {
		values["preview_content"] = result.FilePreviewResult.Content
		values["preview_encoding"] = result.FilePreviewResult.Encoding
		values["preview_is_truncated"] = result.FilePreviewResult.IsTruncated
		values["preview_size"] = result.FilePreviewResult.Size
		values["preview_channel"] = result.FilePreviewResult.Channel
	}
	return w.client.XAdd(ctx, &redis.XAddArgs{
		Stream: w.key,
		Values: values,
		MaxLen: 10000, // 限制 Stream 最大长度，防止无限增长
		Approx: true,  // 使用近似裁剪提升性能
	}).Err()
}

// extractHostID 从 task_id 中提取 host_id
// task_id 格式: {execution_id}_{step_id}_{host_id}_{random}
func extractHostID(taskID string) int {
	parts := strings.Split(taskID, "_")
	if len(parts) >= 3 {
		if hostID, err := strconv.Atoi(parts[2]); err == nil {
			return hostID
		}
	}
	return 0 // 如果解析失败，返回 0
}
