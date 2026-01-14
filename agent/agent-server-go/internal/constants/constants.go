package constants

const (
	// WebSocket message types
	MessageTypeAck        = "ack"
	MessageTypeTaskResult = "task_result"
	MessageTypeLog        = "log"
	MessageTypeHeartbeat  = "heartbeat"
	MessageTypeControl    = "control"  // Agent 控制消息（start/stop/restart）
	MessageTypeUpgrade    = "upgrade"  // Agent 升级消息

	// Log streams
	LogStreamTypeStdout = "stdout"
	LogStreamTypeStderr = "stderr"

	// Agent statuses
	StatusActive     = "active"
	StatusOffline    = "offline"
	StatusOnline     = "online"
	StatusCancelled  = "cancelled"
	StatusDispatched = "dispatched"

	// Control actions
	ActionStart   = "start"
	ActionStop    = "stop"
	ActionRestart = "restart"
)
