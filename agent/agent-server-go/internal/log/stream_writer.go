package log

import (
	"container/ring"
	"context"
	"fmt"
	"sync"

	"ops-job-agent-server/internal/config"

	"github.com/redis/go-redis/v9"
)

// StreamWriter 写日志到 Redis Stream（统一流，按 execution_id 字段区分）
type StreamWriter struct {
	client *redis.Client
	key    string // 固定的 Stream key，如 "agent_logs"

	mu   sync.Mutex
	rbuf *ring.Ring
	size int
	cap  int
}

// NewStreamWriter 创建流写入器，使用注入的Redis客户端。
// 若配置开启日志流但 Redis客户端为空，则返回错误阻止启动。
func NewStreamWriter(rdb *redis.Client, cfg *config.Config) (*StreamWriter, error) {
	if !cfg.LogStream.Enabled {
		return nil, nil
	}
	if rdb == nil {
		return nil, fmt.Errorf("log stream enabled but redis client not provided")
	}
	const defaultCap = 1000
	return &StreamWriter{
		client: rdb,
		key:    cfg.LogStream.Key,
		rbuf:   ring.New(defaultCap),
		cap:    defaultCap,
	}, nil
}

// pushAll 将已缓冲的 + 新的条目统一返回，并清空缓冲
func (w *StreamWriter) pushAll(newEntries []map[string]interface{}) []map[string]interface{} {
	// 取出现有缓冲
	var buffered []map[string]interface{}
	if w.size > 0 {
		buffered = make([]map[string]interface{}, 0, w.size)
		w.rbuf.Do(func(v interface{}) {
			if v != nil {
				buffered = append(buffered, v.(map[string]interface{}))
			}
		})
	}

	// 清空 ring
	w.rbuf = ring.New(w.cap)
	w.size = 0

	// 拼接
	all := make([]map[string]interface{}, 0, len(buffered)+len(newEntries))
	all = append(all, buffered...)
	all = append(all, newEntries...)
	return all
}

// bufferFailed 将写入失败的条目放回 ring（覆盖最旧）
func (w *StreamWriter) bufferFailed(entries []map[string]interface{}) {
	for _, e := range entries {
		w.rbuf.Value = e
		w.rbuf = w.rbuf.Next()
		if w.size < w.cap {
			w.size++
		}
	}
}

// PushLogsByExecutionID 按 execution_id 写入日志到统一流（失败时 ring 缓存，成功清空缓存）
func (w *StreamWriter) PushLogsByExecutionID(ctx context.Context, executionID string, entries []map[string]interface{}) error {
	if w == nil || w.client == nil || len(entries) == 0 {
		return nil
	}

	w.mu.Lock()
	all := w.pushAll(entries)
	w.mu.Unlock()

	pipe := w.client.Pipeline()
	for _, entry := range all {
		entry["execution_id"] = executionID
		pipe.XAdd(ctx, &redis.XAddArgs{
			Stream: w.key, // 使用固定 key
			Values: entry,
		})
	}

	if _, err := pipe.Exec(ctx); err != nil {
		w.mu.Lock()
		w.bufferFailed(all)
		w.mu.Unlock()
		return err
	}

	return nil
}
