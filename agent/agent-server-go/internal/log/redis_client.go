package log

import (
	"context"
	"fmt"
	"time"

	"ops-job-agent-server/internal/config"

	"github.com/redis/go-redis/v9"
)

// NewRedisClient 创建 Redis 客户端（三种 StreamWriter 共用）
func NewRedisClient(cfg *config.Config) (*redis.Client, error) {
	if !cfg.Redis.Enabled {
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
	return rdb, nil
}
