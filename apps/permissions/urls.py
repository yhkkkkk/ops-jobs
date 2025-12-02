"""
权限管理URL配置
"""
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

router = DefaultRouter()
router.register(r'audit-logs', views.AuditLogViewSet, basename='audit-log')

urlpatterns = [
    path('', include(router.urls)),
    
    # 权限检查接口
    path('check/', views.PermissionCheckView.as_view(), name='permission-check'),
    path('user-permissions/', views.UserPermissionsView.as_view(), name='user-permissions'),
    path('resource-permissions/', views.ResourcePermissionsView.as_view(), name='resource-permissions'),
]
