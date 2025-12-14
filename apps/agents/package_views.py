"""
Agent 安装包管理视图
"""
import logging
import hashlib
import os
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from django_filters.rest_framework import DjangoFilterBackend
from django.db import transaction
from django.conf import settings
from django.http import FileResponse, Http404

from utils.responses import SycResponse
from utils.pagination import CustomPagination
from .models import AgentPackage
from .serializers import (
    AgentPackageSerializer,
    AgentPackageCreateSerializer,
)
from .storage_service import StorageService as StorageServiceFactory

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
        # 使用事务确保数据一致性
        with transaction.atomic():
            # 计算文件哈希
            file_obj = serializer.validated_data.get('file')
            storage_type = self.request.data.get('storage_type', 'local')  # 从请求中获取存储类型
            
            if file_obj:
                file_obj.seek(0)
                file_content = file_obj.read()
                file_size = len(file_content)
                md5_hash = hashlib.md5(file_content).hexdigest()
                sha256_hash = hashlib.sha256(file_content).hexdigest()
                file_obj.seek(0)
                
                # 生成统一的存储路径
                version = serializer.validated_data.get('version')
                os_type = serializer.validated_data.get('os_type')
                arch = serializer.validated_data.get('arch')
                filename = file_obj.name
                storage_path = StorageServiceFactory.generate_storage_path(version, os_type, arch, filename)
                
                # 获取存储后端并上传文件
                backend = StorageServiceFactory.get_backend(storage_type)
                if backend is None:
                    logger.warning(f"无法获取存储后端: {storage_type}，将使用本地存储")
                    storage_type = 'local'
                    backend = StorageServiceFactory.get_backend('local')
                
                # 上传文件
                if storage_type == 'local':
                    # 本地存储由Django FileField处理，不需要手动上传
                    pass
                else:
                    # 对象存储，上传文件
                    success, error = backend.upload_file(file_obj, storage_path)
                    if not success:
                        logger.warning(f"对象存储上传失败: {error}，将使用本地存储")
                        storage_type = 'local'
                        backend = StorageServiceFactory.get_backend('local')
                        storage_path = StorageServiceFactory.generate_storage_path(version, os_type, arch, filename)
                        # 不保存文件字段（从validated_data中移除）
                        serializer.validated_data.pop('file', None)
                    else:
                        # 对象存储上传成功，不保存文件字段
                        serializer.validated_data.pop('file', None)
                
                # 保存数据
                save_kwargs = {
                    'created_by': self.request.user,
                    'file_size': file_size,
                    'md5_hash': md5_hash,
                    'sha256_hash': sha256_hash,
                    'storage_type': storage_type,
                    'storage_path': storage_path,
                }
                
                serializer.save(**save_kwargs)
            else:
                serializer.save(created_by=self.request.user)

    def perform_update(self, serializer):
        # 使用事务确保数据一致性
        with transaction.atomic():
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
        
        # 如果设置了外部下载地址（对象存储），重定向到该地址
        if package.download_url:
            from django.http import HttpResponseRedirect
            return HttpResponseRedirect(package.download_url)
        
        # 如果是本地文件，返回文件流
        if package.file and package.file.storage.exists(package.file.name):
            try:
                file_path = package.file.path
                if not os.path.exists(file_path):
                    # 如果文件不在本地，尝试从存储后端获取
                    file_obj = package.file.open('rb')
                    response = FileResponse(
                        file_obj,
                        content_type='application/octet-stream',
                        as_attachment=True
                    )
                    # 设置文件名，支持中文
                    filename = package.file.name.split('/')[-1]
                    response['Content-Disposition'] = f'attachment; filename="{urlquote(filename)}"; filename*=UTF-8\'\'{urlquote(filename)}'
                    response['Content-Length'] = package.file_size
                    return response
                else:
                    # 文件在本地文件系统
                    file_obj = open(file_path, 'rb')
                    response = FileResponse(
                        file_obj,
                        content_type='application/octet-stream',
                        as_attachment=True
                    )
                    filename = os.path.basename(file_path)
                    response['Content-Disposition'] = f'attachment; filename="{urlquote(filename)}"; filename*=UTF-8\'\'{urlquote(filename)}'
                    response['Content-Length'] = package.file_size
                    return response
            except Exception as e:
                logger.error(f"下载文件失败: {e}", exc_info=True)
                return SycResponse.error(message=f"文件下载失败: {str(e)}", code=500)
        
        return SycResponse.error(message="文件不存在或下载地址无效", code=404)

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
