"""
Agent 安装包管理视图
"""
import logging
import hashlib
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from django_filters.rest_framework import DjangoFilterBackend
from django.db import transaction
from django.conf import settings

from utils.responses import SycResponse
from utils.pagination import CustomPagination
from .models import AgentPackage
from .serializers import (
    AgentPackageSerializer,
    AgentPackageCreateSerializer,
)

logger = logging.getLogger(__name__)


class AgentPackageViewSet(viewsets.ModelViewSet):
    """Agent 安装包管理"""
    queryset = AgentPackage.objects.all()
    serializer_class = AgentPackageSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['version', 'os_type', 'arch', 'is_active', 'is_default']
    pagination_class = CustomPagination

    def get_queryset(self):
        queryset = super().get_queryset()
        return queryset.select_related('created_by')

    def get_serializer_class(self):
        if self.action in ['create', 'update', 'partial_update']:
            return AgentPackageCreateSerializer
        return AgentPackageSerializer

    def perform_create(self, serializer):
        # 计算文件哈希
        file_obj = serializer.validated_data.get('file')
        if file_obj:
            file_obj.seek(0)
            file_content = file_obj.read()
            file_size = len(file_content)
            md5_hash = hashlib.md5(file_content).hexdigest()
            sha256_hash = hashlib.sha256(file_content).hexdigest()
            file_obj.seek(0)
            
            serializer.save(
                created_by=self.request.user,
                file_size=file_size,
                md5_hash=md5_hash,
                sha256_hash=sha256_hash
            )
        else:
            serializer.save(created_by=self.request.user)

    def perform_update(self, serializer):
        # 如果更新了文件，重新计算哈希
        if 'file' in serializer.validated_data:
            file_obj = serializer.validated_data['file']
            file_obj.seek(0)
            file_content = file_obj.read()
            file_size = len(file_content)
            md5_hash = hashlib.md5(file_content).hexdigest()
            sha256_hash = hashlib.sha256(file_content).hexdigest()
            file_obj.seek(0)
            
            serializer.save(
                file_size=file_size,
                md5_hash=md5_hash,
                sha256_hash=sha256_hash
            )
        else:
            serializer.save()

    def destroy(self, request, *args, **kwargs):
        """删除安装包"""
        instance = self.get_object()
        try:
            # 删除文件
            if instance.file:
                instance.file.delete()
            instance.delete()
            return SycResponse.success(message="安装包删除成功")
        except Exception as e:
            logger.error(f"删除安装包失败: {e}", exc_info=True)
            return SycResponse.error(message=f"删除失败: {str(e)}", code=500)

    @action(detail=True, methods=['get'])
    def download(self, request, pk=None):
        """下载安装包文件"""
        package = self.get_object()
        download_url = package.get_download_url()
        
        if not download_url:
            return SycResponse.error(message="文件不存在或下载地址无效", code=404)
        
        return SycResponse.success(content={
            'download_url': download_url,
            'file_name': package.file.name.split('/')[-1] if package.file else '',
            'file_size': package.file_size,
            'md5_hash': package.md5_hash,
            'sha256_hash': package.sha256_hash,
        })

    @action(detail=False, methods=['get'])
    def versions(self, request):
        """获取所有版本列表（去重）"""
        versions = AgentPackage.objects.filter(is_active=True).values_list('version', flat=True).distinct().order_by('-version')
        return SycResponse.success(content=list(versions))

    @action(detail=False, methods=['get'])
    def active_packages(self, request):
        """获取启用的安装包列表（用于安装时选择）"""
        packages = AgentPackage.objects.filter(is_active=True).order_by('-is_default', '-created_at')
        serializer = self.get_serializer(packages, many=True)
        return SycResponse.success(content=serializer.data)

    @action(detail=False, methods=['get'])
    def default_packages(self, request):
        """获取默认版本的安装包"""
        packages = AgentPackage.objects.filter(is_default=True, is_active=True)
        serializer = self.get_serializer(packages, many=True)
        return SycResponse.success(content=serializer.data)
