package log

import (
	"context"
	"fmt"
	"time"

	"github.com/bytedance/sonic"

	"ops-job-agent-server/internal/config"

	"github.com/redis/go-redis/v9"
)

// StatusStreamWriter 写 Agent 在线状态/心跳到 Redis Stream
type StatusStreamWriter struct {
	client *redis.Client
	key    string
}

func NewStatusStreamWriter(rdb *redis.Client, cfg *config.Config) (*StatusStreamWriter, error) {
	if !cfg.StatusStream.Enabled {
		return nil, nil
	}
	if rdb == nil {
		return nil, fmt.Errorf("status stream enabled but redis client not provided")
	}
	return &StatusStreamWriter{client: rdb, key: cfg.StatusStream.Key}, nil
}

// PushStatus 写入一条状态，status 通常为 online/offline
func (w *StatusStreamWriter) PushStatus(ctx context.Context, fields map[string]interface{}) error {
	if w == nil || w.client == nil {
		return nil
	}
	if fields == nil {
		fields = make(map[string]interface{})
	}
	if _, ok := fields["timestamp"]; !ok {
		fields["timestamp"] = time.Now().UnixMilli()
	}

	// Redis Stream 的 XADD 不支持嵌套结构，需要将嵌套的 map 序列化为 json 字符串
	flatFields := make(map[string]interface{})
	for k, v := range fields {
		switch val := v.(type) {
		case map[string]interface{}:
			// 将嵌套的 map 序列化为 json 字符串
			if jsonBytes, err := sonic.Marshal(val); err == nil {
				flatFields[k] = string(jsonBytes)
			}
		default:
			flatFields[k] = v
		}
	}

	return w.client.XAdd(ctx, &redis.XAddArgs{
		Stream: w.key,
		Values: flatFields,
	}).Err()
}
