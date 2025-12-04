"""
系统配置URL配置
"""
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import SystemConfigViewSet

router = DefaultRouter()
router.register(r'configs', SystemConfigViewSet, basename='systemconfig')

urlpatterns = [
    path('', include(router.urls)),
]
