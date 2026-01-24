package constants

const (
	// 任务类型
	TaskTypeScript       = "script"
	TaskTypeFileTransfer = "file_transfer"

	// 任务状态
	StatusPending   = "pending"
	StatusRunning   = "running"
	StatusSuccess   = "success"
	StatusFailed    = "failed"
	StatusCancelled = "cancelled"

	// WebSocket 消息类型（Agent -> Agent-Server）
	MessageTypeTask             = "task"
	MessageTypeTasksBatch       = "tasks_batch"
	MessageTypeCancelTask       = "cancel_task"
	MessageTypeCancelTasksBatch = "cancel_tasks_batch"
	MessageTypeHeartbeat        = "heartbeat"
	MessageTypeLog              = "log"
	MessageTypeTaskResult       = "task_result"
	MessageTypeAck              = "ack"

	// WebSocket 消息类型（Agent-Server -> Agent）
	MessageTypeControl = "control"
	MessageTypeUpgrade = "upgrade"

	// 控制动作
	ControlActionStart   = "start"
	ControlActionStop    = "stop"
	ControlActionRestart = "restart"

	// 日志流类型
	StreamStdout = "stdout"
	StreamStderr = "stderr"

	// 脚本类型和扩展名
	ScriptTypeShell      = "shell"
	ScriptTypeBash       = "bash"
	ScriptTypePowerShell = "powershell"
	ScriptTypePwsh       = "pwsh"
	ScriptTypePython     = "python"
	ScriptTypePy         = "py"
	ScriptTypeJS         = "js"
	ScriptTypeNode       = "node"
	ScriptExtPy          = ".py"
	ScriptExtPs1         = ".ps1"
	ScriptExtSh          = ".sh"
	OSWindows            = "windows"

	// 默认值和限制
	DefaultMaxConcurrentTasks   = 5
	DefaultHeartbeatIntervalSec = 10
	WSBackoffInitialMs          = 1000
	WSBackoffMaxMs              = 30000
	WSMaxRetries                = 6
	OutboxFlushBatchSize        = 200 // 可被配置覆盖

	// 缓冲区大小
	LogBufferSize    = 4096
	LineBufferSize   = 1024
	RateLimitBufSize = 32 * 1024

	// 文件传输配置
	DownloadRetryCount      = 3
	DefaultDownloadTimeoutS = 300

	// 模式匹配
	TaskLogFilePattern = "task_%s_%d.log"

	// 消息文本
	MsgTaskCancelled        = "task cancelled"
	MsgTaskSkippedDuplicate = "task skipped as duplicated (already completed)"

	// 传输类型
	TransferTypeUpload = "upload"
)
