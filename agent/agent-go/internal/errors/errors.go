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
	ErrCodeExecutionFailed  ErrorCode = 3000
	ErrCodeCommandNotFound  ErrorCode = 3001
	ErrCodeScriptError      ErrorCode = 3002
	ErrCodePermissionDenied ErrorCode = 3003
	ErrCodeProcessKilled    ErrorCode = 3004
	ErrCodeExitCodeNonZero  ErrorCode = 3005

	// 文件传输错误 (4000-4999)
	ErrCodeFileTransferFailed    ErrorCode = 4000
	ErrCodeFileNotFound          ErrorCode = 4001
	ErrCodeFileReadError         ErrorCode = 4002
	ErrCodeFileWriteError        ErrorCode = 4003
	ErrCodeFilePermissionDenied  ErrorCode = 4004
	ErrCodeDiskSpaceInsufficient ErrorCode = 4005

	// 配置错误 (5000-5999)
	ErrCodeConfigError    ErrorCode = 5000
	ErrCodeConfigNotFound ErrorCode = 5001
	ErrCodeConfigInvalid  ErrorCode = 5002

	// 资源错误 (6000-6999)
	ErrCodeResourceLimit  ErrorCode = 6000
	ErrCodeMemoryLimit    ErrorCode = 6001
	ErrCodeCPULimit       ErrorCode = 6002
	ErrCodeDiskIOLimit    ErrorCode = 6003
	ErrCodeBandwidthLimit ErrorCode = 6004
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

	ErrCodeExecutionFailed:  "执行失败",
	ErrCodeCommandNotFound:  "命令未找到",
	ErrCodeScriptError:      "脚本执行错误",
	ErrCodePermissionDenied: "权限被拒绝",
	ErrCodeProcessKilled:    "进程被终止",
	ErrCodeExitCodeNonZero:  "进程退出码非零",

	ErrCodeFileTransferFailed:    "文件传输失败",
	ErrCodeFileNotFound:          "文件未找到",
	ErrCodeFileReadError:         "文件读取错误",
	ErrCodeFileWriteError:        "文件写入错误",
	ErrCodeFilePermissionDenied:  "文件权限被拒绝",
	ErrCodeDiskSpaceInsufficient: "磁盘空间不足",

	ErrCodeConfigError:    "配置错误",
	ErrCodeConfigNotFound: "配置文件未找到",
	ErrCodeConfigInvalid:  "配置无效",

	ErrCodeResourceLimit:  "资源限制",
	ErrCodeMemoryLimit:    "内存限制",
	ErrCodeCPULimit:       "CPU限制",
	ErrCodeDiskIOLimit:    "磁盘IO限制",
	ErrCodeBandwidthLimit: "带宽限制",
}

var (
	// ErrAuthOrNotFound 暴露给 websocket 包调用者，用于鉴权/不存在错误判断
	ErrAuthOrNotFound     = errors.New("websocket unauthorized or not found")
	ErrReconnectAuthRetry = errors.New("reconnect requires re-register")
)

// AgentError Agent 错误类型
type AgentError struct {
	Code    ErrorCode
	Message string
	Details string
	Err     error
}

// Error 实现 error 接口
func (e *AgentError) Error() string {
	if e.Details != "" {
		return fmt.Sprintf("[%d] %s: %s (%s)", e.Code, e.Message, e.Details, e.Err)
	}
	if e.Err != nil {
		return fmt.Sprintf("[%d] %s: %v", e.Code, e.Message, e.Err)
	}
	return fmt.Sprintf("[%d] %s", e.Code, e.Message)
}

// Unwrap 实现 errors.Unwrap
func (e *AgentError) Unwrap() error {
	return e.Err
}

// NewError 创建新的 Agent 错误
func NewError(code ErrorCode, message string, err error) *AgentError {
	msg := message
	if msg == "" {
		msg = ErrorCodeMap[code]
	}
	return &AgentError{
		Code:    code,
		Message: msg,
		Err:     err,
	}
}

// NewErrorWithDetails 创建带详细信息的错误
func NewErrorWithDetails(code ErrorCode, message string, details string, err error) *AgentError {
	msg := message
	if msg == "" {
		msg = ErrorCodeMap[code]
	}
	return &AgentError{
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
	if agentErr, ok := err.(*AgentError); ok {
		return agentErr.Code
	}
	return ErrCodeUnknown
}

// GetErrorMessage 从错误中提取错误信息
func GetErrorMessage(err error) string {
	if err == nil {
		return ""
	}
	if agentErr, ok := err.(*AgentError); ok {
		if agentErr.Details != "" {
			return fmt.Sprintf("%s: %s", agentErr.Message, agentErr.Details)
		}
		return agentErr.Message
	}
	return err.Error()
}
