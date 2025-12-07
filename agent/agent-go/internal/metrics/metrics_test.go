package metrics

import (
	"testing"
	"time"
)

func TestMetrics_RecordTaskStart(t *testing.T) {
	m := &Metrics{}
	m.RecordTaskStart()
	
	stats := m.GetStats()
	if stats.TotalTasks != 1 {
		t.Errorf("expected TotalTasks to be 1, got %d", stats.TotalTasks)
	}
	if stats.RunningTasks != 1 {
		t.Errorf("expected RunningTasks to be 1, got %d", stats.RunningTasks)
	}
}

func TestMetrics_RecordTaskSuccess(t *testing.T) {
	m := &Metrics{}
	m.RecordTaskStart()
	m.RecordTaskSuccess(5 * time.Second)
	
	stats := m.GetStats()
	if stats.SuccessTasks != 1 {
		t.Errorf("expected SuccessTasks to be 1, got %d", stats.SuccessTasks)
	}
	if stats.RunningTasks != 0 {
		t.Errorf("expected RunningTasks to be 0, got %d", stats.RunningTasks)
	}
	if stats.AvgExecutionTime != 5*time.Second {
		t.Errorf("expected AvgExecutionTime to be 5s, got %v", stats.AvgExecutionTime)
	}
}

func TestMetrics_RecordTaskFailed(t *testing.T) {
	m := &Metrics{}
	m.RecordTaskStart()
	m.RecordTaskFailed(3 * time.Second)
	
	stats := m.GetStats()
	if stats.FailedTasks != 1 {
		t.Errorf("expected FailedTasks to be 1, got %d", stats.FailedTasks)
	}
	if stats.RunningTasks != 0 {
		t.Errorf("expected RunningTasks to be 0, got %d", stats.RunningTasks)
	}
}

func TestMetrics_RecordTaskCancelled(t *testing.T) {
	m := &Metrics{}
	m.RecordTaskStart()
	m.RecordTaskCancelled(1 * time.Second)
	
	stats := m.GetStats()
	if stats.CancelledTasks != 1 {
		t.Errorf("expected CancelledTasks to be 1, got %d", stats.CancelledTasks)
	}
	if stats.RunningTasks != 0 {
		t.Errorf("expected RunningTasks to be 0, got %d", stats.RunningTasks)
	}
}

func TestMetrics_RecordNetworkTransfer(t *testing.T) {
	m := &Metrics{}
	m.RecordNetworkTransfer(1024*1024, 2*time.Second) // 1MB in 2 seconds
	
	stats := m.GetStats()
	if stats.TotalNetworkBytes != 1024*1024 {
		t.Errorf("expected TotalNetworkBytes to be %d, got %d", 1024*1024, stats.TotalNetworkBytes)
	}
	
	// 1MB in 2 seconds = 512 KB/s = 524288 bytes/s
	expectedSpeed := 524288.0
	if stats.AvgNetworkSpeed < expectedSpeed*0.9 || stats.AvgNetworkSpeed > expectedSpeed*1.1 {
		t.Errorf("expected AvgNetworkSpeed to be around %f, got %f", expectedSpeed, stats.AvgNetworkSpeed)
	}
}

func TestMetrics_UpdateSystemMetrics(t *testing.T) {
	m := &Metrics{}
	m.UpdateSystemMetrics(50.5, 75.3)
	
	stats := m.GetStats()
	if stats.CPUUsage != 50.5 {
		t.Errorf("expected CPUUsage to be 50.5, got %f", stats.CPUUsage)
	}
	if stats.MemoryUsage != 75.3 {
		t.Errorf("expected MemoryUsage to be 75.3, got %f", stats.MemoryUsage)
	}
}

func TestMetrics_Reset(t *testing.T) {
	m := &Metrics{}
	m.RecordTaskStart()
	m.RecordTaskSuccess(5 * time.Second)
	m.RecordNetworkTransfer(1024, time.Second)
	
	m.Reset()
	
	stats := m.GetStats()
	if stats.TotalTasks != 0 {
		t.Errorf("expected TotalTasks to be 0 after reset, got %d", stats.TotalTasks)
	}
	if stats.TotalNetworkBytes != 0 {
		t.Errorf("expected TotalNetworkBytes to be 0 after reset, got %d", stats.TotalNetworkBytes)
	}
}

func TestMetrics_ConcurrentAccess(t *testing.T) {
	m := &Metrics{}
	
	// 并发记录任务
	done := make(chan bool, 10)
	for i := 0; i < 10; i++ {
		go func() {
			m.RecordTaskStart()
			m.RecordTaskSuccess(time.Second)
			done <- true
		}()
	}
	
	// 等待所有 goroutine 完成
	for i := 0; i < 10; i++ {
		<-done
	}
	
	stats := m.GetStats()
	if stats.TotalTasks != 10 {
		t.Errorf("expected TotalTasks to be 10, got %d", stats.TotalTasks)
	}
	if stats.SuccessTasks != 10 {
		t.Errorf("expected SuccessTasks to be 10, got %d", stats.SuccessTasks)
	}
}

