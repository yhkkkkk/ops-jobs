# Agent-Server (Go)

Agent-Server 是一个独立的 Go 服务，作为控制面和 Agent 之间的中间层，解决跨云跨网络场景下的连接问题。

## 功能特性

- ✅ **Agent 连接管理**: 支持 Agent 注册、认证和 WebSocket 连接管理
- ✅ **任务转发**: 从控制面接收任务并转发到 Agent
- ✅ **日志聚合**: 聚合 Agent 日志并批量推送到控制面
- ✅ **心跳代理**: 代理 Agent 心跳到控制面
- ✅ **高并发**: 基于 Go 的 goroutine 模型，支持大量并发连接
- ✅ **独立部署**: 与控制面分离，可以独立扩展

## 架构

```
控制面 (Django) ←→ Agent-Server (Go) ←→ Agent (Go)
```

## 快速开始

### 安装

```bash
cd agent/agent-server-go
go mod download
go build -o agent-server cmd/server/main.go
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
  url: "https://control-plane.example.com"
  token: "server-auth-token"
  scope: "default"  # 控制面作用域/租户标识，控制面调用需携带 X-Scope
auth:
  shared_secret: ""      # 可选，启用后控制面请求需带 HMAC 签名
  require_signature: false
  clock_skew: "300s"     # 允许的时间偏移
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
ws://agent-server:8080/ws/agent/{agent_id}?token={agent_token}
```

## 开发

### 项目结构

```
agent-server-go/
├── cmd/server/          # 入口文件
├── internal/            # 内部包
│   ├── config/         # 配置管理
│   ├── server/         # HTTP/WebSocket 服务器
│   ├── agent/          # Agent 连接管理
│   ├── controlplane/   # 控制面客户端
│   ├── task/           # 任务分发
│   ├── log/            # 日志聚合
│   └── logger/         # 日志配置
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
After=network.target

[Service]
Type=simple
User=agent-server
WorkingDirectory=/opt/agent-server
ExecStart=/opt/agent-server/agent-server start
Restart=always

[Install]
WantedBy=multi-user.target
```

## 许可证

MIT

