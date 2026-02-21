package task

import (
	"context"
	"fmt"
	"sync"
	"time"

	"github.com/bytedance/sonic"
	"github.com/redis/go-redis/v9"

	"ops-job-agent-server/internal/logger"
	"ops-job-agent-server/pkg/api"
)

const (
	// Redis key 前缀
	pendingTasksKeyPrefix = "agent:pending_tasks:"
	agentTasksKeyPrefix   = "agent:tasks:"
	taskACKKeyPrefix      = "agent:task_ack:"

	// 默认超时时间
	defaultTaskTimeout = 24 * time.Hour
)

// PendingTask 等待 ACK 的任务
type PendingTask struct {
	AgentID    string        `json:"agent_id"`
	Task       *api.TaskSpec `json:"task"`
	SentAt     time.Time     `json:"sent_at"`
	RetryCount int           `json:"retry_count"`
	MaxRetries int           `json:"max_retries"`
}

// PendingTaskStore 待处理任务存储
// 用于在 Agent-Server 端持久化待处理任务，支持任务恢复和 ACK 确认
type PendingTaskStore struct {
	redis    *redis.Client
	mu       sync.RWMutex
	pending  map[string]*PendingTask // 内存缓存，加速查询
	localTTL time.Duration
}

// NewPendingTaskStore 创建 PendingTaskStore
func NewPendingTaskStore(rdb *redis.Client) *PendingTaskStore {
	if rdb == nil {
		logger.GetLogger().Warn("redis client not provided, PendingTaskStore will work in memory-only mode")
		return &PendingTaskStore{
			pending:  make(map[string]*PendingTask),
			localTTL: 5 * time.Minute,
		}
	}

	return &PendingTaskStore{
		redis:    rdb,
		pending:  make(map[string]*PendingTask),
		localTTL: 5 * time.Minute,
	}
}

// SavePending 保存待处理任务
func (s *PendingTaskStore) SavePending(agentID string, task *api.TaskSpec, maxRetries int) error {
	pending := &PendingTask{
		AgentID:    agentID,
		Task:       task,
		SentAt:     time.Now(),
		RetryCount: 0,
		MaxRetries: maxRetries,
	}

	// 序列化任务
	data, err := sonic.Marshal(pending)
	if err != nil {
		return fmt.Errorf("marshal pending task failed: %w", err)
	}

	key := s.pendingKey(agentID, task.ID)

	// 保存到 Redis
	ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
	defer cancel()

	if s.redis != nil {
		if err := s.redis.Set(ctx, key, data, defaultTaskTimeout).Err(); err != nil {
			return fmt.Errorf("save pending task to redis failed: %w", err)
		}

		// 添加到 Agent 的任务列表
		agentKey := s.agentTasksKey(agentID)
		if err := s.redis.SAdd(ctx, agentKey, task.ID).Err(); err != nil {
			logger.GetLogger().WithError(err).WithField("agent_id", agentID).Warn("failed to add task to agent task set")
		}
		s.redis.Expire(ctx, agentKey, defaultTaskTimeout*2)
	}

	// 更新内存缓存
	s.mu.Lock()
	s.pending[key] = pending
	s.mu.Unlock()

	logger.GetLogger().WithFields(map[string]interface{}{
		"agent_id": agentID,
		"task_id":  task.ID,
	}).Info("task saved to pending store")

	return nil
}

// GetPending 获取待处理任务
func (s *PendingTaskStore) GetPending(agentID, taskID string) (*PendingTask, error) {
	key := s.pendingKey(agentID, taskID)

	// 先检查内存缓存
	s.mu.RLock()
	pending, exists := s.pending[key]
	s.mu.RUnlock()

	if exists {
		return pending, nil
	}

	// 从 Redis 加载
	if s.redis == nil {
		return nil, fmt.Errorf("task not found: %s", taskID)
	}

	ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
	defer cancel()

	data, err := s.redis.Get(ctx, key).Bytes()
	if err != nil {
		if err == redis.Nil {
			return nil, fmt.Errorf("task not found: %s", taskID)
		}
		return nil, fmt.Errorf("get pending task from redis failed: %w", err)
	}

	var pendingTask PendingTask
	if err := sonic.Unmarshal(data, &pendingTask); err != nil {
		return nil, fmt.Errorf("unmarshal pending task failed: %w", err)
	}

	// 更新内存缓存
	s.mu.Lock()
	s.pending[key] = &pendingTask
	s.mu.Unlock()

	return &pendingTask, nil
}

// MarkAcked 标记任务已确认
func (s *PendingTaskStore) MarkAcked(agentID, taskID string) error {
	if err := s.setAck(agentID, taskID, true); err != nil {
		return err
	}
	return s.Delete(agentID, taskID)
}

// Delete 删除待处理任务
func (s *PendingTaskStore) Delete(agentID, taskID string) error {
	key := s.pendingKey(agentID, taskID)

	ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
	defer cancel()

	if s.redis != nil {
		// 从 Redis 删除
		if err := s.redis.Del(ctx, key).Err(); err != nil {
			return fmt.Errorf("delete pending task from redis failed: %w", err)
		}

		// 从 Agent 任务列表移除
		agentKey := s.agentTasksKey(agentID)
		s.redis.SRem(ctx, agentKey, taskID)
	}

	// 从内存缓存移除
	s.mu.Lock()
	delete(s.pending, key)
	s.mu.Unlock()

	logger.GetLogger().WithFields(map[string]interface{}{
		"agent_id": agentID,
		"task_id":  taskID,
	}).Info("task deleted from pending store")

	return nil
}

// HasAcked 检查任务是否已确认（持久化）
func (s *PendingTaskStore) HasAcked(agentID, taskID string) (bool, error) {
	if agentID == "" || taskID == "" {
		return false, fmt.Errorf("invalid agent or task id")
	}

	if s.redis == nil {
		return false, nil
	}

	ctx, cancel := context.WithTimeout(context.Background(), 3*time.Second)
	defer cancel()
	key := s.taskAckKey(agentID)
	exists, err := s.redis.SIsMember(ctx, key, taskID).Result()
	return exists, err
}

// IncrementRetry 重试次数加 1
func (s *PendingTaskStore) IncrementRetry(agentID, taskID string) error {
	key := s.pendingKey(agentID, taskID)

	// 先从内存获取
	s.mu.RLock()
	pending, exists := s.pending[key]
	s.mu.RUnlock()

	if !exists {
		// 从 Redis 加载
		task, err := s.GetPending(agentID, taskID)
		if err != nil {
			return err
		}
		pending = task
	}

	pending.RetryCount++

	// 检查是否超过最大重试次数
	if pending.RetryCount >= pending.MaxRetries {
		logger.GetLogger().WithFields(map[string]interface{}{
			"agent_id":    agentID,
			"task_id":     taskID,
			"retry_count": pending.RetryCount,
			"max_retries": pending.MaxRetries,
		}).Warn("task exceeded max retries, will be marked as failed")
		return s.MarkAcked(agentID, taskID) // 超时不再重试
	}

	// 更新存储
	data, err := sonic.Marshal(pending)
	if err != nil {
		return fmt.Errorf("marshal pending task failed: %w", err)
	}

	ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
	defer cancel()

	if s.redis != nil {
		if err = s.redis.Set(ctx, key, data, defaultTaskTimeout).Err(); err != nil {
			return fmt.Errorf("update pending task in redis failed: %w", err)
		}
	}

	// 更新内存缓存
	s.mu.Lock()
	s.pending[key] = pending
	s.mu.Unlock()

	return nil
}

// GetAgentPendingTasks 获取 Agent 所有待处理任务
func (s *PendingTaskStore) GetAgentPendingTasks(agentID string) ([]*PendingTask, error) {
	agentKey := s.agentTasksKey(agentID)

	ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
	defer cancel()

	var taskIDs []string
	if s.redis != nil {
		ids, err := s.redis.SMembers(ctx, agentKey).Result()
		if err != nil {
			return nil, fmt.Errorf("get agent task IDs from redis failed: %w", err)
		}
		taskIDs = ids
	}

	// 如果 Redis 不可用，从内存缓存获取
	if len(taskIDs) == 0 {
		s.mu.RLock()
		for _, pending := range s.pending {
			if pending.AgentID == agentID {
				taskIDs = append(taskIDs, pending.Task.ID)
			}
		}
		s.mu.RUnlock()
	}

	// 获取每个任务的详细信息
	var tasks []*PendingTask
	for _, taskID := range taskIDs {
		task, err := s.GetPending(agentID, taskID)
		if err != nil {
			logger.GetLogger().WithError(err).WithFields(map[string]interface{}{
				"agent_id": agentID,
				"task_id":  taskID,
			}).Warn("failed to get pending task details")
			continue
		}
		tasks = append(tasks, task)
	}

	return tasks, nil
}

// ClearAgentTasks 清除 Agent 所有待处理任务
func (s *PendingTaskStore) ClearAgentTasks(agentID string) error {
	agentKey := s.agentTasksKey(agentID)

	ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
	defer cancel()

	// 获取所有任务 ID
	taskIDs, err := s.redis.SMembers(ctx, agentKey).Result()
	if err != nil {
		return fmt.Errorf("get agent task IDs failed: %w", err)
	}

	// 删除每个任务
	for _, taskID := range taskIDs {
		key := s.pendingKey(agentID, taskID)
		s.redis.Del(ctx, key)

		s.mu.Lock()
		delete(s.pending, key)
		s.mu.Unlock()
	}

	// 删除 Agent 任务集合
	s.redis.Del(ctx, agentKey)

	logger.GetLogger().WithField("agent_id", agentID).Info("cleared all pending tasks for agent")

	return nil
}

// pendingKey 生成待处理任务 key
func (s *PendingTaskStore) pendingKey(agentID, taskID string) string {
	return fmt.Sprintf("%s%s:%s", pendingTasksKeyPrefix, agentID, taskID)
}

// agentTasksKey 生成 Agent 任务集合 key
func (s *PendingTaskStore) agentTasksKey(agentID string) string {
	return fmt.Sprintf("%s%s", agentTasksKeyPrefix, agentID)
}

// taskAckKey 生成 Agent ack 集合 key
func (s *PendingTaskStore) taskAckKey(agentID string) string {
	return fmt.Sprintf("%s%s", taskACKKeyPrefix, agentID)
}

// Close 关闭存储
func (s *PendingTaskStore) Close() {
	s.mu.Lock()
	s.pending = make(map[string]*PendingTask)
	s.mu.Unlock()
}

// setAck 标记 ack 状态到 redis + 内存
func (s *PendingTaskStore) setAck(agentID, taskID string, acked bool) error {
	if agentID == "" || taskID == "" {
		return fmt.Errorf("invalid agent or task id")
	}
	if s.redis == nil {
		// 无 Redis 环境下，仅日志记录
		return nil
	}
	if s.redis != nil {
		ctx, cancel := context.WithTimeout(context.Background(), 3*time.Second)
		defer cancel()
		key := s.taskAckKey(agentID)
		var err error
		if acked {
			err = s.redis.SAdd(ctx, key, taskID).Err()
		} else {
			err = s.redis.SRem(ctx, key, taskID).Err()
		}
		if err != nil {
			return err
		}
		s.redis.Expire(ctx, key, defaultTaskTimeout*2)
	}
	return nil
}
