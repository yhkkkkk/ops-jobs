package log

import (
	"context"
	"fmt"
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
	values := map[string]interface{}{
		"task_id":     result.TaskID,
		"agent_id":    agentID,
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
	}).Err()
}
