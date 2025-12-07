package core

import (
	"ops-job-agent/internal/logger"
)

// handleWebSocketTask 处理从 WebSocket 接收的任务
func (a *Agent) handleWebSocketTask(task *TaskSpec) {
	logger.GetLogger().WithFields(map[string]interface{}{
		"task_id":   task.ID,
		"task_name": task.Name,
	}).Info("received task via websocket")

	// 异步执行任务
	go a.executeTask(task)
}

// handleWebSocketCancel 处理从 WebSocket 接收的取消任务请求
func (a *Agent) handleWebSocketCancel(taskID string) {
	logger.GetLogger().WithField("task_id", taskID).Info("received cancel task via websocket")

	// 取消任务
	if err := a.CancelTask(taskID); err != nil {
		logger.GetLogger().WithError(err).WithField("task_id", taskID).Error("cancel task failed")
	}
}
