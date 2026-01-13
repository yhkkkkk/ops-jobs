"""
WSGI config for ops_job project.

It exposes the WSGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/4.2/howto/deployment/wsgi/
"""

import os

from django.core.wsgi import get_wsgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'ops_job.settings')

application = get_wsgi_application()

# 解决 gevent + django 数据库连接池的线程检查问题
# 当使用 gevent worker 时，greenlet 切换会导致线程ID变化
# 需要允许跨 greenlet 共享数据库连接
def _enable_db_thread_sharing():
    """启用数据库连接的线程共享，兼容 gevent"""
    try:
        from django.db import connections
        for alias in connections:
            connection = connections[alias]
            connection.inc_thread_sharing()
    except Exception:
        pass  # 静默忽略，可能在非 gevent 环境

_enable_db_thread_sharing()
