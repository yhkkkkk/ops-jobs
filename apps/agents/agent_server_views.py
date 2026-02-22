"""Agent-Server 管理 API"""
import logging

from django.db.models import Q
from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated

from utils.responses import SycResponse
from utils.pagination import CustomPagination
from .models import AgentServer
from .serializers import AgentServerSerializer
from .permissions import AgentServerPermission

logger = logging.getLogger(__name__)


def _parse_bool(value):
    if value is None:
        return None
    value = str(value).strip().lower()
    if value in ('1', 'true', 'yes', 'y'):
        return True
    if value in ('0', 'false', 'no', 'n'):
        return False
    return None


class AgentServerViewSet(viewsets.ModelViewSet):
    """Agent-Server 配置管理"""

    queryset = AgentServer.objects.all().order_by('-created_at')
    serializer_class = AgentServerSerializer
    permission_classes = [IsAuthenticated, AgentServerPermission]
    pagination_class = CustomPagination

    def list(self, request, *args, **kwargs):
        queryset = self.get_queryset()

        keyword = request.query_params.get('search', '')
        if keyword:
            keyword = keyword.strip()
            if keyword:
                queryset = queryset.filter(
                    Q(name__icontains=keyword) | Q(base_url__icontains=keyword)
                )

        is_active = _parse_bool(request.query_params.get('is_active'))
        if is_active is not None:
            queryset = queryset.filter(is_active=is_active)

        require_signature = _parse_bool(request.query_params.get('require_signature'))
        if require_signature is not None:
            queryset = queryset.filter(require_signature=require_signature)

        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            paginator = self.paginator
            return SycResponse.success(
                content={
                    'results': serializer.data,
                    'total': paginator.page.paginator.count,
                    'page': paginator.page.number,
                    'page_size': paginator.page_size,
                },
                message="获取Agent-Server列表成功",
            )

        serializer = self.get_serializer(queryset, many=True)
        return SycResponse.success(
            content={
                'results': serializer.data,
                'total': len(serializer.data),
                'page': 1,
                'page_size': len(serializer.data),
            },
            message="获取Agent-Server列表成功",
        )

    def retrieve(self, request, *args, **kwargs):
        instance = self.get_object()
        serializer = self.get_serializer(instance)
        return SycResponse.success(content=serializer.data, message="获取Agent-Server详情成功")

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        if serializer.is_valid():
            self.perform_create(serializer)
            return SycResponse.success(content=serializer.data, message="创建Agent-Server成功")
        return SycResponse.validation_error(serializer.errors)

    def update(self, request, *args, **kwargs):
        partial = kwargs.pop('partial', False)
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        if serializer.is_valid():
            self.perform_update(serializer)
            return SycResponse.success(content=serializer.data, message="更新Agent-Server成功")
        return SycResponse.validation_error(serializer.errors)

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        self.perform_destroy(instance)
        return SycResponse.success(message="删除Agent-Server成功")
