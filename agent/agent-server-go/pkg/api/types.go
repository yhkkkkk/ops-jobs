package api

// AgentInfo Agent 信息
type AgentInfo struct {
	ID      string            `json:"id,omitempty"`
	Name    string            `json:"name"`
	Token   string            `json:"token,omitempty"`
	Labels  map[string]string `json:"labels,omitempty"`
	System  *SystemInfo       `json:"system,omitempty"`
	Status  string            `json:"status,omitempty"` // active/inactive
}

// SystemInfo 系统信息
type SystemInfo struct {
	Hostname    string             `json:"hostname"`
	OS          string             `json:"os"`
	Arch        string             `json:"arch"`
	IPs         []string           `json:"ips,omitempty"`
	CPUUsage    float64            `json:"cpu_usage,omitempty"`
	MemoryUsage float64            `json:"memory_usage,omitempty"`
	DiskUsage   map[string]float64 `json:"disk_usage,omitempty"`
	LoadAvg     []float64          `json:"load_avg,omitempty"`
	Uptime      int64              `json:"uptime,omitempty"`
}

// TaskSpec 任务定义
type TaskSpec struct {
	ID         string            `json:"id"`
	Name       string            `json:"name"`
	Type       string            `json:"type,omitempty"`        // script/file_transfer/command
	Command    string            `json:"command,omitempty"`     // 要执行的命令或脚本内容
	ScriptType string            `json:"script_type,omitempty"` // shell/python/powershell
	Args       []string          `json:"args,omitempty"`
	Env        map[string]string `json:"env,omitempty"`
	TimeoutSec int               `json:"timeout_sec,omitempty"`
	WorkDir    string            `json:"work_dir,omitempty"`
	FileTransfer *FileTransferSpec `json:"file_transfer,omitempty"`
}

// FileTransferSpec 文件传输规范
type FileTransferSpec struct {
	Type          string `json:"type"` // upload/download
	LocalPath     string `json:"local_path"`
	RemotePath    string `json:"remote_path"`
	Content       []byte `json:"content,omitempty"`
	BandwidthLimit int   `json:"bandwidth_limit,omitempty"`
}

// TaskResult 任务执行结果
type TaskResult struct {
	TaskID     string `json:"task_id"`
	Status     string `json:"status"` // pending/running/success/failed/cancelled
	ExitCode   int    `json:"exit_code"`
	Log        string `json:"log,omitempty"`
	LogSize    int64  `json:"log_size,omitempty"`
	StartedAt  int64  `json:"started_at"`
	FinishedAt int64  `json:"finished_at"`
	ErrorMsg   string `json:"error_msg,omitempty"`
	ErrorCode  int    `json:"error_code,omitempty"`
}

// HeartbeatPayload 心跳数据
type HeartbeatPayload struct {
	Timestamp int64       `json:"timestamp"`
	System    *SystemInfo `json:"system,omitempty"`
}

// LogEntry 日志条目
type LogEntry struct {
	Timestamp int64  `json:"timestamp"`
	Content   string `json:"content"`
	Stream    string `json:"stream"` // stdout/stderr
	TaskID    string `json:"task_id,omitempty"` // 任务 ID（用于日志聚合）
}

// PushLogsRequest 批量推送日志请求
type PushLogsRequest struct {
	TaskID string     `json:"task_id"`
	Logs   []LogEntry `json:"logs"`
}

// WebSocketMessage WebSocket 消息
type WebSocketMessage struct {
	Type    string                 `json:"type"` // heartbeat/task/task_result/log/cancel_task
	TaskID  string                 `json:"task_id,omitempty"`
	Task    *TaskSpec              `json:"task,omitempty"`
	Result  *TaskResult            `json:"result,omitempty"`
	Logs    []LogEntry             `json:"logs,omitempty"`
	Payload map[string]interface{} `json:"payload,omitempty"`
}

// RegisterRequest Agent 注册请求
type RegisterRequest struct {
	Name   string            `json:"name"`
	Token  string            `json:"token,omitempty"`
	Labels map[string]string `json:"labels,omitempty"`
	System *SystemInfo       `json:"system,omitempty"`
}

// RegisterResponse Agent 注册响应
type RegisterResponse struct {
	ID     string `json:"id"`
	Name   string `json:"name"`
	Status string `json:"status"`
	WSURL  string `json:"ws_url,omitempty"`
}

