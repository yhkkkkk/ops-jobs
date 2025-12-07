# Agent-Server 架构设计（Go 实现）

## 架构概述

Agent-Server 是一个独立的 Go 服务，作为控制面和 Agent 之间的中间层，解决跨云跨网络场景下的连接问题。

```
┌─────────────────────────────────────────────────────────┐
│           控制面 (Control Plane - Django)                 │
│  - 任务调度和分发                                         │
│  - Agent 管理                                            │
│  - 日志聚合                                              │
└────────────────────┬──────────────────────────────────────┘
                     │ HTTP/HTTPS
                     │ (跨云网络)
                     ▼
┌─────────────────────────────────────────────────────────┐
│         Agent-Server (Go - 独立服务)                     │
│  - Agent 注册和认证                                      │
│  - WebSocket/HTTP 连接管理                               │
│  - 任务转发                                              │
│  - 日志聚合和转发                                        │
│  - 心跳代理                                              │
└──────┬───────────────────────────────────────┬───────────┘
       │ WebSocket/HTTP                        │
       │ (内网/同云)                           │
       ▼                                       ▼
┌──────────────┐                      ┌──────────────┐
│   Agent 1    │                      │   Agent N    │
│  (内网环境)   │                      │  (内网环境)   │
└──────────────┘                      └──────────────┘
```

## 技术选型

### Agent-Server (Go)

- **Web 框架**: `gin-gonic/gin` - HTTP API 和 WebSocket
- **WebSocket**: `gorilla/websocket` - 实时通信
- **HTTP 客户端**: `go-resty/resty/v2` - 与控制面通信
- **配置管理**: `spf13/viper` - 配置文件和环境变量
- **日志**: `sirupsen/logrus` + `lumberjack` - 结构化日志
- **并发控制**: `sync` + `goroutine` - Go 原生并发
- **数据存储**: Redis（可选，用于状态管理）

### 为什么用 Go？

1. **高并发**: Go 的 goroutine 模型非常适合处理大量并发连接
2. **性能**: 相比 Python，Go 在处理网络 I/O 时性能更好
3. **资源占用**: Go 编译后的二进制文件，资源占用小
4. **部署简单**: 单一二进制文件，无需依赖
5. **与 Agent 技术栈一致**: Agent 也是 Go，代码复用和统一管理

## 项目结构

```
agent-server-go/
├── cmd/
│   └── server/
│       └── main.go              # 入口文件
├── internal/
│   ├── config/
│   │   └── config.go            # 配置管理
│   ├── server/
│   │   ├── server.go            # HTTP/WebSocket 服务器
│   │   └── handlers.go          # 请求处理器
│   ├── agent/
│   │   ├── manager.go           # Agent 连接管理
│   │   └── connection.go        # Agent 连接封装
│   ├── controlplane/
│   │   └── client.go            # 控制面 HTTP 客户端
│   ├── task/
│   │   ├── dispatcher.go        # 任务分发器
│   │   └── queue.go             # 任务队列
│   ├── log/
│   │   └── aggregator.go        # 日志聚合器
│   ├── auth/
│   │   └── authenticator.go      # 认证模块
│   └── logger/
│       └── logger.go             # 日志配置
├── pkg/
│   └── api/
│       └── types.go             # API 类型定义
├── configs/
│   └── config.yaml.example      # 配置示例
├── go.mod
├── go.sum
└── README.md
```

## 核心功能

### 1. Agent 连接管理

**功能**：
- Agent 注册和认证
- WebSocket 连接维护
- 连接健康检查
- 断线重连处理

**数据结构**：
```go
type AgentConnection struct {
    ID          string
    Name        string
    Token       string
    Conn        *websocket.Conn
    Status      string
    LastHeartbeat time.Time
    Labels      map[string]string
    System      *SystemInfo
    TaskQueue   chan *TaskSpec
    LogBuffer   chan *LogEntry
}
```

### 2. 任务转发

**流程**：
1. 控制面发送任务到 Agent-Server
2. Agent-Server 查找目标 Agent
3. 通过 WebSocket 推送任务到 Agent
4. Agent 执行任务
5. Agent 上报结果到 Agent-Server
6. Agent-Server 转发结果到控制面

**API**：

**控制面 → Agent-Server**:
```
POST /api/agent-servers/{server_id}/agents/{agent_id}/tasks/
```

**Agent-Server → Agent** (WebSocket):
```json
{
  "type": "task",
  "task": {
    "id": "task-123",
    "name": "deploy",
    "type": "script",
    "command": "..."
  }
}
```

### 3. 日志聚合

**流程**：
1. Agent 通过 WebSocket 推送日志到 Agent-Server
2. Agent-Server 批量聚合日志
3. Agent-Server 批量推送到控制面

**WebSocket 消息** (Agent → Agent-Server):
```json
{
  "type": "log",
  "task_id": "task-123",
  "logs": [
    {
      "timestamp": 1234567890,
      "content": "Starting...",
      "stream": "stdout"
    }
  ]
}
```

### 4. 心跳代理

**流程**：
1. Agent 定期发送心跳到 Agent-Server
2. Agent-Server 更新 Agent 状态
3. Agent-Server 转发心跳到控制面（可选，减少控制面压力）

## 通信协议

### Agent-Server API (HTTP)

#### 1. Agent 注册

```
POST /api/agents/register/
```

**请求**:
```json
{
  "name": "agent-001",
  "token": "agent-auth-token",
  "labels": {"env": "prod", "region": "us-east"},
  "system": {
    "hostname": "server-01",
    "os": "linux",
    "arch": "amd64"
  }
}
```

**响应**:
```json
{
  "id": "agent-uuid-123",
  "name": "agent-001",
  "status": "active",
  "ws_url": "ws://agent-server:8080/ws/agent/{agent_id}"
}
```

#### 2. 获取 Agent 列表

```
GET /api/agents/
```

#### 3. 获取 Agent 状态

```
GET /api/agents/{agent_id}/
```

### WebSocket 协议

#### 连接 URL

```
ws://agent-server:8080/ws/agent/{agent_id}?token={agent_token}
```

#### 消息格式

**Agent → Agent-Server**:

1. **心跳**:
```json
{
  "type": "heartbeat",
  "timestamp": 1234567890,
  "system": {
    "cpu_usage": 45.2,
    "memory_usage": 60.5
  }
}
```

2. **任务结果**:
```json
{
  "type": "task_result",
  "task_id": "task-123",
  "result": {
    "status": "success",
    "exit_code": 0,
    "output": "..."
  }
}
```

3. **日志**:
```json
{
  "type": "log",
  "task_id": "task-123",
  "logs": [...]
}
```

**Agent-Server → Agent**:

1. **任务推送**:
```json
{
  "type": "task",
  "task": {
    "id": "task-123",
    "name": "deploy",
    "type": "script",
    "command": "..."
  }
}
```

2. **任务取消**:
```json
{
  "type": "cancel_task",
  "task_id": "task-123"
}
```

### Agent-Server → 控制面 API

#### 1. 注册 Agent

```
POST /api/agents/register/
```

```json
{
  "id": "agent-uuid-123",
  "name": "agent-001",
  "server_id": "agent-server-001",
  "labels": {...},
  "system": {...}
}
```

#### 2. 转发心跳

```
POST /api/agents/{agent_id}/heartbeat/
```

#### 3. 拉取任务

```
POST /api/agent-servers/{server_id}/agents/{agent_id}/next-task/
```

#### 4. 上报结果

```
POST /api/agents/{agent_id}/tasks/{task_id}/report/
```

#### 5. 推送日志

```
POST /api/agents/{agent_id}/tasks/{task_id}/logs/
```

## 配置

### Agent-Server 配置

```yaml
# config.yaml
server:
  host: "0.0.0.0"
  port: 8080
  read_timeout: 30s
  write_timeout: 30s

control_plane:
  url: "https://control-plane.example.com"
  token: "server-auth-token"
  timeout: 30s

agent:
  heartbeat_timeout: 60s
  max_connections: 1000
  task_queue_size: 100

logging:
  level: "info"
  dir: "/var/log/agent-server"
  max_size: 100  # MB
  max_files: 10
  max_age: 7     # days

redis:
  enabled: false
  addr: "localhost:6379"
  password: ""
  db: 0
```

### 环境变量

```bash
AGENT_SERVER_HOST=0.0.0.0
AGENT_SERVER_PORT=8080
CONTROL_PLANE_URL=https://control-plane.example.com
CONTROL_PLANE_TOKEN=server-auth-token
AGENT_SERVER_ID=agent-server-001
AGENT_SERVER_NAME=agent-server-prod
```

## 部署方案

### 场景1：单 Agent-Server

```
控制面 (公网)
    ↓
Agent-Server (内网边界，可访问公网)
    ↓
Agent 1, Agent 2, ... (内网)
```

### 场景2：多 Agent-Server（跨云）

```
控制面 (公网)
    ↓
┌─────────────┬─────────────┐
│ Agent-Server│ Agent-Server│
│  (云A)      │  (云B)      │
└──────┬──────┴──────┬───────┘
       │            │
   Agent 1-10   Agent 11-20
```

### 场景3：Agent-Server 集群（高可用）

```
控制面 (公网)
    ↓
负载均衡器 (Nginx/HAProxy)
    ↓
┌─────────────┬─────────────┐
│ Agent-Server│ Agent-Server│
│  (主)       │  (备)       │
└──────┬──────┴──────┬───────┘
       │            │
   Agent 1-10   Agent 11-20
```

## 实现步骤

### Phase 1: 基础框架

1. 创建项目结构
2. 实现配置管理
3. 实现日志系统
4. 实现 HTTP 服务器基础框架

### Phase 2: Agent 连接管理

1. 实现 Agent 注册和认证
2. 实现 WebSocket 连接管理
3. 实现心跳检测
4. 实现连接状态管理

### Phase 3: 任务转发

1. 实现任务接收（从控制面）
2. 实现任务分发（到 Agent）
3. 实现结果上报（到控制面）
4. 实现任务队列管理

### Phase 4: 日志聚合

1. 实现日志接收（从 Agent）
2. 实现日志批量聚合
3. 实现日志转发（到控制面）

### Phase 5: 控制面集成

1. 实现控制面 HTTP 客户端
2. 实现 Agent 注册到控制面
3. 实现任务拉取（从控制面）
4. 实现结果和日志上报（到控制面）

### Phase 6: Agent 修改

1. 支持 Agent-Server 模式配置
2. 实现 WebSocket 连接
3. 实现任务接收（从 WebSocket）
4. 实现日志推送（到 WebSocket）
5. 保持向后兼容（直连模式）

## 优势

1. **独立部署**: Agent-Server 与控制面分离，可以独立扩展
2. **高性能**: Go 的并发模型，可以处理大量并发连接
3. **低资源占用**: Go 编译后的二进制文件，资源占用小
4. **技术栈统一**: Agent 和 Agent-Server 都是 Go，便于维护
5. **网络隔离**: Agent 只需访问 Agent-Server（内网），不需要访问公网
6. **跨云支持**: 可以部署多个 Agent-Server 支持跨云场景

## 注意事项

1. **向后兼容**: Agent 应支持直连控制面模式（用于简单场景）
2. **故障转移**: Agent-Server 故障时，Agent 应能自动重连或切换到备用 Server
3. **性能监控**: 需要监控 Agent-Server 的连接数、任务转发延迟等指标
4. **安全性**: Agent-Server 需要处理认证和授权，防止未授权访问

