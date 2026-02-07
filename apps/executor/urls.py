"""
统一执行记录URL配置
"""
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

app_name = 'executor'

router = DefaultRouter()
router.register(r'execution-records', views.ExecutionRecordViewSet, basename='execution-record')

urlpatterns = [
    path('', include(router.urls)),
]
