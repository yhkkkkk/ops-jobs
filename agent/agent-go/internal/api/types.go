package api

// AgentInfo 是向控制面注册时上报、以及控制面返回的 agent 信息
type AgentInfo struct {
	ID      string      `json:"id,omitempty"`
	Name    string      `json:"name"`
	Version string      `json:"version,omitempty"`
	System  *SystemInfo `json:"system"`
	WSURL   string      `json:"ws_url,omitempty"`
	Token   string      `json:"token,omitempty"`   // 注册成功后返回的正式 token（首次注册后由控制面签发）
	HostID  int         `json:"host_id,omitempty"` // 控制面主机ID，用于建立映射关系
}

// TaskSpec 控制面下发的任务定义
type TaskSpec struct {
	ID         string            `json:"id"`
	Name       string            `json:"name"`
	Type       string            `json:"type,omitempty"`        // script/file_transfer/command
	Command    string            `json:"command,omitempty"`     // 要执行的命令或脚本内容
	ScriptType string            `json:"script_type,omitempty"` // shell/python/powershell/perl/javascript/go
	Args       []string          `json:"args,omitempty"`        // 参数
	Env        map[string]string `json:"env,omitempty"`         // 环境变量
	TimeoutSec int               `json:"timeout_sec,omitempty"` // 超时时间
	WorkDir    string            `json:"work_dir,omitempty"`    // 工作目录
	RunAs      string            `json:"run_as,omitempty"`      // 执行用户（用户名）
	// 文件传输相关（artifact 上传：Agent 从 download_url 拉取并写入 remote_path）
	FileTransfer *FileTransferSpec `json:"file_transfer,omitempty"`
}

// FileTransferSpec 文件传输规范（artifact-only，下载 URL -> 远程路径）
type FileTransferSpec struct {
	RemotePath     string            `json:"remote_path"`               // 目标保存路径
	BandwidthLimit int               `json:"bandwidth_limit,omitempty"` // 带宽限制（MB/s），0表示不限制
	DownloadURL    string            `json:"download_url"`              // 制品下载 URL（必填）
	Checksum       string            `json:"checksum,omitempty"`        // sha256 校验（可选）
	Size           int64             `json:"size,omitempty"`            // 文件大小（字节，可选）
	AuthHeaders    map[string]string `json:"auth_headers,omitempty"`    // 可选认证头
}

// TaskResult 上报给控制面的执行结果
type TaskResult struct {
	TaskID     string `json:"task_id"`
	Status     string `json:"status"`                // pending/running/success/failed/cancelled
	ExitCode   int    `json:"exit_code"`             // 进程退出码
	Log        string `json:"log"`                   // 执行日志（可以是增量或完整）
	LogSize    int64  `json:"log_size,omitempty"`    // 日志大小（字节）
	LogPointer string `json:"log_pointer,omitempty"` // 日志指针（例如 Redis Stream 最后ID或归档路径）
	StartedAt  int64  `json:"started_at"`            // unix 秒
	FinishedAt int64  `json:"finished_at"`           // unix 秒
	ErrorMsg   string `json:"error_msg,omitempty"`
	ErrorCode  int    `json:"error_code,omitempty"` // 错误码（统一错误码体系）
	// 实时日志上报
	IsIncremental bool `json:"is_incremental,omitempty"` // 是否为增量日志
}

// SystemInfo 描述 agent 所在主机的关键信息（简化版，不再包含CPU/内存/磁盘等资源指标）
type SystemInfo struct {
	Hostname string   `json:"hostname"`
	OS       string   `json:"os"`
	Arch     string   `json:"arch"`
	IPs      []string `json:"ips,omitempty"`
}

// HeartbeatPayload 控制面期望的心跳数据（简化版，不再包含系统资源）
type HeartbeatPayload struct {
	Timestamp int64 `json:"timestamp"`
}

// LogEntry 日志条目（用于批量推送）
type LogEntry struct {
	Timestamp int64  `json:"timestamp"` // unix 秒
	Level     string `json:"level"`     // info/warn/error
	Content   string `json:"content"`
	Stream    string `json:"stream,omitempty"`  // stdout/stderr
	TaskID    string `json:"task_id,omitempty"` // 任务 ID（用于日志聚合）
	HostID    int    `json:"host_id,omitempty"`
	HostName  string `json:"host_name,omitempty"`
}

// PushLogsRequest 批量推送日志请求
type PushLogsRequest struct {
	TaskID string     `json:"task_id"`
	Logs   []LogEntry `json:"logs"`
}
