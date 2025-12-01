# OPS Job - 运维作业平台

[![Python](https://img.shields.io/badge/Python-3.10+-blue.svg)](https://www.python.org/)
[![Django](https://img.shields.io/badge/Django-5.0.1-green.svg)](https://www.djangoproject.com/)
[![DRF](https://img.shields.io/badge/DRF-3.14+-orange.svg)](https://www.django-rest-framework.org/)
[![Vue](https://img.shields.io/badge/Vue-3.4+-brightgreen.svg)](https://vuejs.org/)
[![TypeScript](https://img.shields.io/badge/TypeScript-5.3+-blue.svg)](https://www.typescriptlang.org/)
[![Redis](https://img.shields.io/badge/Redis-6.4+-red.svg)](https://redis.io/)
[![Celery](https://img.shields.io/badge/Celery-5.3+-green.svg)](https://celeryproject.org/)
[![License](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

一个基于 Django 5.0 + DRF + Vue 3 + TypeScript 的现代化运维作业平台，提供主机管理、脚本执行、作业模板、定时任务、实时日志、权限管理等功能。支持 SSE 实时日志推送、Redis Stream 数据流、Celery 异步任务处理等企业级特性。

## ✨ 功能特性

### 🖥️ 主机管理

- **主机信息管理**: 支持主机的增删改查，包含 IP、端口、认证信息等
- **主机分组**: 支持按业务、环境等维度对主机进行分组管理
- **连接状态监控**: 实时监控主机连接状态，支持批量连接测试
- **服务器账号管理**: 统一的服务器账号和认证信息管理
- **云同步功能**: 支持从阿里云、腾讯云、AWS 等云厂商自动同步主机信息
- **权限控制**: 基于 Guardian 的对象级权限控制

### 📝 脚本模板

- **脚本管理**: 支持 Shell、Python、PowerShell 等多种脚本类型
- **模板化**: 支持参数化脚本模板，提高脚本复用性
- **版本控制**: 脚本版本管理，支持历史版本回滚
- **分类标签**: 支持脚本分类和标签管理
- **代码高亮**: 集成 Monaco Editor，支持语法高亮和智能提示

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
- **异步处理**: 基于 Celery 的异步任务处理
- **执行控制**: 支持执行过程中的暂停、继续、停止操作

### ⏰ 定时任务

- **Cron 表达式**: 支持标准 Cron 表达式定时调度
- **任务管理**: 支持任务的启用、禁用、删除等操作
- **执行历史**: 完整的任务执行历史记录
- **失败重试**: 支持任务失败自动重试机制

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

## 🏗️ 技术架构

### 后端技术栈

- **框架**: Django 5.0.1 + Django REST Framework 3.14+
- **数据库**: SQLite (开发) / PostgreSQL (生产)
- **缓存**: Redis 6.4+
- **任务队列**: Celery 5.3+ + Redis
- **认证**: JWT + Session + Guardian
- **API 文档**: drf-spectacular (OpenAPI 3.0)
- **权限**: django-guardian 3.0+
- **管理后台**: django-simpleui 2025.6.24+

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

- **SSH 连接**: 基于 Fabric 的安全 SSH 连接
- **文件传输**: 支持 SFTP 文件上传下载
- **实时通信**: SSE + Redis Stream 实时日志推送
- **健康检查**: django-health-check 3.20+ 系统监控
- **日志系统**: 结构化日志记录和轮转
- **任务队列**: Celery 5.3+ 异步任务处理
- **缓存系统**: Redis 6.4+ 多数据库缓存
- **权限系统**: django-guardian 3.0+ 对象级权限
- **API 文档**: drf-spectacular OpenAPI 3.0 文档
- **代码编辑器**: Monaco Editor 0.45+ 代码编辑和语法高亮
- **图表组件**: ECharts 5.6+ 数据可视化和趋势分析

## 🎯 核心特性

### 🔄 实时日志系统

- **SSE 推送**: 基于 Server-Sent Events 的实时日志推送
- **Redis Stream**: 使用 Redis Stream 实现高性能数据流处理
- **日志归档**: 自动将实时日志归档到数据库和文件系统
- **历史查询**: 支持分页查询历史执行日志
- **心跳机制**: 自动心跳检测确保连接稳定性

### ⚡ 异步任务处理

- **Celery 集成**: 基于 Celery 的分布式任务队列
- **任务监控**: 实时监控任务执行状态和进度
- **失败重试**: 智能的任务失败重试机制
- **超时控制**: 可配置的任务执行超时时间
- **资源管理**: 自动资源清理和内存管理

### 🔐 企业级安全

- **多重认证**: JWT + Session + Guardian 三重认证
- **对象级权限**: 基于 Guardian 的细粒度权限控制
- **操作审计**: 完整的用户操作审计日志
- **安全防护**: 集成验证码、登录保护、CSRF 防护
- **数据加密**: 敏感数据加密存储

## 🖼️ 系统界面截图

### 仪表盘
![仪表盘](images/仪表盘.png)

### 主机与账号
![主机管理](images/主机管理.png)
![新建主机](images/新建主机.png)
![新建分组](images/新建分组.png)
![服务器账号](images/服务器账号.png)
![新建账号](images/新建账号.png)

### 脚本模板
![脚本模板](images/脚本模板.png)
![新建脚本](images/新建脚本.png)
![脚本预览](images/脚本预览.png)

### 作业与执行
![作业模板](images/作业模板.png)
![新建job](images/新建job.png)
![job详情](images/job详情.png)
![执行方案](images/执行方案.png)
![快速执行](images/快速执行.png)

### 定时任务与审计
![定时任务1](images/定时任务1.png)
![定时任务2](images/定时任务2.png)
![定时任务3](images/定时任务3.png)
![审计日志](images/审计.png)

## 🚀 快速开始

### 环境要求

- Python 3.10+
- Redis 6.4+
- Node.js 16+ (前端开发)

### 安装部署

1. **克隆项目**

```bash
git clone <repository-url>
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

# 启动 Celery Worker (新终端)
uv run celery -A ops_job worker -l info

# 启动 Celery Beat (新终端)
uv run celery -A ops_job beat -l info

# 启动前端开发服务器 (新终端)
cd frontend
npm run dev
```

7. **访问应用**

- 前端应用: http://localhost:5173/
- API 文档: http://localhost:8000/api/docs/
- 管理后台: http://localhost:8000/admin/
- 健康检查: http://localhost:8000/health/

## 📖 API 文档

### 接口概览

- **认证接口**: `/api/auth/` - 用户登录、注册、权限管理
- **主机管理**: `/api/hosts/` - 主机和主机组管理
- **服务器账号**: `/api/hosts/accounts/` - 服务器账号管理
- **云同步**: `/api/hosts/sync_cloud_hosts/` - 云厂商主机同步
- **脚本模板**: `/api/script-templates/` - 脚本模板管理
- **作业模板**: `/api/templates/` - 作业模板和执行方案
- **执行方案**: `/api/templates/plans/` - 执行方案管理
- **快速执行**: `/api/quick/` - 快速脚本和文件传输
- **定时任务**: `/api/scheduler/` - 定时任务管理
- **执行记录**: `/api/executor/` - 执行记录查询和详情
- **仪表盘**: `/api/dashboard/` - 统计数据和监控
- **权限管理**: `/api/permissions/` - 权限检查和用户权限
- **审计日志**: `/api/permissions/audit-logs/` - 系统操作审计
- **系统配置**: `/api/system/` - 系统配置管理
- **实时通信**: `/api/realtime/sse/` - SSE 实时日志推送
- **健康检查**: `/health/` - 系统健康状态检查

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

# 日志配置
LOG_LEVEL=INFO
EXECUTION_LOGS_DIR=/path/to/logs/executions

# 前端配置
VITE_API_BASE_URL=http://localhost:8000/api

# Celery 配置
CELERY_BROKER_URL=redis://localhost:6379/2
CELERY_RESULT_BACKEND=redis://localhost:6379/2

# 云同步配置
CLOUD_ALIYUN_ACCESS_KEY=your-access-key
CLOUD_ALIYUN_SECRET_KEY=your-secret-key
CLOUD_TENCENT_SECRET_ID=your-secret-id
CLOUD_TENCENT_SECRET_KEY=your-secret-key
```

### 功能开关

```python
# 验证码开关
CAPTCHA_ENABLED = True

# 缓存开关
CACHE_ENABLED = True

# 调试模式
DEBUG = False

# 权限系统开关
GUARDIAN_ENABLED = True
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

- **CI/CD 集成**: 与持续集成流水线集成
- **环境管理**: 开发、测试、生产环境的统一管理
- **数据库运维**: 数据库备份、恢复等操作
- **日志收集**: 批量日志收集和分析
- **代码部署**: 支持多种脚本语言的自动化部署

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

**2. Celery 任务失败**

```bash
# 检查 Celery Worker 状态
celery -A ops_job inspect active

# 查看任务日志
tail -f logs/celery.log

# 重启 Worker
celery -A ops_job worker --purge

# 检查Redis连接
redis-cli ping
```

**3. 前端构建失败**

```bash
# 检查依赖
cd frontend
npm install

# 检查 TypeScript 类型
npm run type-check

# 清理缓存
rm -rf node_modules/.cache
```

**4. 权限问题**

```bash
# 检查 Guardian 配置
python manage.py shell -c "from guardian.shortcuts import get_perms; print(get_perms(user, obj))"

# 查看权限日志
tail -f logs/permissions.log
```

**5. 实时日志问题**

```bash
# 检查Redis Stream
redis-cli XREAD STREAMS job_logs:execution_id 0

# 检查SSE连接
curl -N -H "Accept: text/event-stream" http://localhost:8000/api/realtime/sse/combined/execution_id/

# 查看实时日志服务状态
python manage.py shell -c "from utils.realtime_logs import realtime_log_service; print(realtime_log_service.redis_client.ping())"
```

### 监控指标

- 系统资源使用率 (CPU、内存、磁盘)
- 数据库连接数和查询性能
- Redis 内存使用和命中率
- Celery 任务队列长度和执行时间
- HTTP 请求响应时间和错误率
- 前端页面加载性能
- SSE 连接数和实时日志推送性能
- Redis Stream 数据量和处理延迟

## 🤝 贡献指南

1. Fork 项目
2. 创建功能分支 (`git checkout -b feature/AmazingFeature`)
3. 提交更改 (`git commit -m 'Add some AmazingFeature'`)
4. 推送到分支 (`git push origin feature/AmazingFeature`)
5. 创建 Pull Request

## 📄 许可证

本项目采用 MIT 许可证 - 查看 [LICENSE](LICENSE) 文件了解详情。

## 📞 联系方式

- 项目地址: [GitHub Repository](https://github.com/your-username/ops-job)
- 问题反馈: [Issues](https://github.com/your-username/ops-job/issues)
- 文档地址: [Documentation](https://your-docs-site.com)

---

⭐ 如果这个项目对你有帮助，请给它一个 Star！
