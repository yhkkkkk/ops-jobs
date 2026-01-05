package resource

import (
	"bytes"
	"testing"
	"time"
)

func TestBandwidthLimiter_NoLimit(t *testing.T) {
	limiter := NewBandwidthLimiter(0) // 不限制
	writer := limiter.LimitWriter(&bytes.Buffer{})
	
	data := make([]byte, 1024*1024) // 1MB
	start := time.Now()
	_, err := writer.Write(data)
	duration := time.Since(start)
	
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	
	// 不限制时应该很快完成
	if duration > 100*time.Millisecond {
		t.Errorf("expected fast write without limit, took %v", duration)
	}
}

func TestBandwidthLimiter_WithLimit(t *testing.T) {
	limiter := NewBandwidthLimiter(100) // 100 KB/s
	buf := &bytes.Buffer{}
	writer := limiter.LimitWriter(buf)
	
	data := make([]byte, 200*1024) // 200 KB
	start := time.Now()
	_, err := writer.Write(data)
	duration := time.Since(start)
	
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	
	// 200 KB at 100 KB/s should take at least 2 seconds
	expectedMinDuration := 2 * time.Second
	if duration < expectedMinDuration {
		t.Errorf("expected at least %v, got %v", expectedMinDuration, duration)
	}
	
	// 但也不应该太慢（允许一些误差）
	expectedMaxDuration := 3 * time.Second
	if duration > expectedMaxDuration {
		t.Errorf("expected at most %v, got %v", expectedMaxDuration, duration)
	}
	
	if buf.Len() != len(data) {
		t.Errorf("expected %d bytes written, got %d", len(data), buf.Len())
	}
}

func TestBandwidthLimiter_Reset(t *testing.T) {
	limiter := NewBandwidthLimiter(100)
	limiter.writtenBytes = 1000
	limiter.Reset()
	
	if limiter.writtenBytes != 0 {
		t.Errorf("expected writtenBytes to be 0 after reset, got %d", limiter.writtenBytes)
	}
}

func TestBandwidthLimiter_GetCurrentSpeed(t *testing.T) {
	limiter := NewBandwidthLimiter(100)
	limiter.writtenBytes = 1000
	time.Sleep(100 * time.Millisecond)
	
	speed := limiter.GetCurrentSpeed()
	if speed <= 0 {
		t.Errorf("expected positive speed, got %f", speed)
	}
}

