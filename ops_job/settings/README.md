# Django Settings 配置说明

本项目采用环境隔离的设置配置方式，将开发环境和生产环境的配置分离，提高安全性和可维护性。

## 文件结构

```
ops_job/settings/
├── __init__.py          # 环境选择器，根据环境变量自动加载相应配置
├── base.py             # 基础配置，包含所有环境共享的设置
├── development.py      # 开发环境配置
├── production.py       # 生产环境配置
└── README.md          # 本说明文件
```

## 环境配置

### 环境变量

通过 `DJANGO_ENVIRONMENT` 环境变量控制加载哪个环境的配置：

- `development` - 开发环境（默认）
- `production` - 生产环境

### 开发环境 (development.py)

**特点：**
- 使用SQLite数据库
- DEBUG=True
- 允许所有主机访问
- 使用控制台邮件后端
- 禁用安全限制（如登录限制、验证码）
- 支持Django Debug Toolbar
- Redis密码可选

**使用方法：**
```bash
# 设置环境变量
export DJANGO_ENVIRONMENT=development
# 或者在.env文件中设置
echo "DJANGO_ENVIRONMENT=development" > .env

# 启动开发服务器
python manage.py runserver
```

### 生产环境 (production.py)

**特点：**
- 使用PostgreSQL数据库
- DEBUG=False
- 严格的主机白名单
- SMTP邮件后端
- 启用所有安全功能
- 强制HTTPS
- 严格的CORS配置

**必需环境变量：**
```bash
SECRET_KEY=your-secret-key
ALLOWED_HOSTS=yourdomain.com,www.yourdomain.com
DB_NAME=ops_job
DB_USER=ops_job_user
DB_PASSWORD=your-db-password
DB_HOST=localhost
REDIS_HOST=your-redis-host
REDIS_PASSWORD=your-redis-password
```

## 配置迁移

### 从旧版本迁移

如果你之前使用的是单一的 `settings.py` 文件，现在需要：

1. **备份原配置**：原文件已备份为 `settings_backup.py`
2. **设置环境变量**：在 `.env` 文件或系统环境变量中设置 `DJANGO_ENVIRONMENT`
3. **检查配置**：确认新配置是否符合你的需求

### 自定义配置

如果需要添加新的环境或修改配置：

1. **添加新环境**：在 `settings/` 目录下创建新的配置文件
2. **修改环境选择器**：在 `__init__.py` 中添加新环境的导入逻辑
3. **继承基础配置**：新环境配置应该从 `base.py` 导入基础设置

## 最佳实践

### 1. 环境变量管理

- 使用 `.env` 文件管理本地环境变量
- 生产环境直接设置系统环境变量
- 敏感信息（如密钥、密码）不要提交到版本控制

### 2. 配置验证

生产环境配置包含必需环境变量的验证，如果缺少必需配置会抛出错误。

### 3. 安全考虑

- 生产环境强制使用HTTPS
- 严格的CORS和CSRF配置
- 启用所有Django安全功能
- 使用强密码和密钥

### 4. 性能优化

- 生产环境增加数据库连接池
- 优化缓存配置
- 调整Celery并发数

## 故障排除

### 常见问题

1. **ImportError: No module named 'ops_job.settings'**
   - 确保 `DJANGO_SETTINGS_MODULE` 设置为 `ops_job.settings`

2. **环境变量未生效**
   - 检查 `DJANGO_ENVIRONMENT` 是否正确设置
   - 确认 `.env` 文件位置和格式

3. **生产环境启动失败**
   - 检查所有必需的环境变量是否设置
   - 确认数据库和Redis连接配置

### 调试方法

启动时会打印当前环境信息：
```
🚀 Development environment loaded
📍 DEBUG: True
🗄️  Database: SQLite
🔴 Redis: 127.0.0.1:6379
📧 Email: Console backend
```

## 更新日志

- **v1.0**: 初始版本，支持开发和生产环境隔离
- 原始配置备份在 `settings_backup.py`
