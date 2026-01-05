"""
Django production settings for ops_job project.

This file contains settings specific to the production environment.
"""

import os
from .base import *

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = os.getenv('SECRET_KEY')
if not SECRET_KEY:
    raise ValueError("SECRET_KEY environment variable is required in production")

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = False

# 生产环境必须明确指定允许的主机
ALLOWED_HOSTS = os.getenv('ALLOWED_HOSTS', '').split(',')
if not ALLOWED_HOSTS or ALLOWED_HOSTS == ['']:
    raise ValueError("ALLOWED_HOSTS environment variable is required in production")

# Database - 生产环境使用PostgreSQL
DATABASES = {
    'default': {
        'ENGINE': 'dj_db_conn_pool.backends.postgresql',
        'NAME': os.getenv('DB_NAME'),
        'USER': os.getenv('DB_USER'),
        'PASSWORD': os.getenv('DB_PASSWORD'),
        'HOST': os.getenv('DB_HOST', 'localhost'),
        'PORT': os.getenv('DB_PORT', '5432'),
        'OPTIONS': {
            'connect_timeout': 10,
        },
        'POOL_OPTIONS': {
            'POOL_SIZE': 16,        # 连接池大小（workers × 2）
            'MAX_OVERFLOW': 16,     # 最大溢出连接数（与POOL_SIZE相等）
            'RECYCLE': 1800,        # 连接回收时间（30分钟，避免连接失效）
            'PRE_PING': True,       # 连接前检查健康状态
        }
    }
}

# 验证数据库配置
required_db_vars = ['DB_NAME', 'DB_USER', 'DB_PASSWORD']
for var in required_db_vars:
    if not os.getenv(var):
        raise ValueError(f"{var} environment variable is required in production")

# redis 配置 - 生产环境
REDIS_HOST = os.getenv('REDIS_HOST')
REDIS_PORT = os.getenv('REDIS_PORT', '6379')
REDIS_PASSWORD = os.getenv('REDIS_PASSWORD')

if not REDIS_HOST:
    raise ValueError("REDIS_HOST environment variable is required in production")
if not REDIS_PASSWORD:
    raise ValueError("REDIS_PASSWORD environment variable is required in production")

# 缓存配置 - 生产环境
CACHES = {
    'default': {
        'BACKEND': 'django_redis.cache.RedisCache',
        'LOCATION': f"redis://:{REDIS_PASSWORD}@{REDIS_HOST}:{REDIS_PORT}/{REDIS_DB_CACHE}",
        'OPTIONS': {
            'CLIENT_CLASS': 'django_redis.client.DefaultClient',
            'CONNECTION_POOL_KWARGS': {
                'max_connections': 100,  # 生产环境增加连接数
                'retry_on_timeout': True,
                'socket_keepalive': True,  # 启用 TCP keepalive
                'socket_keepalive_options': {},
                'health_check_interval': 30,  # 健康检查间隔
            },
            'COMPRESSOR': 'django_redis.compressors.zlib.ZlibCompressor',  # 压缩大值
            'IGNORE_EXCEPTIONS': False,  # 生产环境不忽略异常
        },
        'KEY_PREFIX': 'ops_job_prod',
        'TIMEOUT': 300,  # 5分钟默认超时
    }
}

# REDIS_DB_CACHE 已在 base.py 中定义，通过 from .base import * 已导入

# JWT 配置 - 设置SIGNING_KEY
SIMPLE_JWT['SIGNING_KEY'] = SECRET_KEY

# celery 配置 - 生产环境
CELERY_BROKER_URL = f"redis://:{REDIS_PASSWORD}@{REDIS_HOST}:{REDIS_PORT}/{REDIS_DB_CELERY}"
CELERY_RESULT_BACKEND = 'django-db'
CELERY_ACCEPT_CONTENT = ['json', 'pickle']
CELERY_TASK_SERIALIZER = 'json'
CELERY_RESULT_SERIALIZER = 'json'
CELERY_TIMEZONE = TIME_ZONE
CELERY_ENABLE_UTC = True
CELERY_TASK_TRACK_STARTED = True
CELERY_TASK_TIME_LIMIT = 30 * 60  # 30分钟
CELERY_WORKER_CONCURRENCY = 8  # 生产环境增加并发数
CELERY_WORKER_MAX_TASKS_PER_CHILD = 0  # 禁用工作进程重启，保持持续运行
CELERY_WORKER_PREFETCH_MULTIPLIER = 4  # 预取任务数
CELERY_TASK_REJECT_ON_WORKER_LOST = True  # worker丢失时拒绝任务
CELERY_TASK_ALWAYS_EAGER = False  # 确保异步执行
CELERY_TASK_EAGER_PROPAGATES = True  # 异常传播
CELERY_WORKER_DISABLE_RATE_LIMITS = False  # 生产环境启用速率限制
CELERY_TASK_IGNORE_RESULT = False  # 不忽略结果

# Celery 5.1 连接稳定性配置
CELERY_BROKER_CONNECTION_RETRY_ON_STARTUP = True
CELERY_BROKER_CONNECTION_RETRY = True
CELERY_BROKER_CONNECTION_MAX_RETRIES = 10
CELERY_TASK_SEND_SENT_EVENT = True  # 发送任务发送事件
CELERY_WORKER_SEND_TASK_EVENTS = True  # 发送任务事件

# Celery 5.1 连接丢失处理配置
CELERY_WORKER_CANCEL_LONG_RUNNING_TASKS_ON_CONNECTION_LOSS = True  # 连接丢失时取消长时间运行的任务
CELERY_TASK_ACKS_LATE = True  # 任务完成后才确认，避免重复执行

# Celery 连接池配置 - 生产环境增强连接稳定性
CELERY_BROKER_POOL_LIMIT = 50  # 生产环境更大的连接池
CELERY_BROKER_CONNECTION_TIMEOUT = 60  # 增加连接超时时间
CELERY_BROKER_HEARTBEAT = 60  # 增加心跳间隔，减少网络开销

# Redis连接参数优化
CELERY_BROKER_TRANSPORT_OPTIONS = {
    'socket_keepalive': True,   # 启用TCP keepalive
    'socket_timeout': 60,       # socket超时时间
    'socket_connect_timeout': 30,  # 连接超时时间
    'retry_on_timeout': True,   # 超时时重试
    'health_check_interval': 30,  # 健康检查间隔
    'max_connections': 100,     # 生产环境更多连接数
}

# celery 任务路由
CELERY_TASK_ROUTES = {
    'executor.tasks.*': {'queue': 'executor'},
    'scheduler.tasks.*': {'queue': 'scheduler'},
}

# Health Check Redis 配置
REDIS_URL = f"redis://:{REDIS_PASSWORD}@{REDIS_HOST}:{REDIS_PORT}/{REDIS_DB_CACHE}"

# 使用Redis作为Session后端
SESSION_ENGINE = "django.contrib.sessions.backends.cache"
SESSION_CACHE_ALIAS = "default"
SESSION_COOKIE_AGE = 60 * 60 * 8  # 8h
SESSION_COOKIE_NAME = 'sessionid'  # Session Cookie名称
SESSION_COOKIE_PATH = '/'  # Cookie路径，根路径
SESSION_COOKIE_DOMAIN = None  # Cookie域名，None表示当前域名（可通过环境变量设置，如 '.example.com'）
SESSION_COOKIE_HTTPONLY = True  # 防止XSS攻击，JavaScript无法访问
SESSION_COOKIE_SECURE = True  # 生产环境使用HTTPS
SESSION_COOKIE_SAMESITE = 'Strict'  # 防止CSRF攻击，严格模式
SESSION_SAVE_EVERY_REQUEST = False  # 减少缓存写入

# CORS 配置 - 生产环境限制来源
CORS_ALLOW_ALL_ORIGINS = False
CORS_ALLOWED_ORIGINS = os.getenv('CORS_ALLOWED_ORIGINS', '').split(',')
CORS_ALLOW_CREDENTIALS = True
CORS_ALLOW_METHODS = [
    'DELETE',
    'GET',
    'OPTIONS',
    'PATCH',
    'POST',
    'PUT',
]
CORS_ALLOW_HEADERS = [
    'accept',
    'accept-encoding',
    'authorization',
    'content-type',
    'dnt',
    'origin',
    'user-agent',
    'x-csrftoken',
    'x-requested-with',
]

# 安全配置
SECURE_BROWSER_XSS_FILTER = True
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True
SECURE_HSTS_SECONDS = 31536000  # 1年
SECURE_REFERRER_POLICY = 'strict-origin-when-cross-origin'
# 允许通过环境变量关闭强制https（默认开启）；纯http部署需要设置 SECURE_SSL_REDIRECT=false
SECURE_SSL_REDIRECT = os.getenv('SECURE_SSL_REDIRECT', 'True').lower() == 'true'
USE_TZ = True

# CSRF 配置
CSRF_COOKIE_NAME = 'csrftoken'  # CSRF Cookie名称
CSRF_COOKIE_PATH = '/'  # Cookie路径
CSRF_COOKIE_DOMAIN = None  # Cookie域名，None表示当前域名（可通过环境变量设置）
CSRF_COOKIE_SECURE = True  # 生产环境使用HTTPS
CSRF_COOKIE_HTTPONLY = False  # CSRF token需要JavaScript访问，不能设为True
CSRF_COOKIE_SAMESITE = 'Strict'  # 与Session保持一致，严格模式
CSRF_COOKIE_AGE = None  # None表示会话Cookie（浏览器关闭时删除）
CSRF_USE_SESSIONS = False  # 不使用Session存储CSRF token，使用Cookie
CSRF_TRUSTED_ORIGINS = os.getenv('CSRF_TRUSTED_ORIGINS', '').split(',')

# 静态文件配置
STATIC_ROOT = os.getenv('STATIC_ROOT', BASE_DIR / 'staticfiles')
STATICFILES_STORAGE = 'django.contrib.staticfiles.storage.ManifestStaticFilesStorage'

# 媒体文件配置
MEDIA_URL = '/media/'
MEDIA_ROOT = os.getenv('MEDIA_ROOT', BASE_DIR / 'media')

# 邮件配置
EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
EMAIL_HOST = os.getenv('EMAIL_HOST')
EMAIL_PORT = int(os.getenv('EMAIL_PORT', '587'))
EMAIL_USE_TLS = os.getenv('EMAIL_USE_TLS', 'True').lower() == 'true'
EMAIL_HOST_USER = os.getenv('EMAIL_HOST_USER')
EMAIL_HOST_PASSWORD = os.getenv('EMAIL_HOST_PASSWORD')
DEFAULT_FROM_EMAIL = os.getenv('DEFAULT_FROM_EMAIL', EMAIL_HOST_USER)

# 生产环境日志配置调整
LOGGING['handlers']['console']['level'] = 'WARNING'
LOGGING['loggers']['django']['level'] = 'WARNING'
LOGGING['root']['level'] = 'WARNING'

# 启用所有安全功能
AXES_ENABLED = True
CAPTCHA_ENABLED = True

# 生产环境性能优化
CONN_MAX_AGE = 600  # 数据库连接池

# 限流配置加强
REST_FRAMEWORK['DEFAULT_THROTTLE_RATES'] = {
    'anon': '50/hour',    # 匿名用户限制更严格
    'user': '500/hour'    # 认证用户限制更严格
}

# 管理员邮件配置
ADMINS = [
    ('Admin', os.getenv('ADMIN_EMAIL', '')),
]
MANAGERS = ADMINS

# 服务器错误邮件通知
SERVER_EMAIL = os.getenv('SERVER_EMAIL', DEFAULT_FROM_EMAIL)

print(f"Production environment loaded")
print(f"DEBUG: {DEBUG}")
print(f"Database: PostgreSQL")
print(f"Redis: {REDIS_HOST}:{REDIS_PORT}")
print(f"Email: SMTP backend")
print(f"Security features enabled")
