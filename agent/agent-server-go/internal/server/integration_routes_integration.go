//go:build integration

package server

import (
	"context"
	"net/http"
	"os"
	"sync"
	"time"

	"ops-job-agent-server/internal/constants"
	serrors "ops-job-agent-server/internal/errors"
	"ops-job-agent-server/pkg/api"

	"github.com/gin-gonic/gin"
	"github.com/spf13/cast"
)

type integrationStore struct {
	mu      sync.Mutex
	logs    []map[string]interface{}
	results []*api.TaskResult
}

func (s *integrationStore) PushLogsByExecutionID(_ context.Context, _ string, entries []map[string]interface{}) error {
	s.mu.Lock()
	defer s.mu.Unlock()
	s.logs = append(s.logs, entries...)
	return nil
}

func (s *integrationStore) PushResult(_ context.Context, _ string, result *api.TaskResult) error {
	s.mu.Lock()
	defer s.mu.Unlock()
	if result != nil {
		s.results = append(s.results, result)
	}
	return nil
}

func (s *integrationStore) reset() {
	s.mu.Lock()
	defer s.mu.Unlock()
	s.logs = nil
	s.results = nil
}

var integrationSink = &integrationStore{}

func setupIntegrationRoutes(s *Server) {
	if os.Getenv("AGENT_SERVER_INTEGRATION") != "1" {
		return
	}

	// override sinks for integration assertions
	s.logStream = integrationSink
	s.resultStream = integrationSink

	s.engine.GET("/_test/logs", func(c *gin.Context) {
		integrationSink.mu.Lock()
		defer integrationSink.mu.Unlock()
		c.JSON(http.StatusOK, gin.H{"logs": integrationSink.logs})
	})
	s.engine.GET("/_test/results", func(c *gin.Context) {
		integrationSink.mu.Lock()
		defer integrationSink.mu.Unlock()
		c.JSON(http.StatusOK, gin.H{"results": integrationSink.results})
	})
	s.engine.POST("/_test/reset", func(c *gin.Context) {
		integrationSink.reset()
		c.JSON(http.StatusOK, gin.H{"ok": true})
	})

	s.engine.POST("/_test/agents/:id/disconnect", func(c *gin.Context) {
		agentID := c.Param("id")
		if blockMsStr := c.Query("block_ms"); blockMsStr != "" {
			if blockMs, err := cast.ToIntE(blockMsStr); err == nil && blockMs > 0 {
				setWSBlock(agentID, time.Duration(blockMs)*time.Millisecond)
			}
		}
		conn, exists := s.agentManager.Get(agentID)
		if !exists {
			c.JSON(http.StatusNotFound, gin.H{"error": serrors.ErrAgentNotFound.Error()})
			return
		}
		if conn.Conn != nil {
			_ = conn.Conn.Close()
		}
		conn.MarkDisconnected()
		c.JSON(http.StatusOK, gin.H{"status": constants.StatusInactive})
	})
}
