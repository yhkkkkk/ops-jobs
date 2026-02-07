//go:build integration

package server

import (
	"sync"
	"time"
)

var (
	wsBlockMu    sync.Mutex
	wsBlockUntil = make(map[string]time.Time)
)

func setWSBlock(agentID string, duration time.Duration) {
	if agentID == "" || duration <= 0 {
		return
	}
	wsBlockMu.Lock()
	wsBlockUntil[agentID] = time.Now().Add(duration)
	wsBlockMu.Unlock()
}

func shouldBlockWS(agentID string) bool {
	if agentID == "" {
		return false
	}
	wsBlockMu.Lock()
	defer wsBlockMu.Unlock()
	until, ok := wsBlockUntil[agentID]
	if !ok {
		return false
	}
	if time.Now().After(until) {
		delete(wsBlockUntil, agentID)
		return false
	}
	return true
}
