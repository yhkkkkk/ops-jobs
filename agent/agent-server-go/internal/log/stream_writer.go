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
	key    string // 废弃：不再使用统一key
	// 简易内存缓冲区：在 Redis 短暂不可用时暂存少量日志，下一次写入成功时一并刷新
	buffer []map[string]interface{}
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
		buffer: make([]map[string]interface{}, 0),
	}, nil
}

// PushLogsByExecutionID 按execution_id写入日志（新方法）
func (w *StreamWriter) PushLogsByExecutionID(ctx context.Context, executionID string, entries []map[string]interface{}) error {
	if w == nil || w.client == nil || len(entries) == 0 {
		return nil
	}

	streamKey := fmt.Sprintf("job_logs:%s", executionID)

	// 先把之前缓冲的日志拼接上
	all := make([]map[string]interface{}, 0, len(w.buffer)+len(entries))
	all = append(all, w.buffer...)
	all = append(all, entries...)

	pipe := w.client.Pipeline()
	for _, entry := range all {
		pipe.XAdd(ctx, &redis.XAddArgs{
			Stream: streamKey,
			Values: entry,
		})
	}
	// 设置过期时间为12小时
	pipe.Expire(ctx, streamKey, 12*time.Hour)

	_, err := pipe.Exec(ctx)
	if err != nil {
		// 写入失败：更新缓冲区，限制最大长度，避免内存无限增长
		const maxBufferSize = 1000
		if len(all) > maxBufferSize {
			w.buffer = all[len(all)-maxBufferSize:]
		} else {
			w.buffer = all
		}
		return err
	}

	// 写入成功后清空缓冲区
	w.buffer = w.buffer[:0]
	return nil
}

// PushLogs 写入日志条目（批量）
// fields 要求包含 task_id/agent_id/host/level/content/timestamp 等，调用侧封装
func (w *StreamWriter) PushLogs(ctx context.Context, entries []map[string]interface{}) error {
	if w == nil || w.client == nil || len(entries) == 0 {
		return nil
	}

	// 先把之前缓冲的日志拼接上
	all := make([]map[string]interface{}, 0, len(w.buffer)+len(entries))
	all = append(all, w.buffer...)
	all = append(all, entries...)

	pipe := w.client.Pipeline()
	for _, entry := range all {
		pipe.XAdd(ctx, &redis.XAddArgs{
			Stream: w.key,
			Values: entry,
		})
	}
	_, err := pipe.Exec(ctx)
	if err != nil {
		// 写入失败：更新缓冲区，限制最大长度，避免内存无限增长
		const maxBufferSize = 1000
		if len(all) > maxBufferSize {
			w.buffer = all[len(all)-maxBufferSize:]
		} else {
			w.buffer = all
		}
		return err
	}

	// 写入成功后清空缓冲区
	w.buffer = w.buffer[:0]
	return nil
}
