package log

import (
	"context"

	"ops-job-agent-server/internal/config"

	"github.com/redis/go-redis/v9"
)

// StreamWriter 写日志到 Redis Stream（统一流，按 execution_id 字段区分）
type StreamWriter struct {
	client *redis.Client
	key    string // 固定的 Stream key，如 "agent_logs"
	// 简易内存缓冲区：在 Redis 短暂不可用时暂存少量日志，下一次写入成功时一并刷新
	buffer []map[string]interface{}
}

// NewStreamWriter 创建流写入器，复用 redis 配置
func NewStreamWriter(cfg *config.Config) (*StreamWriter, error) {
	if !cfg.Redis.Enabled || !cfg.LogStream.Enabled {
		return nil, nil
	}
	rdb, err := NewRedisClient(cfg)
	if err != nil {
		return nil, err
	}
	return &StreamWriter{
		client: rdb,
		key:    cfg.LogStream.Key,
		buffer: make([]map[string]interface{}, 0),
	}, nil
}

// PushLogsByExecutionID 按execution_id写入日志到统一流
func (w *StreamWriter) PushLogsByExecutionID(ctx context.Context, executionID string, entries []map[string]interface{}) error {
	if w == nil || w.client == nil || len(entries) == 0 {
		return nil
	}

	// 先把之前缓冲的日志拼接上
	all := make([]map[string]interface{}, 0, len(w.buffer)+len(entries))
	all = append(all, w.buffer...)
	all = append(all, entries...)

	pipe := w.client.Pipeline()
	for _, entry := range all {
		// 添加 execution_id 字段，用于 Python 消费者识别和转发
		entry["execution_id"] = executionID
		pipe.XAdd(ctx, &redis.XAddArgs{
			Stream: w.key, // 使用固定 key
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
