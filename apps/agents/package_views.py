"""
Agent 安装包管理视图
"""
import logging
import hashlib
import os
import tarfile
import zipfile
from concurrent.futures import ThreadPoolExecutor

from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from django_filters.rest_framework import DjangoFilterBackend
from django.db import transaction
from django.conf import settings
from django.http import FileResponse, Http404
from urllib.parse import unquote

from utils.responses import SycResponse
from utils.pagination import CustomPagination
from .models import AgentPackage
from .serializers import (
    AgentPackageSerializer,
    AgentPackageCreateSerializer,
)
from .storage_service import StorageService as StorageServiceFactory

logger = logging.getLogger(__name__)


_package_validate_executor = ThreadPoolExecutor(max_workers=2)


def _safe_member_name(name: str) -> bool:
    """检查压缩包成员名称是否安全，防止路径穿越等问题。"""
    if not name or name.startswith("/") or name.startswith("\\"):
        return False
    # 统一为正斜杠判断
    norm = name.replace("\\", "/")
    parts = [p for p in norm.split("/") if p not in ("", ".")]
    return all(p != ".." for p in parts)


def _validate_compressed_package(file_path: str, os_type: str) -> None:
    """
    对压缩包做结构与安全校验。

    - 防止 zip/tar bomb（限制文件数与总解压大小）
    - 禁止路径穿越
    - 尝试检查是否包含 agent 可执行文件
    """
    if not os.path.exists(file_path):
        raise ValueError("安装包文件不存在")

    max_files = 2000
    max_total_size = 2 * 1024 * 1024 * 1024  # 2GB

    _, ext = os.path.splitext(file_path.lower())
    # 兼容 .tar.gz / .tgz
    if file_path.lower().endswith(".tar.gz") or file_path.lower().endswith(".tgz"):
        mode = "r:gz"
        with tarfile.open(file_path, mode) as tf:
            members = tf.getmembers()
            if len(members) > max_files:
                raise ValueError("压缩包文件数量过多，疑似异常包")
            total = 0
            has_agent_binary = False
            for m in members:
                if not _safe_member_name(m.name):
                    raise ValueError(f"压缩包内包含不安全路径: {m.name}")
                total += max(m.size, 0)
                if total > max_total_size:
                    raise ValueError("压缩包解压后总大小超出限制，疑似异常包")
                base = os.path.basename(m.name).lower()
                if "ops-job-agent" in base or base == "agent":
                    has_agent_binary = True
            if not has_agent_binary:
                logger.warning("安装包中未检测到明显的 agent 可执行文件（包含 'ops-job-agent' 或 'agent' 字样）")
        return

    if ext == ".zip":
        with zipfile.ZipFile(file_path, "r") as zf:
            infos = zf.infolist()
            if len(infos) > max_files:
                raise ValueError("压缩包文件数量过多，疑似异常包")
            total = 0
            has_agent_binary = False
            for info in infos:
                if not _safe_member_name(info.filename):
                    raise ValueError(f"压缩包内包含不安全路径: {info.filename}")
                total += max(info.file_size, 0)
                if total > max_total_size:
                    raise ValueError("压缩包解压后总大小超出限制，疑似异常包")
                base = os.path.basename(info.filename).lower()
                if "ops-job-agent" in base or base == "agent":
                    has_agent_binary = True
            if not has_agent_binary:
                logger.warning("安装包中未检测到明显的 agent 可执行文件（包含 'ops-job-agent' 或 'agent' 字样）")
        return

    # 其他类型（如 .exe/.bin）仅做基础存在与大小校验，详细校验后续按需扩展
    stat = os.stat(file_path)
    if stat.st_size <= 0:
        raise ValueError("安装包文件大小异常")


def _run_package_validation(package_id: int) -> None:
    """后台线程中执行的安装包校验逻辑。"""
    from django.db import transaction

    try:
        pkg = AgentPackage.objects.get(id=package_id)
    except AgentPackage.DoesNotExist:
        logger.warning("安装包校验失败：包不存在, id=%s", package_id)
        return

    # 标记为 running
    AgentPackage.objects.filter(id=package_id).update(
        validate_status="running",
        validate_message="",
    )

    try:
        # 目前仅对本地存储做深度结构校验，其它存储类型后续可扩展为预下载到本地再校验
        file_path = None
        if pkg.file and pkg.file.name:
            try:
                file_path = pkg.file.path
            except Exception:  # pragma: no cover - 防御性
                file_path = None

        if pkg.storage_type == "local" and file_path:
            _validate_compressed_package(file_path, pkg.os_type)

        # 校验通过
        AgentPackage.objects.filter(id=package_id).update(
            validate_status="passed",
            validate_message="",
        )
        logger.info("安装包校验通过, id=%s", package_id)
    except Exception as exc:  # noqa: BLE001
        msg = str(exc)
        logger.error("安装包校验失败, id=%s, error=%s", package_id, msg, exc_info=True)
        AgentPackage.objects.filter(id=package_id).update(
            validate_status="failed",
            validate_message=msg[:2000],
        )


def _schedule_package_validation(package_id: int) -> None:
    """在事务提交后调度后台线程执行安装包校验。"""
    def _on_commit():
        try:
            _package_validate_executor.submit(_run_package_validation, package_id)
        except Exception as exc:  # noqa: BLE001
            logger.error("提交安装包校验任务失败 id=%s, error=%s", package_id, exc, exc_info=True)

    transaction.on_commit(_on_commit)


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

    def create(self, request, *args, **kwargs):
        """创建安装包"""
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            self.perform_create(serializer)
            return SycResponse.success(
                content=serializer.data,
                message="安装包创建成功"
            )
        except Exception as exc:  # noqa: BLE001
            logger.error("创建安装包失败: %s", exc, exc_info=True)
            return SycResponse.error(message=f"安装包创建失败: {str(exc)}")

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
                    'validate_status': 'pending',
                    'validate_message': '',
                }

                package = serializer.save(**save_kwargs)
                _schedule_package_validation(package.id)
            else:
                package = serializer.save(
                    created_by=self.request.user,
                    validate_status='pending',
                    validate_message='',
                )
                _schedule_package_validation(package.id)

    def update(self, request, *args, **kwargs):
        """更新安装包"""
        partial = kwargs.pop('partial', False)
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        
        try:
            self.perform_update(serializer)
            # 重新获取更新后的实例
            updated_instance = self.get_object()
            response_serializer = self.get_serializer(updated_instance)
            return SycResponse.success(
                content=response_serializer.data,
                message="安装包更新成功"
            )
        except Exception as exc:
            logger.error("更新安装包失败: %s", exc, exc_info=True)
            return SycResponse.error(message=f"安装包更新失败: {str(exc)}")

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
                
                # 获取存储类型（更新时不传，使用现有的）
                storage_type = self.request.data.get('storage_type', serializer.instance.storage_type)
                
                # 生成统一的存储路径
                version = serializer.validated_data.get('version', serializer.instance.version)
                os_type = serializer.validated_data.get('os_type', serializer.instance.os_type)
                arch = serializer.validated_data.get('arch', serializer.instance.arch)
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
                    'file_size': file_size,
                    'md5_hash': md5_hash,
                    'sha256_hash': sha256_hash,
                    'storage_type': storage_type,
                    'storage_path': storage_path,
                    'validate_status': 'pending',
                    'validate_message': '',
                }
                
                package = serializer.save(**save_kwargs)
                _schedule_package_validation(package.id)
            else:
                # 如果没有上传新文件，保持已有的存储相关字段不变（前端更新不包含存储类型）
                serializer.save(
                    storage_type=serializer.instance.storage_type,
                    storage_path=serializer.instance.storage_path,
                    file_size=serializer.instance.file_size,
                    md5_hash=serializer.instance.md5_hash,
                    sha256_hash=serializer.instance.sha256_hash,
                )

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
                    response['Content-Disposition'] = f'attachment; filename="{unquote(filename)}"; filename*=UTF-8\'\'{unquote(filename)}'
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
                    response['Content-Disposition'] = f'attachment; filename="{unquote(filename)}"; filename*=UTF-8\'\'{unquote(filename)}'
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
