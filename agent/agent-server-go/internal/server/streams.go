package server

import (
	"context"

	logstream "ops-job-agent-server/internal/log"
	"ops-job-agent-server/pkg/api"
)

// LogSink 抽象日志写入，便于测试注入
type LogSink interface {
	PushLogsByExecutionID(ctx context.Context, executionID string, entries []map[string]interface{}) error
}

// ResultSink 抽象结果写入
type ResultSink interface {
	PushResult(ctx context.Context, agentID string, result *api.TaskResult) error
}

// StatusSink 抽象状态写入，便于测试注入
type StatusSink interface {
	PushStatus(ctx context.Context, fields map[string]interface{}) error
}

// ensure LogSink/ResultSink can wrap existing stream writers
type logStreamAdapter struct{ *logstream.StreamWriter }

func (a *logStreamAdapter) PushLogsByExecutionID(ctx context.Context, executionID string, entries []map[string]interface{}) error {
	return a.StreamWriter.PushLogsByExecutionID(ctx, executionID, entries)
}

type resultStreamAdapter struct{ *logstream.ResultStreamWriter }

func (a *resultStreamAdapter) PushResult(ctx context.Context, agentID string, result *api.TaskResult) error {
	return a.ResultStreamWriter.PushResult(ctx, agentID, result)
}

type statusStreamAdapter struct{ *logstream.StatusStreamWriter }

func (a *statusStreamAdapter) PushStatus(ctx context.Context, fields map[string]interface{}) error {
	return a.StatusStreamWriter.PushStatus(ctx, fields)
}
