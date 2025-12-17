package api

// AgentInfo 是向控制面注册时上报、以及控制面返回的 agent 信息
type AgentInfo struct {
	ID      string            `json:"id,omitempty"`
	Name    string            `json:"name"`
	Labels  map[string]string `json:"labels,omitempty"`
	Version string            `json:"version,omitempty"`
	System  *SystemInfo       `json:"system"`
	WSURL   string            `json:"ws_url,omitempty"`
	Token   string            `json:"token,omitempty"` // 注册成功后返回的正式 token（首次注册后由控制面签发）
}

// TaskSpec 控制面下发的任务定义
type TaskSpec struct {
	ID         string            `json:"id"`
	Name       string            `json:"name"`
	Type       string            `json:"type,omitempty"`        // script/file_transfer/command
	Command    string            `json:"command,omitempty"`     // 要执行的命令或脚本内容
	ScriptType string            `json:"script_type,omitempty"` // shell/python/powershell
	Args       []string          `json:"args,omitempty"`        // 参数
	Env        map[string]string `json:"env,omitempty"`         // 环境变量
	TimeoutSec int               `json:"timeout_sec,omitempty"` // 超时时间
	WorkDir    string            `json:"work_dir,omitempty"`    // 工作目录
	// 文件传输相关
	FileTransfer *FileTransferSpec `json:"file_transfer,omitempty"`
}

// FileTransferSpec 文件传输规范
type FileTransferSpec struct {
	Type           string `json:"type"` // upload/download
	LocalPath      string `json:"local_path"`
	RemotePath     string `json:"remote_path"`
	Content        []byte `json:"content,omitempty"`         // 上传文件内容
	BandwidthLimit int    `json:"bandwidth_limit,omitempty"` // 带宽限制（KB/s），0表示不限制
}

// TaskResult 上报给控制面的执行结果
type TaskResult struct {
	TaskID     string `json:"task_id"`
	Status     string `json:"status"`             // pending/running/success/failed/cancelled
	ExitCode   int    `json:"exit_code"`          // 进程退出码
	Log        string `json:"log"`                // 执行日志（可以是增量或完整）
	LogSize    int64  `json:"log_size,omitempty"` // 日志大小（字节）
	StartedAt  int64  `json:"started_at"`         // unix 秒
	FinishedAt int64  `json:"finished_at"`        // unix 秒
	ErrorMsg   string `json:"error_msg,omitempty"`
	ErrorCode  int    `json:"error_code,omitempty"` // 错误码（统一错误码体系）
	// 实时日志上报
	IsIncremental bool `json:"is_incremental,omitempty"` // 是否为增量日志
}

// SystemInfo 描述 agent 所在主机的关键信息
type SystemInfo struct {
	Hostname    string             `json:"hostname"`
	OS          string             `json:"os"`
	Arch        string             `json:"arch"`
	IPs         []string           `json:"ips,omitempty"`
	CPUUsage    float64            `json:"cpu_usage,omitempty"`    // CPU 使用率百分比
	MemoryUsage float64            `json:"memory_usage,omitempty"` // 内存使用率百分比
	DiskUsage   map[string]float64 `json:"disk_usage,omitempty"`   // 磁盘使用率，key 为挂载点
	LoadAvg     []float64          `json:"load_avg,omitempty"`     // 负载平均值（Unix）
	Uptime      int64              `json:"uptime,omitempty"`       // 系统运行时间（秒）
}

// HeartbeatPayload 控制面期望的心跳数据
type HeartbeatPayload struct {
	Timestamp int64       `json:"timestamp"`
	System    *SystemInfo `json:"system,omitempty"`
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
