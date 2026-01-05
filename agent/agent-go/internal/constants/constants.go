package constants

const (
	// Task types
	TaskTypeScript       = "script"
	TaskTypeFileTransfer = "file_transfer"
	TaskTypeFilePreview  = "file_preview"

	// Task statuses
	StatusPending   = "pending"
	StatusRunning   = "running"
	StatusSuccess   = "success"
	StatusFailed    = "failed"
	StatusCancelled = "cancelled"

	// Log/stream/message types
	StreamStdout          = "stdout"
	StreamStderr          = "stderr"
	MessageTypeAck        = "ack"
	MessageTypeLog        = "log"
	MessageTypeTaskResult = "task_result"

	// Script types and extensions
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

	// Defaults and limits
	DefaultMaxConcurrentTasks   = 5
	DefaultHeartbeatIntervalSec = 10
	WSBackoffInitialMs          = 1000
	WSBackoffMaxMs              = 30000
	WSMaxRetries                = 6
	OutboxFlushBatchSize        = 200

	// Buffers
	LogBufferSize    = 4096
	LineBufferSize   = 1024
	RateLimitBufSize = 32 * 1024

	// File transfer
	DownloadRetryCount      = 3
	DefaultDownloadTimeoutS = 300
	// File preview
	DefaultMaxPreviewBytes = 128 * 1024

	// Patterns
	TaskLogFilePattern = "task_%s_%d.log"

	// Messages
	MsgTaskCancelled        = "task cancelled"
	MsgTaskSkippedDuplicate = "task skipped as duplicated (already completed)"

	// Transfer types
	TransferTypeUpload   = "upload"
	TransferTypeDownload = "download"
)
