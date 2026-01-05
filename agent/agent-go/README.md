# OPS Job Agent (Go)

运维作业平台的 Agent 客户端，使用 Go 语言实现，参考蓝鲸和 codo 的 agent 设计思想。

## 功能特性

### 核心功能
- ✅ Agent 注册和心跳机制
- ✅ 任务拉取和执行
- ✅ 脚本执行（支持 shell/python/powershell）
- ✅ 文件传输（上传/下载）
- ✅ 任务取消机制
- ✅ 实时日志上报
- ✅ 系统信息收集（CPU、内存、磁盘等）
- ✅ 任务队列和并发控制（使用 semaphore 库）
- ✅ 自动重连和错误恢复
- ✅ 配置管理（使用 viper，支持配置文件和环境变量）
- ✅ 本地日志记录和轮转（使用 logrus + lumberjack）
- ✅ 统一错误码体系
- ✅ 资源限制（带宽限制）
- ✅ 性能监控和指标上报
- ✅ 测试覆盖

### 技术栈

- **日志**: logrus + lumberjack（日志轮转）
- **配置**: viper（支持 YAML/JSON/环境变量）
- **并发控制**: semaphore（信号量库）
- **HTTP 客户端**: resty
- **Web 框架**: gin

### 架构设计

```
agent-go/
├── cmd/agent/          # 主程序入口
├── internal/
│   ├── api/           # API 类型定义
│   ├── config/        # 配置管理（使用 viper）
│   ├── core/          # Agent 核心逻辑
│   ├── executor/      # 任务执行器
│   │   ├── executor.go        # 基础执行器
│   │   ├── script_executor.go # 脚本执行器
│   │   └── file_transfer.go  # 文件传输执行器
│   ├── httpclient/    # HTTP 客户端
│   ├── logger/        # 日志管理（使用 logrus + lumberjack）
│   ├── server/        # HTTP 服务器（健康检查等）
│   └── system/        # 系统信息收集
```

## 快速开始

### 安装依赖

```bash
cd agent/agent-go
go mod tidy
```

### 编译

```bash
go build -o ops-job-agent ./cmd/agent
```

### 配置

#### 方式1：环境变量

```bash
export CONTROL_PLANE_URL=http://localhost:8000
export AGENT_TOKEN=your-token-here
export AGENT_NAME=my-agent
export AGENT_LABELS=env=prod,region=us-east-1
export AGENT_MODE=direct                 # direct 或 agent-server
export AGENT_SERVER_URL=wss://agent-server.example.com
export AGENT_SERVER_BACKUP_URL=wss://agent-server-backup.example.com
export AGENT_WS_BACKOFF_INITIAL_MS=1000
export AGENT_WS_BACKOFF_MAX_MS=30000
export AGENT_WS_MAX_RETRIES=6
```

#### 方式2：配置文件（YAML）

创建 `~/.ops-job-agent/config.yaml`:

```yaml
mode: "direct"  # 或 "agent-server"
control_plane_url: "http://localhost:8000"
agent_server_url: "wss://agent-server.example.com"
agent_server_backup_url: "wss://agent-server-backup.example.com"
ws_backoff_initial_ms: 1000
ws_backoff_max_ms: 30000
ws_max_retries: 6
agent_token: "your-token-here"
agent_name: "my-agent"
agent_labels:
  env: "prod"
  region: "us-east-1"
log_dir: "/var/log/ops-job-agent"
log_max_size: 10        # MB
log_max_files: 5
log_max_age: 7          # 天
heartbeat_interval: 10   # 秒
task_poll_interval: 5   # 秒
max_concurrent_tasks: 5
enable_tls: false
tls_cert_file: ""
tls_key_file: ""
```

#### 方式3：配置文件（JSON）

创建 `~/.ops-job-agent/config.json`:

```json
{
  "control_plane_url": "http://localhost:8000",
  "agent_token": "your-token-here",
  "agent_name": "my-agent",
  "agent_labels": {
    "env": "prod",
    "region": "us-east-1"
  },
  "log_dir": "/var/log/ops-job-agent",
  "log_max_size": 10,
  "log_max_files": 5,
  "log_max_age": 7,
  "heartbeat_interval": 10,
  "task_poll_interval": 5,
  "max_concurrent_tasks": 5
}
```

### 运行

```bash
./ops-job-agent start
```

## 配置说明

| 环境变量 | 配置文件字段 | 默认值 | 说明 |
|---------|------------|--------|------|
| `AGENT_MODE` | `mode` | `direct` | 连接模式：`direct` or `agent-server` |
| `CONTROL_PLANE_URL` | `control_plane_url` | `http://localhost:8000` | 控制面 URL |
| `AGENT_SERVER_URL` | `agent_server_url` | `ws://localhost:8080` | Agent-Server WebSocket 入口（agent-server 模式） |
| `AGENT_SERVER_BACKUP_URL` | `agent_server_backup_url` | `` | 备用 Agent-Server WS 入口 |
| `AGENT_WS_BACKOFF_INITIAL_MS` | `ws_backoff_initial_ms` | `1000` | WS 重连初始退避（毫秒） |
| `AGENT_WS_BACKOFF_MAX_MS` | `ws_backoff_max_ms` | `30000` | WS 重连最大退避（毫秒） |
| `AGENT_WS_MAX_RETRIES` | `ws_max_retries` | `6` | WS 重试次数 |
| `AGENT_TOKEN` | `agent_token` | - | Agent 认证 Token |
| `AGENT_NAME` | `agent_name` | 主机名 | Agent 名称 |
| `AGENT_LABELS` | `agent_labels` | - | Agent 标签（格式：key1=value1,key2=value2） |
| `AGENT_LOG_DIR` | `log_dir` | `/tmp/ops-job-agent/logs` | 日志目录 |
| `AGENT_LOG_MAX_SIZE` | `log_max_size` | `10` | 日志文件最大大小（MB） |
| `AGENT_LOG_MAX_FILES` | `log_max_files` | `5` | 最大保留日志文件数 |
| `AGENT_LOG_MAX_AGE` | `log_max_age` | `7` | 日志保留天数 |
| `AGENT_HEARTBEAT_INTERVAL` | `heartbeat_interval` | `10` | 心跳间隔（秒） |
| `AGENT_TASK_POLL_INTERVAL` | `task_poll_interval` | `5` | 任务轮询间隔（秒） |
| `AGENT_MAX_CONCURRENT_TASKS` | `max_concurrent_tasks` | `5` | 最大并发任务数 |
| `AGENT_CONFIG_FILE` | - | `~/.ops-job-agent/config.yaml` | 配置文件路径 |

**注意**: 环境变量优先级高于配置文件。

### 连接模式

- **direct**（默认）：Agent 直接通过 HTTP 连接控制面，适合节点较少、无跨网需求的场景。
- **agent-server**：Agent 通过 Agent-Server 注册，并使用 WebSocket 接收任务、心跳和日志；控制面仅需向 Agent-Server 使用 HTTP 主动推送任务，适合大规模或跨网络部署。此模式需要配置 `AGENT_SERVER_URL` 并保证 Agent 出站可访问。

## API 接口

Agent 与控制面通过以下 API 交互：

### 1. 注册
```
POST /api/agents/register/
```

### 2. 心跳
```
POST /api/agents/{agent_id}/heartbeat/
```

### 3. 拉取任务
```
POST /api/agents/{agent_id}/next-task/
```

### 4. 上报结果
```
POST /api/agents/{agent_id}/tasks/{task_id}/report/
```

## 任务类型

### 脚本执行

```json
{
  "id": "task-123",
  "name": "执行脚本",
  "type": "script",
  "script_type": "shell",
  "command": "#!/bin/bash\necho 'Hello World'",
  "timeout_sec": 300,
  "env": {
    "VAR1": "value1"
  }
}
```

### 文件传输

```json
{
  "id": "task-124",
  "name": "文件上传",
  "type": "file_transfer",
  "file_transfer": {
    "type": "upload",
    "remote_path": "/tmp/file.txt",
    "content": "base64_encoded_content"
  }
}
```

## 系统信息收集

Agent 会定期收集并上报以下系统信息：

- 主机名
- 操作系统和架构
- IP 地址列表
- CPU 使用率
- 内存使用率
- 磁盘使用率（各挂载点）
- 负载平均值（Unix）
- 系统运行时间

## 日志管理

使用 **logrus** + **lumberjack** 实现：

- 结构化日志（支持字段）
- 日志文件自动轮转（达到最大大小时）
- 保留指定数量的历史日志文件
- 自动压缩旧日志文件
- 同时输出到标准输出和日志文件
- 支持日志级别（Debug/Info/Warn/Error）

## 开发计划

- [ ] WebSocket 实时日志推送
- [ ] TLS 支持
- [ ] 任务优先级队列
- [ ] 资源限制（CPU、内存）
- [ ] 插件系统
- [ ] 性能监控和指标上报

## 参考

- [蓝鲸标准运维](https://github.com/Tencent/bk-sops)
- [Codo](https://github.com/opendevops-cn/codo)
- [logrus](https://github.com/sirupsen/logrus)
- [lumberjack](https://github.com/natefinch/lumberjack)
- [viper](https://github.com/spf13/viper)
- [semaphore](https://github.com/marusama/semaphore)
