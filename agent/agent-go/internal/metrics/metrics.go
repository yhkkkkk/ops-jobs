package metrics

import (
	"sync"
	"time"
)

// Metrics 性能指标收集器
type Metrics struct {
	// 任务统计
	TotalTasks     int64
	SuccessTasks   int64
	FailedTasks    int64
	CancelledTasks int64
	RunningTasks   int64

	// 任务执行时间统计
	TotalExecutionTime time.Duration
	MinExecutionTime   time.Duration
	MaxExecutionTime   time.Duration

	// 网络统计
	TotalNetworkBytes int64
	TotalNetworkTime  time.Duration

	// 锁
	mu sync.RWMutex
}

var globalMetrics = &Metrics{}

// GetMetrics 获取全局指标实例
func GetMetrics() *Metrics {
	return globalMetrics
}

// RecordTaskStart 记录任务开始
func (m *Metrics) RecordTaskStart() {
	m.mu.Lock()
	defer m.mu.Unlock()
	m.TotalTasks++
	m.RunningTasks++
}

// RecordTaskSuccess 记录任务成功
func (m *Metrics) RecordTaskSuccess(duration time.Duration) {
	m.mu.Lock()
	defer m.mu.Unlock()
	m.SuccessTasks++
	m.RunningTasks--
	m.TotalExecutionTime += duration
	if m.MinExecutionTime == 0 || duration < m.MinExecutionTime {
		m.MinExecutionTime = duration
	}
	if duration > m.MaxExecutionTime {
		m.MaxExecutionTime = duration
	}
}

// RecordTaskFailed 记录任务失败
func (m *Metrics) RecordTaskFailed(duration time.Duration) {
	m.mu.Lock()
	defer m.mu.Unlock()
	m.FailedTasks++
	m.RunningTasks--
	m.TotalExecutionTime += duration
	if m.MinExecutionTime == 0 || duration < m.MinExecutionTime {
		m.MinExecutionTime = duration
	}
	if duration > m.MaxExecutionTime {
		m.MaxExecutionTime = duration
	}
}

// RecordTaskCancelled 记录任务取消
func (m *Metrics) RecordTaskCancelled(duration time.Duration) {
	m.mu.Lock()
	defer m.mu.Unlock()
	m.CancelledTasks++
	m.RunningTasks--
	if duration > 0 {
		m.TotalExecutionTime += duration
	}
}

// RecordNetworkTransfer 记录网络传输
func (m *Metrics) RecordNetworkTransfer(bytes int64, duration time.Duration) {
	m.mu.Lock()
	defer m.mu.Unlock()
	m.TotalNetworkBytes += bytes
	m.TotalNetworkTime += duration
}

// GetStats 获取统计信息
func (m *Metrics) GetStats() Stats {
	m.mu.RLock()
	defer m.mu.RUnlock()

	avgExecutionTime := time.Duration(0)
	if m.SuccessTasks+m.FailedTasks > 0 {
		avgExecutionTime = m.TotalExecutionTime / time.Duration(m.SuccessTasks+m.FailedTasks)
	}

	avgNetworkSpeed := float64(0)
	if m.TotalNetworkTime > 0 {
		avgNetworkSpeed = float64(m.TotalNetworkBytes) / m.TotalNetworkTime.Seconds()
	}

	return Stats{
		TotalTasks:        m.TotalTasks,
		SuccessTasks:      m.SuccessTasks,
		FailedTasks:       m.FailedTasks,
		CancelledTasks:    m.CancelledTasks,
		RunningTasks:      m.RunningTasks,
		AvgExecutionTime:  avgExecutionTime,
		MinExecutionTime:  m.MinExecutionTime,
		MaxExecutionTime:  m.MaxExecutionTime,
		TotalNetworkBytes: m.TotalNetworkBytes,
		AvgNetworkSpeed:   avgNetworkSpeed,
	}
}

// Reset 重置指标
func (m *Metrics) Reset() {
	m.mu.Lock()
	defer m.mu.Unlock()
	m.TotalTasks = 0
	m.SuccessTasks = 0
	m.FailedTasks = 0
	m.CancelledTasks = 0
	m.RunningTasks = 0
	m.TotalExecutionTime = 0
	m.MinExecutionTime = 0
	m.MaxExecutionTime = 0
	m.TotalNetworkBytes = 0
	m.TotalNetworkTime = 0
}

// Stats 统计信息
type Stats struct {
	TotalTasks        int64         `json:"total_tasks"`
	SuccessTasks      int64         `json:"success_tasks"`
	FailedTasks       int64         `json:"failed_tasks"`
	CancelledTasks    int64         `json:"cancelled_tasks"`
	RunningTasks      int64         `json:"running_tasks"`
	AvgExecutionTime  time.Duration `json:"avg_execution_time"`
	MinExecutionTime  time.Duration `json:"min_execution_time"`
	MaxExecutionTime  time.Duration `json:"max_execution_time"`
	TotalNetworkBytes int64         `json:"total_network_bytes"`
	AvgNetworkSpeed   float64       `json:"avg_network_speed"` // 字节/秒
}
