# Agent 容量计算器

## 快速计算

### 输入参数

```python
# Agent 配置
HEARTBEAT_INTERVAL = 10  # 心跳间隔（秒）
TASK_POLL_INTERVAL = 5   # 任务轮询间隔（秒）

# 控制面配置
WORKER_COUNT = 8         # Django/Gunicorn Worker 数量
AVG_REQUEST_TIME = 0.1   # 平均请求处理时间（秒）
```

### 计算公式

```python
# 每个 Agent 的请求频率（次/秒）
agent_request_rate = (60 / HEARTBEAT_INTERVAL + 60 / TASK_POLL_INTERVAL) / 60

# 控制面处理能力（次/秒）
control_plane_capacity = WORKER_COUNT * (1 / AVG_REQUEST_TIME)

# 支持的 Agent 数量
max_agents = control_plane_capacity / agent_request_rate
```

### 示例计算

```python
# 默认配置
HEARTBEAT_INTERVAL = 10
TASK_POLL_INTERVAL = 5
WORKER_COUNT = 8
AVG_REQUEST_TIME = 0.1

agent_request_rate = (60/10 + 60/5) / 60 = (6 + 12) / 60 = 0.3 次/秒
control_plane_capacity = 8 * (1/0.1) = 80 次/秒
max_agents = 80 / 0.3 = 266 个 Agent

# 考虑任务上报和日志推送（增加 30%）
max_agents_with_overhead = 266 * 0.7 = 186 个 Agent
```

---

## 不同配置下的容量

| Worker数 | 请求处理时间 | Agent请求频率 | 理论容量 | 实际容量（70%） |
|---------|--------------|-------------|---------|----------------|
| 4 | 100ms | 0.3 req/s | 133 | 93 |
| 8 | 100ms | 0.3 req/s | 266 | 186 |
| 8 | 50ms | 0.3 req/s | 533 | 373 |
| 16 | 100ms | 0.3 req/s | 533 | 373 |
| 16 | 50ms | 0.3 req/s | 1066 | 746 |

**注意**：实际容量需要考虑：
- 数据库连接数限制
- 网络带宽
- 内存使用
- 峰值负载（建议保留 30% 余量）

---

## 优化建议

### 1. 增加心跳间隔（低负载时）

```go
// agent 配置
heartbeat_interval: 30  // 从 10 秒增加到 30 秒
```

**效果**：
- Agent 请求频率：从 0.3 降到 0.2 req/s
- 容量提升：**50%**

### 2. 增加任务轮询间隔（无任务时）

```go
// agent 配置
task_poll_interval: 10  // 从 5 秒增加到 10 秒
```

**效果**：
- Agent 请求频率：从 0.3 降到 0.2 req/s
- 容量提升：**50%**

### 3. 优化控制面请求处理时间

- 使用缓存（Redis）减少数据库查询
- 异步处理日志写入（Celery）
- 优化数据库查询（索引、连接池）

**效果**：
- 请求处理时间：从 100ms 降到 50ms
- 容量提升：**100%**

---

## 监控指标

### 关键指标

1. **请求处理时间**（P50, P95, P99）
2. **数据库连接数**
3. **HTTP 连接数**
4. **CPU 使用率**
5. **内存使用率**
6. **请求失败率**

### 告警阈值

- 请求处理时间 P95 > 500ms：需要优化
- 数据库连接数 > 80%：需要增加连接池
- 请求失败率 > 1%：需要扩容

---

## 实际部署建议

### 小规模（< 50 台）

- 单机 Django，4-8 Workers
- 无需特殊优化
- 当前架构完全够用

### 中规模（50-200 台）

- 单机 Django，8-16 Workers
- 启用数据库连接池（已配置）
- 启用 Redis 缓存
- 使用 Nginx 反向代理

### 大规模（200-500 台）

- 2-3 个 Django 实例
- Nginx 负载均衡
- Redis 集群（如果需要）
- 数据库读写分离（如果需要）

### 超大规模（> 500 台）

- 考虑引入 agent-server
- 或使用消息队列（RabbitMQ/Kafka）
- 分布式架构

