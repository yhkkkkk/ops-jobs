"""
快速执行URL配置
"""
from django.urls import path
from . import views

app_name = 'quick_execute'

urlpatterns = [
    # 快速执行接口
    path('execute_script/', views.QuickScriptExecuteView.as_view(), name='execute_script'),
    path('transfer_file/', views.QuickFileTransferView.as_view(), name='transfer_file'),
]
