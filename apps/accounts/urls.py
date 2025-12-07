"""
用户认证URL配置
"""
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt.views import TokenRefreshView
from django.conf import settings
from . import views


router = DefaultRouter()
router.register(r'users', views.UserViewSet, basename='user')

urlpatterns = [
    # 认证接口 (支持Session + JWT)
    path('login/', views.CustomTokenObtainPairView.as_view(), name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('refresh/', TokenRefreshView.as_view(), name='token_refresh'),

    # 用户相关接口
    path('', include(router.urls)),
]

# 2FA相关路由（如果启用）
if getattr(settings, 'TWO_FACTOR_ENABLED', False):
    urlpatterns.extend([
        path('check-2fa/', views.check_2fa_required, name='check_2fa_required'),
        path('2fa/setup/', views.two_factor_setup, name='two_factor_setup'),
        path('2fa/verify/', views.two_factor_verify, name='two_factor_verify'),
        path('2fa/status/', views.two_factor_status, name='two_factor_status'),
        path('2fa/disable/', views.two_factor_disable, name='two_factor_disable'),
    ])
