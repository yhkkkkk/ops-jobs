package task

import (
	"context"
	"encoding/json"
	"fmt"
	"sort"
	"time"

	"ops-job-agent-server/internal/config"
	"ops-job-agent-server/internal/logger"
	"ops-job-agent-server/pkg/api"

	"github.com/hibiken/asynq"
	"github.com/redis/go-redis/v9"
)

const (
	// 任务类型
	TaskTypeAgentTask = "agent:task"

	// 队列名称
	QueueDefault  = "default"
	QueueCritical = "critical"
	// QueueLong 长任务队列：用于超长/重任务，避免挤占短任务
	QueueLong = "long"
)

// TaskQueue 任务队列管理器
type TaskQueue struct {
	client   *asynq.Client
	server   *asynq.Server
	mux      *asynq.ServeMux
	redisOpt asynq.RedisClientOpt
	cfg      config.AsynqConfig
}

// TaskPayload 任务负载
type TaskPayload struct {
	AgentID string        `json:"agent_id"`
	Task    *api.TaskSpec `json:"task"`
}

// NewTaskQueue 创建任务队列管理器
func NewTaskQueue(redisAddr, redisPassword string, redisDB int, cfg config.AsynqConfig) (*TaskQueue, error) {
	redisOpt := asynq.RedisClientOpt{
		Addr:     redisAddr,
		Password: redisPassword,
		DB:       redisDB,
	}

	// 创建 redis 客户端用于健康检查
	rdb := redis.NewClient(&redis.Options{
		Addr:     redisAddr,
		Password: redisPassword,
		DB:       redisDB,
	})

	// 测试连接
	ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
	defer cancel()
	if err := rdb.Ping(ctx).Err(); err != nil {
		return nil, fmt.Errorf("redis connection failed: %w", err)
	}

	// 创建 asynq 客户端
	client := asynq.NewClient(redisOpt)

	// 创建 asynq 服务器
	if cfg.Concurrency <= 0 {
		cfg.Concurrency = 10
	}
	if cfg.RetryMax <= 0 {
		cfg.RetryMax = 3
	}
	if cfg.RetryDelay <= 0 {
		cfg.RetryDelay = 1 * time.Second
	}
	if cfg.TaskTimeout <= 0 {
		cfg.TaskTimeout = 5 * time.Minute
	}

	server := asynq.NewServer(redisOpt, asynq.Config{
		Concurrency: cfg.Concurrency,
		Queues: map[string]int{
			QueueCritical: 10, // 高优先级队列权重
			QueueDefault:  5,  // 默认队列权重
			QueueLong:     1,  // 长任务队列权重
		},
		StrictPriority: false, // 使用加权优先级
		ErrorHandler: asynq.ErrorHandlerFunc(func(ctx context.Context, t *asynq.Task, err error) {
			logger.GetLogger().WithError(err).WithFields(map[string]interface{}{
				"task_type": t.Type(),
			}).Error("task processing error")
		}),
		RetryDelayFunc: func(n int, err error, task *asynq.Task) time.Duration {
			// 指数退避：1s, 2s, 4s, 8s, 16s
			delay := time.Duration(1<<uint(n)) * cfg.RetryDelay
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
		cfg:      cfg,
	}, nil
}

// Start 启动任务队列服务器
func (q *TaskQueue) Start() error {
	logger.GetLogger().Info("starting asynq server")
	return q.server.Run(q.mux)
}

// Stop 停止任务队列服务器
func (q *TaskQueue) Stop() {
	logger.GetLogger().Info("stopping asynq server")
	q.client.Close()
	q.server.Shutdown()
}

// EnqueueTask 将任务入队
func (q *TaskQueue) EnqueueTask(agentID string, task *api.TaskSpec, opts ...asynq.Option) (*asynq.TaskInfo, error) {
	payload := TaskPayload{
		AgentID: agentID,
		Task:    task,
	}

	payloadBytes, err := json.Marshal(payload)
	if err != nil {
		return nil, fmt.Errorf("marshal task payload: %w", err)
	}

	// 默认选项
	defaultOpts := []asynq.Option{
		asynq.Queue(QueueDefault),
		asynq.MaxRetry(q.cfg.RetryMax),
		asynq.Timeout(q.cfg.TaskTimeout),
	}

	// 幂等：对“同一 execution_id 的任务”做 24h 去重（依赖 task payload，因此无需显式 uniqueKey）
	if task.ExecutionID != "" {
		defaultOpts = append(defaultOpts, asynq.Unique(24*time.Hour))
	}

	// 合并用户选项
	allOpts := append(defaultOpts, opts...)

	// 创建任务
	asynqTask := asynq.NewTask(TaskTypeAgentTask, payloadBytes)

	// 入队
	info, err := q.client.Enqueue(asynqTask, allOpts...)
	if err != nil {
		return nil, fmt.Errorf("enqueue task: %w", err)
	}

	logger.GetLogger().WithFields(map[string]interface{}{
		"agent_id": agentID,
		"task_id":  task.ID,
		"queue_id": info.ID,
	}).Info("task enqueued to asynq")

	return info, nil
}

// EnqueueWithPolicy 基于任务特征选择队列、幂等键和超时/重试策略
func (q *TaskQueue) EnqueueWithPolicy(agentID string, task *api.TaskSpec) (*asynq.TaskInfo, error) {
	if task == nil {
		return nil, fmt.Errorf("task is nil")
	}

	queue := selectQueue(task)
	timeout := q.selectTimeout(task)
	maxRetry := q.selectMaxRetry(task)

	opts := []asynq.Option{
		asynq.Queue(queue),
		asynq.Timeout(timeout),
		asynq.MaxRetry(maxRetry),
	}

	// 仅对具备 execution_id 的任务做去重（避免脚本/文件传输被重复下发）
	if task.ExecutionID != "" {
		opts = append(opts, asynq.Unique(24*time.Hour))
	}

	return q.EnqueueTask(agentID, task, opts...)
}

func selectQueue(task *api.TaskSpec) string {
	// 超长任务进入 long 队列，避免阻塞短任务
	if task.TimeoutSec >= 900 {
		return QueueLong
	}
	if task.TimeoutSec >= 300 {
		return QueueDefault
	}
	return QueueCritical
}

func (q *TaskQueue) selectTimeout(task *api.TaskSpec) time.Duration {
	if task.TimeoutSec > 0 {
		return time.Duration(task.TimeoutSec) * time.Second
	}
	return q.cfg.TaskTimeout
}

func (q *TaskQueue) selectMaxRetry(task *api.TaskSpec) int {
	if task.RetryCount > 0 {
		return task.RetryCount
	}
	return q.cfg.RetryMax
}

// EnqueueTaskWithPriority 将任务入队（带优先级）
func (q *TaskQueue) EnqueueTaskWithPriority(agentID string, task *api.TaskSpec, priority string) (*asynq.TaskInfo, error) {
	var queue string
	switch priority {
	case "high", "critical":
		queue = QueueCritical
	case "low":
		queue = QueueLong
	default:
		queue = QueueDefault
	}

	return q.EnqueueTask(agentID, task, asynq.Queue(queue))
}

// RegisterHandler 注册任务处理器
func (q *TaskQueue) RegisterHandler(handler func(ctx context.Context, agentID string, task *api.TaskSpec) error) {
	q.mux.HandleFunc(TaskTypeAgentTask, func(ctx context.Context, t *asynq.Task) error {
		var payload TaskPayload
		if err := json.Unmarshal(t.Payload(), &payload); err != nil {
			return fmt.Errorf("unmarshal task payload: %w", err)
		}

		logger.GetLogger().WithFields(map[string]interface{}{
			"agent_id": payload.AgentID,
			"task_id":  payload.Task.ID,
		}).Info("processing task from queue")

		return handler(ctx, payload.AgentID, payload.Task)
	})
}

// ListPendingTasks 列出指定Agent的待处理任务
// 使用asynq Inspector API，支持分页、排序、过滤
// 查询所有状态的任务：pending, active, retry, scheduled
func (q *TaskQueue) ListPendingTasks(agentID string) ([]*api.TaskSpec, error) {
	inspector := asynq.NewInspector(q.redisOpt)
	defer inspector.Close()

	queues := []string{QueueCritical, QueueDefault, QueueLong}
	var allTasks []TaskWithMetadata

	// 遍历所有队列，查询不同状态的任务
	for _, queueName := range queues {
		allTasks = append(allTasks, q.queryTasksByState(inspector, queueName, agentID, "pending")...)
		allTasks = append(allTasks, q.queryTasksByState(inspector, queueName, agentID, "active")...)
		allTasks = append(allTasks, q.queryTasksByState(inspector, queueName, agentID, "retry")...)
		allTasks = append(allTasks, q.queryTasksByState(inspector, queueName, agentID, "scheduled")...)
	}

	// 按优先级和状态排序
	q.sortTasksByPriority(allTasks)

	// 提取TaskSpec列表
	tasks := make([]*api.TaskSpec, 0, len(allTasks))
	for _, taskMeta := range allTasks {
		tasks = append(tasks, taskMeta.Task)
	}

	logger.GetLogger().WithFields(map[string]interface{}{
		"agent_id":   agentID,
		"task_count": len(tasks),
		"breakdown": map[string]int{
			"pending":   countByState(allTasks, "pending"),
			"active":    countByState(allTasks, "active"),
			"retry":     countByState(allTasks, "retry"),
			"scheduled": countByState(allTasks, "scheduled"),
		},
	}).Info("listed pending tasks for agent")

	return tasks, nil
}

// queryTasksByState 按状态查询任务
func (q *TaskQueue) queryTasksByState(inspector *asynq.Inspector, queueName, agentID, state string) []TaskWithMetadata {
	var tasks []TaskWithMetadata
	page := 1
	pageSize := 100

	for {
		var taskInfos []*asynq.TaskInfo
		var err error

		switch state {
		case "pending":
			taskInfos, err = inspector.ListPendingTasks(queueName, asynq.PageSize(pageSize), asynq.Page(page))
		case "active":
			taskInfos, err = inspector.ListActiveTasks(queueName, asynq.PageSize(pageSize), asynq.Page(page))
		case "retry":
			taskInfos, err = inspector.ListRetryTasks(queueName, asynq.PageSize(pageSize), asynq.Page(page))
		case "scheduled":
			taskInfos, err = inspector.ListScheduledTasks(queueName, asynq.PageSize(pageSize), asynq.Page(page))
		default:
			return tasks
		}

		if err != nil {
			logger.GetLogger().WithError(err).WithFields(map[string]interface{}{
				"queue": queueName,
				"state": state,
			}).Warn("list tasks failed")
			break
		}

		if len(taskInfos) == 0 {
			break
		}

		for _, taskInfo := range taskInfos {
			var payload TaskPayload
			if err := json.Unmarshal(taskInfo.Payload, &payload); err != nil {
				logger.GetLogger().WithError(err).WithFields(map[string]interface{}{
					"queue":   queueName,
					"task_id": taskInfo.ID,
				}).Warn("unmarshal task payload failed")
				continue
			}

			// 只返回指定Agent的任务
			if payload.AgentID == agentID {
				taskMeta := TaskWithMetadata{
					Task:     payload.Task,
					Queue:    queueName,
					TaskID:   taskInfo.ID,
					State:    state,
					Priority: getQueuePriority(queueName),
				}
				if !taskInfo.NextProcessAt.IsZero() {
					taskMeta.NextProcessAt = taskInfo.NextProcessAt
				}
				tasks = append(tasks, taskMeta)
			}
		}

		// 如果返回的任务数少于pageSize，说明已经是最后一页
		if len(taskInfos) < pageSize {
			break
		}
		page++
	}

	return tasks
}

// sortTasksByPriority 按优先级和状态排序任务
func (q *TaskQueue) sortTasksByPriority(allTasks []TaskWithMetadata) {
	stateOrder := map[string]int{
		"pending":   0,
		"active":    1,
		"retry":     2,
		"scheduled": 3,
	}

	sort.Slice(allTasks, func(i, j int) bool {
		// 先按优先级排序
		if allTasks[i].Priority != allTasks[j].Priority {
			return allTasks[i].Priority > allTasks[j].Priority
		}
		// 再按状态排序
		orderI := stateOrder[allTasks[i].State]
		orderJ := stateOrder[allTasks[j].State]
		if orderI != orderJ {
			return orderI < orderJ
		}
		// 最后按NextProcessAt排序（如果有）
		if !allTasks[i].NextProcessAt.IsZero() && !allTasks[j].NextProcessAt.IsZero() {
			return allTasks[i].NextProcessAt.Before(allTasks[j].NextProcessAt)
		}
		return false
	})
}

// TaskWithMetadata 带元数据的任务
type TaskWithMetadata struct {
	Task          *api.TaskSpec
	Queue         string
	TaskID        string
	State         string
	Priority      int
	RetryCount    int
	NextProcessAt time.Time
}

// getQueuePriority 获取队列优先级
func getQueuePriority(queueName string) int {
	switch queueName {
	case QueueCritical:
		return 3
	case QueueDefault:
		return 2
	case QueueLong:
		return 1
	default:
		return 0
	}
}

// countByState 按状态统计任务数
func countByState(tasks []TaskWithMetadata, state string) int {
	count := 0
	for _, task := range tasks {
		if task.State == state {
			count++
		}
	}
	return count
}

// GetRedisOpt 获取 Redis 配置（用于创建 Inspector）
func (q *TaskQueue) GetRedisOpt() asynq.RedisClientOpt {
	return q.redisOpt
}

// DeleteTask 删除任务
func (q *TaskQueue) DeleteTask(queueName, taskID string) error {
	inspector := asynq.NewInspector(q.redisOpt)
	defer inspector.Close()

	return inspector.DeleteTask(queueName, taskID)
}

// GetTaskStats 获取任务统计信息
func (q *TaskQueue) GetTaskStats() (map[string]interface{}, error) {
	inspector := asynq.NewInspector(q.redisOpt)
	defer inspector.Close()

	queues := []string{QueueCritical, QueueDefault, QueueLong}
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
