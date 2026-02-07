# OPS Job - 运维作业平台（还在开发完善...）

[![Python](https://img.shields.io/badge/Python-3.10+-blue.svg)](https://www.python.org/)
[![Django](https://img.shields.io/badge/Django-5.0.1-green.svg)](https://www.djangoproject.com/)
[![DRF](https://img.shields.io/badge/DRF-3.14+-orange.svg)](https://www.django-rest-framework.org/)
[![Vue](https://img.shields.io/badge/Vue-3.4+-brightgreen.svg)](https://vuejs.org/)
[![TypeScript](https://img.shields.io/badge/TypeScript-5.3+-blue.svg)](https://www.typescriptlang.org/)
[![Redis](https://img.shields.io/badge/Redis-6.4+-red.svg)](https://redis.io/)
[![License](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

一个基于 Django 5.0 + DRF + Vue 3 + TypeScript 的现代化运维作业平台，提供主机管理、脚本执行、作业模板、定时任务、实时日志、权限管理等功能。支持 SSE 实时日志推送、Redis Stream 数据流，以及基于 Agent / Agent-Server 的异步任务处理等企业级特性。

## ✨ 功能特性

### 🖥️ 主机管理

- **主机信息管理**: 支持主机的增删改查，包含 IP、端口、认证信息等
- **主机分组**: 支持按业务、环境等维度对主机进行分组管理
- **连接状态监控**: 实时监控主机连接状态，支持批量连接测试
- **服务器账号管理**: 统一的服务器账号和认证信息管理
- **云同步功能**: 支持从阿里云、腾讯云、AWS 等云厂商自动同步主机信息
- **权限控制**: 基于 Guardian 的对象级权限控制

### 📝 脚本模板

- **脚本管理**: 支持 Shell、Python、PowerShell、JavaScript、Go 等多种脚本类型
- **模板化**: 支持参数化脚本模板，提高脚本复用性
- **版本控制**: 脚本版本管理，支持历史版本回滚与版本 Diff
- **分类标签**: 支持脚本分类和标签管理
- **代码高亮**: 集成 Monaco Editor，支持多语言语法高亮与基础校验

### 🔧 作业模板

- **可视化编排**: 支持多步骤作业流程编排
- **步骤管理**: 支持脚本执行、文件传输等多种步骤类型
- **执行方案**: 支持一个模板创建多个执行方案，灵活配置步骤选择和执行顺序
- **同步机制**: 智能的模板与执行方案同步机制
- **步骤配置**: 支持步骤超时时间、忽略错误、参数覆盖等配置

### ⚡ 快速执行

- **即时执行**: 支持脚本和文件传输的快速执行
- **批量操作**: 支持批量主机的并行执行
- **实时日志**: 基于 SSE 的实时日志推送和查看
- **结果统计**: 执行结果统计和成功率分析
- **异步处理**: 基于 Agent / Agent-Server 的异步任务处理
- **执行控制**: 支持执行过程中的暂停、继续、停止操作（依托 Agent 取消能力）

### ⏰ 定时任务

- **Cron 表达式**: 支持标准 Cron 表达式定时调度
- **任务管理**: 支持任务的启用、禁用、删除等操作
- **执行历史**: 完整的任务执行历史记录
- **失败重试**: 支持任务失败自动重试机制（基于 APScheduler + 业务侧重试逻辑）

### 📊 仪表盘

- **数据概览**: 主机、模板、执行记录等关键指标统计
- **趋势分析**: 执行趋势和成功率趋势分析（基于 ECharts）
- **实时监控**: 系统状态和服务健康检查
- **最近活动**: 最近的执行记录和操作日志
- **缓存优化**: 基于 Redis 的缓存机制
- **时间过滤**: 支持按时间范围筛选统计数据
- **交互式图表**: 支持图表交互和钻取分析

### 👥 用户管理

- **用户认证**: 支持 JWT Token 和 Session 双重认证
- **权限管理**: 基于 Guardian 的对象级权限控制系统
- **操作审计**: 完整的用户操作日志记录
- **安全防护**: 集成验证码和登录保护机制

### 🔐 权限管理

- **细粒度权限**: 基于 Guardian 的对象级权限控制
- **权限检查**: 前端权限检查和后端权限验证
- **审计日志**: 完整的权限操作审计记录
- **权限分配**: 通过 Django Admin 进行权限管理

### ⚙️ 系统配置

- **配置管理**: 系统级配置参数管理
- **环境变量**: 支持环境变量配置
- **功能开关**: 灵活的功能启用/禁用控制

### 🔄 实时通信

- **SSE 推送**: 基于 Server-Sent Events 的实时日志推送
- **Redis Stream**: 使用 Redis Stream 实现数据流处理
- **心跳机制**: 自动心跳检测和连接管理
- **连接恢复**: 自动重连和状态恢复机制

### 🤖 Agent / Agent-Server 系统

- **Agent-Server 支持**: 统一的 Agent-Server 模式，支持跨云跨网络部署，任务/日志/结果走单一 WebSocket 通道
- **控制面集成**: Django 侧提供 Agent 安装/卸载、生命周期管理、版本管理和批量操作，支持基于安装脚本的 `pending → online → offline/disabled` 状态机
- ****Agent-Server 网关****: 维护与 Agent 的 WebSocket 连接，通过 **Redis Streams 将日志/结果/状态回传控制面**；日志/结果消息携带 `message_id`，服务端幂等去重并回 `ack`；离线任务使用 PendingTaskStore 持久化
- **幂等与取消**: 控制面提供任务取消 API；Agent 侧维护“最近完成任务”缓存避免重复执行，Agent-Server 优先通过 WS 下发取消指令，失败时回退删除队列任务
- **多语言执行器**: Agent 内置 Shell / Python / PowerShell / JS 等多语言执行器，支持并发与基础重试
- **任务分发**: 控制面主动推送任务到 Agent-Server，Agent-Server 通过 WebSocket 实时推送给 Agent（Agent 在线时）或持久化到 PendingTaskStore（Agent 离线时）
- **资源监控**: 实时收集和上报 Agent 系统资源使用情况（CPU、内存、磁盘、网络）
- **性能指标**: 内置性能监控和指标收集（任务统计、执行时间、网络传输等）
- **统一错误码**: 完善的错误码体系，便于问题定位和错误处理
- **带宽限制**: 支持文件传输的带宽限制，避免网络拥塞

## 🏗️ 技术架构

### 后端技术栈

- **框架**: Django 5.0.1 + Django REST Framework 3.14+
- **数据库**: SQLite (开发) / PostgreSQL (生产)
- **缓存**: Redis 6.4+
- **任务调度与队列**: APScheduler + Redis（控制面定时任务与后台任务） / PendingTaskStore（Agent-Server 离线任务持久化）
- **认证**: JWT + Session + Guardian
- **API 文档**: drf-spectacular (OpenAPI 3.0)
- **权限**: django-guardian 3.0+
- **管理后台**: django-simpleui 2025.6.24+

### Agent 技术栈

- **语言**: Go 1.24+
- **Web 框架**: Gin 1.10+ (Agent 本地 HTTP 服务)
- **HTTP 客户端**: Resty 2.13+ (与控制面通信)
- **WebSocket**: Gorilla WebSocket 1.5+ (Agent-Server 模式)
- **配置管理**: Viper 1.21+ (配置文件和环境变量)
- **日志系统**: Logrus + Lumberjack (结构化日志和轮转)
- **系统监控**: gopsutil 3.24+ (跨平台系统信息收集)
- **并发控制**: Semaphore (任务并发限制)

### Agent-Server 技术栈

- **语言**: Go 1.24+
- **Web 框架**: Gin 1.10+ (HTTP API服务)
- **WebSocket**: Gorilla WebSocket 1.5+ (Agent连接管理)
- **任务持久化**: PendingTaskStore Redis（离线任务存储）
- **配置管理**: Viper 1.21+ (配置文件和环境变量)
- **日志系统**: Logrus + Lumberjack (结构化日志)
- **认证**: HMAC签名 (可选的安全认证)

### 前端技术栈

- **框架**: Vue 3.4+ + TypeScript 5.3+
- **构建工具**: Vite 6.3+
- **UI 组件**: Arco Design Vue 2.57+
- **状态管理**: Pinia 2.1+
- **路由**: Vue Router 4.5+
- **图表**: ECharts 5.6+
- **代码编辑器**: Monaco Editor 0.45+
- **HTTP 客户端**: Axios 1.8+

### 核心组件

- **Agent 执行链路**: 以 Agent / Agent-Server 为统一通道完成脚本执行、作业步骤和文件上传/下发（HTTP + WebSocket，日志/结果经 Redis Streams，WS `message_id`+`ack` 去重/重传）
- **SSH 能力**: 仍保留 Fabric/SSH 能力，主要用于 Agent 安装/卸载等少量场景
- **实时通信**: SSE + Redis Stream 实时日志推送
- **健康检查**: django-health-check 3.20+ 系统监控
- **日志系统**: 结构化日志记录和轮转
- **任务队列**: Redis + APScheduler 后台任务调度，Agent-Server 侧使用 PendingTaskStore 进行离线任务持久化
- **缓存系统**: Redis 6.4+ 多数据库缓存
- **权限系统**: django-guardian 3.0+ 对象级权限
- **API 文档**: drf-spectacular OpenAPI 3.0 文档
- **代码编辑器**: Monaco Editor 0.45+ 代码编辑和语法高亮
- **图表组件**: ECharts 5.6+ 数据可视化和趋势分析
- **Agent 系统**: Go 语言实现的轻量级 Agent，支持脚本执行、文件传输等
- **Agent-Server**: Go 语言实现的 Agent 管理服务器，支持跨云跨网络部署

## 🎯 核心特性

### 🔄 实时日志系统

- **SSE 推送**: 基于 Server-Sent Events 的实时日志推送
- **Redis Stream**: 使用 Redis Stream 实现高性能数据流处理
- **日志归档**: 自动将实时日志归档到数据库和文件系统
- **历史查询**: 支持分页查询历史执行日志
- **心跳机制**: 自动心跳检测确保连接稳定性

### ⚡ 异步任务处理

- **任务监控**: 实时监控任务执行状态和进度（ExecutionRecord + Agent 结果流）
- **失败重试**: 智能的任务失败重试机制（ExecutionService + Agent-Server 重试策略）
- **超时控制**: 可配置的任务执行超时时间（作业模板/执行方案级别）
- **资源管理**: 自动资源清理和内存管理

### 🔐 企业级安全

- **多重认证**: JWT + Session + Guardian 三重认证
- **对象级权限**: 基于 Guardian 的细粒度权限控制
- **操作审计**: 完整的用户操作审计日志
- **安全防护**: 集成验证码、登录保护、CSRF 防护
- **数据加密**: 敏感数据加密存储

## 🖼️ 系统界面截图

### 仪表盘

![运维台仪表盘](images/运维台仪表盘.png)
![仪表盘](images/仪表盘.png)

### Agent 与安装包

![Agent 管理](images/agent管理.png)
![安装包管理](images/agent安装包管理.png)

### 主机与账号

![主机管理](images/主机管理.png)
![新建主机](images/新建主机.png)
![新建分组](images/新建分组.png)
![服务器账号](images/服务器账号.png)
![新建账号](images/新建账号.png)

### 脚本模板

![脚本模板](images/脚本模板.png)
![版本管理](images/脚本模板版本管理.png)
![新建脚本](images/新建脚本.png)

### 作业与执行

![作业模板](images/作业模板.png)
![新建job](images/新建job.png)
![job详情](images/job详情.png)
![执行方案](images/执行方案.png)
![快速执行](images/快速执行.png)

### 定时任务与审计

![定时任务](images/定时任务.png)
![定时任务2](images/定时任务2.png)
![定时任务3](images/定时任务3.png)
![审计日志](images/审计日志.png)

## 🚀 快速开始

### 环境要求

- Python 3.10+
- Redis 6.4+
- Node.js 16+ (前端开发)
- Go 1.24+ (Agent开发，可选)
- Docker & Docker Compose (推荐)

### 使用 Docker Compose (推荐)

1. **克隆项目**

```bash
git clone https://github.com/yhkkkkk/ops-jobs.git
cd ops-job
```

2. **配置环境变量**

```bash
# 复制环境变量文件
cp .env.example .env

# 编辑环境变量 (可选，Docker Compose 有默认值)
vim .env
```

3. **启动服务**

```bash
# 启动所有服务 (控制面 + 前端 + 数据库 + Redis)
docker-compose up -d

# 查看服务状态
docker-compose ps

# 查看日志
docker-compose logs -f control-plane
```

4. **访问应用**

- 前端应用: http://localhost:5173/
- API 文档: http://localhost:8000/api/docs/
- 管理后台: http://localhost:8000/admin/

5. **启动 Agent (可选)**

```bash
# 方式1: 使用 Docker Compose 启动 Agent-Server
docker-compose --profile agents up -d

# 方式2: 在宿主机运行 Agent
cd agent/agent-go
go build -o ops-job-agent cmd/agent/main.go

# 配置环境变量
export AGENT_MODE=agent-server
export AGENT_AGENT_SERVER_URL=ws://localhost:8080
export AGENT_TOKEN=your-agent-token

# 启动 Agent
./ops-job-agent
```

### 手动安装部署

1. **克隆项目**

```bash
git clone https://github.com/yhkkkkk/ops-jobs.git
cd ops-job
```

2. **安装后端依赖**

```bash
# 使用 uv (推荐)
uv sync

# 或使用 pip
pip install -r requirements.txt
```

3. **安装前端依赖**

```bash
cd frontend
npm install
# 或使用 pnpm
pnpm install
```

4. **配置环境**

```bash
# 复制配置文件
cp .env.example .env

# 编辑配置文件
vim .env
```

5. **初始化数据库**

```bash
uv run python manage.py migrate
uv run python manage.py createsuperuser
```

6. **启动服务**

```bash
# 启动 Django 服务
uv run python manage.py runserver

# 启动前端开发服务器 (新终端)
cd frontend
npm run dev
```

8. **启动 Agent (可选)**

```bash
# 进入 Agent 目录
cd agent/agent-go

# 编译 Agent
go build -o ops-job-agent cmd/agent/main.go

# 运行 Agent (Agent-Server 模式)
./ops-job-agent --config configs/config.yaml

# 或使用环境变量
AGENT_MODE=agent-server \
AGENT_AGENT_SERVER_URL=ws://localhost:8080 \
AGENT_TOKEN=your-token \
./ops-job-agent
```

9. **启动 Agent-Server**

```bash
# 进入 Agent-Server 目录
cd agent/agent-server-go

# 编译 Agent-Server
go build -o ops-job-agent-server cmd/server/main.go

# 运行 Agent-Server
./ops-job-agent-server --config configs/config.yaml

# Agent 使用 Agent-Server 模式
cd agent/agent-go
AGENT_MODE=agent-server \
AGENT_AGENT_SERVER_URL=ws://localhost:8080 \
AGENT_TOKEN=your-token \
./ops-job-agent
```

10. **访问应用**

- 前端应用: http://localhost:5173/
- API 文档: http://localhost:8000/api/docs/
- 管理后台: http://localhost:8000/admin/
- 健康检查: http://localhost:8000/health/
- Agent 本地服务: http://localhost:8080/ (Agent HTTP 服务)
- Agent-Server: http://localhost:8080/ (Agent-Server HTTP 服务)

## 📖 API 文档

### 接口概览

- **认证**: `/api/auth/` 登录 / 刷新 / 权限
- **主机与账号**: `/api/hosts/`、`/api/hosts/accounts/`、`/api/hosts/sync_cloud_hosts/`
- **脚本模板**: `/api/script-templates/`（版本管理、标签）
- **作业模板与执行方案**: `/api/templates/`、`/api/templates/plans/`
- **快速执行**: `/api/quick/execute_script/`、`/api/quick/transfer_file/`
- **定时任务**: `/api/scheduler/` 相关crud
- **执行记录 / 日志**: `/api/executor/execution-records/` 及详情
- **仪表盘**: `/api/dashboard/` 统计与监控
- **权限与审计**: `/api/permissions/`，`/api/permissions/audit-logs/`
- **系统配置**: `/api/system/`
- **实时通信 (SSE)**:
  - 作业日志：`/api/realtime/sse/logs/<execution_id>/`
  - 作业状态：`/api/realtime/sse/status/<execution_id>/`
  - 作业合并流：`/api/realtime/sse/combined/<execution_id>/`
  - Agent 安装进度：`/api/realtime/sse/agent-install/<install_task_id>/`
- **Agent 管理**: `/api/agents/`（列表/详情/启停/删除），`/api/agents/generate_install_script/`，`/api/agents/batch_install/`，`/api/agents/batch_uninstall/`，`/api/agents/install_records/`，`/api/agents/uninstall_records/`，`/api/agents/packages/`，`/api/agents/{id}/issue_token/` 等
- **健康检查**: `/health/`

### 认证方式

```bash
# JWT Token 认证
Authorization: Bearer <access_token>

# 或 Session 认证 (Cookie)
```

### 响应格式

```json
{
  "code": 200,
  "message": "操作成功",
  "success": true,
  "content": {
    "data": "响应数据"
  }
}
```

## 🔧 配置说明

### 环境变量

```bash
# 数据库配置
DATABASE_URL=sqlite:///db.sqlite3
# 或 PostgreSQL
DATABASE_URL=postgresql://user:password@localhost:5432/ops_job

# Redis 配置
REDIS_URL=redis://localhost:6379/0
REDIS_DB_CACHE=0
REDIS_DB_SESSION=1
REDIS_DB_CELERY=2
REDIS_DB_REALTIME=3

# 安全配置
SECRET_KEY=your-secret-key
DEBUG=False

# 控制面配置 (重要!)
# Agent-Server 用于连接控制面的URL
# 开发环境: http://localhost:8000 (宿主机访问)
# Docker环境: http://control-plane:8000 (容器内部访问)
# 生产环境: https://your-domain.com (外部可访问URL)
CONTROL_PLANE_URL=http://localhost:8000

# 日志配置
LOG_LEVEL=INFO
EXECUTION_LOGS_DIR=/path/to/logs/executions

# 前端配置
VITE_API_BASE_URL=http://localhost:8000/api

# 云同步配置
CLOUD_ALIYUN_ACCESS_KEY=your-access-key
CLOUD_ALIYUN_SECRET_KEY=your-secret-key
CLOUD_TENCENT_SECRET_ID=your-secret-id
CLOUD_TENCENT_SECRET_KEY=your-secret-key

# Agent 配置 (Agent-Server 模式)
AGENT_MODE=agent-server
AGENT_AGENT_SERVER_URL=ws://localhost:8080
AGENT_TOKEN=your-agent-token
AGENT_NAME=agent-01
AGENT_HTTP_ADDR=:8080
AGENT_HEARTBEAT_INTERVAL=10
AGENT_MAX_CONCURRENT_TASKS=5

# Agent-Server 配置
AGENT_SERVER_HOST=0.0.0.0
AGENT_SERVER_PORT=8080
AGENT_SERVER_CONTROL_PLANE_URL=http://localhost:8000
AGENT_SERVER_CONTROL_PLANE_TOKEN=your-token
AGENT_SERVER_MAX_CONNECTIONS=1000
AGENT_SERVER_HEARTBEAT_TIMEOUT=60
```

### 功能开关

```python
# 验证码开关（与双因子认证互斥）
CAPTCHA_ENABLED = True

# 双因子认证/OTP 开关（与验证码互斥）
TWO_FACTOR_ENABLED = False

# 登录限制开关（防止暴力破解）
AXES_ENABLED = True

# LDAP 认证开关
LDAP_ENABLED = False

# 调试模式
DEBUG = False
```

## 📝 开发指南

### 项目结构

```
ops-job/
├── apps/                      # Django 应用目录
│   ├── accounts/             # 用户认证模块
│   ├── hosts/               # 主机管理模块（含云同步）
│   ├── script_templates/    # 脚本模板模块
│   ├── job_templates/       # 作业模板模块
│   ├── quick_execute/       # 快速执行模块
│   ├── scheduler/           # 定时任务模块
│   ├── executor/            # 执行记录模块
│   ├── dashboard/           # 仪表盘模块
│   ├── permissions/         # 权限管理模块
│   └── system_config/       # 系统配置模块
├── agent/                     # Agent 相关代码
│   ├── agent-go/            # Go Agent 实现
│   │   ├── cmd/             # 命令行入口
│   │   ├── internal/        # 内部包
│   │   │   ├── api/        # API 类型定义
│   │   │   ├── config/     # 配置管理
│   │   │   ├── core/       # Agent 核心逻辑
│   │   │   ├── errors/     # 错误码体系
│   │   │   ├── executor/   # 任务执行器
│   │   │   ├── httpclient/ # HTTP 客户端
│   │   │   ├── logger/     # 日志系统
│   │   │   ├── metrics/    # 性能指标
│   │   │   ├── resource/   # 资源限制
│   │   │   ├── server/     # 本地 HTTP 服务
│   │   │   ├── system/     # 系统信息收集
│   │   │   └── websocket/  # WebSocket 客户端
│   │   └── configs/        # 配置文件示例
│   └── agent-server-go/    # Agent-Server 实现
│       ├── cmd/             # 命令行入口
│       ├── internal/        # 内部包
│       │   ├── agent/       # Agent 连接管理
│       │   ├── config/     # 配置管理
│       │   ├── controlplane/ # 控制面客户端
│       │   ├── logger/     # 日志系统
│       │   ├── server/     # HTTP/WebSocket 服务器
│       │   └── task/       # 任务分发器
│       └── pkg/            # 公共包
│           └── api/        # API 类型定义
├── frontend/                 # 前端 Vue 应用
│   ├── src/
│   │   ├── views/           # 页面组件
│   │   │   ├── dashboard/   # 仪表盘页面
│   │   │   ├── hosts/       # 主机管理页面
│   │   │   ├── accounts/    # 服务器账号页面
│   │   │   ├── script-templates/ # 脚本模板页面
│   │   │   ├── job-templates/   # 作业模板页面
│   │   │   ├── plans/       # 执行方案页面
│   │   │   ├── quick-execute/   # 快速执行页面
│   │   │   ├── scheduled-tasks/ # 定时任务页面
│   │   │   ├── execution-records/ # 执行记录页面
│   │   │   ├── audit-logs/  # 审计日志页面
│   │   │   └── system-config/ # 系统配置页面
│   │   ├── components/      # 通用组件
│   │   │   ├── MonacoEditor/ # 代码编辑器组件
│   │   │   ├── RealtimeLog/ # 实时日志组件
│   │   │   └── ...          # 其他通用组件
│   │   ├── stores/          # Pinia 状态管理
│   │   ├── router/          # 路由配置
│   │   ├── api/             # API 接口
│   │   ├── types/           # TypeScript 类型定义
│   │   └── utils/           # 工具函数
│   ├── package.json         # 前端依赖
│   └── vite.config.ts       # Vite 配置
├── utils/                   # 工具模块
│   ├── realtime_logs.py     # 实时日志服务
│   ├── sse_views.py         # SSE 视图
│   ├── log_archive_service.py # 日志归档服务
│   └── responses.py         # 统一响应格式
├── docs/                    # 文档目录
│   └── cloud_sync_setup.md  # 云同步设置指南
├── ops_job/                 # 项目配置
│   ├── settings/            # 环境配置
│   ├── urls.py             # 主URL配置
│   └── wsgi.py             # WSGI配置
├── pyproject.toml           # Python 项目配置
├── requirements.txt         # Python 依赖
└── logs/                    # 日志目录
```

### 开发命令

```bash
# 后端开发
uv run python manage.py check
uv run python manage.py test
uv run python manage.py makemigrations
uv run python manage.py migrate
uv run python manage.py collectstatic

# 前端开发
cd frontend
npm run dev          # 开发服务器
npm run build        # 生产构建
npm run type-check   # TypeScript 类型检查
npm run preview      # 预览构建结果
```

### 管理命令

```bash
# 数据库迁移
uv run python manage.py migrate
uv run python manage.py makemigrations

# 创建超级用户
uv run python manage.py createsuperuser

# 收集静态文件
uv run python manage.py collectstatic

# 健康检查
uv run python manage.py health_check

# Django Shell
uv run python manage.py shell

# 运行测试
uv run python manage.py test

# 权限管理
uv run python manage.py guardian_cleanup

# 清理过期会话
uv run python manage.py clearsessions
```

## 🔒 安全特性

- **认证保护**: JWT + Session + Guardian 三重认证
- **权限控制**: 基于 Guardian 的对象级细粒度权限
- **验证码**: 登录验证码防暴力破解
- **操作审计**: 完整的操作日志记录
- **数据加密**: 敏感数据加密存储
- **安全头**: 完整的 HTTP 安全头配置
- **CSRF 保护**: 跨站请求伪造保护
- **XSS 防护**: 跨站脚本攻击防护

## 📊 监控运维

- **健康检查**: `/health/` 端点提供系统健康状态
- **日志监控**: 结构化日志便于分析和告警
- **性能指标**: 内置性能监控和统计
- **错误追踪**: 完整的错误日志和堆栈跟踪
- **实时监控**: SSE 实时状态推送
- **审计追踪**: 完整的用户操作审计日志

## 🎯 使用场景

### 运维自动化

- **批量部署**: 支持应用的批量部署和更新
- **配置管理**: 统一的配置文件分发和管理
- **服务管理**: 批量的服务启停和重启操作
- **监控巡检**: 定时的系统巡检和健康检查

### 开发运维

- **环境管理**: 开发、测试、生产环境的统一管理
- **数据库运维**: 数据库备份、恢复等操作
- **日志收集**: 批量日志收集和分析
- **脚本自动化**: 支持多种脚本语言的自动化任务

### 安全运维

- **安全扫描**: 定时的安全漏洞扫描
- **补丁管理**: 系统补丁的批量安装
- **合规检查**: 安全合规性检查和报告
- **应急响应**: 安全事件的快速响应
- **权限审计**: 完整的操作审计和权限追踪

## 🔍 功能演示

### 主机管理

```bash
# 添加主机
POST /api/hosts/
{
    "name": "web-server-01",
    "ip_address": "192.168.1.100",
    "port": 22,
    "username": "root",
    "password": "password123",
    "group": 1
}

# 云同步主机
POST /api/hosts/sync_cloud_hosts/
{
    "provider": "aliyun",
    "region": "cn-hangzhou"
}
```

### 作业模板

```bash
# 创建作业模板
POST /api/templates/
{
    "name": "Web应用部署",
    "description": "自动化Web应用部署流程",
    "category": "deployment"
}

# 创建执行方案
POST /api/templates/plans/
{
    "name": "生产环境部署",
    "template_id": 1,
    "selected_steps": [
        {"step_id": 1, "order": 1, "timeout": 300},
        {"step_id": 2, "order": 2, "timeout": 600}
    ]
}
```

### 快速执行

```bash
# 执行脚本
POST /api/quick/execute_script/
{
    "script_content": "echo 'Hello World'",
    "script_type": "shell",
    "target_host_ids": [1, 2, 3],
    "timeout": 300
}

# 文件传输
POST /api/quick/transfer_file/
{
    "local_path": "/local/file.txt",
    "remote_path": "/remote/file.txt",
    "target_host_ids": [1, 2, 3],
    "transfer_mode": "upload"
}
```

### 实时日志

```bash
# 获取实时日志
GET /api/realtime/sse/logs/{execution_id}/

# 获取执行记录详情
GET /api/executor/execution-records/{id}/

# 获取仪表盘数据
GET /api/dashboard/stats/
```

## 🤖 Agent / Agent-Server 架构指南

### 系统架构总览

```mermaid
graph TB
    subgraph "Control Plane 控制面 Django"
        CP[控制面 API]
        SSE[SSE 实时推送]
        RedisCP[Redis Client]
    end

    subgraph "Agent-Server Go"
        AS[Agent-Server :8080]
        WSM[WebSocket Manager]
        Dispatcher[任务分发器]
        PendingStore[PendingTaskStore Redis]
        LogWriter[日志流写入]
        ResultWriter[结果流写入]
        StatusWriter[状态流写入]
        AckStore[ACK 存储 Redis]
    end

    subgraph "Agent Go"
        Agent[Agent]
        WSClient[WebSocket Client]
        Outbox[FileOutbox 本地文件]
        Executor[任务执行器]
        Heartbeat[心跳循环]
    end

    subgraph "Redis Streams"
        Logs[agent_logs]
        Results[agent_results]
        Status[agent_status]
        Ack[agent-ack:*]
    end

    %% 连接关系
    CP -->|HTTP POST 任务| AS
    AS -->|WebSocket| Agent
    Agent -->|WebSocket| AS
    AS -->|XADD| Logs
    AS -->|XADD| Results
    AS -->|XADD| Status
    AS -->|HSET| Ack
    Logs -->|XREAD| RedisCP
    Results -->|XREAD| RedisCP
    Status -->|XREAD| RedisCP
    RedisCP -->|SSE| SSE
    Agent -->|Persist| Outbox
```

### Agent 注册流程

```mermaid
sequenceDiagram
    participant A as Agent
    participant AS as Agent-Server
    participant R as Redis
    participant CP as Control Plane

    Note over A,CP: Agent-Server 模式注册流程

    A->>AS: POST /api/agents/register<br/>{name, token, system, labels}
    AS->>AS: 生成 agent_id
    AS->>AS: 保存到 Manager<br/>agents[agent_id]
    AS->>R: XADD agent_status<br/>{event: registered, status: online}
    AS->>A: 200 OK<br/>{id, ws_url, status: active}
    Note over A,AS: A->>AS: WS 连接 ws://.../ws/agent/{id}<br/>Sec-WebSocket-Protocol: agent-token,{token}
    AS->>AS: 更新 Conn.LastHeartbeat

    Note over CP: consume_streams.py 消费状态流
    R->>CP: 消费 agent_status 更新 Agent 状态
```

### 任务分发流程

```mermaid
sequenceDiagram
    participant CP as Control Plane
    participant AS as Agent-Server
    participant A as Agent
    participant R as Redis
    participant FE as Frontend

    Note over CP,FE: 1. 任务下发阶段
    CP->>AS: POST /api/agents/:id/tasks/<br/>{task_spec}
    AS->>AS: 验证 Agent 在线状态

    alt Agent 在线
        AS->>A: WebSocket: type=task<br/>{message_id, task}
        A->>AS: WS: type=ack {message_id}
        AS->>R: HSET agent-ack:{message_id}
    else Agent 离线
        AS->>R: LPUSH pending_tasks:{agent_id}
    end

    Note over A,AS: 2. 任务执行与结果上报阶段
    A->>A: 执行任务 (executor)
    A->>AS: WS: type=log {message_id, content}
    A->>AS: WS: type=result {message_id, exit_code, log}

    Note over AS,R: 3. 日志/结果写入 Redis Stream
    AS->>R: XADD agent_logs {execution_id, task_id, message_id, content}
    AS->>R: XADD agent_results {execution_id, task_id, exit_code, progress, ...}

    Note over CP,R: 4. 控制面消费 Stream
    R-->>CP: consume_streams 消费
    CP->>CP: 更新 ExecutionRecord/Step 状态

    Note over CP,FE: 5. SSE 实时推送
    CP->>FE: SSE: 实时日志
    CP->>FE: SSE: 执行进度/结果

    Note over A,AS: 6. 心跳保活
    A->>AS: WS: type=heartbeat
    AS->>R: XADD agent_status {status: online}
```

### 消息可靠性机制

```mermaid
flowchart TB
    subgraph "Agent 发送端"
        Msg[生成消息]
        ID[分配 message_id]
        Outbox[FileOutbox 持久化]
        WS[WebSocket 发送]
        Ack[等待 ACK]
    end

    subgraph "Agent-Server 接收端"
        Receive[接收消息]
        Dedup[幂等检查 Redis]
        Process[处理消息]
        Reply[回复 ACK]
        Stream[写入 Redis Stream]
    end

    Msg --> ID
    ID --> Outbox
    Outbox --> WS
    WS --> Receive
    Receive --> Dedup
    Dedup -->|已存在| Skip[丢弃]
    Dedup -->|新消息| Process
    Process --> Reply
    Reply --> Stream
```

### 数据流汇总

| 数据类型  | 源     | 目标   | 传输方式           | 用途              |
| --------- | ------ | ------ | ------------------ | ----------------- |
| 任务下发  | 控制面 | Agent  | HTTP → WS         | 执行脚本/文件传输 |
| 任务结果  | Agent  | 控制面 | WS → Redis Stream | 更新执行状态      |
| 执行日志  | Agent  | 控制面 | WS → Redis Stream | 实时日志 SSE      |
| 心跳/状态 | Agent  | 控制面 | WS → Redis Stream | 在线状态监控      |
| 任务取消  | 控制面 | Agent  | HTTP → WS         | 中断执行          |

### Redis Stream 配置

| Stream Key        | 用途          | 消费者                  |
| ----------------- | ------------- | ----------------------- |
| `agent_logs`    | 执行日志      | consume_streams.py, SSE |
| `agent_results` | 执行结果+进度 | consume_streams.py, SSE |
| `agent_status`  | 在线状态变更  | consume_streams.py      |
| `agent-ack:*`   | ACK 存储      | Agent-Server 去重       |

### 组件职责

| 组件                       | 职责                                                   |
| -------------------------- | ------------------------------------------------------ |
| **Agent**            | 任务执行、日志上报、心跳、本地消息持久化（FileOutbox） |
| **Agent-Server**     | Agent 连接管理、任务分发、消息聚合、Redis Stream 写入  |
| **PendingTaskStore** | 离线任务持久化，Agent 重连后补发                       |
| **FileOutbox**       | Agent 断线时本地消息持久化，重连后自动补发             |
| **ACK Store**        | 消息去重，避免重复处理                                 |
| **SSE**              | 向前端推送日志和进度更新                               |

### Agent 连接模式

仅支持 **Agent-Server 模式**：

```
┌─────────────────────────────────────────────────────────────────┐
│                    Agent-Server 模式                             │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│   Agent (内网)          Agent-Server (DMZ)        控制面         │
│       │                      │                      │           │
│       │  WebSocket (ws://)   │                      │           │
│       └─────────────────────►│                      │           │
│                              │  HTTP (POST tasks)   │           │
│                              │◄─────────────────────┘           │
│                              │                      │           │
│                              │  Redis Streams      │           │
│                              └─────────────────────►│           │
│                                                      │           │
└─────────────────────────────────────────────────────────────────┘
│ 特点: 跨云、跨网络，单一 WS 通道，无 HTTP 回退                   │
└─────────────────────────────────────────────────────────────────┘
```

## 🔧 故障排查

### 常见问题

**1. SSH 连接失败**

```bash
# 检查网络连通性
ping target_host

# 检查 SSH 服务
ssh -v user@target_host

# 查看日志
tail -f logs/ssh.log
```

**2. 前端构建失败**

```bash
# 检查依赖
cd frontend
npm install

# 检查 TypeScript 类型
npm run type-check

# 清理缓存
rm -rf node_modules/.cache
```

**3. 权限问题**

```bash
# 检查 Guardian 配置
python manage.py shell -c "from guardian.shortcuts import get_perms; print(get_perms(user, obj))"

# 查看权限日志
tail -f logs/permissions.log
```

**4. 实时日志问题**

```bash
# 检查Redis Stream
redis-cli XREAD STREAMS job_logs:execution_id 0

# 检查SSE连接
curl -N -H "Accept: text/event-stream" http://localhost:8000/api/realtime/sse/combined/execution_id/

# 查看实时日志服务状态
python manage.py shell -c "from utils.realtime_logs import realtime_log_service; print(realtime_log_service.redis_client.ping())"
```

**5. Agent 连接问题**

```bash
# 检查 Agent 状态
curl http://localhost:8080/health

# 查看 Agent 日志
tail -f agent/agent-go/logs/agent.log

# 检查 Agent 配置
cat agent/agent-go/configs/config.yaml

# 测试 Agent-Server 连接
curl http://localhost:8080/health

# 测试 Agent-Server 连接 (Agent-Server 模式)
curl http://agent-server:8080/health
```

**6. Agent-Server 问题**

```bash
# 检查 Agent-Server 状态
curl http://localhost:8080/health

# 查看 Agent-Server 日志
tail -f agent/agent-server-go/logs/agent-server.log

# 查看连接的 Agent 列表
curl http://localhost:8080/api/agents

# 检查控制面连接
curl http://localhost:8000/health
```

### 监控指标

- 系统资源使用率 (CPU、内存、磁盘)
- 数据库连接数和查询性能
- Redis 内存使用和命中率
- HTTP 请求响应时间和错误率
- 前端页面加载性能
- SSE 连接数和实时日志推送性能
- Redis Stream 数据量和处理延迟
- Agent 连接数和任务执行性能
- Agent-Server 连接数和消息处理延迟
- WebSocket 连接稳定性和重连次数

## 🤝 贡献指南

1. Fork 项目
2. 创建功能分支 (`git checkout -b feature/AmazingFeature`)
3. 提交更改 (`git commit -m 'Add some AmazingFeature'`)
4. 推送到分支 (`git push origin feature/AmazingFeature`)
5. 创建 Pull Request

## 📄 许可证

本项目采用 MIT 许可证 - 查看 [LICENSE](LICENSE) 文件了解详情。

## 📞 联系方式

- 项目地址: [GitHub Repository](https://github.com/yhkkkkk/ops-jobs)
- 问题反馈: [Issues](https://github.com/yhkkkkk/ops-jobs/issues)
- 文档地址: [Documentation](https://github.com/yhkkkkk/ops-jobs/blob/dev-master-agent/README.md)

---

⭐ 如果这个项目对你有帮助，请给它一个 Star！
