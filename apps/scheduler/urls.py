"""
调度管理URL配置
"""
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

app_name = 'scheduler'

router = DefaultRouter()
router.register(r'scheduled-jobs', views.ScheduledJobViewSet, basename='scheduled-job')

urlpatterns = [
    path('', include(router.urls)),
]
