package errors

import (
	"errors"
	"fmt"
)

// ErrorCode 错误码类型
type ErrorCode int

const (
	// 通用错误 (1000-1999)
	ErrCodeUnknown      ErrorCode = 1000
	ErrCodeInternal     ErrorCode = 1001
	ErrCodeInvalidParam ErrorCode = 1002
	ErrCodeNotFound     ErrorCode = 1003
	ErrCodeTimeout      ErrorCode = 1004

	// 网络错误 (2000-2999)
	ErrCodeNetworkError      ErrorCode = 2000
	ErrCodeConnectionFailed  ErrorCode = 2001
	ErrCodeConnectionTimeout ErrorCode = 2002
	ErrCodeRequestFailed     ErrorCode = 2003
	ErrCodeResponseError     ErrorCode = 2004

	// 执行错误 (3000-3999)
	ErrCodeExecutionFailed ErrorCode = 3000

	// 文件传输错误 (4000-4999)
	ErrCodeFileTransferFailed ErrorCode = 4000

	// 配置错误 (5000-5999)
	ErrCodeConfigError   ErrorCode = 5000
	ErrCodeConfigInvalid ErrorCode = 5002
)

// ErrorCodeMap 错误码到错误信息的映射
var ErrorCodeMap = map[ErrorCode]string{
	ErrCodeUnknown:      "未知错误",
	ErrCodeInternal:     "内部错误",
	ErrCodeInvalidParam: "参数无效",
	ErrCodeNotFound:     "资源未找到",
	ErrCodeTimeout:      "操作超时",

	ErrCodeNetworkError:      "网络错误",
	ErrCodeConnectionFailed:  "连接失败",
	ErrCodeConnectionTimeout: "连接超时",
	ErrCodeRequestFailed:     "请求失败",
	ErrCodeResponseError:     "响应错误",

	ErrCodeExecutionFailed: "执行失败",

	ErrCodeFileTransferFailed: "文件传输失败",

	ErrCodeConfigError:   "配置错误",
	ErrCodeConfigInvalid: "配置无效",
}

// Sentinel errors，集中管理常用文本，避免散落字面量
var (
	ErrTasksArrayEmpty         = errors.New("tasks array is empty")
	ErrTaskIDsArrayEmpty       = errors.New("task_ids array is empty")
	ErrAgentNotFound           = errors.New("agent not found")
	ErrAgentNotActive          = errors.New("agent is not active")
	ErrAgentConnectionClosed   = errors.New("agent connection closed")
	ErrAgentConnectionInactive = errors.New("agent connection is not active")
	ErrMaxConnectionsReached   = errors.New("max connections reached")
	ErrPendingTaskNotFound     = errors.New("agent not found and task not found in pending store")
	ErrPendingTaskInactive     = errors.New("agent connection is not active and task not found in pending store")
	ErrMissingSignature        = errors.New("missing signature headers")
	ErrInvalidTimestamp        = errors.New("invalid timestamp")
	ErrTimestampSkew           = errors.New("timestamp skew too large")
	ErrReadBodyFailed          = errors.New("failed to read body")
	ErrInvalidSignature        = errors.New("invalid signature")
	ErrInvalidTaskID           = errors.New("invalid task_id format")
	ErrLogStreamUnavailable    = errors.New("log stream unavailable")
	ErrLogStreamWriteFailed    = errors.New("log stream write failed")
	ErrInvalidControlAction    = errors.New("invalid action, must be start/stop/restart")
	ErrTargetVersionRequired   = errors.New("target_version is required")
	ErrDownloadURLRequired     = errors.New("download_url is required")
	ErrSelfControlOnlyRestart  = errors.New("agent-server only supports restart action")
	ErrPendingStoreDisabled    = errors.New("pending task store not enabled")
	ErrPendingTaskNotFoundOnly = errors.New("task not found in pending store")
	ErrWebSocketUnavailable    = errors.New("websocket temporarily unavailable")
	ErrInvalidToken            = errors.New("invalid token")
	ErrWebSocketUpgradeFailed  = errors.New("websocket upgrade failed")
	ErrAgentConnectFailed      = errors.New("connect agent failed")
)

// ServerError 服务器错误
type ServerError struct {
	Code    ErrorCode
	Message string
	Details string
	Err     error
}

// Error 实现 error 接口
func (e *ServerError) Error() string {
	if e.Details != "" {
		return fmt.Sprintf("[%d] %s: %s (%v)", e.Code, e.Message, e.Details, e.Err)
	}
	if e.Err != nil {
		return fmt.Sprintf("[%d] %s: %v", e.Code, e.Message, e.Err)
	}
	return fmt.Sprintf("[%d] %s", e.Code, e.Message)
}

// Unwrap 实现 errors.Unwrap
func (e *ServerError) Unwrap() error {
	return e.Err
}

// NewError 创建新的 ServerError
func NewError(code ErrorCode, message string, err error) *ServerError {
	msg := message
	if msg == "" {
		msg = ErrorCodeMap[code]
	}
	return &ServerError{
		Code:    code,
		Message: msg,
		Err:     err,
	}
}

// NewErrorWithDetails 创建带详细信息的错误
func NewErrorWithDetails(code ErrorCode, message string, details string, err error) *ServerError {
	msg := message
	if msg == "" {
		msg = ErrorCodeMap[code]
	}
	return &ServerError{
		Code:    code,
		Message: msg,
		Details: details,
		Err:     err,
	}
}

// GetErrorCode 从错误中提取错误码
func GetErrorCode(err error) ErrorCode {
	if err == nil {
		return 0
	}
	if e, ok := err.(*ServerError); ok {
		return e.Code
	}
	return ErrCodeUnknown
}

// GetErrorMessage 从错误中提取错误信息
func GetErrorMessage(err error) string {
	if err == nil {
		return ""
	}
	if e, ok := err.(*ServerError); ok {
		if e.Details != "" {
			return fmt.Sprintf("%s: %s", e.Message, e.Details)
		}
		return e.Message
	}
	return err.Error()
}
