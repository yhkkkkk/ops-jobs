package server

import (
	"errors"
	"fmt"
	"net/http"
	"strings"

	"github.com/bytedance/sonic"

	"ops-job-agent-server/internal/constants"
	serrors "ops-job-agent-server/internal/errors"
	"ops-job-agent-server/internal/logger"
	"ops-job-agent-server/pkg/api"

	"github.com/gin-gonic/gin"
)

// handleRegister 处理 Agent 注册
func (s *Server) handleRegister(c *gin.Context) {
	var req api.RegisterRequest
	if err := c.ShouldBindJSON(&req); err != nil {
		writeError(c, http.StatusBadRequest, serrors.ErrCodeInvalidParam, err.Error())
		return
	}

	// 兼容：优先使用请求体 token；若为空则读取 Authorization 头（Bearer）
	if strings.TrimSpace(req.Token) == "" {
		if authHeader := c.GetHeader(constants.HeaderAuthorization); authHeader != "" {
			const bearerPrefix = "bearer "
			lower := strings.ToLower(authHeader)
			if strings.HasPrefix(lower, bearerPrefix) {
				req.Token = strings.TrimSpace(authHeader[len(bearerPrefix):])
			} else {
				req.Token = strings.TrimSpace(authHeader)
			}
		}
	}

	_, agentID, err := s.agentManager.Register(req.Name, req.Token, req.Labels, req.System, req.HostID)
	if err != nil {
		if errors.Is(err, serrors.ErrMaxConnectionsReached) {
			writeError(c, http.StatusServiceUnavailable, serrors.ErrCodeInternal, serrors.ErrMaxConnectionsReached.Error())
			return
		}
		writeError(c, http.StatusInternalServerError, serrors.ErrCodeInternal, err.Error())
		return
	}

	// 通知控制面 Agent 已上线（通过状态流）
	if s.statusStream != nil {
		statusFields := map[string]interface{}{
			"agent_id":   agentID,
			"agent_name": req.Name,
			"host_id":    req.HostID,
			"status":     constants.StatusActive,
			"event":      "registered",
			"labels":     req.Labels,
		}
		if req.System != nil {
			if systemJSON, err := sonic.Marshal(req.System); err == nil {
				statusFields["system"] = string(systemJSON)
			}
		}
		if err := s.statusStream.PushStatus(c.Request.Context(), statusFields); err != nil {
			logger.GetLogger().WithError(err).WithField("agent_id", agentID).Warn("push registration status to stream failed")
		}
	}

	// 注意：token 不再放在 wsURL 中，而是通过 Sec-WebSocket-Protocol 头部传递
	wsURL := fmt.Sprintf("ws://%s:%d/ws/agent/%s",
		s.cfg.Server.Host, s.cfg.Server.Port, agentID)

	c.JSON(http.StatusOK, api.RegisterResponse{
		ID:     agentID,
		Name:   req.Name,
		Status: constants.StatusActive,
		WSURL:  wsURL,
	})
}

// handleListAgents 列出所有 Agent
func (s *Server) handleListAgents(c *gin.Context) {
	agents := s.agentManager.List()
	result := make([]map[string]interface{}, 0, len(agents))
	for _, agentConn := range agents {
		result = append(result, map[string]interface{}{
			"id":             agentConn.ID,
			"name":           agentConn.Name,
			"status":         agentConn.Status,
			"last_heartbeat": agentConn.LastHeartbeat,
		})
	}
	c.JSON(http.StatusOK, gin.H{"agents": result})
}

// handleGetAgent 获取 Agent 详情
func (s *Server) handleGetAgent(c *gin.Context) {
	agentID := c.Param("id")
	conn, exists := s.agentManager.Get(agentID)
	if !exists {
		writeError(c, http.StatusNotFound, serrors.ErrCodeNotFound, serrors.ErrAgentNotFound.Error())
		return
	}

	c.JSON(http.StatusOK, gin.H{
		"id":             conn.ID,
		"name":           conn.Name,
		"status":         conn.Status,
		"last_heartbeat": conn.LastHeartbeat,
		"labels":         conn.Labels,
		"system":         conn.System,
	})
}

// handlePushTask 处理控制面推送的任务
func (s *Server) handlePushTask(c *gin.Context) {
	agentID := c.Param("id")

	var taskSpec api.TaskSpec
	if err := c.ShouldBindJSON(&taskSpec); err != nil {
		writeError(c, http.StatusBadRequest, serrors.ErrCodeInvalidParam, err.Error())
		return
	}

	if err := s.taskDispatcher.DispatchTaskToAgent(agentID, &taskSpec); err != nil {
		if errors.Is(err, serrors.ErrAgentNotFound) {
			writeError(c, http.StatusNotFound, serrors.ErrCodeNotFound, serrors.ErrAgentNotFound.Error())
			return
		}
		if errors.Is(err, serrors.ErrAgentNotFound) {
			writeError(c, http.StatusServiceUnavailable, serrors.ErrCodeConnectionFailed, serrors.ErrAgentConnectionClosed.Error())
			return
		}
		writeError(c, http.StatusInternalServerError, serrors.ErrCodeInternal, err.Error())
		return
	}

	c.JSON(http.StatusOK, gin.H{
		"task_id":  taskSpec.ID,
		"agent_id": agentID,
		"status":   constants.StatusDispatched,
	})
}

// handlePushTasksBatch 批量推送任务到指定 Agent
func (s *Server) handlePushTasksBatch(c *gin.Context) {
	agentID := c.Param("id")

	var taskSpecs []api.TaskSpec
	if err := c.ShouldBindJSON(&taskSpecs); err != nil {
		writeError(c, http.StatusBadRequest, serrors.ErrCodeInvalidParam, err.Error())
		return
	}

	if len(taskSpecs) == 0 {
		writeError(c, http.StatusBadRequest, serrors.ErrCodeInvalidParam, serrors.ErrTasksArrayEmpty.Error())
		return
	}

	// 获取 Agent 连接
	conn, exists := s.agentManager.Get(agentID)
	if !exists {
		writeError(c, http.StatusNotFound, serrors.ErrCodeNotFound, serrors.ErrAgentNotFound.Error())
		return
	}

	// 转换为指针数组
	taskPtrs := make([]*api.TaskSpec, len(taskSpecs))
	for i := range taskSpecs {
		taskPtrs[i] = &taskSpecs[i]
	}

	// 批量发送任务
	if err := conn.SendTasks(taskPtrs); err != nil {
		if errors.Is(err, serrors.ErrAgentConnectionClosed) {
			writeError(c, http.StatusServiceUnavailable, serrors.ErrCodeConnectionFailed, serrors.ErrAgentConnectionClosed.Error())
			return
		}
		writeError(c, http.StatusInternalServerError, serrors.ErrCodeInternal, err.Error())
		return
	}

	// 记录所有任务为运行状态
	for _, task := range taskPtrs {
		conn.AddRunningTask(task)
	}

	taskIDs := make([]string, len(taskSpecs))
	for i, task := range taskSpecs {
		taskIDs[i] = task.ID
	}

	logger.GetLogger().WithFields(map[string]interface{}{
		"agent_id":   agentID,
		"task_count": len(taskSpecs),
		"task_ids":   taskIDs,
	}).Info("batch tasks pushed to agent")

	c.JSON(http.StatusOK, gin.H{
		"task_ids": taskIDs,
		"agent_id": agentID,
		"status":   constants.StatusDispatched,
		"count":    len(taskSpecs),
	})
}

// handleCancelTask 处理取消任务请求
// 支持两种情况：
// 1. Agent 在线：通过 WebSocket 发送取消消息
// 2. Agent 离线：从 pendingTaskStore 中删除任务
func (s *Server) handleCancelTask(c *gin.Context) {
	agentID := c.Param("id")
	taskID := c.Param("task_id")

	conn, exists := s.agentManager.Get(agentID)
	if !exists {
		// Agent 不存在，尝试从 pendingTaskStore 中删除任务
		if s.pendingTaskStore != nil {
			if err := s.cancelTaskFromQueue(agentID, taskID); err != nil {
				writeError(c, http.StatusNotFound, serrors.ErrCodeNotFound, serrors.ErrPendingTaskNotFound.Error())
				return
			}
			c.JSON(http.StatusOK, gin.H{
				"task_id":  taskID,
				"agent_id": agentID,
				"status":   constants.StatusCancelled,
				"source":   "pending_store",
			})
			return
		}
		writeError(c, http.StatusNotFound, serrors.ErrCodeNotFound, serrors.ErrAgentNotFound.Error())
		return
	}

	// Agent 在线，尝试通过 WebSocket 发送取消消息
	if conn.Status == constants.StatusActive && conn.Conn != nil {
		if err := conn.SendCancelTask(taskID); err != nil {
			logger.GetLogger().WithError(err).WithFields(map[string]interface{}{
				"agent_id": agentID,
				"task_id":  taskID,
			}).Error("send cancel task message failed")
			// WebSocket 发送失败，尝试从 pendingTaskStore 中删除
			if s.pendingTaskStore != nil {
				if err := s.cancelTaskFromQueue(agentID, taskID); err == nil {
					c.JSON(http.StatusOK, gin.H{
						"task_id":  taskID,
						"agent_id": agentID,
						"status":   constants.StatusCancelled,
						"source":   "pending_store",
					})
					return
				}
			}
			writeError(c, http.StatusInternalServerError, serrors.ErrCodeInternal, err.Error())
			return
		}

		logger.GetLogger().WithFields(map[string]interface{}{
			"agent_id": agentID,
			"task_id":  taskID,
		}).Info("cancel task request sent to agent via websocket")

		c.JSON(http.StatusOK, gin.H{
			"task_id":  taskID,
			"agent_id": agentID,
			"status":   constants.StatusCancelled,
			"source":   "websocket",
		})
		return
	}

	// Agent 连接不活跃，尝试从 pendingTaskStore 中删除
	if s.pendingTaskStore != nil {
		if err := s.cancelTaskFromQueue(agentID, taskID); err != nil {
			writeError(c, http.StatusServiceUnavailable, serrors.ErrCodeConnectionFailed, serrors.ErrPendingTaskInactive.Error())
			return
		}
		c.JSON(http.StatusOK, gin.H{
			"task_id":  taskID,
			"agent_id": agentID,
			"status":   constants.StatusCancelled,
			"source":   "pending_store",
		})
		return
	}

	writeError(c, http.StatusServiceUnavailable, serrors.ErrCodeConnectionFailed, serrors.ErrAgentConnectionInactive.Error())
}

// handleCancelTasksBatch 批量取消任务
func (s *Server) handleCancelTasksBatch(c *gin.Context) {
	agentID := c.Param("id")

	var req struct {
		TaskIDs []string `json:"task_ids"`
	}
	if err := c.ShouldBindJSON(&req); err != nil {
		writeError(c, http.StatusBadRequest, serrors.ErrCodeInvalidParam, err.Error())
		return
	}

	if len(req.TaskIDs) == 0 {
		writeError(c, http.StatusBadRequest, serrors.ErrCodeInvalidParam, serrors.ErrTaskIDsArrayEmpty.Error())
		return
	}

	conn, exists := s.agentManager.Get(agentID)
	if !exists {
		writeError(c, http.StatusNotFound, serrors.ErrCodeNotFound, serrors.ErrAgentNotFound.Error())
		return
	}

	results := make([]map[string]interface{}, 0, len(req.TaskIDs))
	successCount := 0
	failedCount := 0

	// Agent 在线，通过 WebSocket 批量发送取消消息
	if conn.Status == constants.StatusActive && conn.Conn != nil {
		if err := conn.SendCancelTasks(req.TaskIDs); err != nil {
			logger.GetLogger().WithError(err).WithFields(map[string]interface{}{
				"agent_id":   agentID,
				"task_count": len(req.TaskIDs),
			}).Error("send cancel tasks batch message failed")

			// WebSocket 发送失败，逐个尝试从 pendingTaskStore 中删除
			if s.pendingTaskStore != nil {
				for _, taskID := range req.TaskIDs {
					if err := s.cancelTaskFromQueue(agentID, taskID); err == nil {
						results = append(results, map[string]interface{}{
							"task_id": taskID,
							"status":  constants.StatusCancelled,
							"source":  "pending_store",
						})
						successCount++
					} else {
						results = append(results, map[string]interface{}{
							"task_id": taskID,
							"status":  "failed",
							"error":   err.Error(),
						})
						failedCount++
					}
				}
			} else {
				writeError(c, http.StatusInternalServerError, serrors.ErrCodeInternal, err.Error())
				return
			}
		} else {
			// WebSocket 批量发送成功
			for _, taskID := range req.TaskIDs {
				results = append(results, map[string]interface{}{
					"task_id": taskID,
					"status":  constants.StatusCancelled,
					"source":  "websocket",
				})
				successCount++
			}
		}
	} else {
		// Agent 离线，尝试从 pendingTaskStore 中逐个删除
		if s.pendingTaskStore != nil {
			for _, taskID := range req.TaskIDs {
				if err := s.cancelTaskFromQueue(agentID, taskID); err == nil {
					results = append(results, map[string]interface{}{
						"task_id": taskID,
						"status":  constants.StatusCancelled,
						"source":  "pending_store",
					})
					successCount++
				} else {
					results = append(results, map[string]interface{}{
						"task_id": taskID,
						"status":  "failed",
						"error":   err.Error(),
					})
					failedCount++
				}
			}
		} else {
			writeError(c, http.StatusServiceUnavailable, serrors.ErrCodeConnectionFailed, serrors.ErrAgentConnectionInactive.Error())
			return
		}
	}

	logger.GetLogger().WithFields(map[string]interface{}{
		"agent_id":      agentID,
		"task_count":    len(req.TaskIDs),
		"success_count": successCount,
		"failed_count":  failedCount,
	}).Info("batch cancel tasks completed")

	c.JSON(http.StatusOK, gin.H{
		"agent_id":      agentID,
		"task_count":    len(req.TaskIDs),
		"success_count": successCount,
		"failed_count":  failedCount,
		"results":       results,
	})
}

// cancelTaskFromQueue 从待处理任务存储中取消任务
func (s *Server) cancelTaskFromQueue(agentID, taskID string) error {
	if s.pendingTaskStore == nil {
		return serrors.ErrPendingStoreDisabled
	}

	// 直接从 pendingTaskStore 删除任务
	if err := s.pendingTaskStore.Delete(agentID, taskID); err != nil {
		logger.GetLogger().WithError(err).WithFields(map[string]interface{}{
			"agent_id": agentID,
			"task_id":  taskID,
		}).Warn("task not found in pending store")
		return serrors.ErrPendingTaskNotFoundOnly
	}

	logger.GetLogger().WithFields(map[string]interface{}{
		"agent_id": agentID,
		"task_id":  taskID,
	}).Info("task cancelled from pending store")

	return nil
}
