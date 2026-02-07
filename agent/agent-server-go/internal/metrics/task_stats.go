package metrics

import (
	"context"
	"sync"
	"time"

	"ops-job-agent-server/internal/config"
	"ops-job-agent-server/internal/logger"

	"github.com/redis/go-redis/v9"
)

// TaskStats 任务执行统计
type TaskStats struct {
	AgentID        string
	TotalTasks     int
	SuccessTasks   int
	FailedTasks    int
	CancelledTasks int
	TotalDuration  int64 // 毫秒，总执行时长
	LastUpdated    time.Time
}

// successRate 计算成功率
func (s *TaskStats) successRate() float64 {
	if s.TotalTasks == 0 {
		return 0.0
	}
	return float64(s.SuccessTasks) / float64(s.TotalTasks) * 100
}

// avgDurationMs 计算平均执行时长（毫秒）
func (s *TaskStats) avgDurationMs() float64 {
	if s.TotalTasks == 0 {
		return 0.0
	}
	return float64(s.TotalDuration) / float64(s.TotalTasks)
}

// TaskStatsStreamWriter 写任务统计到 Redis Stream
type TaskStatsStreamWriter struct {
	client *redis.Client
	key    string
}

// NewTaskStatsStreamWriter 创建任务统计流写入器
func NewTaskStatsStreamWriter(rdb *redis.Client, cfg *config.Config) (*TaskStatsStreamWriter, error) {
	if rdb == nil {
		return nil, nil
	}
	streamKey := cfg.TaskStatsStream.Key
	if streamKey == "" {
		streamKey = "agent_task_stats"
	}
	return &TaskStatsStreamWriter{client: rdb, key: streamKey}, nil
}

// PushStats 写入任务统计
func (w *TaskStatsStreamWriter) PushStats(ctx context.Context, stats *TaskStats) error {
	if w == nil || w.client == nil {
		return nil
	}

	fields := map[string]interface{}{
		"agent_id":        stats.AgentID,
		"total":           stats.TotalTasks,
		"success":         stats.SuccessTasks,
		"failed":          stats.FailedTasks,
		"cancelled":       stats.CancelledTasks,
		"avg_duration_ms": stats.avgDurationMs(),
		"success_rate":    stats.successRate(),
		"timestamp":       time.Now().UnixMilli(),
	}

	return w.client.XAdd(ctx, &redis.XAddArgs{
		Stream: w.key,
		Values: fields,
	}).Err()
}

// TaskStatsAggregator 聚合和维护每个 Agent 的任务执行统计
type TaskStatsAggregator struct {
	mu            sync.RWMutex
	stats         map[string]*TaskStats // key: agent ID
	streamWriter  *TaskStatsStreamWriter
	pushInterval  time.Duration        // 推送间隔
	lastPushTimes map[string]time.Time // 上次推送时间
}

// NewTaskStatsAggregator 创建任务统计聚合器
func NewTaskStatsAggregator(rdb *redis.Client, cfg *config.Config) (*TaskStatsAggregator, error) {
	streamWriter, err := NewTaskStatsStreamWriter(rdb, cfg)
	if err != nil {
		return nil, err
	}

	agg := &TaskStatsAggregator{
		stats:         make(map[string]*TaskStats),
		streamWriter:  streamWriter,
		pushInterval:  30 * time.Second, // 默认30秒推送一次
		lastPushTimes: make(map[string]time.Time),
	}

	// 从配置读取推送间隔
	if cfg.TaskStatsStream.PushInterval > 0 {
		agg.pushInterval = time.Duration(cfg.TaskStatsStream.PushInterval) * time.Second
	}

	return agg, nil
}

// UpdateTaskStats 更新任务统计
// result: 任务结果状态 (success/failed/cancelled)
// durationMs: 任务执行时长（毫秒）
func (a *TaskStatsAggregator) UpdateTaskStats(agentID string, result string, durationMs int64) {
	if agentID == "" {
		return
	}

	a.mu.Lock()
	defer a.mu.Unlock()

	stats, exists := a.stats[agentID]
	if !exists {
		stats = &TaskStats{
			AgentID: agentID,
		}
		a.stats[agentID] = stats
	}

	stats.TotalTasks++
	stats.TotalDuration += durationMs
	stats.LastUpdated = time.Now()

	switch result {
	case "success":
		stats.SuccessTasks++
	case "failed":
		stats.FailedTasks++
	case "cancelled":
		stats.CancelledTasks++
	}
}

// GetStats 获取指定 Agent 的统计快照
func (a *TaskStatsAggregator) GetStats(agentID string) *TaskStats {
	if agentID == "" {
		return nil
	}

	a.mu.RLock()
	defer a.mu.RUnlock()

	stats, exists := a.stats[agentID]
	if !exists {
		return nil
	}

	// 返回副本
	copy := *stats
	return &copy
}

// GetAllStats 获取所有 Agent 的统计快照
func (a *TaskStatsAggregator) GetAllStats() map[string]*TaskStats {
	a.mu.RLock()
	defer a.mu.RUnlock()

	result := make(map[string]*TaskStats)
	for id, stats := range a.stats {
		copy := *stats
		result[id] = &copy
	}
	return result
}

// ShouldPush 判断是否应该推送指定 Agent 的统计
func (a *TaskStatsAggregator) ShouldPush(agentID string) bool {
	a.mu.RLock()
	defer a.mu.RUnlock()

	lastPush, exists := a.lastPushTimes[agentID]
	if !exists {
		return true
	}

	return time.Since(lastPush) >= a.pushInterval
}

// PushToStream 推送指定 Agent 的统计到状态流
func (a *TaskStatsAggregator) PushToStream(ctx context.Context, agentID string) error {
	if a.streamWriter == nil {
		return nil
	}

	stats := a.GetStats(agentID)
	if stats == nil {
		return nil
	}

	if err := a.streamWriter.PushStats(ctx, stats); err != nil {
		logger.GetLogger().WithError(err).WithField("agent_id", agentID).Warn("push task stats to stream failed")
		return err
	}

	a.mu.Lock()
	a.lastPushTimes[agentID] = time.Now()
	a.mu.Unlock()

	return nil
}

// PushAllToStream 推送所有 Agent 的统计到状态流（用于 Agent 断开连接时）
func (a *TaskStatsAggregator) PushAllToStream(ctx context.Context) {
	if a.streamWriter == nil {
		return
	}

	allStats := a.GetAllStats()
	for agentID := range allStats {
		if err := a.PushToStream(ctx, agentID); err != nil {
			logger.GetLogger().WithError(err).WithField("agent_id", agentID).Warn("push task stats on disconnect failed")
		}
	}
}

// OnAgentDisconnect Agent 断开连接时调用，同步统计并清理
func (a *TaskStatsAggregator) OnAgentDisconnect(ctx context.Context, agentID string) {
	// 推送最终统计
	_ = a.PushToStream(ctx, agentID)

	// 清理本地状态
	a.mu.Lock()
	delete(a.stats, agentID)
	delete(a.lastPushTimes, agentID)
	a.mu.Unlock()
}

// GetStatsCount 获取当前统计的 Agent 数量
func (a *TaskStatsAggregator) GetStatsCount() int {
	a.mu.RLock()
	defer a.mu.RUnlock()
	return len(a.stats)
}
