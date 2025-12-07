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

app_name = 'accounts'

urlpatterns = [
    # 认证接口 (支持Session + JWT)
    path('login/', views.CustomTokenObtainPairView.as_view(), name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('refresh/', TokenRefreshView.as_view(), name='token_refresh'),

    # 用户相关接口
    path('', include(router.urls)),
]

# 2FA 相关路由（仅在启用时添加）
if getattr(settings, 'TWO_FACTOR_ENABLED', False):
    urlpatterns.extend([
        path('2fa/setup/', views.TwoFactorSetupView.as_view(), name='2fa_setup'),
        path('2fa/verify/', views.TwoFactorVerifyView.as_view(), name='2fa_verify'),
        path('2fa/status/', views.TwoFactorStatusView.as_view(), name='2fa_status'),
        path('2fa/disable/', views.TwoFactorDisableView.as_view(), name='2fa_disable'),
    ])
