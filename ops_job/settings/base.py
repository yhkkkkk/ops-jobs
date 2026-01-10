"""
Django base settings for ops_job project.

This file contains common settings shared across all environments.
"""

import os
from pathlib import Path
from datetime import timedelta

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent.parent

# Application definition
INSTALLED_APPS = [
    'simpleui',
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',

    # 第三方应用
    'channels',                          # Django Channels (ASGI支持)
    'rest_framework',
    'rest_framework_extensions',
    'rest_framework_simplejwt',
    'rest_framework_simplejwt.token_blacklist',
    'drf_spectacular',
    'corsheaders',                       # cors支持
    'django_json_widget',                # json编辑器
    'admin_auto_filters',                # admin自动完成过滤器
    'axes',                              # 登录安全防护
    'django_filters',                    # drf过滤器
    'guardian',                          # 对象级权限管理
    'django_apscheduler',                # APScheduler 持久化配置
    'django_extensions',                 # django extensions
    'captcha',                           # 验证码
    'health_check',                      # 健康检查
    'health_check.db',                   # 数据库健康检查
    'health_check.contrib.redis',        # redis健康检查

    # 自定义应用
    'apps.hosts',           # 主机管理
    'apps.job_templates',   # 作业模板
    'apps.executor',        # 执行引擎
    'apps.script_templates', # 脚本模板
    'apps.quick_execute',   # 快速执行
    'apps.scheduler',       # 定时任务
    'apps.accounts',        # 用户权限
    'apps.permissions',     # 权限管理
    'apps.dashboard',       # 仪表盘
    'apps.system_config',   # 系统配置
    'apps.agents',          # Agent 管理
]


MIDDLEWARE = [
    'corsheaders.middleware.CorsMiddleware',
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'axes.middleware.AxesMiddleware',     # Axes安全中间件
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'ops_job.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'ops_job.wsgi.application'

# Password validation
AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]

# Internationalization
LANGUAGE_CODE = 'zh-hans'
TIME_ZONE = 'Asia/Shanghai'
USE_I18N = True
USE_TZ = True

# Static files (CSS, JavaScript, Images)
STATIC_URL = 'static/'

# Default primary key field type
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# Django REST Framework 配置
REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'rest_framework_simplejwt.authentication.JWTAuthentication',
        'rest_framework.authentication.SessionAuthentication',  # 临时启用Session认证用于调试
        'rest_framework.authentication.BasicAuthentication',
    ],
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.IsAuthenticated',
    ],
    'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.PageNumberPagination',
    'PAGE_SIZE': 20,
    'DEFAULT_PARSER_CLASSES': (
        'rest_framework.parsers.JSONParser',
        'rest_framework.parsers.FormParser',
        'rest_framework.parsers.MultiPartParser',
    ),
    'DEFAULT_RENDERER_CLASSES': [
        'rest_framework.renderers.JSONRenderer',
        'rest_framework.renderers.BrowsableAPIRenderer',
    ],
    'DEFAULT_THROTTLE_CLASSES': [
        'rest_framework.throttling.AnonRateThrottle',
        'rest_framework.throttling.UserRateThrottle'
    ],
    'DEFAULT_THROTTLE_RATES': {
        'anon': '100/hour',
        'user': '1000/hour'
    },
    'DEFAULT_SCHEMA_CLASS': 'drf_spectacular.openapi.AutoSchema',
}

# DRF Extensions 配置
REST_FRAMEWORK_EXTENSIONS = {
    'DEFAULT_CACHE_RESPONSE_TIMEOUT': 60 * 5,  # 5分钟缓存
    'DEFAULT_CACHE_ERRORS': False,
    'DEFAULT_USE_CACHE': 'default',
    # 缓存键构建方式 - 使用自定义的键构造器，包含用户上下文信息
    'DEFAULT_KEY_CONSTRUCTOR_MEMOIZE_FOR_REQUEST': True,
    'DEFAULT_KEY_CONSTRUCTOR': 'utils.cache_key_constructors.CustomKeyConstructor',
    # 'DEFAULT_KEY_CONSTRUCTOR': 'rest_framework_extensions.key_constructor.constructors.DefaultKeyConstructor',
    'DEFAULT_OBJECT_CACHE_KEY_FUNC': 'rest_framework_extensions.utils.default_object_cache_key_func',
    'DEFAULT_LIST_CACHE_KEY_FUNC': 'rest_framework_extensions.utils.default_list_cache_key_func',
}

# redis 数据库索引配置
REDIS_DB_CACHE = 0  # 用于一般缓存
REDIS_DB_SESSION = 1  # 用于会话存储
REDIS_DB_CELERY = 2  # 用于 Celery
REDIS_DB_REALTIME = 3  # 用于实时日志 (Redis Stream)

# 控制面 URL（用于生成 Agent-Server 配置）
CONTROL_PLANE_URL = os.getenv('CONTROL_PLANE_URL', '')

# JWT 配置 (SECRET_KEY 将在具体环境中设置)
SIMPLE_JWT = {
    'ACCESS_TOKEN_LIFETIME': timedelta(hours=4),
    'REFRESH_TOKEN_LIFETIME': timedelta(days=7),
    'ROTATE_REFRESH_TOKENS': True,
    'BLACKLIST_AFTER_ROTATION': True,
    'UPDATE_LAST_LOGIN': True,

    'ALGORITHM': 'HS256',
    'VERIFYING_KEY': None,
    'AUDIENCE': None,
    'ISSUER': None,
    'JWK_URL': None,
    'LEEWAY': 0,

    'AUTH_HEADER_TYPES': ('Bearer',),
    'AUTH_HEADER_NAME': 'HTTP_AUTHORIZATION',
    'USER_ID_FIELD': 'id',
    'USER_ID_CLAIM': 'user_id',
    'USER_AUTHENTICATION_RULE': 'rest_framework_simplejwt.authentication.default_user_authentication_rule',

    'AUTH_TOKEN_CLASSES': ('rest_framework_simplejwt.tokens.AccessToken',),
    'TOKEN_TYPE_CLAIM': 'token_type',
    'TOKEN_USER_CLASS': 'rest_framework_simplejwt.models.TokenUser',

    'JTI_CLAIM': 'jti',

    'SLIDING_TOKEN_REFRESH_EXP_CLAIM': 'refresh_exp',
    'SLIDING_TOKEN_LIFETIME': timedelta(hours=4),
    'SLIDING_TOKEN_REFRESH_LIFETIME': timedelta(days=7),
}

# drf_spectacular 配置
SPECTACULAR_SETTINGS = {
    'TITLE': 'OPS Job API',
    'DESCRIPTION': '运维作业平台 API 文档',
    'VERSION': '1.0.0',
    'SERVE_INCLUDE_SCHEMA': False,
    'COMPONENT_SPLIT_REQUEST': True,
    'SCHEMA_PATH_PREFIX': '/api/',
    'SWAGGER_UI_SETTINGS': {
        'deepLinking': True,
        'persistAuthorization': True,
        'displayOperationId': True,
    },
    'PREPROCESSING_HOOKS': [
        'drf_spectacular.hooks.preprocess_exclude_path_format',
    ],
    'POSTPROCESSING_HOOKS': [
        'drf_spectacular.hooks.postprocess_schema_enums',
    ],
    # 排除sse接口
    'SCHEMA_PATH_PREFIX_TRIM': True,
    'SCHEMA_PATH_PREFIX_INSERT': '/api/',
    'EXCLUDE_PATH_FORMAT': [
        '/api/realtime/sse/*',  # 排除sse接口
    ],
}

# django-axes 安全配置 + Guardian 对象级权限
AUTHENTICATION_BACKENDS = [
    'axes.backends.AxesStandaloneBackend',  # Axes认证后端
    'django.contrib.auth.backends.ModelBackend',  # Django默认认证后端
    'guardian.backends.ObjectPermissionBackend',  # Guardian对象级权限后端
]

# LDAP 认证配置
LDAP_ENABLED = os.getenv('LDAP_ENABLED', 'False').lower() == 'true'

if LDAP_ENABLED:
    import ldap
    from django_auth_ldap.config import LDAPSearch, GroupOfUniqueNamesType

    # 添加 LDAP backend 到认证后端列表
    axes_backend_index = AUTHENTICATION_BACKENDS.index('axes.backends.AxesStandaloneBackend')
    AUTHENTICATION_BACKENDS.insert(axes_backend_index + 1, 'django_auth_ldap.backend.LDAPBackend')
    
    # LDAP 服务器配置
    AUTH_LDAP_SERVER_URI = os.getenv('LDAP_SERVER_URI', 'ldap://localhost:389')
    
    # LDAP 绑定配置（用于搜索用户）
    AUTH_LDAP_BIND_DN = os.getenv('LDAP_BIND_DN', '')
    AUTH_LDAP_BIND_PASSWORD = os.getenv('LDAP_BIND_PASSWORD', '')
    
    # LDAP 基础配置
    AUTH_LDAP_USER_SEARCH = LDAPSearch(
        os.getenv('LDAP_USER_SEARCH_BASE', 'ou=users,dc=example,dc=com'),
        ldap.SCOPE_SUBTREE,
        os.getenv('LDAP_USER_SEARCH_FILTER', '(uid=%(user)s)')
    )
    
    # 用户DN模板（如果使用固定模板而不是搜索）
    # AUTH_LDAP_USER_DN_TEMPLATE = os.getenv('LDAP_USER_DN_TEMPLATE', 'uid=%(user)s,ou=users,dc=example,dc=com')
    
    # 用户属性映射
    AUTH_LDAP_USER_ATTR_MAP = {
        'first_name': os.getenv('LDAP_ATTR_FIRST_NAME', 'givenName'),
        'last_name': os.getenv('LDAP_ATTR_LAST_NAME', 'sn'),
        'email': os.getenv('LDAP_ATTR_EMAIL', 'mail'),
    }
    
    # LDAP 连接选项
    AUTH_LDAP_CONNECTION_OPTIONS = {
        ldap.OPT_REFERRALS: 0,
        ldap.OPT_PROTOCOL_VERSION: 3,
    }
    
    # 如果启用 TLS
    if os.getenv('LDAP_START_TLS', 'False').lower() == 'true':
        AUTH_LDAP_START_TLS = True
    
    # 组配置（可选）
    if os.getenv('LDAP_REQUIRE_GROUP', ''):
        AUTH_LDAP_REQUIRE_GROUP = os.getenv('LDAP_REQUIRE_GROUP')
        AUTH_LDAP_GROUP_SEARCH = LDAPSearch(
            os.getenv('LDAP_GROUP_SEARCH_BASE', 'ou=groups,dc=example,dc=com'),
            ldap.SCOPE_SUBTREE,
            os.getenv('LDAP_GROUP_SEARCH_FILTER', '(objectClass=groupOfNames)')
        )
        AUTH_LDAP_GROUP_TYPE = GroupOfUniqueNamesType()
        AUTH_LDAP_USER_FLAGS_BY_GROUP = {
            'is_active': os.getenv('LDAP_GROUP_ACTIVE', ''),
            'is_staff': os.getenv('LDAP_GROUP_STAFF', ''),
            'is_superuser': os.getenv('LDAP_GROUP_SUPERUSER', ''),
        }
    
    # 用户同步配置
    # 如果设置为True，则Django将为用户创建本地账户，即使用户之前未在Django中创建过账户
    AUTH_LDAP_ALWAYS_UPDATE_USER = True  # 每次登录时同步用户信息
    AUTH_LDAP_USER_ATTRLIST_BY_GROUP = {}
    
    # 缓存配置（可选，提升性能）
    # AUTH_LDAP_CACHE_TIMEOUT = 3600


# 双因子认证（2FA）配置
TWO_FACTOR_ENABLED = os.getenv('TWO_FACTOR_ENABLED', 'False').lower() == 'true'

# 双因子认证（2FA/TOTP）配置
if TWO_FACTOR_ENABLED:
    # 添加 django-otp 相关应用
    INSTALLED_APPS.extend([
        'django_otp',
        'django_otp.plugins.otp_totp',      # TOTP设备支持
        'django_otp.plugins.otp_static',    # 静态备份令牌支持
    ])

    auth_middleware_index = MIDDLEWARE.index('django.contrib.auth.middleware.AuthenticationMiddleware')
    MIDDLEWARE.insert(auth_middleware_index + 1, 'django_otp.middleware.OTPMiddleware')

    # TOTP配置
    OTP_TOTP_ISSUER = os.getenv('OTP_TOTP_ISSUER', 'Ops Job Platform')  # 在验证器APP中显示的名称
    
    # TOTP设备配置
    OTP_TOTP_THROTTLE_FACTOR = int(os.getenv('OTP_TOTP_THROTTLE_FACTOR', '1'))  # 节流因子，防止暴力破解
    
    # 静态备份令牌配置（可选，用于紧急情况）
    # 如果用户丢失了TOTP设备，可以使用备份令牌登录
    OTP_STATIC_THROTTLE_FACTOR = int(os.getenv('OTP_STATIC_THROTTLE_FACTOR', '1'))
    
    # 是否要求所有用户启用2FA（False表示可选）
    TWO_FACTOR_REQUIRED = os.getenv('TWO_FACTOR_REQUIRED', 'False').lower() == 'true'
    
    # 2FA验证超时时间（秒），0表示不超时
    TWO_FACTOR_LOGIN_TIMEOUT = int(os.getenv('TWO_FACTOR_LOGIN_TIMEOUT', '600'))  # 默认10分钟

AXES_ENABLED = True
AXES_FAILURE_LIMIT = 5  # 允许的最大失败次数
AXES_LOCK_OUT_AT_FAILURE = True  # 达到限制后锁定
AXES_COOLOFF_TIME = timedelta(minutes=30)  # 锁定时间
AXES_RESET_ON_SUCCESS = True  # 登录成功后重置失败计数
AXES_DISABLE_ACCESS_LOG = False
AXES_ENABLE_ACCESS_FAILURE_LOG = True  # 记录失败访问
# 前后端分离相关配置
AXES_LOCKOUT_PARAMETERS = ["ip_address", ["username", "user_agent"]]  # 锁定字段
AXES_LOCKOUT_CALLABLE = 'utils.responses.account_locked'  # 自定义锁定响应处理
AXES_USERNAME_FORM_FIELD = 'username'  # 用户名字段

# Guardian 配置
GUARDIAN_RAISE_403 = True  # 当权限检查失败时抛出 PermissionDenied
ANONYMOUS_USER_NAME = None  # 禁用匿名用户功能
GUARDIAN_AUTO_PREFETCH = True  # 启用权限预加载以提升性能

# SimpleUI 配置
SIMPLEUI_HOME_TITLE = "运维作业管理后台"
SIMPLEUI_HOME_ICON = "fas fa-server"
SIMPLEUI_LOGO = "https://cdn-icons-png.flaticon.com/512/1087/1087815.png"  # 齿轮图标
# 隐藏右侧SimpleUI广告链接
SIMPLEUI_HOME_INFO = False
# 默认主题
SIMPLEUI_DEFAULT_THEME = 'element.css'

# SSH 连接配置
SSH_TIMEOUT = 30
SSH_CONNECT_TIMEOUT = 10
SSH_MAX_RETRIES = 3

# Health Check 配置
HEALTH_CHECK = {
    'DISK_USAGE_MAX': 80,  # 磁盘使用率阈值
    'MEMORY_MIN': 100,     # 最小可用内存(MB)
}

# Health Check Celery 配置
HEALTHCHECK_CELERY_TIMEOUT = 5.0   # Celery健康检查超时时间(秒)
HEALTHCHECK_CELERY_RESULT_TIMEOUT = 5.0
HEALTHCHECK_CELERY_QUEUE_TIMEOUT = 5.0

# 验证码配置
CAPTCHA_ENABLED = os.getenv('CAPTCHA_ENABLED', 'False').lower() == 'true'

# 验证码和2FA互斥检查：两者不能同时启用
if CAPTCHA_ENABLED and TWO_FACTOR_ENABLED:
    raise ValueError(
        "CAPTCHA_ENABLED 和 TWO_FACTOR_ENABLED 不能同时启用。"
        "请只启用其中一个：验证码（CAPTCHA）或双因子认证（2FA）。"
    )
CAPTCHA_IMAGE_SIZE = (120, 40)  # 验证码图片大小
CAPTCHA_LENGTH = 4  # 验证码长度
CAPTCHA_TIMEOUT = 5  # 验证码超时时间（分钟）
CAPTCHA_FONT_SIZE = 28  # 字体大小
CAPTCHA_BACKGROUND_COLOR = '#ffffff'  # 背景颜色
CAPTCHA_FOREGROUND_COLOR = '#333333'  # 前景颜色
CAPTCHA_FILTER_FUNCTIONS = (
    'captcha.helpers.post_smooth',
)
# 验证码字符集（只使用数字和大写字母，避免混淆）
CAPTCHA_CHALLENGE_FUNCT = 'captcha.helpers.random_char_challenge'
CAPTCHA_MATH_CHALLENGE_OPERATOR = '+'  # 数学验证码操作符

# 日志配置
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '%(levelname)s %(asctime)s %(module)s %(process)d %(thread)d %(message)s',
            'datefmt': '%Y-%m-%d %H:%M:%S',
        },
        'simple': {
            'format': '%(levelname)s %(message)s',
        },
        'standard': {
            'format': '[%(asctime)s] %(levelname)s [%(name)s:%(lineno)s] %(message)s',
            'datefmt': '%Y-%m-%d %H:%M:%S'
        },
        'json': {
            '()': 'pythonjsonlogger.jsonlogger.JsonFormatter',
            'format': '%(asctime)s %(levelname)s %(name)s %(lineno)d %(message)s',
            'datefmt': '%Y-%m-%d %H:%M:%S',
        },
    },
    'filters': {
        'require_debug_false': {
            '()': 'django.utils.log.RequireDebugFalse',
        },
        'require_debug_true': {
            '()': 'django.utils.log.RequireDebugTrue',
        },
    },
    'handlers': {
        'console': {
            'level': 'DEBUG',
            'class': 'logging.StreamHandler',
            'formatter': 'verbose',
        },
        'file': {
            'level': 'INFO',
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': BASE_DIR / 'logs' / 'django.log',
            'maxBytes': 1024*1024*50,  # 50MB
            'backupCount': 5,
            'formatter': 'standard',
            'encoding': 'utf-8',
        },
        'error_file': {
            'level': 'ERROR',
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': BASE_DIR / 'logs' / 'error.log',
            'maxBytes': 1024*1024*50,  # 50MB
            'backupCount': 5,
            'formatter': 'verbose',
            'encoding': 'utf-8',
        },
        'security_file': {
            'level': 'INFO',
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': BASE_DIR / 'logs' / 'security.log',
            'maxBytes': 1024*1024*50,  # 50MB
            'backupCount': 10,
            'formatter': 'json',
            'encoding': 'utf-8',
        },
        'axes_file': {
            'level': 'INFO',
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': BASE_DIR / 'logs' / 'axes.log',
            'maxBytes': 1024*1024*20,  # 20MB
            'backupCount': 5,
            'formatter': 'standard',
            'encoding': 'utf-8',
        },
        'ssh_file': {
            'level': 'INFO',
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': BASE_DIR / 'logs' / 'ssh.log',
            'maxBytes': 1024*1024*30,  # 30MB
            'backupCount': 5,
            'formatter': 'standard',
            'encoding': 'utf-8',
        },
        'mail_admins': {
            'level': 'ERROR',
            'filters': ['require_debug_false'],
            'class': 'django.utils.log.AdminEmailHandler',
            'formatter': 'verbose',
        },
    },
    'root': {
        'level': 'DEBUG',
        'handlers': ['console', 'file'],
    },
    'loggers': {
        'django': {
            'handlers': ['console', 'file'],
            'level': 'INFO',
            'propagate': False,
        },
        'django.request': {
            'handlers': ['console', 'error_file', 'mail_admins'],
            'level': 'ERROR',
            'propagate': False,
        },
        'django.security': {
            'handlers': ['security_file'],
            'level': 'INFO',
            'propagate': False,
        },
        'axes': {
            'handlers': ['axes_file', 'security_file'],
            'level': 'INFO',
            'propagate': False,
        },
        'hosts.ssh_manager': {
            'handlers': ['ssh_file'],
            'level': 'INFO',
            'propagate': False,
        },
        'scheduler.tasks': {
            'handlers': ['file'],
            'level': 'INFO',
            'propagate': False,
        },
        'accounts.models': {
            'handlers': ['security_file'],
            'level': 'INFO',
            'propagate': False,
        },
        'permissions.services': {
            'handlers': ['security_file'],
            'level': 'INFO',
            'propagate': False,
        },
        # 应用级别的日志记录器
        'hosts': {
            'handlers': ['file'],
            'level': 'INFO',
            'propagate': True,
        },
        'job_templates': {
            'handlers': ['file'],
            'level': 'INFO',
            'propagate': True,
        },
        'executor': {
            'handlers': ['console', 'file'],
            'level': 'INFO',
            'propagate': True,
        },
        'scheduler': {
            'handlers': ['file'],
            'level': 'INFO',
            'propagate': True,
        },
        'script_templates': {
            'handlers': ['file'],
            'level': 'INFO',
            'propagate': True,
        },
        'quick_execute': {
            'handlers': ['file'],
            'level': 'INFO',
            'propagate': True,
        },
        'accounts': {
            'handlers': ['security_file'],
            'level': 'INFO',
            'propagate': True,
        },
        'permissions': {
            'handlers': ['security_file'],
            'level': 'INFO',
            'propagate': True,
        },
        'dashboard': {
            'handlers': ['file'],
            'level': 'INFO',
            'propagate': True,
        },
    },
}

# ASGI 应用配置
# Channels 层配置将在具体环境配置中设置 (development.py, production.py)
ASGI_APPLICATION = 'ops_job.asgi.application'
