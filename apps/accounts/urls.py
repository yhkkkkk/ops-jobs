"""
用户认证URL配置
"""
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt.views import TokenRefreshView
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
