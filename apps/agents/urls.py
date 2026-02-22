"""
Agent 管理 API
"""
from django.urls import path, include
from rest_framework.routers import DefaultRouter

from .views import AgentViewSet
from .package_views import AgentPackageViewSet
from .views import ArtifactUploadView
from .agent_server_views import AgentServerViewSet

router = DefaultRouter()
# 先注册具体路径，避免被空路径匹配
router.register(r'agent_servers', AgentServerViewSet, basename='agent-server')
router.register(r'packages', AgentPackageViewSet, basename='package')
router.register(r'', AgentViewSet, basename='agent')

app_name = 'agents'

urlpatterns = [
    path('artifacts/upload/', ArtifactUploadView.as_view(), name='artifact-upload'),
    path('', include(router.urls)),
]
