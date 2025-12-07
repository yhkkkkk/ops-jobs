package errors

import (
	"errors"
	"testing"
)

func TestNewError(t *testing.T) {
	err := NewError(ErrCodeNetworkError, "", nil)
	if err.Code != ErrCodeNetworkError {
		t.Errorf("expected error code %d, got %d", ErrCodeNetworkError, err.Code)
	}
	if err.Message != ErrorCodeMap[ErrCodeNetworkError] {
		t.Errorf("expected message %s, got %s", ErrorCodeMap[ErrCodeNetworkError], err.Message)
	}
}

func TestNewErrorWithDetails(t *testing.T) {
	details := "connection timeout after 30s"
	err := NewErrorWithDetails(ErrCodeConnectionTimeout, "", details, nil)
	if err.Details != details {
		t.Errorf("expected details %s, got %s", details, err.Details)
	}
}

func TestGetErrorCode(t *testing.T) {
	tests := []struct {
		name     string
		err      error
		expected ErrorCode
	}{
		{
			name:     "AgentError",
			err:      NewError(ErrCodeExecutionFailed, "", nil),
			expected: ErrCodeExecutionFailed,
		},
		{
			name:     "standard error",
			err:      errors.New("standard error"),
			expected: ErrCodeUnknown,
		},
		{
			name:     "nil error",
			err:      nil,
			expected: 0,
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			code := GetErrorCode(tt.err)
			if code != tt.expected {
				t.Errorf("expected error code %d, got %d", tt.expected, code)
			}
		})
	}
}

func TestGetErrorMessage(t *testing.T) {
	tests := []struct {
		name     string
		err      error
		expected string
	}{
		{
			name:     "AgentError with details",
			err:      NewErrorWithDetails(ErrCodeFileNotFound, "", "file.txt", nil),
			expected: ErrorCodeMap[ErrCodeFileNotFound] + ": file.txt",
		},
		{
			name:     "AgentError without details",
			err:      NewError(ErrCodeNetworkError, "", nil),
			expected: ErrorCodeMap[ErrCodeNetworkError],
		},
		{
			name:     "standard error",
			err:      errors.New("standard error"),
			expected: "standard error",
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			msg := GetErrorMessage(tt.err)
			if msg != tt.expected {
				t.Errorf("expected message %s, got %s", tt.expected, msg)
			}
		})
	}
}

