package websocket

import (
	"sync"
	"time"
)

// AckStore 简易去重存储，记录已处理的 message_id，TTL 控制。
type AckStore struct {
	mu    sync.Mutex
	ttl   time.Duration
	store map[string]time.Time
	max   int
}

func NewAckStore(ttl time.Duration, max int) *AckStore {
	if ttl <= 0 {
		ttl = 10 * time.Minute
	}
	if max <= 0 {
		max = 2000
	}
	return &AckStore{
		ttl:   ttl,
		max:   max,
		store: make(map[string]time.Time),
	}
}

// Seen 检查是否已存在
func (s *AckStore) Seen(id string) bool {
	if id == "" {
		return false
	}
	now := time.Now()
	s.mu.Lock()
	defer s.mu.Unlock()
	if t, ok := s.store[id]; ok {
		if now.Sub(t) < s.ttl {
			return true
		}
		delete(s.store, id)
	}
	// 清理超量
	if len(s.store) >= s.max {
		s.evictLocked(now)
	}
	s.store[id] = now
	return false
}

func (s *AckStore) evictLocked(now time.Time) {
	for k, t := range s.store {
		if now.Sub(t) > s.ttl {
			delete(s.store, k)
		}
	}
	// 如果仍超量，随机删除若干（简单策略）
	for len(s.store) > s.max {
		for k := range s.store {
			delete(s.store, k)
			break
		}
	}
}
