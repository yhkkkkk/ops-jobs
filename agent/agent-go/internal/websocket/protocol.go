package websocket

import "ops-job-agent/internal/api"

// Message 是 Agent 与 Agent-Server 之间的统一 WS 消息协议载体。
type Message struct {
	Type      string `json:"type"`
	RequestID string `json:"request_id,omitempty"`
	Timestamp int64  `json:"ts,omitempty"` // unix ms
	TaskID    string `json:"task_id,omitempty"`

	Task   *api.TaskSpec   `json:"task,omitempty"`
	Result *api.TaskResult `json:"result,omitempty"`
	Logs   []api.LogEntry  `json:"logs,omitempty"`

	Payload map[string]interface{} `json:"payload,omitempty"`
	Error   *ErrorPayload          `json:"error,omitempty"`
}

type ErrorPayload struct {
	Code    string `json:"code,omitempty"`
	Message string `json:"message,omitempty"`
}
