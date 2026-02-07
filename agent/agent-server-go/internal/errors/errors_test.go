package errors

import "testing"

func TestErrorCodeMapCoverage(t *testing.T) {
	all := []ErrorCode{
		ErrCodeUnknown,
		ErrCodeInternal,
		ErrCodeInvalidParam,
		ErrCodeNotFound,
		ErrCodeTimeout,
		ErrCodeNetworkError,
		ErrCodeConnectionFailed,
		ErrCodeConnectionTimeout,
		ErrCodeRequestFailed,
		ErrCodeResponseError,
		ErrCodeExecutionFailed,
		ErrCodeFileTransferFailed,
		ErrCodeConfigError,
		ErrCodeConfigInvalid,
	}
	for _, code := range all {
		if _, ok := ErrorCodeMap[code]; !ok {
			t.Fatalf("error code %d missing from ErrorCodeMap", code)
		}
	}
}

func TestNewError(t *testing.T) {
	e := NewError(ErrCodeNetworkError, "", nil)
	if e.Code != ErrCodeNetworkError {
		t.Fatalf("code mismatch: %d", e.Code)
	}
	if e.Message == "" {
		t.Fatalf("message should be filled from map")
	}
}

func TestGetters(t *testing.T) {
	err := NewErrorWithDetails(ErrCodeInvalidParam, "", "bad body", nil)
	if GetErrorCode(err) != ErrCodeInvalidParam {
		t.Fatalf("GetErrorCode mismatch")
	}
	if msg := GetErrorMessage(err); msg == "" {
		t.Fatalf("GetErrorMessage empty")
	}
}
