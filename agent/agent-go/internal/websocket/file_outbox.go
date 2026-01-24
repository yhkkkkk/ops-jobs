package websocket

import (
	"bufio"
	"encoding/json"
	"fmt"
	"os"
	"path/filepath"
	"sync"
	"time"

	"ops-job-agent/internal/logger"

	"github.com/bytedance/sonic"
)

const (
	// DefaultOutboxMaxSize 默认 Outbox 最大消息数量
	DefaultOutboxMaxSize = 1000

	// DefaultOutboxFileName 默认 outbox 文件名
	DefaultOutboxFileName = "agent_outbox.txt"

	// OutboxFilePermission outbox 文件权限
	OutboxFilePermission = 0600
)

// FileOutbox 是一个持久化的待发送队列，使用本地文件存储 WS 消息。
// 采用内存队列 + 本地文件双模式：
// - 内存队列：提供快速写入和读取
// - 本地文件：提供持久化保证，确保断线重启后消息不丢失
type FileOutbox struct {
	mu          sync.Mutex
	agentID     string
	filePath    string
	messages    []Message // 内存队列
	maxSize     int       // 最大消息数量（内存）
	fileEnabled bool      // 是否启用文件持久化
	dropped     int64     // 丢弃的消息数量
	writeCount  int64     // 写入文件次数（用于轮转判断）
}

// fileMessage 是本地文件存储的消息格式
type fileMessage struct {
	MessageID string `json:"message_id"`
	Type      string `json:"type"`
	Timestamp int64  `json:"ts"`
	TaskID    string `json:"task_id"`
	Payload   string `json:"payload"` // JSON 序列化后的消息内容
	CreatedAt int64  `json:"created_at"`
}

// NewFileOutbox 创建一个新的 FileOutbox
// agentID: Agent 唯一标识
// outboxDir: outbox 文件存储目录（为空则使用默认目录）
// maxSize: 最大消息数量（<=0 使用默认值）
func NewFileOutbox(agentID, outboxDir string, maxSize int) *FileOutbox {
	if maxSize <= 0 {
		maxSize = DefaultOutboxMaxSize
	}

	// 确定文件路径
	filePath := DefaultOutboxFileName
	if outboxDir != "" {
		// 确保目录存在
		if err := os.MkdirAll(outboxDir, 0755); err != nil {
			logger.GetLogger().WithError(err).WithField("dir", outboxDir).Warn("Failed to create outbox dir, using memory-only mode")
			outboxDir = ""
		} else {
			filePath = filepath.Join(outboxDir, fmt.Sprintf("outbox_%s.txt", agentID))
		}
	}

	outbox := &FileOutbox{
		agentID:     agentID,
		filePath:    filePath,
		messages:    make([]Message, 0, maxSize),
		maxSize:     maxSize,
		fileEnabled: outboxDir != "",
		dropped:     0,
		writeCount:  0,
	}

	// 从文件恢复未发送的消息
	if outbox.fileEnabled {
		outbox.recoverFromFile()
	}

	if outbox.fileEnabled {
		logger.GetLogger().WithFields(map[string]interface{}{
			"agent_id":  agentID,
			"file_path": filePath,
			"max_size":  maxSize,
			"recovered": len(outbox.messages),
		}).Info("FileOutbox initialized with file persistence")
	} else {
		logger.GetLogger().WithFields(map[string]interface{}{
			"agent_id": agentID,
			"max_size": maxSize,
		}).Warn("FileOutbox initialized in memory-only mode (no file persistence)")
	}

	return outbox
}

// Enqueue 添加消息到队列
// 消息会先添加到内存队列，然后尝试写入文件（如果启用）
func (o *FileOutbox) Enqueue(msg Message) {
	o.mu.Lock()
	defer o.mu.Unlock()

	// 检查队列是否已满
	if len(o.messages) >= o.maxSize {
		// 移除最旧的消息
		o.messages = o.messages[1:]
		o.dropped++
		logger.GetLogger().WithField("message_id", msg.MessageID).Warn("Outbox is full, dropped oldest message")
	}

	// 添加到内存队列
	o.messages = append(o.messages, msg)

	// 尝试写入文件（异步，不阻塞）
	if o.fileEnabled {
		o.writeToFileAsync(msg)
	}

	logger.GetLogger().WithFields(map[string]interface{}{
		"message_id": msg.MessageID,
		"msg_type":   msg.Type,
		"queue_size": len(o.messages),
	}).Debug("Message enqueued to FileOutbox")
}

// writeToFileAsync 异步写入文件
// 使用单独的 goroutine 避免阻塞主流程
func (o *FileOutbox) writeToFileAsync(msg Message) {
	go func() {
		fileMsg := fileMessage{
			MessageID: msg.MessageID,
			Type:      msg.Type,
			Timestamp: msg.Timestamp,
			TaskID:    msg.TaskID,
			CreatedAt: time.Now().UnixMilli(),
		}

		// 序列化消息内容
		payload, err := sonic.Marshal(msg)
		if err != nil {
			logger.GetLogger().WithError(err).WithField("message_id", msg.MessageID).Error("Failed to marshal message for file")
			return
		}
		fileMsg.Payload = string(payload)

		// 写入文件
		data, err := json.Marshal(fileMsg)
		if err != nil {
			logger.GetLogger().WithError(err).WithField("message_id", msg.MessageID).Error("Failed to marshal file message")
			return
		}

		file, err := os.OpenFile(o.filePath, os.O_APPEND|os.O_CREATE|os.O_WRONLY, OutboxFilePermission)
		if err != nil {
			logger.GetLogger().WithError(err).WithField("file_path", o.filePath).Error("Failed to open outbox file for write")
			return
		}
		defer file.Close()

		// 每行一个 JSON 对象
		data = append(data, '\n')

		if _, err := file.Write(data); err != nil {
			logger.GetLogger().WithError(err).WithField("file_path", o.filePath).Error("Failed to write to outbox file")
			return
		}

		o.writeCount++
	}()
}

// Drain 从队列中取出最多 max 条消息
// 消息按顺序取出，取出后从队列中移除
func (o *FileOutbox) Drain(max int) []Message {
	o.mu.Lock()
	defer o.mu.Unlock()

	if max <= 0 || len(o.messages) == 0 {
		return nil
	}

	if max > len(o.messages) {
		max = len(o.messages)
	}

	messages := make([]Message, max)
	copy(messages, o.messages[:max])
	o.messages = o.messages[max:]

	if len(messages) > 0 {
		logger.GetLogger().WithFields(map[string]interface{}{
			"agent_id":      o.agentID,
			"drained_count": len(messages),
			"requested_max": max,
			"remaining":     len(o.messages),
		}).Info("Drained messages from FileOutbox")
	}

	return messages
}

// Len 返回队列中的消息数量
func (o *FileOutbox) Len() int {
	o.mu.Lock()
	defer o.mu.Unlock()
	return len(o.messages)
}

// Dropped 返回丢弃的消息数量
func (o *FileOutbox) Dropped() int64 {
	o.mu.Lock()
	defer o.mu.Unlock()
	return o.dropped
}

// Close 关闭 Outbox
// 清理资源，但不清除文件（保留未发送的消息供下次恢复）
func (o *FileOutbox) Close() {
	o.mu.Lock()
	defer o.mu.Unlock()

	// 刷新所有待写入的消息到文件
	if o.fileEnabled && len(o.messages) > 0 {
		o.flushToFileLocked()
	}

	logger.GetLogger().WithField("agent_id", o.agentID).Info("FileOutbox closed")
}

// Clear 清除所有消息（包括文件）
func (o *FileOutbox) Clear() {
	o.mu.Lock()
	defer o.mu.Unlock()

	o.messages = make([]Message, 0, o.maxSize)
	o.dropped = 0

	// 清除文件
	if o.fileEnabled && o.filePath != "" {
		if err := os.Remove(o.filePath); err != nil && !os.IsNotExist(err) {
			logger.GetLogger().WithError(err).WithField("file_path", o.filePath).Error("Failed to clear outbox file")
		}
	}

	logger.GetLogger().WithField("agent_id", o.agentID).Info("FileOutbox cleared")
}

// recoverFromFile 从文件恢复未发送的消息
func (o *FileOutbox) recoverFromFile() {
	if o.filePath == "" {
		return
	}

	file, err := os.OpenFile(o.filePath, os.O_RDONLY|os.O_CREATE, OutboxFilePermission)
	if err != nil {
		if os.IsNotExist(err) {
			return // 文件不存在是正常的
		}
		logger.GetLogger().WithError(err).WithField("file_path", o.filePath).Error("Failed to open outbox file for recovery")
		return
	}
	defer file.Close()

	scanner := bufio.NewScanner(file)
	recoveredCount := 0
	skippedCount := 0

	for scanner.Scan() {
		line := scanner.Bytes()
		if len(line) == 0 {
			continue
		}

		var fileMsg fileMessage
		if err := json.Unmarshal(line, &fileMsg); err != nil {
			logger.GetLogger().WithError(err).Warn("Skipped corrupted line in outbox file")
			skippedCount++
			continue
		}

		// 反序列化消息
		var msg Message
		if err := sonic.Unmarshal([]byte(fileMsg.Payload), &msg); err != nil {
			logger.GetLogger().WithError(err).WithField("message_id", fileMsg.MessageID).Warn("Skipped corrupted message in outbox file")
			skippedCount++
			continue
		}

		// 检查是否已超过 24 小时（避免恢复太旧的消息）
		if time.Since(time.UnixMilli(fileMsg.CreatedAt)) > 24*time.Hour {
			skippedCount++
			continue
		}

		// 检查队列是否已满
		if len(o.messages) >= o.maxSize {
			skippedCount++
			continue
		}

		o.messages = append(o.messages, msg)
		recoveredCount++
	}

	if err := scanner.Err(); err != nil {
		logger.GetLogger().WithError(err).WithField("file_path", o.filePath).Error("Error reading outbox file")
	}

	if recoveredCount > 0 || skippedCount > 0 {
		logger.GetLogger().WithFields(map[string]interface{}{
			"agent_id":  o.agentID,
			"recovered": recoveredCount,
			"skipped":   skippedCount,
			"file_path": o.filePath,
		}).Info("Recovered messages from outbox file")
	}
}

// flushToFileLocked 将内存队列中的所有消息刷新到文件
// caller must hold o.mu
func (o *FileOutbox) flushToFileLocked() {
	if !o.fileEnabled || len(o.messages) == 0 {
		return
	}

	file, err := os.OpenFile(o.filePath, os.O_TRUNC|os.O_CREATE|os.O_WRONLY, OutboxFilePermission)
	if err != nil {
		logger.GetLogger().WithError(err).WithField("file_path", o.filePath).Error("Failed to open outbox file for flush")
		return
	}
	defer file.Close()

	writer := bufio.NewWriter(file)
	defer writer.Flush()

	for _, msg := range o.messages {
		fileMsg := fileMessage{
			MessageID: msg.MessageID,
			Type:      msg.Type,
			Timestamp: msg.Timestamp,
			TaskID:    msg.TaskID,
			CreatedAt: time.Now().UnixMilli(),
		}

		payload, err := sonic.Marshal(msg)
		if err != nil {
			continue
		}
		fileMsg.Payload = string(payload)

		data, err := json.Marshal(fileMsg)
		if err != nil {
			continue
		}

		data = append(data, '\n')
		if _, err := writer.Write(data); err != nil {
			logger.GetLogger().WithError(err).WithField("message_id", msg.MessageID).Error("Failed to write message to outbox file")
		}
	}

	logger.GetLogger().WithField("agent_id", o.agentID).WithField("count", len(o.messages)).Info("Flushed messages to outbox file")
}

// GetStats 获取 Outbox 统计信息
func (o *FileOutbox) GetStats() map[string]interface{} {
	o.mu.Lock()
	defer o.mu.Unlock()

	stats := map[string]interface{}{
		"queue_size":   len(o.messages),
		"max_size":     o.maxSize,
		"dropped":      o.dropped,
		"file_enabled": o.fileEnabled,
	}

	if o.fileEnabled {
		if fileInfo, err := os.Stat(o.filePath); err == nil {
			stats["file_size"] = fileInfo.Size()
		}
	}

	return stats
}
