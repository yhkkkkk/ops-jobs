package log

import (
	"context"
	"fmt"
	"time"

	"ops-job-agent-server/internal/config"

	"github.com/redis/go-redis/v9"
)

// StreamWriter 写日志到 Redis Stream
type StreamWriter struct {
	client *redis.Client
	key    string
}

// NewStreamWriter 创建流写入器，复用 redis 配置
func NewStreamWriter(cfg *config.Config) (*StreamWriter, error) {
	if !cfg.Redis.Enabled || !cfg.LogStream.Enabled {
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
	return &StreamWriter{
		client: rdb,
		key:    cfg.LogStream.Key,
	}, nil
}

// PushLogs 写入日志条目（批量）
// fields 要求包含 task_id/agent_id/host/level/content/timestamp 等，调用侧封装
func (w *StreamWriter) PushLogs(ctx context.Context, entries []map[string]interface{}) error {
	if w == nil || w.client == nil || len(entries) == 0 {
		return nil
	}
	pipe := w.client.Pipeline()
	for _, entry := range entries {
		pipe.XAdd(ctx, &redis.XAddArgs{
			Stream: w.key,
			Values: entry,
		})
	}
	_, err := pipe.Exec(ctx)
	return err
}
