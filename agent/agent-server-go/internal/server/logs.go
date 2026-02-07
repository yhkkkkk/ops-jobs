package server

import (
	"context"
	"fmt"
	"sort"
	"strings"
	"time"

	serrors "ops-job-agent-server/internal/errors"
	"ops-job-agent-server/internal/logger"
	"ops-job-agent-server/pkg/api"

	"github.com/spf13/cast"
)

// pushLogs 将日志写入日志流（按 execution_id 聚合）
func (s *Server) pushLogs(ctx context.Context, agentID, taskID string, logs []api.LogEntry) error {
	if len(logs) == 0 {
		return nil
	}
	if s.logStream == nil {
		return serrors.ErrLogStreamUnavailable
	}
	executionID, hostID, err := parseTaskID(taskID)
	if err != nil {
		return err
	}

	now := time.Now().UnixMilli()
	entries := make([]map[string]interface{}, 0, len(logs))
	for _, log := range logs {
		entry := map[string]interface{}{
			"task_id":  taskID,
			"agent_id": agentID,
			"content":  log.Content,
		}
		if log.TaskID != "" {
			entry["task_id"] = log.TaskID
		}
		if log.Stream != "" {
			entry["stream"] = log.Stream
		}
		if log.Level != "" {
			entry["level"] = log.Level
		}
		ts := log.Timestamp
		if ts == 0 {
			ts = now
		}
		entry["timestamp"] = ts
		if log.HostID != 0 {
			entry["host_id"] = log.HostID
		} else if hostID != 0 {
			entry["host_id"] = hostID
		}
		if log.HostName != "" {
			entry["host_name"] = log.HostName
		}
		entries = append(entries, entry)
	}

	if err := s.logStream.PushLogsByExecutionID(ctx, executionID, entries); err != nil {
		return fmt.Errorf("%w: %v", serrors.ErrLogStreamWriteFailed, err)
	}
	return nil
}

// pushResult 写入任务结果流（若未开启则直接忽略）
func (s *Server) pushResult(ctx context.Context, agentID string, result *api.TaskResult) error {
	if result == nil {
		return nil
	}
	if result.TaskID == "" {
		return serrors.ErrInvalidTaskID
	}
	if s.resultStream == nil {
		return nil
	}
	if err := s.resultStream.PushResult(ctx, agentID, result); err != nil {
		return err
	}
	return nil
}

// parseTaskID 从 task_id 提取 execution_id 和 host_id
// task_id 格式: {execution_id}_{step_id}_{host_id}_{random}
func parseTaskID(taskID string) (string, int, error) {
	trimmed := strings.TrimSpace(taskID)
	if trimmed == "" {
		return "", 0, serrors.ErrInvalidTaskID
	}
	parts := strings.Split(trimmed, "_")
	if len(parts) == 0 || strings.TrimSpace(parts[0]) == "" {
		return "", 0, serrors.ErrInvalidTaskID
	}
	executionID := parts[0]
	hostID := 0
	if len(parts) >= 3 {
		if v, err := cast.ToIntE(parts[2]); err == nil {
			hostID = v
		}
	}
	return executionID, hostID, nil
}

func sortLogsByTimestamp(logs []api.LogEntry) {
	sort.Slice(logs, func(i, j int) bool {
		return logs[i].Timestamp < logs[j].Timestamp
	})
}

// evictOldLogs 尝试从其他任务中淘汰最旧日志，返回是否仍然满
func (s *Server) evictOldLogs(taskLogs map[string][]api.LogEntry, totalBuffered *int, currentTaskID string) bool {
	if totalBuffered == nil || *totalBuffered <= 0 {
		return false
	}
	for taskID, logs := range taskLogs {
		if taskID == currentTaskID || len(logs) == 0 {
			continue
		}
		// 其他任务淘汰最旧日志
		taskLogs[taskID] = logs[1:]
		*totalBuffered--
		if len(taskLogs[taskID]) == 0 {
			delete(taskLogs, taskID)
		}
		return false
	}
	logger.GetLogger().WithField("task_id", currentTaskID).Warn("log buffer full, no eviction candidate")
	return true
}
