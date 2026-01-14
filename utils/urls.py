"""
工具类URL配置 - SSE实时日志接口
"""
from django.urls import path
from django.views.generic import TemplateView
from .sse_views import JobLogsSSEView, JobStatusSSEView, JobCombinedSSEView
from .agent_install_sse_views import AgentInstallProgressSSEView, AgentUninstallProgressSSEView

app_name = 'utils'

urlpatterns = [
    # SSE实时日志接口
    path('sse/logs/<str:execution_id>/', JobLogsSSEView.as_view(), name='job_logs_sse'),
    path('sse/status/<str:execution_id>/', JobStatusSSEView.as_view(), name='job_status_sse'),
    path('sse/combined/<str:execution_id>/', JobCombinedSSEView.as_view(), name='job_combined_sse'),
    # Agent安装进度SSE接口
    path('sse/agent-install/<str:install_task_id>/', AgentInstallProgressSSEView.as_view(), name='agent_install_progress_sse'),
    # Agent卸载进度SSE接口
    path('sse/agent-uninstall/<str:uninstall_task_id>/', AgentUninstallProgressSSEView.as_view(), name='agent_uninstall_progress_sse'),
]
