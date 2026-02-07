package api

// AgentInfo Agent 信息
type AgentInfo struct {
	ID     string            `json:"id,omitempty"`
	Name   string            `json:"name"`
	Token  string            `json:"token,omitempty"`
	Labels map[string]string `json:"labels,omitempty"`
	System *SystemInfo       `json:"system,omitempty"`
	Status string            `json:"status,omitempty"` // active/inactive
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

// HeartbeatPayload 控制面期望的心跳数据
type HeartbeatPayload struct {
	Timestamp int64       `json:"timestamp"`
	System    *SystemInfo `json:"system,omitempty"`
}

// TaskSpec 任务定义
type TaskSpec struct {
	ID           string            `json:"id"`
	Name         string            `json:"name"`
	Type         string            `json:"type,omitempty"`        // script/file_transfer/command
	Command      string            `json:"command,omitempty"`     // 要执行的命令或脚本内容
	ScriptType   string            `json:"script_type,omitempty"` // shell/python/powershell
	Args         []string          `json:"args,omitempty"`
	Env          map[string]string `json:"env,omitempty"`
	TimeoutSec   int               `json:"timeout_sec,omitempty"`
	WorkDir      string            `json:"work_dir,omitempty"`
	FileTransfer *FileTransferSpec `json:"file_transfer,omitempty"`
	// ExecutionRecord 关联信息（用于重试和状态跟踪）
	ExecutionID  string `json:"execution_id,omitempty"`   // ExecutionRecord的execution_id
	StepID       string `json:"step_id,omitempty"`        // ExecutionStep的ID（如果是工作流）
	HostID       int    `json:"host_id,omitempty"`        // 目标主机ID
	IsRetry      bool   `json:"is_retry,omitempty"`       // 是否为重试任务
	RetryCount   int    `json:"retry_count,omitempty"`    // 当前重试次数
	ParentTaskID string `json:"parent_task_id,omitempty"` // 父任务ID（用于重试链）
}

// FileTransferSpec 文件传输规范（artifact 上传）
type FileTransferSpec struct {
	RemotePath     string            `json:"remote_path"`               // 目标保存路径
	BandwidthLimit int               `json:"bandwidth_limit,omitempty"` // MB/s
	DownloadURL    string            `json:"download_url"`              // 制品下载 URL
	Checksum       string            `json:"checksum,omitempty"`        // sha256
	Size           int64             `json:"size,omitempty"`            // 字节
	AuthHeaders    map[string]string `json:"auth_headers,omitempty"`    // 认证头
}

// TaskResult 任务执行结果
type TaskResult struct {
	TaskID     string `json:"task_id"`
	Status     string `json:"status"` // pending/running/success/failed/cancelled
	ExitCode   int    `json:"exit_code"`
	Log        string `json:"log,omitempty"`
	LogSize    int64  `json:"log_size,omitempty"`
	LogPointer string `json:"log_pointer,omitempty"`
	StartedAt  int64  `json:"started_at,omitempty"`
	FinishedAt int64  `json:"finished_at,omitempty"`
	ErrorMsg   string `json:"error_msg,omitempty"`
	ErrorCode  int    `json:"error_code,omitempty"`
}

// RegisterRequest Agent注册请求
type RegisterRequest struct {
	Name   string            `json:"name"`
	Token  string            `json:"token,omitempty"`
	Labels map[string]string `json:"labels,omitempty"`
	System *SystemInfo       `json:"system,omitempty"`
	HostID int               `json:"host_id,omitempty"`
}

// RegisterResponse Agent注册响应
type RegisterResponse struct {
	ID     string `json:"id"`
	Name   string `json:"name"`
	Status string `json:"status"`
	WSURL  string `json:"ws_url,omitempty"`
}

// WebSocketMessage 通过 WebSocket 传输的消息格式
type WebSocketMessage struct {
	Type      string                 `json:"type"`
	MessageID string                 `json:"message_id,omitempty"`
	AckID     string                 `json:"ack_id,omitempty"`
	Task      *TaskSpec              `json:"task,omitempty"`
	Tasks     []*TaskSpec            `json:"tasks,omitempty"` // 批量任务
	TaskID    string                 `json:"task_id,omitempty"`
	TaskIDs   []string               `json:"task_ids,omitempty"` // 批量任务ID
	Result    *TaskResult            `json:"result,omitempty"`
	Logs      []LogEntry             `json:"logs,omitempty"`
	Payload   map[string]interface{} `json:"payload,omitempty"`
	Progress  *ProgressPayload       `json:"progress,omitempty"`
}

// ProgressPayload 用于传输进度信息（预留）
type ProgressPayload struct {
	Percent float64 `json:"percent,omitempty"`
	Speed   int64   `json:"speed,omitempty"`
}

// LogEntry 日志条目
type LogEntry struct {
	Timestamp int64  `json:"timestamp"`
	Level     string `json:"level"`
	Content   string `json:"content"`
	Stream    string `json:"stream,omitempty"`
	TaskID    string `json:"task_id,omitempty"`
	HostID    int    `json:"host_id,omitempty"`
	HostName  string `json:"host_name,omitempty"`
}

// PushLogsRequest 批量推送日志请求
type PushLogsRequest struct {
	TaskID string     `json:"task_id"`
	Logs   []LogEntry `json:"logs"`
}

// ControlRequest Agent 控制请求
type ControlRequest struct {
	Action string `json:"action"` // start/stop/restart
	Reason string `json:"reason,omitempty"`
}

// ControlResponse Agent 控制响应
type ControlResponse struct {
	Message string `json:"message"`
	Status  string `json:"status"`
}

// UpgradeRequest Agent 升级请求
type UpgradeRequest struct {
	TargetVersion string `json:"target_version"`
	DownloadURL   string `json:"download_url"`
	MD5Hash       string `json:"md5_hash,omitempty"`
	SHA256Hash    string `json:"sha256_hash,omitempty"`
}

// UpgradeResponse Agent 升级响应
type UpgradeResponse struct {
	Message string `json:"message"`
	Status  string `json:"status"`
}
