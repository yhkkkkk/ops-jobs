"""
脚本模板URL配置
"""
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

app_name = 'script_templates'

router = DefaultRouter()
router.register(r'', views.ScriptTemplateViewSet, basename='script-template')

urlpatterns = [
    path('', include(router.urls)),
]
