package websocket

import (
	"bufio"
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

	// DefaultMaxFileSize 默认最大文件大小（10MB）
	DefaultMaxFileSize = 10 * 1024 * 1024

	// DefaultFileRetention 默认文件保留期限（7天）
	DefaultFileRetention = 7 * 24 * time.Hour

	// DefaultCleanInterval 默认清理间隔（1小时）
	DefaultCleanInterval = time.Hour
)

// FileOutbox 是一个持久化的待发送队列，使用本地文件存储 WS 消息。
// 采用内存队列 + 本地文件双模式：
// - 内存队列：提供快速写入和读取
// - 本地文件：提供持久化保证，确保断线重启后消息不丢失
type FileOutbox struct {
	mu            sync.Mutex
	agentID       string
	filePath      string
	messages      []Message     // 内存队列
	maxSize       int           // 最大消息数量（内存）
	fileEnabled   bool          // 是否启用文件持久化
	dropped       int64         // 丢弃的消息数量
	writeCount    int64         // 写入文件次数（用于轮转判断）
	maxFileSize   int64         // 最大文件大小（字节）
	fileRetention time.Duration // 文件保留期限
	cleanTicker   *time.Ticker  // 清理定时器
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
		agentID:       agentID,
		filePath:      filePath,
		messages:      make([]Message, 0, maxSize),
		maxSize:       maxSize,
		fileEnabled:   outboxDir != "",
		dropped:       0,
		writeCount:    0,
		maxFileSize:   DefaultMaxFileSize,
		fileRetention: DefaultFileRetention,
	}

	// 从文件恢复未发送的消息
	if outbox.fileEnabled {
		outbox.recoverFromFile()
		// 启动定期清理任务
		outbox.startCleanupTask()
	}

	if outbox.fileEnabled {
		logger.GetLogger().WithFields(map[string]interface{}{
			"agent_id":    agentID,
			"file_path":   filePath,
			"max_size":    maxSize,
			"recovered":   len(outbox.messages),
			"max_file_mb": DefaultMaxFileSize / 1024 / 1024,
		}).Info("FileOutbox initialized with file persistence")
	} else {
		logger.GetLogger().WithFields(map[string]interface{}{
			"agent_id": agentID,
			"max_size": maxSize,
		}).Warn("FileOutbox initialized in memory-only mode (no file persistence)")
	}

	return outbox
}

// startCleanupTask 启动定期清理任务
func (o *FileOutbox) startCleanupTask() {
	o.cleanTicker = time.NewTicker(DefaultCleanInterval)
	go func() {
		for range o.cleanTicker.C {
			o.cleanOldFiles()
		}
	}()
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
		data, err := sonic.Marshal(fileMsg)
		if err != nil {
			logger.GetLogger().WithError(err).WithField("message_id", msg.MessageID).Error("Failed to marshal file message")
			return
		}

		// 先获取文件锁，检查是否需要轮转
		o.mu.Lock()
		needsRotate, err := o.checkAndRotateFile()
		o.mu.Unlock()

		if err != nil {
			logger.GetLogger().WithError(err).WithField("file_path", o.filePath).Error("Failed to check file rotation")
			return
		}

		if needsRotate {
			// 文件已轮转，重新打开
			logger.GetLogger().WithField("file_path", o.filePath).Info("Outbox file rotated due to size limit")
		}

		file, err := os.OpenFile(o.filePath, os.O_APPEND|os.O_CREATE|os.O_WRONLY, OutboxFilePermission)
		if err != nil {
			logger.GetLogger().WithError(err).WithField("file_path", o.filePath).Error("Failed to open outbox file for write")
			return
		}
		defer func() {
			_ = file.Close()
		}()

		// 每行一个json对象
		data = append(data, '\n')

		if _, err := file.Write(data); err != nil {
			logger.GetLogger().WithError(err).WithField("file_path", o.filePath).Error("Failed to write to outbox file")
			return
		}

		o.mu.Lock()
		o.writeCount++
		o.mu.Unlock()
	}()
}

// checkAndRotateFile 检查文件大小，如果超过限制则轮转
// caller must hold o.mu
func (o *FileOutbox) checkAndRotateFile() (bool, error) {
	if !o.fileEnabled || o.filePath == "" {
		return false, nil
	}

	fileInfo, err := os.Stat(o.filePath)
	if err != nil {
		if os.IsNotExist(err) {
			return false, nil
		}
		return false, err
	}

	// 检查文件大小是否超过限制
	if fileInfo.Size() >= o.maxFileSize {
		// 生成带时间戳的历史文件名
		timestamp := time.Now().Format("20060102_150405")
		historyPath := fmt.Sprintf("%s.%s.old", o.filePath, timestamp)

		// 重命名当前文件
		if err := os.Rename(o.filePath, historyPath); err != nil {
			logger.GetLogger().WithError(err).WithFields(map[string]interface{}{
				"from": o.filePath,
				"to":   historyPath,
			}).Error("Failed to rotate outbox file")
			return false, err
		}

		logger.GetLogger().WithFields(map[string]interface{}{
			"old_file": historyPath,
			"size_mb":  float64(fileInfo.Size()) / 1024 / 1024,
		}).Info("Outbox file rotated successfully")
		return true, nil
	}

	return false, nil
}

// cleanOldFiles 清理过期的历史文件
func (o *FileOutbox) cleanOldFiles() {
	if !o.fileEnabled || o.filePath == "" {
		return
	}

	dir := filepath.Dir(o.filePath)
	baseName := filepath.Base(o.filePath)
	prefix := fmt.Sprintf("%s.", baseName)

	entries, err := os.ReadDir(dir)
	if err != nil {
		logger.GetLogger().WithError(err).WithField("dir", dir).Error("Failed to read directory for cleanup")
		return
	}

	cutoff := time.Now().Add(-o.fileRetention)
	var deletedCount int
	var deletedSize int64

	for _, entry := range entries {
		if !entry.IsDir() && len(entry.Name()) > len(prefix) && entry.Name()[:len(prefix)] == prefix {
			info, err := entry.Info()
			if err != nil {
				continue
			}

			// 检查文件是否过期
			if info.ModTime().Before(cutoff) {
				fullPath := filepath.Join(dir, entry.Name())
				size := info.Size()

				if err := os.Remove(fullPath); err != nil {
					logger.GetLogger().WithError(err).WithField("file", fullPath).Warn("Failed to delete old outbox file")
					continue
				}

				deletedCount++
				deletedSize += size
			}
		}
	}

	if deletedCount > 0 {
		logger.GetLogger().WithFields(map[string]interface{}{
			"deleted_count": deletedCount,
			"deleted_size":  deletedSize,
		}).Info("Cleaned up old outbox files")
	}
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

// Stats 返回队列长度与丢弃数量（用于测试或监控）
func (o *FileOutbox) Stats() (int, int64) {
	o.mu.Lock()
	defer o.mu.Unlock()
	return len(o.messages), o.dropped
}

// Close 关闭 Outbox
// 清理资源，但不清除文件（保留未发送的消息供下次恢复）
func (o *FileOutbox) Close() {
	// 停止清理定时器
	if o.cleanTicker != nil {
		o.cleanTicker.Stop()
	}

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
	defer func() {
		_ = file.Close()
	}()

	scanner := bufio.NewScanner(file)
	recoveredCount := 0
	skippedCount := 0

	for scanner.Scan() {
		line := scanner.Bytes()
		if len(line) == 0 {
			continue
		}

		var fileMsg fileMessage
		if err := sonic.Unmarshal(line, &fileMsg); err != nil {
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
	defer func() {
		_ = file.Close()
	}()

	writer := bufio.NewWriter(file)
	defer func() {
		_ = writer.Flush()
	}()

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

		data, err := sonic.Marshal(fileMsg)
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
			stats["file_size_mb"] = float64(fileInfo.Size()) / 1024 / 1024
		}
	}

	return stats
}
