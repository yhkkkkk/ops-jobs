"""
仪表盘URL配置
"""
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views


router = DefaultRouter()
router.register(r'', views.DashboardViewSet, basename='dashboard')

app_name = 'dashboard'

urlpatterns = [
    path('', include(router.urls)),
]
