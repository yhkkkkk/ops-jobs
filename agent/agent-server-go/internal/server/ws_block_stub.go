//go:build !integration

package server

import "time"

func setWSBlock(agentID string, duration time.Duration) {
	_ = agentID
	_ = duration
}

func shouldBlockWS(agentID string) bool {
	_ = agentID
	return false
}
