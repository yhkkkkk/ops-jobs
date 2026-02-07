"""
URL configuration for ops_job project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/4.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path, include
from django.views.generic import RedirectView
from drf_spectacular.views import (
    SpectacularAPIView,
    SpectacularSwaggerView,
    SpectacularRedocView,
)
from django.conf import settings

urlpatterns = [
    path('admin/', admin.site.urls),

    # 路由
    path('api/dashboard/', include('apps.dashboard.urls')),  # 仪表盘接口
    path('api/hosts/', include('apps.hosts.urls')),
    path('api/agents/', include('apps.agents.urls')),
    path('api/auth/', include('apps.accounts.urls')),
    path('api/job-templates/', include('apps.job_templates.urls')),
    path('api/quick/', include('apps.quick_execute.urls')),
    path('api/scheduler/', include('apps.scheduler.urls')),  # 作业调度接口
    path('api/executor/', include('apps.executor.urls')),  # 统一执行记录接口
    path('api/script-templates/', include('apps.script_templates.urls')),  # 脚本模板接口
    path('api/permissions/', include('apps.permissions.urls')),  # 权限管理接口
    path('api/system/', include('apps.system_config.urls')),  # 系统配置接口
    path('api/realtime/', include('utils.urls')),  # 实时日志SSE接口
    path('api/captcha/', include('utils.captcha_urls')),  # 验证码接口
    path('health/', include('health_check.urls')),  # 健康检查接口

    # 接口文档
    path('docs/schema/', SpectacularAPIView.as_view(), name='schema'),
    path('docs/swagger/', SpectacularSwaggerView.as_view(url_name='schema'), name='swagger-ui'),
    path('docs/redoc/', SpectacularRedocView.as_view(url_name='schema'), name='redoc'),
]


if settings.DEBUG:
    import debug_toolbar
    urlpatterns += [
        # path('', RedirectView.as_view(url='/admin/', permanent=False)),
        path('__debug__/', include(debug_toolbar.urls)),
    ]
