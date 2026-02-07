package constants

const (
	// WebSocket 消息类型（Agent-Server -> Agent）
	MessageTypeTask             = "task"
	MessageTypeTasksBatch       = "tasks_batch"
	MessageTypeCancelTask       = "cancel_task"
	MessageTypeCancelTasksBatch = "cancel_tasks_batch"
	MessageTypeHeartbeat        = "heartbeat"
	MessageTypeAck              = "ack"
	MessageTypeLog              = "log"
	MessageTypeTaskResult       = "task_result"
	MessageTypeControl          = "control" // Agent 控制消息（start/stop/restart）
	MessageTypeUpgrade          = "upgrade" // Agent 升级消息

	// 日志流类型
	LogStreamTypeStdout = "stdout"
	LogStreamTypeStderr = "stderr"

	// Agent 状态
	StatusActive     = "active"
	StatusInactive   = "inactive"
	StatusOffline    = "offline"
	StatusOnline     = "online"
	StatusCancelled  = "cancelled"
	StatusDispatched = "dispatched"

	// 控制动作
	ActionStart   = "start"
	ActionStop    = "stop"
	ActionRestart = "restart"
)

// 兼容旧命名（用于测试与历史代码）
const (
	StreamStdout = LogStreamTypeStdout
	StreamStderr = LogStreamTypeStderr
)

// 控制面认证相关的 HTTP 请求头
const (
	HeaderTimestamp            = "X-Timestamp"
	HeaderSignature            = "X-Signature"
	HeaderAuthorization        = "Authorization"
	HeaderSecWebSocketProtocol = "Sec-WebSocket-Protocol"
)

// 兼容旧命名（用于测试与历史代码）
const (
	ControlActionStart   = ActionStart
	ControlActionStop    = ActionStop
	ControlActionRestart = ActionRestart
)
