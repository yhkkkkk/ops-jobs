package websocket

import (
	"bufio"
	"context"
	"encoding/json"
	"fmt"
	"os"
	"path/filepath"
	"sync"
	"time"

	"ops-job-agent-server/internal/logger"

	"github.com/redis/go-redis/v9"
	"github.com/spf13/cast"
)

// AckStore 持久化去重存储，优先 Redis；失败时回退到文件+内存。
type AckStore struct {
	mu          sync.Mutex
	redisKey    string
	rdb         *redis.Client
	redisEnable bool
	ttl         time.Duration

	// fallback
	filePath   string
	mem        map[string]int64
	fileLoaded bool
}

type ackRecord struct {
	ID string `json:"id"`
	Ts int64  `json:"ts"`
}

// NewAckStore 创建持久化的 AckStore
func NewAckStore(rdb *redis.Client, agentServerID string) *AckStore {
	fileName := fmt.Sprintf("ack_store_%s.log", agentServerID)
	filePath := filepath.Join(os.TempDir(), fileName)

	ackStore := &AckStore{
		redisKey:    fmt.Sprintf("agent-server:acks:%s", agentServerID),
		rdb:         rdb,
		redisEnable: rdb != nil,
		ttl:         10 * time.Minute, // 默认10分钟TTL
		filePath:    filePath,
		mem:         make(map[string]int64),
	}

	if rdb != nil {
		logger.GetLogger().WithField("redis_key", ackStore.redisKey).Info("AckStore initialized with Redis persistence")
	} else {
		logger.GetLogger().WithField("file", filePath).Warn("Redis not provided, AckStore will use file+memory fallback")
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

	now := time.Now().Unix()

	// 1) Redis 优先
	if s.redisEnable {
		if seen, ok := s.checkRedis(id, now); ok {
			return seen
		}
	}

	// 2) 文件 + 内存兜底
	s.ensureLoaded(now)

	if ts, ok := s.mem[id]; ok && now-ts < int64(s.ttl.Seconds()) {
		return true
	}

	// 标记为已处理
	s.mem[id] = now
	_ = s.appendFile(id, now)

	return false
}

func (s *AckStore) checkRedis(id string, now int64) (bool, bool) {
	ctx, cancel := context.WithTimeout(context.Background(), 2*time.Second)
	defer cancel()

	result := s.rdb.HGet(ctx, s.redisKey, id)
	if result.Err() == nil {
		if timestampStr := result.Val(); timestampStr != "" {
			if ts, err := cast.ToInt64E(timestampStr); err == nil {
				if now-ts < int64(s.ttl.Seconds()) {
					return true, true
				}
			}
		}
	}

	// 写入 redis
	if err := s.rdb.HSet(ctx, s.redisKey, id, now).Err(); err != nil {
		logger.GetLogger().WithError(err).WithFields(map[string]interface{}{
			"redis_key":  s.redisKey,
			"message_id": id,
		}).Warn("Failed to mark message as seen in Redis, falling back to file+memory")
		return false, false
	}

	if err := s.rdb.Expire(ctx, s.redisKey, s.ttl).Err(); err != nil {
		logger.GetLogger().WithError(err).WithField("redis_key", s.redisKey).Warn("Failed to set expiration on AckStore key")
	}

	logger.GetLogger().WithFields(map[string]interface{}{
		"redis_key":  s.redisKey,
		"message_id": id,
	}).Debug("Message marked as seen in Redis AckStore")

	return false, true
}

func (s *AckStore) ensureLoaded(now int64) {
	if s.fileLoaded {
		s.gcMem(now)
		return
	}

	file, err := os.Open(s.filePath)
	if err == nil {
		defer file.Close()
		scanner := bufio.NewScanner(file)
		for scanner.Scan() {
			var rec ackRecord
			if err := json.Unmarshal(scanner.Bytes(), &rec); err != nil {
				continue
			}
			if rec.ID == "" {
				continue
			}
			if now-rec.Ts < int64(s.ttl.Seconds()) {
				s.mem[rec.ID] = rec.Ts
			}
		}
	}
	s.fileLoaded = true
	s.gcMem(now)
}

func (s *AckStore) appendFile(id string, ts int64) error {
	file, err := os.OpenFile(s.filePath, os.O_CREATE|os.O_APPEND|os.O_WRONLY, 0600)
	if err != nil {
		logger.GetLogger().WithError(err).WithField("file", s.filePath).Warn("AckStore fallback file open failed")
		return err
	}
	defer file.Close()

	rec := ackRecord{ID: id, Ts: ts}
	data, err := json.Marshal(rec)
	if err != nil {
		return err
	}
	data = append(data, '\n')
	if _, err := file.Write(data); err != nil {
		logger.GetLogger().WithError(err).WithField("file", s.filePath).Warn("AckStore fallback file write failed")
		return err
	}
	return nil
}

func (s *AckStore) gcMem(now int64) {
	for k, v := range s.mem {
		if now-v >= int64(s.ttl.Seconds()) {
			delete(s.mem, k)
		}
	}
}

// Close 关闭 Redis 连接
func (s *AckStore) Close() {
	s.mu.Lock()
	defer s.mu.Unlock()

	if s.redisEnable && s.rdb != nil {
		s.rdb.Close()
		s.redisEnable = false
		logger.GetLogger().WithField("redis_key", s.redisKey).Info("AckStore Redis connection closed")
	}
}
