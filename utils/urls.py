"""
工具类URL配置 - SSE实时日志接口
"""
from django.urls import path
from django.views.generic import TemplateView
from .sse_views import JobLogsSSEView, JobStatusSSEView, JobCombinedSSEView

app_name = 'utils'

urlpatterns = [
    # SSE实时日志接口
    path('sse/logs/<str:execution_id>/', JobLogsSSEView.as_view(), name='job_logs_sse'),
    path('sse/status/<str:execution_id>/', JobStatusSSEView.as_view(), name='job_status_sse'),
    path('sse/combined/<str:execution_id>/', JobCombinedSSEView.as_view(), name='job_combined_sse'),
]
