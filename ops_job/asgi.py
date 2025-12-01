"""
ASGI config for ops_job project.

It exposes the ASGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/4.2/howto/deployment/asgi/
"""

import os
from django.core.asgi import get_asgi_application
from channels.routing import ProtocolTypeRouter, URLRouter
from channels.auth import AuthMiddlewareStack

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'ops_job.settings')

# 初始化 Django ASGI 应用
django_asgi_app = get_asgi_application()

# ASGI 应用配置
application = ProtocolTypeRouter({
    # HTTP 请求使用 Django 的 ASGI 应用
    "http": django_asgi_app,
    # WebSocket 连接（如果需要的话）
    # "websocket": AuthMiddlewareStack(
    #     URLRouter([
    #         # WebSocket URL 路由
    #     ])
    # ),
})
