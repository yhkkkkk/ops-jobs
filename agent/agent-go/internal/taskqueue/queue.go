package taskqueue

import (
	"context"
	"encoding/json"
	"fmt"
	"time"

	"ops-job-agent/internal/api"
	"ops-job-agent/internal/config"
	"ops-job-agent/internal/logger"

	"github.com/hibiken/asynq"
	"github.com/redis/go-redis/v9"
)

const (
	// 任务类型
	TaskTypeAgentTask = "agent:task"

	// 队列名称（与agent-server保持一致）
	QueueDefault  = "default"
	QueueCritical = "critical"
	QueueLow      = "low"
)

// TaskQueue Agent端的任务队列管理器
// 用于从asynq队列拉取任务（当Agent离线后重新上线时）
type TaskQueue struct {
	client   *asynq.Client
	server   *asynq.Server
	mux      *asynq.ServeMux
	redisOpt asynq.RedisClientOpt
	enabled  bool
}

// TaskPayload 任务负载
type TaskPayload struct {
	AgentID string        `json:"agent_id"`
	Task    *api.TaskSpec `json:"task"`
}

// NewTaskQueue 创建Agent端的任务队列管理器
func NewTaskQueue(cfg *config.Config) (*TaskQueue, error) {
	// 检查是否启用asynq
	if !cfg.Asynq.Enabled || !cfg.Redis.Asynq.Enabled {
		return &TaskQueue{enabled: false}, nil
	}

	redisOpt := asynq.RedisClientOpt{
		Addr:     cfg.Redis.Asynq.Addr,
		Password: cfg.Redis.Asynq.Password,
		DB:       cfg.Redis.Asynq.DB,
	}

	// 创建Redis客户端用于健康检查
	rdb := redis.NewClient(&redis.Options{
		Addr:     cfg.Redis.Asynq.Addr,
		Password: cfg.Redis.Asynq.Password,
		DB:       cfg.Redis.Asynq.DB,
	})

	// 测试连接
	ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
	defer cancel()
	if err := rdb.Ping(ctx).Err(); err != nil {
		return nil, fmt.Errorf("redis connection failed: %w", err)
	}

	// 创建asynq客户端
	client := asynq.NewClient(redisOpt)

	// 创建asynq服务器（用于处理任务）
	server := asynq.NewServer(redisOpt, asynq.Config{
		Concurrency: cfg.Asynq.Concurrency,
		Queues: map[string]int{
			QueueCritical: 10,
			QueueDefault:  5,
			QueueLow:      1,
		},
		StrictPriority: false,
		ErrorHandler: asynq.ErrorHandlerFunc(func(ctx context.Context, t *asynq.Task, err error) {
			logger.GetLogger().WithError(err).WithFields(map[string]interface{}{
				"task_type": t.Type(),
			}).Error("task processing error in agent")
		}),
		RetryDelayFunc: func(n int, err error, task *asynq.Task) time.Duration {
			delay := time.Duration(1<<uint(n)) * time.Second
			if delay > 30*time.Second {
				delay = 30 * time.Second
			}
			return delay
		},
	})

	// 创建任务处理器
	mux := asynq.NewServeMux()

	return &TaskQueue{
		client:   client,
		server:   server,
		mux:      mux,
		redisOpt: redisOpt,
		enabled:  true,
	}, nil
}

// Start 启动任务队列服务器
func (q *TaskQueue) Start() error {
	if !q.enabled {
		return nil
	}
	logger.GetLogger().Info("starting agent asynq server")
	return q.server.Run(q.mux)
}

// Stop 停止任务队列服务器
func (q *TaskQueue) Stop() {
	if !q.enabled {
		return
	}
	logger.GetLogger().Info("stopping agent asynq server")
	q.client.Close()
	q.server.Shutdown()
}

// RegisterHandler 注册任务处理器
// handler函数会在从队列中取出任务时被调用
func (q *TaskQueue) RegisterHandler(handler func(ctx context.Context, task *api.TaskSpec) error) {
	if !q.enabled {
		return
	}

	q.mux.HandleFunc(TaskTypeAgentTask, func(ctx context.Context, t *asynq.Task) error {
		var payload TaskPayload
		if err := json.Unmarshal(t.Payload(), &payload); err != nil {
			return fmt.Errorf("unmarshal task payload: %w", err)
		}

		logger.GetLogger().WithFields(map[string]interface{}{
			"task_id":  payload.Task.ID,
			"agent_id": payload.AgentID,
		}).Info("processing task from asynq queue in agent")

		return handler(ctx, payload.Task)
	})
}

// ListPendingTasks 列出指定Agent的待处理任务
// 使用asynq Inspector API，支持分页查询
func (q *TaskQueue) ListPendingTasks(agentID string, limit int) ([]*api.TaskSpec, error) {
	if !q.enabled {
		return nil, nil
	}

	inspector := asynq.NewInspector(q.redisOpt)
	defer inspector.Close()

	queues := []string{QueueCritical, QueueDefault, QueueLow}
	var allTasks []*api.TaskSpec

	// 遍历所有队列
	for _, queueName := range queues {
		// 查询待处理任务
		page := 1
		pageSize := 50
		if limit > 0 && limit < pageSize {
			pageSize = limit
		}

		for {
			pending, err := inspector.ListPendingTasks(queueName, asynq.PageSize(pageSize), asynq.Page(page))
			if err != nil {
				logger.GetLogger().WithError(err).WithField("queue", queueName).Warn("list pending tasks failed")
				break
			}

			if len(pending) == 0 {
				break
			}

			for _, taskInfo := range pending {
				// 解析任务负载
				var payload TaskPayload
				if err := json.Unmarshal(taskInfo.Payload, &payload); err != nil {
					continue
				}

				// 只返回指定Agent的任务
				if payload.AgentID == agentID {
					allTasks = append(allTasks, payload.Task)
					// 如果达到限制，返回
					if limit > 0 && len(allTasks) >= limit {
						return allTasks, nil
					}
				}
			}

			// 如果返回的任务数少于pageSize，说明已经是最后一页
			if len(pending) < pageSize {
				break
			}
			page++

			// 如果达到限制，停止查询
			if limit > 0 && len(allTasks) >= limit {
				break
			}
		}
	}

	logger.GetLogger().WithFields(map[string]interface{}{
		"agent_id":   agentID,
		"task_count": len(allTasks),
	}).Info("listed pending tasks for agent from asynq")

	return allTasks, nil
}

// GetTaskStats 获取任务统计信息
func (q *TaskQueue) GetTaskStats() (map[string]interface{}, error) {
	if !q.enabled {
		return nil, nil
	}

	inspector := asynq.NewInspector(q.redisOpt)
	defer inspector.Close()

	queues := []string{QueueCritical, QueueDefault, QueueLow}
	stats := make(map[string]interface{})

	for _, queueName := range queues {
		queueInfo, err := inspector.GetQueueInfo(queueName)
		if err != nil {
			logger.GetLogger().WithError(err).WithField("queue", queueName).Warn("get queue info failed")
			continue
		}

		stats[queueName] = map[string]interface{}{
			"pending":   queueInfo.Pending,
			"active":    queueInfo.Active,
			"scheduled": queueInfo.Scheduled,
			"retry":     queueInfo.Retry,
			"archived":  queueInfo.Archived,
		}
	}

	return stats, nil
}
