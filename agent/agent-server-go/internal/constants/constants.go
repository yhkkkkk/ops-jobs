package constants

const (
	// WebSocket message types
	MessageTypeAck        = "ack"
	MessageTypeTaskResult = "task_result"
	MessageTypeLog        = "log"
	MessageTypeHeartbeat  = "heartbeat"

	// Log streams
	LogStreamTypeStdout = "stdout"
	LogStreamTypeStderr = "stderr"

	// Agent statuses
	StatusActive     = "active"
	StatusOffline    = "offline"
	StatusOnline     = "online"
	StatusCancelled  = "cancelled"
	StatusDispatched = "dispatched"
)
