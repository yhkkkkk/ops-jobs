package websocket

import (
	"context"
	"fmt"
	"strconv"
	"sync"
	"time"

	"ops-job-agent-server/internal/logger"

	"github.com/redis/go-redis/v9"
)

// AckStore 持久化去重存储，使用 Redis Hash 记录已处理的 message_id。
type AckStore struct {
	mu       sync.Mutex
	redisKey string
	rdb      *redis.Client
	enabled  bool
	ttl      time.Duration
}

// NewAckStore 创建持久化的 AckStore
func NewAckStore(rdb *redis.Client, agentServerID string) *AckStore {
	ackStore := &AckStore{
		redisKey: fmt.Sprintf("agent-server:acks:%s", agentServerID),
		enabled:  false,
		ttl:      10 * time.Minute, // 默认10分钟TTL
	}

	// 如果提供了Redis客户端，启用AckStore
	if rdb != nil {
		ackStore.rdb = rdb
		ackStore.enabled = true
		logger.GetLogger().WithField("redis_key", ackStore.redisKey).Info("AckStore initialized with Redis persistence")
	} else {
		logger.GetLogger().Warn("Redis client not provided, AckStore will be disabled")
	}

	return ackStore
}

// Seen 检查消息是否已处理，如果未处理则标记为已处理
func (s *AckStore) Seen(id string) bool {
	if id == "" {
		return false
	}

	s.mu.Lock()
	defer s.mu.Unlock()

	if !s.enabled {
		// Redis不可用时，允许所有消息通过（避免阻塞）
		return false
	}

	ctx, cancel := context.WithTimeout(context.Background(), 2*time.Second)
	defer cancel()

	now := time.Now().Unix()

	// 使用 HGET 检查是否存在
	result := s.rdb.HGet(ctx, s.redisKey, id)
	if result.Err() == nil {
		// 已存在，检查是否过期
		if timestampStr := result.Val(); timestampStr != "" {
			if timestamp, err := strconv.ParseInt(timestampStr, 10, 64); err == nil {
				if time.Now().Unix()-timestamp < int64(s.ttl.Seconds()) {
					return true // 未过期，认为是已处理的
				}
			}
		}
	}

	// 不存在或已过期，标记为已处理
	if err := s.rdb.HSet(ctx, s.redisKey, id, now).Err(); err != nil {
		logger.GetLogger().WithError(err).WithFields(map[string]interface{}{
			"redis_key":  s.redisKey,
			"message_id": id,
		}).Warn("Failed to mark message as seen in Redis")
		return false // 出错时允许通过，避免阻塞
	}

	// 设置 Hash 的过期时间
	if err := s.rdb.Expire(ctx, s.redisKey, s.ttl).Err(); err != nil {
		logger.GetLogger().WithError(err).WithField("redis_key", s.redisKey).Warn("Failed to set expiration on AckStore key")
	}

	logger.GetLogger().WithFields(map[string]interface{}{
		"redis_key":  s.redisKey,
		"message_id": id,
	}).Debug("Message marked as seen in persistent AckStore")

	return false
}

// Close 关闭 Redis 连接
func (s *AckStore) Close() {
	s.mu.Lock()
	defer s.mu.Unlock()

	if s.enabled && s.rdb != nil {
		s.rdb.Close()
		s.enabled = false
		logger.GetLogger().WithField("redis_key", s.redisKey).Info("AckStore Redis connection closed")
	}
}
