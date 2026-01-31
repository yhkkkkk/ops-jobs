package log

import (
	"context"
	"fmt"
	"strings"
	"time"

	"github.com/spf13/cast"

	"ops-job-agent-server/internal/config"
	"ops-job-agent-server/pkg/api"

	"github.com/redis/go-redis/v9"
)

// ResultStreamWriter 写任务结果到 Redis Stream
type ResultStreamWriter struct {
	client *redis.Client
	key    string
}

func NewResultStreamWriter(rdb *redis.Client, cfg *config.Config) (*ResultStreamWriter, error) {
	if !cfg.ResultStream.Enabled {
		return nil, nil
	}
	if rdb == nil {
		return nil, fmt.Errorf("result stream enabled but redis client not provided")
	}
	return &ResultStreamWriter{client: rdb, key: cfg.ResultStream.Key}, nil
}

func (w *ResultStreamWriter) PushResult(ctx context.Context, agentID string, result *api.TaskResult) error {
	if w == nil || w.client == nil || result == nil {
		return nil
	}
	logPointer := result.LogPointer
	if logPointer == "" && result.LogSize > 0 {
		logPointer = "redis:job_logs/" + result.TaskID + "@"
	}

	// 解析 task_id 提取 host_id 和 execution_id
	// task_id 格式: {execution_id}_{step_id}_{host_id}_{random}
	executionID := extractExecutionID(result.TaskID)
	hostID := extractHostID(result.TaskID)

	values := map[string]interface{}{
		"task_id":      result.TaskID,
		"execution_id": executionID,
		"agent_id":     agentID,
		"host_id":      hostID,
		"status":       result.Status,
		"exit_code":    result.ExitCode,
		"error_msg":    result.ErrorMsg,
		"error_code":   result.ErrorCode,
		"started_at":   result.StartedAt,
		"finished_at":  result.FinishedAt,
		"log_size":     result.LogSize,
		"log_pointer":  logPointer,
		"received_at":  time.Now().UnixMilli(),
	}

	// 计算并添加作业进度信息
	if executionID > 0 {
		progress := w.calculateProgress(ctx, executionID)
		for k, v := range progress {
			values[k] = v
		}
	}

	return w.client.XAdd(ctx, &redis.XAddArgs{
		Stream: w.key,
		Values: values,
		MaxLen: 10000, // 限制 Stream 最大长度，防止无限增长
		Approx: true,  // 使用近似裁剪提升性能
	}).Err()
}

// calculateProgress 计算作业执行进度
// 从 agent_results stream 中聚合计算进度信息
func (w *ResultStreamWriter) calculateProgress(ctx context.Context, executionID int) map[string]interface{} {
	progress := map[string]interface{}{
		"total_hosts":   0,
		"success_hosts": 0,
		"failed_hosts":  0,
		"running_hosts": 0,
		"pending_hosts": 0,
		"progress":      0,
	}

	// 从 agent_results stream 中读取该 execution 的所有任务结果
	streamKey := w.key
	messages, err := w.client.XRange(ctx, streamKey, "-", "+").Result()
	if err != nil {
		return progress
	}

	// 统计该 execution 的任务状态
	totalHosts := make(map[int]bool)
	successHosts := make(map[int]bool)
	failedHosts := make(map[int]bool)
	runningHosts := make(map[int]bool)

	for _, msg := range messages {
		msgExecID, _ := cast.ToIntE(msg.Values["execution_id"])
		if msgExecID != executionID {
			continue
		}

		hostID, _ := cast.ToIntE(msg.Values["host_id"])
		if hostID == 0 {
			continue
		}

		status := msg.Values["status"].(string)
		totalHosts[hostID] = true

		switch status {
		case "success":
			successHosts[hostID] = true
		case "failed":
			failedHosts[hostID] = true
		case "running":
			runningHosts[hostID] = true
		}
	}

	// 计算进度
	total := len(totalHosts)
	success := len(successHosts)
	failed := len(failedHosts)
	running := len(runningHosts)
	pending := total - success - failed - running

	progressPercent := 0
	if total > 0 {
		progressPercent = (success * 100) / total
	}

	progress["total_hosts"] = total
	progress["success_hosts"] = success
	progress["failed_hosts"] = failed
	progress["running_hosts"] = running
	progress["pending_hosts"] = pending
	progress["progress"] = progressPercent

	return progress
}

// extractExecutionID 从 task_id 中提取 execution_id
// task_id 格式: {execution_id}_{step_id}_{host_id}_{random}
func extractExecutionID(taskID string) int {
	parts := strings.Split(taskID, "_")
	if len(parts) >= 1 {
		if execID, err := cast.ToIntE(parts[0]); err == nil {
			return execID
		}
	}
	return 0
}

// extractHostID 从 task_id 中提取 host_id
// task_id 格式: {execution_id}_{step_id}_{host_id}_{random}
func extractHostID(taskID string) int {
	parts := strings.Split(taskID, "_")
	if len(parts) >= 3 {
		if hostID, err := cast.ToIntE(parts[2]); err == nil {
			return hostID
		}
	}
	return 0
}
