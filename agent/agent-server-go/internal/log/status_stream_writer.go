package log

import (
	"context"
	"fmt"
	"time"

	"ops-job-agent-server/internal/config"

	"github.com/redis/go-redis/v9"
)

// StatusStreamWriter 写 Agent 在线状态/心跳到 Redis Stream
type StatusStreamWriter struct {
	client *redis.Client
	key    string
}

func NewStatusStreamWriter(cfg *config.Config) (*StatusStreamWriter, error) {
	if !cfg.Redis.Enabled || !cfg.StatusStream.Enabled {
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
	return w.client.XAdd(ctx, &redis.XAddArgs{
		Stream: w.key,
		Values: fields,
	}).Err()
}


