package logstream

import (
	"context"
	"sync"
	"time"

	"ops-job-agent/internal/api"
	"ops-job-agent/internal/httpclient"
	"ops-job-agent/internal/logger"
)

// LogStream 日志流管理器，负责批量推送日志
type LogStream struct {
	client        *httpclient.Client
	agentID       string
	buffer        map[string]*LogBuffer // task_id -> buffer
	bufferLock    sync.RWMutex
	batchSize     int           // 批量大小
	flushInterval time.Duration // 刷新间隔
	stopCh        chan struct{}
	wg            sync.WaitGroup
}

// LogBuffer 日志缓冲区
type LogBuffer struct {
	TaskID    string
	Logs      []api.LogEntry
	Lock      sync.Mutex
	LastFlush time.Time
}

// LogEntry 日志条目
type LogEntry struct {
	Timestamp int64  `json:"timestamp"`
	Level     string `json:"level"` // info/warn/error
	Content   string `json:"content"`
	HostID    int    `json:"host_id,omitempty"`
	HostName  string `json:"host_name,omitempty"`
}

// NewLogStream 创建日志流管理器
func NewLogStream(client *httpclient.Client, agentID string, batchSize int, flushInterval time.Duration) *LogStream {
	if batchSize <= 0 {
		batchSize = 10 // 默认批量大小
	}
	if flushInterval <= 0 {
		flushInterval = 200 * time.Millisecond // 默认 200ms
	}

	ls := &LogStream{
		client:        client,
		agentID:       agentID,
		buffer:        make(map[string]*LogBuffer),
		batchSize:     batchSize,
		flushInterval: flushInterval,
		stopCh:        make(chan struct{}),
	}

	// 启动定期刷新协程
	ls.wg.Add(1)
	go ls.flushLoop()

	return ls
}

// PushLog 推送单条日志
func (ls *LogStream) PushLog(taskID string, entry LogEntry) {
	ls.bufferLock.Lock()
	buf, exists := ls.buffer[taskID]
	if !exists {
		buf = &LogBuffer{
			TaskID:    taskID,
			Logs:      make([]api.LogEntry, 0, ls.batchSize),
			LastFlush: time.Now(),
		}
		ls.buffer[taskID] = buf
	}
	ls.bufferLock.Unlock()

	buf.Lock.Lock()
	defer buf.Lock.Unlock()

	// 转换为 API 格式
	apiEntry := api.LogEntry{
		Timestamp: entry.Timestamp,
		Level:     entry.Level,
		Content:   entry.Content,
		HostID:    entry.HostID,
		HostName:  entry.HostName,
	}

	buf.Logs = append(buf.Logs, apiEntry)

	// 如果达到批量大小，立即刷新
	if len(buf.Logs) >= ls.batchSize {
		ls.flushBuffer(taskID, buf)
	}
}

// flushLoop 定期刷新循环
func (ls *LogStream) flushLoop() {
	defer ls.wg.Done()
	ticker := time.NewTicker(ls.flushInterval)
	defer ticker.Stop()

	for {
		select {
		case <-ls.stopCh:
			// 停止时刷新所有缓冲区
			ls.flushAll()
			return
		case <-ticker.C:
			ls.flushAll()
		}
	}
}

// flushAll 刷新所有缓冲区
func (ls *LogStream) flushAll() {
	ls.bufferLock.RLock()
	buffers := make([]*LogBuffer, 0, len(ls.buffer))
	for _, buf := range ls.buffer {
		buffers = append(buffers, buf)
	}
	ls.bufferLock.RUnlock()

	for _, buf := range buffers {
		buf.Lock.Lock()
		if len(buf.Logs) > 0 {
			// 检查是否超过刷新间隔
			if time.Since(buf.LastFlush) >= ls.flushInterval {
				ls.flushBuffer(buf.TaskID, buf)
			}
		}
		buf.Lock.Unlock()
	}
}

// flushBuffer 刷新单个缓冲区
func (ls *LogStream) flushBuffer(taskID string, buf *LogBuffer) {
	if len(buf.Logs) == 0 {
		return
	}

	// 复制日志并清空缓冲区
	logs := make([]api.LogEntry, len(buf.Logs))
	copy(logs, buf.Logs)
	buf.Logs = buf.Logs[:0]
	buf.LastFlush = time.Now()

	// 异步推送，避免阻塞
	go func() {
		ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
		defer cancel()

		if err := ls.client.PushLogs(ctx, ls.agentID, taskID, logs); err != nil {
			logger.GetLogger().WithError(err).WithField("task_id", taskID).
				Error("push logs failed")
		}
	}()
}

// Stop 停止日志流
func (ls *LogStream) Stop() {
	close(ls.stopCh)
	ls.wg.Wait()
}

// RemoveTask 移除任务缓冲区
func (ls *LogStream) RemoveTask(taskID string) {
	ls.bufferLock.Lock()
	defer ls.bufferLock.Unlock()

	if buf, exists := ls.buffer[taskID]; exists {
		buf.Lock.Lock()
		// 刷新剩余日志
		if len(buf.Logs) > 0 {
			ls.flushBuffer(taskID, buf)
		}
		buf.Lock.Unlock()
		delete(ls.buffer, taskID)
	}
}
