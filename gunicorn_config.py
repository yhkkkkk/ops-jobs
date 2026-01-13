"""
Gunicorn 配置文件
用于生产环境部署，支持多 Workers 配置

使用方法：
    gunicorn -c gunicorn_config.py ops_job.wsgi:application
"""

import multiprocessing
import os

# 服务器配置
bind = os.getenv('GUNICORN_BIND', '0.0.0.0:8000')
backlog = 2048  # 等待连接的最大数量

# Worker 配置
# 建议 Workers 数量 = (CPU 核心数 × 2) + 1
# 可以通过环境变量 GUNICORN_WORKERS 覆盖
cpu_count = multiprocessing.cpu_count()
workers = int(os.getenv('GUNICORN_WORKERS', cpu_count * 2 + 1))

# Worker 类型
# worker_class = 'sync'  # 同步 Worker，适合 I/O 密集型应用
worker_class = 'gevent'  # 异步 Worker，支持更高并发，适合作业等待场景
worker_connections = 1000  # gevent 模式下每个 worker 的并发连接数

# Worker 超时配置
timeout = 120  # Worker 超时时间（秒），超过此时间会被重启
graceful_timeout = 30  # 优雅关闭超时时间（秒）
keepalive = 5  # Keep-alive 连接超时时间（秒）

# 进程管理
max_requests = 1000  # 每个 Worker 处理的最大请求数，达到后重启（防止内存泄漏）
max_requests_jitter = 50  # 随机抖动，避免所有 Worker 同时重启
preload_app = True  # 预加载应用，减少内存占用，但可能导致 Worker 间数据不同步

# 日志配置
accesslog = os.getenv('GUNICORN_ACCESS_LOG', '-')  # '-' 表示输出到 stdout
errorlog = os.getenv('GUNICORN_ERROR_LOG', '-')  # '-' 表示输出到 stderr
loglevel = os.getenv('GUNICORN_LOG_LEVEL', 'info')  # debug, info, warning, error, critical
access_log_format = '%(h)s %(l)s %(u)s %(t)s "%(r)s" %(s)s %(b)s "%(f)s" "%(a)s" %(D)s'  # 包含响应时间（微秒）

# 进程命名
proc_name = 'ops-job-gunicorn'

# 用户和组（生产环境建议使用非 root 用户）
# user = 'www-data'
# group = 'www-data'

# 临时目录
tmp_upload_dir = None  # 临时上传目录

# SSL 配置（如果使用 HTTPS）
# keyfile = '/path/to/keyfile'
# certfile = '/path/to/certfile'

# 性能调优
worker_tmp_dir = '/dev/shm'  # 使用内存文件系统（如果可用），提高性能

# 环境变量
raw_env = [
    f'DJANGO_SETTINGS_MODULE={os.getenv("DJANGO_SETTINGS_MODULE", "ops_job.settings.production")}',
]

# 启动时的钩子函数
def on_starting(server):
    """服务器启动时调用"""
    server.log.info(f"🚀 Starting Gunicorn with {workers} workers")
    server.log.info(f"📍 Binding to {bind}")
    server.log.info(f"💻 CPU cores: {cpu_count}")

def on_reload(server):
    """重载时调用"""
    server.log.info("🔄 Reloading Gunicorn...")

def when_ready(server):
    """服务器就绪时调用"""
    server.log.info("✅ Gunicorn is ready to accept connections")

def worker_int(worker):
    """Worker 收到 INT 信号时调用"""
    worker.log.info("⚠️ Worker received INT signal")

def pre_fork(server, worker):
    """Fork Worker 前调用"""
    pass

def post_fork(server, worker):
    """Fork Worker 后调用"""
    server.log.info(f"👷 Worker spawned (pid: {worker.pid})")

def post_worker_init(worker):
    """Worker 初始化后调用"""
    pass

def worker_abort(worker):
    """Worker 异常退出时调用"""
    worker.log.error("❌ Worker aborted")

def on_exit(server):
    """服务器退出时调用"""
    server.log.info("👋 Gunicorn is shutting down")

