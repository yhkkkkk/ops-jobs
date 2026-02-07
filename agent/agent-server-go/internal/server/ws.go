package server

import (
	"bytes"
	"context"
	"crypto/hmac"
	"fmt"
	"io"
	"net/http"
	"time"

	"github.com/bytedance/sonic"
	"github.com/tidwall/gjson"

	"ops-job-agent-server/internal/agent"
	"ops-job-agent-server/internal/auth"
	"ops-job-agent-server/internal/constants"
	serrors "ops-job-agent-server/internal/errors"
	"ops-job-agent-server/internal/logger"
	"ops-job-agent-server/pkg/api"

	"github.com/avast/retry-go/v4"
	"github.com/gin-gonic/gin"
	"github.com/gorilla/websocket"
	"github.com/spf13/cast"
)

// handleWebSocket 处理 WebSocket 连接
func (s *Server) handleWebSocket(c *gin.Context) {
	agentID := c.Param("id")

	if shouldBlockWS(agentID) {
		c.JSON(http.StatusServiceUnavailable, gin.H{"error": serrors.ErrWebSocketUnavailable.Error()})
		return
	}

	// 从 Sec-WebSocket-Protocol 头部获取 token（更安全，不暴露在 URL 中）
	token := s.extractTokenFromProtocol(c.GetHeader(constants.HeaderSecWebSocketProtocol))

	// 获取 Agent 连接
	conn, exists := s.agentManager.Get(agentID)
	if !exists {
		writeError(c, http.StatusNotFound, serrors.ErrCodeNotFound, serrors.ErrAgentNotFound.Error())
		return
	}

	// 验证 token
	if conn.Token != token {
		writeError(c, http.StatusUnauthorized, serrors.ErrCodeInvalidParam, serrors.ErrInvalidToken.Error())
		return
	}

	// 升级为 WebSocket
	ws, err := s.upgrader.Upgrade(c.Writer, c.Request, nil)
	if err != nil {
		logger.GetLogger().WithError(err).Error("websocket upgrade failed")
		writeError(c, http.StatusInternalServerError, serrors.ErrCodeNetworkError, serrors.ErrWebSocketUpgradeFailed.Error())
		return
	}
	defer func() {
		_ = ws.Close()
	}()

	// 建立连接
	agentConn, err := s.agentManager.Connect(agentID, token, ws)
	if err != nil {
		logger.GetLogger().WithError(err).Error("connect agent failed")
		writeError(c, http.StatusInternalServerError, serrors.ErrCodeConnectionFailed, serrors.ErrAgentConnectFailed.Error())
		return
	}

	logger.GetLogger().WithFields(map[string]interface{}{
		"agent_id": agentID,
	}).Info("websocket connected")

	// Agent上线时，处理待处理任务
	if s.taskDispatcher != nil {
		go func() {
			if err := s.taskDispatcher.ProcessPendingTasksForAgent(agentID); err != nil {
				logger.GetLogger().WithError(err).WithField("agent_id", agentID).Error("process pending tasks failed")
			}
		}()
	}

	// 启动消息处理
	s.handleWebSocketMessages(agentConn)
}

// extractTokenFromProtocol 从 Sec-WebSocket-Protocol 头部提取 token
// 格式: "agent-token,<actual-token>"
func (s *Server) extractTokenFromProtocol(protocol string) string {
	if protocol == "" {
		return ""
	}
	// 格式: "agent-token,<token>"
	prefix := "agent-token,"
	if len(protocol) > len(prefix) && protocol[:len(prefix)] == prefix {
		return protocol[len(prefix):]
	}
	// 兼容旧格式：直接是 token
	return protocol
}

// requireSignature 校验 HMAC 时间窗签名：X-Timestamp + X-Signature
func (s *Server) requireSignature() gin.HandlerFunc {
	secret := s.cfg.Auth.SharedSecret
	clockSkew := s.cfg.Auth.ClockSkew
	if clockSkew <= 0 {
		clockSkew = 5 * time.Minute
	}
	return func(c *gin.Context) {
		if secret == "" {
			c.Next()
			return
		}

		tsStr := c.GetHeader(constants.HeaderTimestamp)
		sig := c.GetHeader(constants.HeaderSignature)
		if tsStr == "" || sig == "" {
			c.AbortWithStatusJSON(http.StatusForbidden, gin.H{"error": serrors.ErrMissingSignature.Error()})
			return
		}
		ts, err := cast.ToInt64E(tsStr)
		if err != nil {
			c.AbortWithStatusJSON(http.StatusForbidden, gin.H{"error": serrors.ErrInvalidTimestamp.Error()})
			return
		}
		now := time.Now().Unix()
		if auth.AbsInt64(now-ts) > int64(clockSkew.Seconds()) {
			c.AbortWithStatusJSON(http.StatusForbidden, gin.H{"error": serrors.ErrTimestampSkew.Error()})
			return
		}

		bodyBytes, err := c.GetRawData()
		if err != nil {
			c.AbortWithStatusJSON(http.StatusForbidden, gin.H{"error": serrors.ErrReadBodyFailed.Error()})
			return
		}
		// 读过 body 之后需要恢复
		c.Request.Body = io.NopCloser(bytes.NewBuffer(bodyBytes))

		// 使用真实 URL.Path（而不是gin的FullPath路由模板），保证控制面计算签名稳定一致
		path := c.Request.URL.Path
		expected := auth.ComputeHMAC(secret, c.Request.Method, path, tsStr, bodyBytes)
		if !hmac.Equal([]byte(expected), []byte(sig)) {
			c.AbortWithStatusJSON(http.StatusForbidden, gin.H{"error": serrors.ErrInvalidSignature.Error()})
			return
		}

		c.Next()
	}
}

// handleWebSocketMessages 处理 WebSocket 消息
func (s *Server) handleWebSocketMessages(conn *agent.Connection) {
	defer func() {
		// Agent断开连接时单次推送离线状态
		go s.pushStatus(context.Background(), conn, constants.StatusOffline, map[string]interface{}{
			"disconnect_reason": "websocket_closed",
			"disconnect_time":   time.Now().Unix(),
		})

		// Agent断开连接时推送最终任务统计
		if s.taskStatsAggregator != nil {
			s.taskStatsAggregator.OnAgentDisconnect(context.Background(), conn.ID)
		}

		conn.MarkDisconnected()
		logger.GetLogger().WithField("agent_id", conn.ID).Info("websocket disconnected")
	}()

	// 启动任务队列处理
	go s.handleTaskQueue(conn)

	// 启动日志缓冲处理
	go s.handleLogBuffer(conn)

	for {
		var msg api.WebSocketMessage
		if err := conn.Conn.ReadJSON(&msg); err != nil {
			if websocket.IsUnexpectedCloseError(err, websocket.CloseGoingAway, websocket.CloseAbnormalClosure) {
				logger.GetLogger().WithError(err).Error("websocket read error")
			}
			break
		}

		switch msg.Type {
		case constants.MessageTypeHeartbeat:
			conn.UpdateHeartbeat()
			// 写入状态流：online
			go s.pushStatus(context.Background(), conn, constants.StatusOnline, msg.Payload)

		case constants.MessageTypeTaskResult:
			if msg.MessageID == "" {
				logger.GetLogger().WithField("agent_id", conn.ID).Warn("task_result missing message_id, dropped")
				continue
			}
			if conn.SeenMessage(msg.MessageID, constants.AckCacheTTL, constants.AckCacheMax) {
				s.sendAck(conn, msg.MessageID)
				continue
			}
			if msg.Result == nil {
				logger.GetLogger().WithField("message_id", msg.MessageID).Warn("task_result missing payload")
				continue
			}
			if err := s.pushResult(context.Background(), conn.ID, msg.Result); err != nil {
				logger.GetLogger().WithError(err).WithFields(map[string]interface{}{
					"agent_id":   conn.ID,
					"message_id": msg.MessageID,
					"task_id":    msg.TaskID,
				}).Warn("push result failed, waiting for retry")
				continue
			}

			// 更新任务统计
			if s.taskStatsAggregator != nil && msg.Result != nil {
				// 计算执行时长（毫秒）
				var durationMs int64
				if msg.Result.StartedAt > 0 && msg.Result.FinishedAt > 0 {
					durationMs = msg.Result.FinishedAt - msg.Result.StartedAt
				}
				// 使用 result.status 作为任务状态
				s.taskStatsAggregator.UpdateTaskStats(conn.ID, msg.Result.Status, durationMs)

				// 节流推送：如果到达推送间隔，异步推送到状态流
				if s.taskStatsAggregator.ShouldPush(conn.ID) {
					go func(agentID string) {
						if err := s.taskStatsAggregator.PushToStream(context.Background(), agentID); err != nil {
							logger.GetLogger().WithError(err).WithField("agent_id", agentID).Warn("push task stats failed")
						}
					}(conn.ID)
				}
			}

			// 任务完成，从运行任务列表中移除
			conn.RemoveRunningTask(msg.TaskID)
			s.sendAck(conn, msg.MessageID)

		case constants.MessageTypeLog:
			if msg.MessageID == "" {
				logger.GetLogger().WithField("agent_id", conn.ID).Warn("log message missing message_id, dropped")
				continue
			}
			if msg.TaskID == "" {
				logger.GetLogger().WithFields(map[string]interface{}{
					"agent_id":   conn.ID,
					"message_id": msg.MessageID,
				}).Warn("log message missing task_id, ack to avoid retry")
				s.sendAck(conn, msg.MessageID)
				continue
			}
			if conn.SeenMessage(msg.MessageID, constants.AckCacheTTL, constants.AckCacheMax) {
				s.sendAck(conn, msg.MessageID)
				continue
			}
			if len(msg.Logs) == 0 {
				logger.GetLogger().WithFields(map[string]interface{}{
					"agent_id":   conn.ID,
					"message_id": msg.MessageID,
				}).Warn("log message empty, ack to avoid retry")
				s.sendAck(conn, msg.MessageID)
				continue
			}

			// 填充 task_id 到所有日志条目
			for i := range msg.Logs {
				if msg.TaskID != "" {
					msg.Logs[i].TaskID = msg.TaskID
				}
			}

			// 写入 LogBuffer 通道（非阻塞，避免阻塞消息循环）
			s.writeToLogBuffer(conn, msg.Logs)

			// 立即 ACK，因为已写入缓冲
			s.sendAck(conn, msg.MessageID)
		}
	}
}

func (s *Server) sendAck(conn *agent.Connection, messageID string) {
	if conn == nil || messageID == "" {
		return
	}
	ack := api.WebSocketMessage{
		Type:  constants.MessageTypeAck,
		AckID: messageID,
	}
	if err := conn.Conn.WriteJSON(ack); err != nil {
		logger.GetLogger().WithError(err).WithFields(map[string]interface{}{
			"agent_id":   conn.ID,
			"message_id": messageID,
		}).Warn("send websocket ack failed")
	}
}

// writeToLogBuffer 将日志写入 LogBuffer 通道（非阻塞）
func (s *Server) writeToLogBuffer(conn *agent.Connection, logs []api.LogEntry) {
	if len(logs) == 0 {
		return
	}

	// 获取缓冲区配置
	bufferSize := s.cfg.LogStream.BufferSize
	if bufferSize <= 0 {
		bufferSize = 1000
	}

	// 非阻塞写入，避免阻塞消息循环
	droppedCount := 0
	for _, log := range logs {
		select {
		case conn.LogBuffer <- &log:
			// 写入成功
		default:
			// 缓冲区满，丢弃当前日志
			droppedCount++
		}
	}

	if droppedCount > 0 {
		logger.GetLogger().WithFields(map[string]interface{}{
			"agent_id":      conn.ID,
			"total_logs":    len(logs),
			"dropped_count": droppedCount,
			"buffer_size":   bufferSize,
		}).Warn("log buffer full, some logs dropped")
	}
}

// handleTaskQueue 处理任务队列
func (s *Server) handleTaskQueue(conn *agent.Connection) {
	for task := range conn.TaskQueue {
		if err := conn.SendTask(task); err != nil {
			logger.GetLogger().WithError(err).WithField("task_id", task.ID).Error("send task failed")
			if s.pendingTaskStore != nil {
				if incErr := s.pendingTaskStore.IncrementRetry(conn.ID, task.ID); incErr != nil {
					logger.GetLogger().WithError(incErr).WithFields(map[string]interface{}{
						"agent_id": conn.ID,
						"task_id":  task.ID,
					}).Warn("increment pending task retry failed")
				}
			}
		}
	}
}

// handleLogBuffer 处理日志缓冲
// 从 LogBuffer 通道读取日志，按 task_id 分组，批量写入 Redis Stream
func (s *Server) handleLogBuffer(conn *agent.Connection) {
	// 从配置获取参数，使用默认值防止配置未设置
	bufferSize := s.cfg.LogStream.BufferSize
	if bufferSize <= 0 {
		bufferSize = 1000
	}

	batchSize := s.cfg.LogStream.BatchSize
	if batchSize <= 0 {
		batchSize = 50
	}

	flushInterval := time.Duration(s.cfg.LogStream.FlushInterval) * time.Millisecond
	if flushInterval <= 0 {
		flushInterval = 2 * time.Second
	}

	var totalBuffered int // 当前缓冲的总日志条数

	ticker := time.NewTicker(flushInterval)
	defer ticker.Stop()

	// 按 task_id 分组日志
	taskLogs := make(map[string][]api.LogEntry)
	for {
		select {
		case logEntry, ok := <-conn.LogBuffer:
			if !ok {
				// 通道关闭（Agent断线），优雅地处理剩余日志
				s.handleAgentDisconnectLogs(conn.ID, taskLogs, totalBuffered)
				return
			}

			// 从日志条目中获取 task_id
			taskID := logEntry.TaskID
			if taskID == "" {
				taskID = "unknown"
			}

			// 检查总缓冲大小限制
			if totalBuffered >= bufferSize {
				logger.GetLogger().WithFields(map[string]interface{}{
					"agent_id": conn.ID,
					"task_id":  taskID,
				}).Warn("log buffer full, dropping old logs")

				// 丢弃最旧的日志：优先丢弃其他任务的日志，保留当前任务
				if s.evictOldLogs(taskLogs, &totalBuffered, taskID) {
					// 如果还是满了，丢弃当前日志
					continue
				}
			}

			taskLogs[taskID] = append(taskLogs[taskID], *logEntry)
			totalBuffered++

			// 批量发送（每个任务达到 batchSize 条日志时）
			if len(taskLogs[taskID]) >= batchSize {
				if err := s.pushLogs(context.Background(), conn.ID, taskID, taskLogs[taskID]); err != nil {
					logger.GetLogger().WithError(err).WithFields(map[string]interface{}{
						"agent_id": conn.ID,
						"task_id":  taskID,
					}).Warn("push logs failed (buffer flush)")
				}
				totalBuffered -= len(taskLogs[taskID])
				taskLogs[taskID] = taskLogs[taskID][:0]
			}

		case <-ticker.C:
			// 定时发送所有任务的日志
			for taskID, logs := range taskLogs {
				if len(logs) > 0 {
					if err := s.pushLogs(context.Background(), conn.ID, taskID, logs); err != nil {
						logger.GetLogger().WithError(err).WithFields(map[string]interface{}{
							"agent_id": conn.ID,
							"task_id":  taskID,
						}).Warn("push logs failed (tick flush)")
					}
					taskLogs[taskID] = logs[:0]
				}
			}
		}
	}
}

// pushStatus 将 Agent 在线状态写入状态流
func (s *Server) pushStatus(ctx context.Context, conn *agent.Connection, status string, payload map[string]interface{}) {
	if s.statusStream == nil || conn == nil {
		return
	}

	fields := map[string]interface{}{
		"agent_id":       conn.ID,
		"agent_name":     conn.Name,
		"host_id":        conn.HostID,
		"status":         status,
		"last_heartbeat": conn.LastHeartbeat.UnixMilli(),
	}

	// 从 SystemInfo / payload 中提取补充信息
	if conn.System != nil {
		if conn.System.Hostname != "" {
			fields["hostname"] = conn.System.Hostname
		}
		if conn.System.OS != "" {
			fields["os"] = conn.System.OS
		}
		if conn.System.Arch != "" {
			fields["arch"] = conn.System.Arch
		}
	}

	// 从心跳 payload 中提取系统资源监控数据
	// payload 格式: {"timestamp": int64, "system": SystemInfo}
	if payload != nil {
		// 将payload转换为json字符串用于gjson解析
		payloadJSON, err := sonic.Marshal(payload)
		if err != nil {
			logger.GetLogger().WithError(err).WithField("agent_id", conn.ID).Warn("failed to marshal payload for gjson parsing")
		} else {
			systemData := make(map[string]interface{})

			// 使用gjson高效提取系统信息
			systemResult := gjson.GetBytes(payloadJSON, "system")
			if systemResult.Exists() {
				// CPU 使用率
				if cpuUsage := gjson.GetBytes(payloadJSON, "system.cpu_usage"); cpuUsage.Exists() {
					systemData["cpu_usage"] = cpuUsage.Value()
				}

				// 内存信息 - 控制面期望格式: memory: {total, used, usage}
				memoryInfo := make(map[string]interface{})
				if memUsage := gjson.GetBytes(payloadJSON, "system.memory_usage"); memUsage.Exists() {
					memoryInfo["usage"] = memUsage.Value()
				}
				if memTotal := gjson.GetBytes(payloadJSON, "system.memory_total"); memTotal.Exists() {
					memoryInfo["total"] = memTotal.Value()
				}
				if memUsed := gjson.GetBytes(payloadJSON, "system.memory_used"); memUsed.Exists() {
					memoryInfo["used"] = memUsed.Value()
				}
				if len(memoryInfo) > 0 {
					systemData["memory"] = memoryInfo
				}

				// 磁盘使用率
				if diskUsage := gjson.GetBytes(payloadJSON, "system.disk_usage"); diskUsage.Exists() {
					systemData["disk"] = diskUsage.Value()
				}

				// 负载信息 - 控制面期望格式: load_avg: {1m, 5m, 15m}
				loadAvgResult := gjson.GetBytes(payloadJSON, "system.load_avg")
				if loadAvgResult.Exists() && loadAvgResult.IsArray() {
					loadArr := loadAvgResult.Array()
					if len(loadArr) >= 3 {
						systemData["load_avg"] = map[string]interface{}{
							"1m":  loadArr[0].Value(),
							"5m":  loadArr[1].Value(),
							"15m": loadArr[2].Value(),
						}
					}
				}

				// 系统运行时间
				if uptime := gjson.GetBytes(payloadJSON, "system.uptime"); uptime.Exists() {
					systemData["uptime"] = uptime.Value()
				}
			}

			if len(systemData) > 0 {
				fields["system"] = systemData
			}
		}
	}

	if err := s.statusStream.PushStatus(ctx, fields); err != nil {
		logger.GetLogger().WithError(err).WithField("agent_id", conn.ID).Warn("push status to stream failed")
	}
}

// cleanupLoop 定期清理非活跃连接
func (s *Server) cleanupLoop() {
	ticker := time.NewTicker(10 * time.Second)
	defer ticker.Stop()

	for {
		select {
		case <-ticker.C:
			// 清理非活跃连接，并为变为离线的连接写一条 offline 状态
			agents := s.agentManager.List()
			s.agentManager.CleanupInactive()
			for _, a := range agents {
				if !a.IsAlive(s.cfg.Agent.HeartbeatTimeout) {
					go s.pushStatus(context.Background(), a, constants.StatusOffline, nil)
				}
			}
		}
	}
}

// handleAgentDisconnectLogs 处理Agent断线时的日志，确保日志完整性
func (s *Server) handleAgentDisconnectLogs(agentID string, taskLogs map[string][]api.LogEntry, totalBuffered int) {
	if len(taskLogs) == 0 {
		logger.GetLogger().WithField("agent_id", agentID).Debug("no buffered logs on agent disconnect")
		return
	}

	logger.GetLogger().WithFields(map[string]interface{}{
		"agent_id":       agentID,
		"buffered_tasks": len(taskLogs),
		"total_logs":     totalBuffered,
	}).Info("handling buffered logs on agent disconnect")

	// 设置超时上下文，确保不会无限等待
	ctx, cancel := context.WithTimeout(context.Background(), 30*time.Second)
	defer cancel()

	successCount := 0
	failedCount := 0
	totalPushedLogs := 0

	// 尝试推送所有缓冲的日志
	for taskID, logs := range taskLogs {
		if len(logs) == 0 {
			continue
		}

		// 对每个任务的日志按时间戳排序
		sortedLogs := make([]api.LogEntry, len(logs))
		copy(sortedLogs, logs)
		sortLogsByTimestamp(sortedLogs)

		err := retry.Do(
			func() error {
				return s.pushLogs(ctx, agentID, taskID, sortedLogs)
			},
			retry.Attempts(3),
			retry.Delay(500*time.Millisecond),
			retry.DelayType(retry.BackOffDelay),
			retry.Context(ctx),
		)
		if err != nil {
			logger.GetLogger().WithError(err).WithFields(map[string]interface{}{
				"agent_id":  agentID,
				"task_id":   taskID,
				"log_count": len(sortedLogs),
				"retries":   3,
			}).Error("permanently failed to push logs on agent disconnect")
			failedCount++
		} else {
			logger.GetLogger().WithFields(map[string]interface{}{
				"agent_id":  agentID,
				"task_id":   taskID,
				"log_count": len(sortedLogs),
			}).Debug("successfully pushed logs on disconnect")
			successCount++
			totalPushedLogs += len(sortedLogs)
		}

	}

	logger.GetLogger().WithFields(map[string]interface{}{
		"agent_id":      agentID,
		"tasks_total":   len(taskLogs),
		"tasks_success": successCount,
		"tasks_failed":  failedCount,
		"logs_pushed":   totalPushedLogs,
		"logs_total":    totalBuffered,
		"success_rate":  fmt.Sprintf("%.1f%%", float64(totalPushedLogs)/float64(totalBuffered)*100),
	}).Info("completed handling agent disconnect logs")
}
