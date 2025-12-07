# Agent 架构容量分析

## 当前架构特点

### Agent 端行为
- **心跳频率**: 默认 10 秒/次
- **任务轮询**: 默认 5 秒/次
- **HTTP 超时**: 30 秒
- **日志批量推送**: 默认 10 条/批次，200ms 间隔
- **并发任务数**: 默认 5 个/agent

### 控制面（Django）需要处理的请求

每个 Agent 每分钟产生的请求：
- **心跳**: 60秒 / 10秒 = **6 次/分钟**
- **任务轮询**: 60秒 / 5秒 = **12 次/分钟**
- **任务上报**: 取决于任务执行频率（假设平均 1 次/分钟）
- **日志推送**: 取决于任务活跃度（假设平均 5 次/分钟）

**总计**: 约 **24 次/分钟/Agent** = **0.4 次/秒/Agent**

---

## 容量估算

### 理论容量（基于 HTTP 请求处理能力）

#### 场景1：单机 Django（无负载均衡）

**假设条件**：
- Django 使用 Gunicorn + uWSGI
- Worker 数量：4-8 个
- 每个请求处理时间：50-100ms
- 数据库连接池：20-50 个连接

**计算**：
- 单 Worker 处理能力：1000ms / 100ms = **10 req/s**
- 4 Workers：**40 req/s**
- 8 Workers：**80 req/s**

**支持的 Agent 数量**：
- 4 Workers：40 / 0.4 = **100 个 Agent**
- 8 Workers：80 / 0.4 = **200 个 Agent**

#### 场景2：Django + 负载均衡（多实例）

**假设条件**：
- 2 个 Django 实例，每个 8 Workers
- 负载均衡器（Nginx/HAProxy）

**计算**：
- 总处理能力：2 × 80 = **160 req/s**
- 支持的 Agent 数量：160 / 0.4 = **400 个 Agent**

#### 场景3：高配置单机

**假设条件**：
- 16 Workers
- 优化后的请求处理时间：50ms

**计算**：
- 处理能力：16 × (1000/50) = **320 req/s**
- 支持的 Agent 数量：320 / 0.4 = **800 个 Agent**

---

## 瓶颈分析

### 1. 数据库连接数

**问题**：
- 每个请求可能需要数据库查询
- Django 默认连接池可能不够

**估算**：
- 100 个 Agent × 0.4 req/s = 40 req/s
- 假设 50% 请求需要 DB：20 DB 操作/秒
- 平均连接持有时间：100ms
- 需要连接数：20 × 0.1 = **2 个连接**（理论值）
- 实际考虑并发峰值：**10-20 个连接**

**建议**：
```python
# settings.py
DATABASES = {
    'default': {
        'CONN_MAX_AGE': 600,  # 连接复用
        'OPTIONS': {
            'connect_timeout': 10,
        }
    }
}
# 使用连接池（如 django-db-connection-pool）
```

### 2. HTTP 连接数

**问题**：
- Agent 使用短连接（HTTP/1.1）
- 控制面需要处理大量并发连接

**估算**：
- 100 个 Agent，心跳间隔 10 秒
- 峰值并发连接：100 / 10 = **10 个并发连接**（心跳）
- 加上任务轮询和上报：**20-30 个并发连接**

**建议**：
- 使用 HTTP/2（如果支持）
- 增加 Nginx 的 `worker_connections`
- 使用连接复用（Agent 端已使用 resty，支持连接池）

### 3. 内存使用

**问题**：
- 每个 Agent 连接会占用内存
- 任务队列和日志缓冲

**估算**：
- 每个 Agent 连接：约 1-2 KB
- 100 个 Agent：**100-200 KB**（连接相关）
- 任务队列：假设 1000 个待执行任务，每个 1 KB = **1 MB**
- 日志缓冲：假设 100 个活跃任务，每个 10 KB = **1 MB**

**总计**：约 **2-3 MB**（可忽略）

### 4. CPU 使用

**问题**：
- JSON 序列化/反序列化
- 数据库查询
- 日志处理

**估算**：
- 100 个 Agent，24 次/分钟 = 2400 次/分钟 = **40 次/秒**
- 假设每个请求 CPU 时间：10ms
- CPU 使用率：40 × 0.01 = **0.4 核心**（单核）

**结论**：CPU 不是瓶颈

---

## 实际容量建议

### 保守估算（考虑实际因素）

| 场景 | Agent 数量 | 说明 |
|------|-----------|------|
| **小规模** | 10-50 台 | 单机 Django，4 Workers，无压力 |
| **中规模** | 50-200 台 | 单机 Django，8 Workers，需要优化 |
| **大规模** | 200-500 台 | 需要负载均衡，2-3 个 Django 实例 |
| **超大规模** | 500+ 台 | 建议引入 agent-server 架构 |

### 关键优化点

#### 1. 控制面优化

```python
# 1. 数据库连接池
DATABASES = {
    'default': {
        'CONN_MAX_AGE': 600,
        'OPTIONS': {
            'connect_timeout': 10,
        }
    }
}

# 2. 使用缓存（Redis）
CACHES = {
    'default': {
        'BACKEND': 'django_redis.cache.RedisCache',
        'LOCATION': 'redis://127.0.0.1:6379/1',
        'OPTIONS': {
            'CLIENT_CLASS': 'django_redis.client.DefaultClient',
            'CONNECTION_POOL_KWARGS': {
                'max_connections': 50
            }
        }
    }
}

# 3. 异步任务处理（Celery）
# 将日志写入、状态更新等异步化
```

#### 2. Agent 端优化

```go
// 1. 增加心跳间隔（低负载时）
heartbeat_interval: 30  // 30秒

// 2. 增加任务轮询间隔（无任务时）
task_poll_interval: 10  // 10秒

// 3. 使用 HTTP 连接复用（resty 已支持）
// 4. 批量日志推送（已实现）
```

#### 3. 网络优化

```nginx
# Nginx 配置
worker_processes auto;
worker_connections 4096;

upstream django {
    server 127.0.0.1:8000;
    keepalive 32;
}

server {
    listen 80;
    keepalive_timeout 65;
    keepalive_requests 100;
    
    location /api/agents/ {
        proxy_pass http://django;
        proxy_http_version 1.1;
        proxy_set_header Connection "";
    }
}
```

---

## 容量测试方法（无需真实环境）

### 1. 压力测试脚本

使用 `wrk` 或 `ab` 模拟 Agent 请求：

```bash
# 模拟心跳请求
wrk -t4 -c100 -d30s \
  -H "Authorization: Token your-token" \
  -H "Content-Type: application/json" \
  -s heartbeat.lua \
  http://localhost:8000/api/agents/test-agent-id/heartbeat/

# heartbeat.lua
request = function()
   body = '{"timestamp":' .. os.time() .. ',"system":{}}'
   return wrk.format("POST", "/api/agents/test/heartbeat/", {
      ["Authorization"] = "Token test",
      ["Content-Type"] = "application/json"
   }, body)
end
```

### 2. 监控指标

在 Django 中添加监控：

```python
# middleware.py
import time
from django.core.cache import cache

class AgentRequestMonitor:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if '/api/agents/' in request.path:
            start_time = time.time()
            response = self.get_response(request)
            duration = time.time() - start_time
            
            # 记录指标
            cache.incr('agent_requests_total')
            cache.set('agent_request_duration', duration, timeout=60)
            
            return response
        return self.get_response(request)
```

### 3. 理论计算验证

使用以下公式验证：

```
支持的 Agent 数 = (Worker 数 × 请求处理能力) / (每个 Agent 的请求频率)

其中：
- 请求处理能力 = 1000ms / 平均请求处理时间(ms)
- 每个 Agent 的请求频率 = (60/心跳间隔 + 60/轮询间隔) / 60
```

---

## 扩展性建议

### 当前架构适用场景

✅ **适合**：
- 中小规模（< 200 台服务器）
- 内网环境
- 简单的任务执行场景

### 需要引入 agent-server 的场景

⚠️ **考虑引入**：
- 大规模（> 500 台服务器）
- 跨网络部署（NAT、防火墙）
- 需要统一认证和审计
- 需要集中日志和监控

### 渐进式扩展方案

1. **第一阶段**（当前）：直接 HTTP 通信
2. **第二阶段**：优化控制面（连接池、缓存、异步）
3. **第三阶段**：引入 agent-server（如果需要）

---

## 总结

### 理论容量

| 配置 | Agent 数量 |
|------|-----------|
| 单机 4 Workers | 100 台 |
| 单机 8 Workers | 200 台 |
| 2 实例 × 8 Workers | 400 台 |
| 高配单机 16 Workers | 800 台 |

### 实际建议

- **< 50 台**：当前架构完全够用
- **50-200 台**：需要优化控制面（连接池、缓存）
- **200-500 台**：需要负载均衡 + 多实例
- **> 500 台**：建议引入 agent-server

### 关键优化

1. ✅ 数据库连接池
2. ✅ Redis 缓存
3. ✅ 异步任务处理（Celery）
4. ✅ Nginx 负载均衡
5. ✅ Agent 端连接复用（已实现）
6. ✅ 批量日志推送（已实现）

