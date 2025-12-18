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
	if !cfg.Redis.Enabled || !cfg.ResultStream.Enabled {
		return nil, nil
	}
	rdb := redis.NewClient(&redis.Options{
		Addr:     cfg.Redis.Addr,
		Password: cfg.Redis.Password,
		DB:       cfg.Redis.DB,
	})
	ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
	defer cancel()
	if err := rdb.Ping(ctx).Err(); err != nil {
		return nil, fmt.Errorf("redis ping failed: %w", err)
	}
	return &ResultStreamWriter{client: rdb, key: cfg.ResultStream.Key}, nil
}

func (w *ResultStreamWriter) PushResult(ctx context.Context, agentID string, result *api.TaskResult) error {
	if w == nil || w.client == nil || result == nil {
		return nil
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
		"received_at": time.Now().UnixMilli(),
	}
	return w.client.XAdd(ctx, &redis.XAddArgs{
		Stream: w.key,
		Values: values,
	}).Err()
}
