"""
Django development settings for ops_job project.

This file contains settings specific to the development environment.
"""

import os
from .base import *

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = 'django-insecure-6c1-^k)gceo*z@vs-=(!*yb)=7k)6%87!-*wp8vve8x=e=$-m@'

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = True

ALLOWED_HOSTS = ['*']

# Database
# 默认使用环境变量指定的 MySQL；如未提供 DB_HOST 则回退到下方的 SQLite 注释配置
DB_ENGINE = os.getenv('DB_ENGINE', 'dj_db_conn_pool.backends.mysql')
DB_NAME = os.getenv('DB_NAME', 'ops_job')
DB_USER = os.getenv('DB_USER', 'root')
DB_PASSWORD = os.getenv('DB_PASSWORD', '')
DB_HOST = os.getenv('DB_HOST', '')
DB_PORT = os.getenv('DB_PORT', '')

if DB_HOST:
    DATABASES = {
        'default': {
            'ENGINE': DB_ENGINE,
            'NAME': DB_NAME,
            'USER': DB_USER,
            'PASSWORD': DB_PASSWORD,
            'HOST': DB_HOST,
            'PORT': int(DB_PORT) if DB_PORT else '',
            'OPTIONS': {
                'connect_timeout': 10,
            },
            'POOL_OPTIONS': {
                'POOL_SIZE': 16,        # 连接池大小（workers × 2）
                'MAX_OVERFLOW': 16,     # 最大溢出连接数（与POOL_SIZE相等）
                'RECYCLE': 1800,        # 连接回收时间（30分钟，避免连接失效）
                'PRE_PING': True,       # 连接前检查健康状态
            },
            # 测试环境复用同名库，避免自动创建 test_* 库
            'TEST': {
                'NAME': DB_NAME,
            },
        }
    }
else:
    # 开发环境使用SQLite（保留注释以便快速切换）
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': BASE_DIR / 'db.sqlite3',
        }
    }

# redis 配置 - 开发环境
REDIS_HOST = os.getenv('REDIS_HOST', '127.0.0.1')
REDIS_PORT = os.getenv('REDIS_PORT', '6379')
REDIS_PASSWORD = os.getenv('REDIS_PASSWORD', '913689yhk')

# 缓存配置 - 开发环境
CACHES = {
    'default': {
        'BACKEND': 'django_redis.cache.RedisCache',
        'LOCATION': f"redis://:{REDIS_PASSWORD}@{REDIS_HOST}:{REDIS_PORT}/{REDIS_DB_CACHE}"
        if REDIS_PASSWORD else f"redis://{REDIS_HOST}:{REDIS_PORT}/{REDIS_DB_CACHE}",
        'OPTIONS': {
            'CLIENT_CLASS': 'django_redis.client.DefaultClient',
            'CONNECTION_POOL_KWARGS': {
                'max_connections': 50,
                'retry_on_timeout': True,
            },
            # 'COMPRESSOR': 'django_redis.compressors.zlib.ZlibCompressor',
            'IGNORE_EXCEPTIONS': True,
        },
        'KEY_PREFIX': 'ops_job_dev',
        'TIMEOUT': 300,  # 5分钟默认超时
    }
}

# JWT 配置 - 设置SIGNING_KEY
SIMPLE_JWT['SIGNING_KEY'] = SECRET_KEY


# celery 配置 - 开发环境
# CELERY_BROKER_URL = f"redis://:{REDIS_PASSWORD}@{REDIS_HOST}:{REDIS_PORT}/{REDIS_DB_CELERY}" if REDIS_PASSWORD else f"redis://{REDIS_HOST}:{REDIS_PORT}/{REDIS_DB_CELERY}"
# CELERY_RESULT_BACKEND = 'django-db'
# CELERY_ACCEPT_CONTENT = ['json', 'pickle']
# CELERY_TASK_SERIALIZER = 'json'
# CELERY_RESULT_SERIALIZER = 'json'
# CELERY_TIMEZONE = TIME_ZONE
# CELERY_ENABLE_UTC = True
# CELERY_TASK_TRACK_STARTED = True
# CELERY_TASK_TIME_LIMIT = 30 * 60  # 30分钟
# CELERY_WORKER_CONCURRENCY = 1  # 开发环境使用单进程，便于调试
# CELERY_WORKER_MAX_TASKS_PER_CHILD = None  # 禁用工作进程重启，保持持续运行
# CELERY_WORKER_PREFETCH_MULTIPLIER = 1  # 减少预取任务数，避免任务积压
# CELERY_TASK_REJECT_ON_WORKER_LOST = True  # worker丢失时拒绝任务
# CELERY_TASK_ALWAYS_EAGER = False  # 确保异步执行
# CELERY_TASK_EAGER_PROPAGATES = True  # 异常传播
# CELERY_WORKER_DISABLE_RATE_LIMITS = True  # 禁用速率限制
# CELERY_TASK_IGNORE_RESULT = False  # 不忽略结果

# 调试配置
# CELERY_TASK_SOFT_TIME_LIMIT = 60  # 软超时时间
# CELERY_WORKER_SEND_TASK_EVENTS = True  # 发送任务事件
# CELERY_TASK_SEND_SENT_EVENT = True  # 发送任务发送事件

# Celery 5.1 连接丢失处理配置
# CELERY_WORKER_CANCEL_LONG_RUNNING_TASKS_ON_CONNECTION_LOSS = True  # 连接丢失时取消长时间运行的任务
# CELERY_TASK_ACKS_LATE = True  # 任务完成后才确认，避免重复执行

# Celery 连接池配置 - 增强连接稳定性
# CELERY_BROKER_POOL_LIMIT = 20  # 增加连接池大小
# CELERY_BROKER_CONNECTION_TIMEOUT = 60  # 增加连接超时时间
# CELERY_BROKER_HEARTBEAT = 60  # 增加心跳间隔，减少网络开销
# CELERY_BROKER_CONNECTION_RETRY_DELAY = 2.0  # 增加重试延迟
# CELERY_BROKER_CONNECTION_RETRY = True  # 启用连接重试
# CELERY_BROKER_CONNECTION_MAX_RETRIES = 10  # 最大重试次数

# Redis连接参数优化
# CELERY_BROKER_TRANSPORT_OPTIONS = {
#     'socket_keepalive': True,   # 启用TCP keepalive
#     'socket_timeout': 60,       # socket超时时间
#     'socket_connect_timeout': 30,  # 连接超时时间
#     'retry_on_timeout': True,   # 超时时重试
#     'health_check_interval': 30,  # 健康检查间隔
#     'max_connections': 50,      # 最大连接数
# }

# celery 任务路由
# CELERY_TASK_ROUTES = {
#     'executor.tasks.*': {'queue': 'executor'},
#     'scheduler.tasks.*': {'queue': 'scheduler'},
# }

# Celery 日志配置
# CELERY_WORKER_LOG_FORMAT = '[%(asctime)s: %(levelname)s/%(processName)s] %(message)s'
# CELERY_WORKER_TASK_LOG_FORMAT = '[%(asctime)s: %(levelname)s/%(processName)s][%(task_name)s(%(task_id)s)] %(message)s'
# CELERY_TASK_LOG_FORMAT = '[%(asctime)s: %(levelname)s/%(processName)s][%(task_name)s(%(task_id)s)] %(message)s'

# 确保Celery worker输出日志
# CELERY_WORKER_HIJACK_ROOT_LOGGER = False
# CELERY_WORKER_LOG_COLOR = False
# CELERY_WORKER_REDIRECT_STDOUTS_LEVEL = 'INFO'

# Health Check Redis 配置
REDIS_URL = f"redis://:{REDIS_PASSWORD}@{REDIS_HOST}:{REDIS_PORT}/{REDIS_DB_CACHE}" if REDIS_PASSWORD else f"redis://{REDIS_HOST}:{REDIS_PORT}/{REDIS_DB_CACHE}"

# Channels 层配置
CHANNEL_LAYERS = {
    'default': {
        'BACKEND': 'channels_redis.core.RedisChannelLayer',
        'CONFIG': {
            "hosts": [(REDIS_HOST, int(REDIS_PORT))],
            "password": REDIS_PASSWORD if REDIS_PASSWORD else None,
        },
    },
}

# Session配置 - 用于django admin，接口使用jwt
SESSION_ENGINE = 'django.contrib.sessions.backends.db'  # 使用数据库存储session
SESSION_COOKIE_AGE = 60 * 60 * 24  # 24h
SESSION_COOKIE_NAME = 'sessionid'  # Session Cookie名称
SESSION_COOKIE_PATH = '/'  # Cookie路径，根路径
SESSION_COOKIE_DOMAIN = None  # Cookie域名，None表示当前域名
SESSION_COOKIE_HTTPONLY = True  # 防止XSS攻击，JavaScript无法访问
SESSION_COOKIE_SECURE = False  # 开发环境不使用HTTPS
SESSION_COOKIE_SAMESITE = 'Lax'  # 防止CSRF攻击，允许同站请求
SESSION_SAVE_EVERY_REQUEST = False  # 减少数据库写入

# CSRF Cookie配置 - 开发环境
CSRF_COOKIE_NAME = 'csrftoken'  # CSRF Cookie名称
CSRF_COOKIE_PATH = '/'  # Cookie路径
CSRF_COOKIE_DOMAIN = None  # Cookie域名
CSRF_COOKIE_SECURE = False  # 开发环境不使用HTTPS
CSRF_COOKIE_HTTPONLY = False  # CSRF token需要JavaScript访问，不能设为True
CSRF_COOKIE_SAMESITE = 'Lax'  # 与Session保持一致
CSRF_COOKIE_AGE = None  # None表示会话Cookie（浏览器关闭时删除）
CSRF_USE_SESSIONS = False  # 不使用Session存储CSRF token，使用Cookie
# CSRF 配置 - 开发环境信任前端来源
CSRF_TRUSTED_ORIGINS = [
    'http://127.0.0.1:5173',  # Vite开发服务器
    'http://localhost:5173',
]

# CORS 配置 - 开发环境允许所有来源
CORS_ALLOW_ALL_ORIGINS = True
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
    'cache-control',
]

# 开发环境特定配置
EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'  # 邮件输出到控制台

# 静态文件配置
STATIC_ROOT = BASE_DIR / 'staticfiles'
STATICFILES_DIRS = [
    BASE_DIR / 'static',
]

# 媒体文件配置
MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

# 开发环境日志级别调整
LOGGING['handlers']['console']['level'] = 'INFO'
LOGGING['loggers']['django']['level'] = 'INFO'

# 开发环境禁用某些安全检查
AXES_ENABLED = False  # 开发环境禁用登录限制

# 开发环境验证码配置
CAPTCHA_ENABLED = True  # 开发环境禁用验证码

# 开发环境调试工具
if DEBUG:
    try:
        import debug_toolbar
        INSTALLED_APPS.append('debug_toolbar')
        MIDDLEWARE.insert(0, 'debug_toolbar.middleware.DebugToolbarMiddleware')
        
        # Debug Toolbar 配置
        DEBUG_TOOLBAR_CONFIG = {
            'SHOW_TOOLBAR_CALLBACK': lambda request: True,
            'IS_RUNNING_TESTS': False,
        }

        # Debug Toolbar 面板配置
        DEBUG_TOOLBAR_PANELS = [
            'debug_toolbar.panels.timer.TimerPanel',  # 请求计时
            'debug_toolbar.panels.request.RequestPanel',  # 请求信息
            'debug_toolbar.panels.sql.SQLPanel',  # SQL查询
            'debug_toolbar.panels.cache.CachePanel',  # 缓存操作
            'debug_toolbar.panels.profiling.ProfilingPanel',  # 性能分析
        ]
        
        INTERNAL_IPS = [
            '127.0.0.1',
            'localhost',
        ]
    except ImportError:
        pass

print(f"Development environment loaded")
print(f"DEBUG: {DEBUG}")
# 显示实际数据库配置来源
db_target = f"{DB_ENGINE}://{DB_HOST}:{DB_PORT}" if DB_HOST else "sqlite://db.sqlite3"
print(f"Database: {db_target}")
print(f"Redis: {REDIS_HOST}:{REDIS_PORT}")
print(f"Email: Console backend")
