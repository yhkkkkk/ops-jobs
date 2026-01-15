"""
作业模板URL配置
"""
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

router = DefaultRouter()
router.register(r'templates', views.JobTemplateViewSet, basename='jobtemplate')
router.register(r'plans', views.ExecutionPlanViewSet, basename='executionplan')
router.register(r'steps', views.JobStepViewSet, basename='jobstep')
router.register(r'favorites', views.UserFavoriteViewSet, basename='userfavorite')

app_name = 'job_templates'

urlpatterns = [
    path('', include(router.urls)),
]
