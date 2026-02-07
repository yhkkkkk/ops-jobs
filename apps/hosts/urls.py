"""
主机管理API URL配置
"""
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

router = DefaultRouter()
router.register(r'groups', views.HostGroupViewSet, basename='hostgroup')
router.register(r'hosts', views.HostViewSet, basename='host')
router.register(r'accounts', views.ServerAccountViewSet, basename='serveraccount')

app_name = 'hosts'

urlpatterns = [
    path('', include(router.urls)),
]
