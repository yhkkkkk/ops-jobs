from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import FlowEdgeViewSet, FlowNodeViewSet, FlowRunViewSet, FlowScheduleViewSet, FlowTemplateViewSet


router = DefaultRouter()
router.register(r"templates", FlowTemplateViewSet, basename="flow-template")
router.register(r"nodes", FlowNodeViewSet, basename="flow-node")
router.register(r"edges", FlowEdgeViewSet, basename="flow-edge")
router.register(r"runs", FlowRunViewSet, basename="flow-run")
router.register(r"schedules", FlowScheduleViewSet, basename="flow-schedule")

urlpatterns = [
    path("", include(router.urls)),
]
