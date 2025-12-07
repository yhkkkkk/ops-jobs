package logstream

import (
	"context"
	"encoding/json"
	"fmt"
	"sync"
	"time"

	"github.com/redis/go-redis/v9"
	"ops-job-agent/internal/api"
	"ops-job-agent/internal/logger"
)

// RedisLogStream 基于 Redis Stream 的日志流管理器
type RedisLogStream struct {
	client        *redis.Client
	streamPrefix  string
	buffer        map[string]*LogBuffer // task_id -> buffer
	bufferLock    sync.RWMutex
	batchSize     int           // 批量大小
	flushInterval time.Duration // 刷新间隔
	stopCh        chan struct{}
	wg            sync.WaitGroup
}

// NewRedisLogStream 创建基于 Redis Stream 的日志流管理器
func NewRedisLogStream(redisClient *redis.Client, streamPrefix string, batchSize int, flushInterval time.Duration) *RedisLogStream {
	if streamPrefix == "" {
		streamPrefix = "job_logs:"
	}
	if batchSize <= 0 {
		batchSize = 10
	}
	if flushInterval <= 0 {
		flushInterval = 200 * time.Millisecond
	}

	ls := &RedisLogStream{
		client:        redisClient,
		streamPrefix:  streamPrefix,
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
func (ls *RedisLogStream) PushLog(taskID string, entry LogEntry) {
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
func (ls *RedisLogStream) flushLoop() {
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
func (ls *RedisLogStream) flushAll() {
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

// flushBuffer 刷新单个缓冲区到 Redis Stream
func (ls *RedisLogStream) flushBuffer(taskID string, buf *LogBuffer) {
	if len(buf.Logs) == 0 {
		return
	}

	// 复制日志并清空缓冲区
	logs := make([]api.LogEntry, len(buf.Logs))
	copy(logs, buf.Logs)
	buf.Logs = buf.Logs[:0]
	buf.LastFlush = time.Now()

	// 异步写入 Redis，避免阻塞
	go func() {
		ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
		defer cancel()

		streamKey := fmt.Sprintf("%s%s", ls.streamPrefix, taskID)
		pipe := ls.client.Pipeline()

		// 批量写入日志
		for _, log := range logs {
			message := map[string]interface{}{
				"timestamp": log.Timestamp,
				"level":     log.Level,
				"content":   log.Content,
			}
			if log.HostID > 0 {
				message["host_id"] = log.HostID
			}
			if log.HostName != "" {
				message["host_name"] = log.HostName
			}

			// 将 map 转换为 Redis 需要的格式
			redisMsg := make(map[string]interface{})
			for k, v := range message {
				var val string
				switch v := v.(type) {
				case string:
					val = v
				case int:
					val = fmt.Sprintf("%d", v)
				case int64:
					val = fmt.Sprintf("%d", v)
				default:
					if data, err := json.Marshal(v); err == nil {
						val = string(data)
					} else {
						val = fmt.Sprintf("%v", v)
					}
				}
				redisMsg[k] = val
			}

			pipe.XAdd(ctx, &redis.XAddArgs{
				Stream: streamKey,
				Values: redisMsg,
			})
		}

		// 设置过期时间（12小时）
		pipe.Expire(ctx, streamKey, 12*time.Hour)

		// 执行 pipeline
		_, err := pipe.Exec(ctx)
		if err != nil {
			logger.GetLogger().WithError(err).WithField("task_id", taskID).
				Error("push logs to redis stream failed")
		}
	}()
}

// Stop 停止日志流
func (ls *RedisLogStream) Stop() {
	close(ls.stopCh)
	ls.wg.Wait()
}

// RemoveTask 移除任务缓冲区
func (ls *RedisLogStream) RemoveTask(taskID string) {
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

