# Agent-Server (Go)

Agent-Server 是一个独立的 Go 服务，作为控制面和 Agent 之间的中间层，解决跨云跨网络场景下的连接问题。

## 功能特性

- ✅ **Agent 连接管理**: 支持 Agent 注册、认证和 WebSocket 连接管理
- ✅ **任务转发**: 从控制面接收任务并转发到 Agent
- ✅ **日志聚合**: 聚合 Agent 日志并批量推送到控制面（支持 Redis 流）
- ✅ **心跳检测**: 监控 Agent 心跳超时，自动标记离线 Agent
- ✅ **认证授权**: 支持 HMAC 签名认证
- ✅ **高并发**: 基于 Go 的 goroutine 模型，支持大量并发连接
- ✅ **性能监控**: 内置指标收集和监控
- ✅ **WebSocket ACK**: 消息确认机制
- ✅ **独立部署**: 与控制面分离，可以独立扩展
- ✅ **单一 WS 通道**: 任务/心跳/日志/结果全部通过 WS，`message_id` 必填，缺失直接丢弃；日志/结果/状态仅写入 Redis Stream，无 HTTP/文件回退通道

## 架构

```
控制面 (Django) ←→ Agent-Server (Go) ←→ Agent (Go)
```

## 快速开始

### 安装

```bash
cd agent/agent-server-go
go mod download
go build -o .\bin\agent-server .\cmd\server\main.go
```

### 配置

复制配置文件：

```bash
cp configs/config.yaml.example configs/config.yaml
```

编辑 `configs/config.yaml`：

```yaml
server:
  host: "0.0.0.0"
  port: 8080

control_plane:
  url: "http://localhost:8000"  # 开发环境使用，或生产环境的实际URL
  token: "server-auth-token"    # 从控制面获取的token
  timeout: "30s"                # 请求超时时间
  task_poll_interval: "5s"      # 任务轮询间隔

agent:
  max_connections: 1000         # 最大Agent连接数
  heartbeat_timeout: "60s"      # Agent心跳超时
  cleanup_interval: "30s"       # 清理间隔

auth:
  shared_secret: ""             # 可选，启用后控制面请求需带 HMAC 签名
  require_signature: false      # 是否要求签名
  clock_skew: "300s"            # 允许的时间偏移

logging:
  level: "info"
  file: "logs/agent-server.log"
```

### 运行

```bash
./agent-server start
```

### 环境变量

```bash
AGENT_SERVER_HOST=0.0.0.0
AGENT_SERVER_PORT=8080
CONTROL_PLANE_URL=https://control-plane.example.com
CONTROL_PLANE_TOKEN=server-auth-token
CONTROL_PLANE_SCOPE=default
AUTH_SHARED_SECRET=your-hmac-secret
AUTH_REQUIRE_SIGNATURE=true
```

## API 接口

### Agent 注册

```
POST /api/agents/register/
```

### WebSocket 连接

```
ws://agent-server:8080/ws/agent/{agent_id}
```

**认证方式**：使用 `Sec-WebSocket-Protocol` 头部传递 token，格式：`agent-token,{agent_token}`

```go
// Agent 端连接示例
headers := http.Header{
    "Sec-WebSocket-Protocol": []string{"agent-token," + token},
}
conn, _, err := dialer.Dial(wsURL, headers)
```

> **安全性说明**：token 通过 WebSocket 标准协议头部传递，不暴露在 URL 中，不会记录在服务器访问日志。

### 控制面 API

Agent-Server 与控制面通过以下 API 交互：

- **任务接收**: `POST /api/agents/{agent_id}/tasks/` - 从控制面接收任务并通过 WebSocket 转发给 Agent
- **结果上报**: 接收 Agent 的执行结果并转发给控制面（通过 Redis Stream `agent_results`）
- **任务取消**: `POST /api/agents/{agent_id}/tasks/{task_id}/cancel/` - 取消任务

> **注意**: Agent 心跳通过 WebSocket 发送，Agent-Server 内部检测心跳超时并自动清理离线 Agent，无需转发到控制面。

## 开发

### 项目结构

```
agent-server-go/
├── cmd/server/          # 入口文件
├── internal/            # 内部包
│   ├── agent/          # Agent 连接管理
│   │   ├── connection.go    # 连接处理
│   │   └── manager.go       # 连接管理器
│   ├── auth/           # 认证处理
│   ├── config/         # 配置管理
│   ├── constants/      # 常量定义
│   ├── controlplane/   # 控制面客户端
│   ├── log/            # 日志聚合
│   │   ├── redis_client.go          # Redis 客户端
│   │   ├── result_stream_writer.go  # 结果流写入
│   │   ├── status_stream_writer.go  # 状态流写入
│   │   └── stream_writer.go         # 流写入器
│   ├── logger/         # 日志配置
│   ├── metrics/        # 性能监控
│   ├── server/         # HTTP/WebSocket 服务器
│   │   ├── handlers_control.go      # 控制面处理器
│   │   ├── server.go                # 服务器主逻辑
│   │   └── utils.go                 # 工具函数
│   ├── task/          # 任务分发
│   │   ├── dispatcher.go            # 任务分发器
│   │   └── queue.go                 # 任务队列
│   └── websocket/     # WebSocket 处理
│       └── ack_store.go             # ACK 存储
├── pkg/api/            # API 类型定义
└── configs/            # 配置文件
```

## 部署

### Docker

```dockerfile
FROM golang:1.24-alpine AS builder
WORKDIR /app
COPY . .
RUN go build -o agent-server cmd/server/main.go

FROM alpine:latest
RUN apk --no-cache add ca-certificates
WORKDIR /root/
COPY --from=builder /app/agent-server .
COPY --from=builder /app/configs ./configs
CMD ["./agent-server", "start"]
```

### Systemd

```ini
[Unit]
Description=Agent-Server
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=agent-server
WorkingDirectory=/opt/agent-server
ExecStart=/opt/agent-server/agent-server start
Restart=always

[Install]
WantedBy=multi-user.target
```
