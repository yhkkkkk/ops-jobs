"""
Agent 安装包管理视图
"""
import logging
import hashlib
import os
import tarfile
import zipfile
import tempfile
import importlib
from concurrent.futures import ThreadPoolExecutor

from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from django_filters.rest_framework import DjangoFilterBackend
from django.db import transaction
from django.conf import settings
from django.http import FileResponse, Http404
from django.core.files.uploadedfile import SimpleUploadedFile
from urllib.parse import unquote

from utils.responses import SycResponse
from utils.pagination import CustomPagination
from .models import AgentPackage
from .serializers import (
    AgentPackageSerializer,
    AgentPackageCreateSerializer,
)
from .storage_service import StorageService

logger = logging.getLogger(__name__)


_package_validate_executor = ThreadPoolExecutor(max_workers=4)


def _persist_temp_file(file_content: bytes, filename: str) -> str:
    suffix = os.path.splitext(filename)[1] or ".tmp"
    temp = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
    try:
        temp.write(file_content)
        temp.flush()
        return temp.name
    finally:
        temp.close()


def _safe_member_name(name: str) -> bool:
    """检查压缩包成员名称是否安全，防止路径穿越等问题。"""
    if not name or name.startswith("/") or name.startswith("\\"):
        return False
    # 统一为正斜杠判断
    norm = name.replace("\\", "/")
    parts = [p for p in norm.split("/") if p not in ("", ".")]
    return all(p != ".." for p in parts)


def _validate_compressed_package(file_path: str, os_type: str, package_type: str) -> None:
    """
    对压缩包做结构与安全校验。
    - 防止 zip/tar bomb（限制文件数与总解压大小）
    - 禁止路径穿越
    - 按包类型校验固定的扁平文件结构
    """
    if not os.path.exists(file_path):
        raise ValueError("安装包文件不存在")

    max_files = 100
    max_total_size = 100 * 1024 * 1024  # 100MB
    expected_files_map = {
        "agent": {"agent", "config.example.yaml"},
        "agent-server": {"agent-server", "config.example.yaml"},
    }
    expected_files = {name.lower() for name in expected_files_map.get(package_type, set())}

    def _validate_entries(entries: list[tuple[str, int, bool, bool]]) -> None:
        if len(entries) > max_files:
            raise ValueError("压缩包文件数量过多，疑似异常包")
        total = 0
        file_names: set[str] = set()
        for name, size, is_dir, is_link in entries:
            if not _safe_member_name(name):
                raise ValueError(f"压缩包内包含不安全路径: {name}")
            norm = name.replace("\\", "/").strip()
            if norm.startswith("./"):
                norm = norm[2:]
            if "/" in norm:
                raise ValueError("安装包内不允许包含子目录，必须是扁平结构")
            if is_dir:
                raise ValueError("安装包内不允许包含目录，仅允许文件")
            if is_link:
                raise ValueError("安装包内不允许包含符号链接/硬链接")

            total += max(size, 0)
            if total > max_total_size:
                raise ValueError("压缩包解压后总大小超出限制，疑似异常包")
            file_names.add(norm.lower())

        if expected_files:
            missing = expected_files - file_names
            extra = file_names - expected_files
            if missing or extra:
                raise ValueError(
                    f"安装包内容不符合要求，需包含 {sorted(expected_files)}，"
                    f"缺少 {sorted(missing) if missing else []}，多余 {sorted(extra) if extra else []}"
                )
        elif not file_names:
            raise ValueError("安装包文件为空或未找到有效文件")

    _, ext = os.path.splitext(file_path.lower())
    # 兼容 .tar.gz / .tgz
    if file_path.lower().endswith(".tar.gz") or file_path.lower().endswith(".tgz"):
        mode = "r:gz"
        with tarfile.open(file_path, mode) as tf:
            entries = []
            for m in tf.getmembers():
                entries.append((m.name, m.size, m.isdir(), m.issym() or m.islnk()))
            _validate_entries(entries)
        return

    if ext == ".zip":
        with zipfile.ZipFile(file_path, "r") as zf:
            entries = []
            for info in zf.infolist():
                entries.append((info.filename, info.file_size, info.is_dir(), False))
            _validate_entries(entries)
        return

    # 其他类型（如 .exe/.bin）仅做基础存在与大小校验，详细校验后续按需扩展
    stat = os.stat(file_path)
    if stat.st_size <= 0:
        raise ValueError("安装包文件大小异常")


def _check_storage_dependency(storage_type: str) -> None:
    """上传前检查存储类型所需的依赖库是否已安装。"""
    module_map = {
        "oss": "oss2",
        "cos": "qcloud_cos",
        "minio": "minio",
        "s3": "boto3",
        "rustfs": "boto3",
    }
    mod = module_map.get(storage_type)
    if not mod:
        return
    try:
        importlib.import_module(mod)
    except ImportError:
        raise ValueError(f"存储类型 {storage_type} 需要安装依赖 {mod}，请先安装后再上传")


def _run_package_validation(package_id: int, context: dict | None = None) -> None:
    """后台线程中执行安装包校验+上传逻辑，确保先校验再上传。"""

    ctx = context or {}
    file_path = ctx.get("file_path")
    storage_type = ctx.get("storage_type")
    target_storage_path = ctx.get("storage_path", "")
    file_name = ctx.get("file_name", "")
    file_size = ctx.get("file_size")
    md5_hash = ctx.get("md5_hash", "")
    sha256_hash = ctx.get("sha256_hash", "")

    def _cleanup_temp_file() -> None:
        if file_path and os.path.exists(file_path):
            try:
                os.unlink(file_path)
            except Exception:
                pass

    try:
        pkg = AgentPackage.objects.get(id=package_id)
    except AgentPackage.DoesNotExist:
        logger.warning("安装包校验失败：包不存在, id=%s", package_id)
        _cleanup_temp_file()
        return

    # 标记为 running
    AgentPackage.objects.filter(id=package_id).update(
        validate_status="running",
        validate_message="",
    )

    try:
        if not file_path or not os.path.exists(file_path):
            raise ValueError("待校验的安装包文件不存在，无法完成校验")

        _validate_compressed_package(file_path, pkg.os_type, pkg.package_type)

        # 校验通过后再上传
        backend = StorageService.get_backend(storage_type or pkg.storage_type)
        if backend is None:
            raise ValueError(f"无法获取存储后端: {storage_type or pkg.storage_type}")

        with open(file_path, "rb") as f:
            file_bytes = f.read()
        upload_obj = SimpleUploadedFile(file_name or os.path.basename(file_path), file_bytes)
        success, error = backend.upload_file(upload_obj, target_storage_path)
        if not success:
            raise ValueError(f"文件上传失败: {error or '未知错误'}")

        AgentPackage.objects.filter(id=package_id).update(
            file_name=file_name or pkg.file_name,
            file_size=file_size if file_size is not None else pkg.file_size,
            md5_hash=md5_hash or pkg.md5_hash,
            sha256_hash=sha256_hash or pkg.sha256_hash,
            storage_type=storage_type or pkg.storage_type,
            storage_path=target_storage_path or pkg.storage_path,
            validate_status="passed",
            validate_message="",
        )
        logger.info("安装包校验并上传通过, id=%s", package_id)
    except Exception as exc:
        msg = str(exc)
        logger.error("安装包校验/上传失败, id=%s, error=%s", package_id, msg, exc_info=True)
        AgentPackage.objects.filter(id=package_id).update(
            validate_status="failed",
            validate_message=msg[:500],
        )
    finally:
        _cleanup_temp_file()


def _schedule_package_validation(package_id: int, context: dict | None = None) -> None:
    """在事务提交后调度后台线程执行安装包校验与上传。"""
    def _on_commit():
        try:
            _package_validate_executor.submit(_run_package_validation, package_id, context)
        except Exception as exc:
            logger.error("提交安装包校验任务失败 id=%s, error=%s", package_id, exc, exc_info=True)

    transaction.on_commit(_on_commit)


class AgentPackageViewSet(viewsets.ModelViewSet):
    """Agent 安装包管理"""
    queryset = AgentPackage.objects.all()
    serializer_class = AgentPackageSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['package_type', 'version', 'os_type', 'arch', 'storage_type', 'is_active', 'is_default']
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
        except Exception as exc:
            logger.error("创建安装包失败: %s", exc, exc_info=True)
            return SycResponse.error(message="安装包创建失败")

    def perform_create(self, serializer):
        # 使用事务确保数据一致性
        with transaction.atomic():
            # 计算文件哈希
            file_obj = serializer.validated_data.get('file')
            storage_type = self.request.data.get('storage_type')  # 从请求中获取存储类型
            if storage_type:
                _check_storage_dependency(storage_type)
            
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
                temp_file_path = _persist_temp_file(file_content, filename)
                storage_path = StorageService.generate_storage_path(version, os_type, arch, filename)
                
                # 保存数据
                save_kwargs = {
                    'created_by': self.request.user,
                    'file_name': filename,
                    'file_size': file_size,
                    'md5_hash': md5_hash,
                    'sha256_hash': sha256_hash,
                    'storage_type': storage_type,
                    'storage_path': storage_path,
                    'validate_status': 'pending',
                    'validate_message': '',
                }

                package = serializer.save(**save_kwargs)
                _schedule_package_validation(package.id, {
                    'file_path': temp_file_path,
                    'storage_type': storage_type,
                    'storage_path': storage_path,
                    'file_name': filename,
                    'file_size': file_size,
                    'md5_hash': md5_hash,
                    'sha256_hash': sha256_hash,
                })
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
                if storage_type:
                    _check_storage_dependency(storage_type)

                # 生成统一的存储路径
                version = serializer.validated_data.get('version', serializer.instance.version)
                os_type = serializer.validated_data.get('os_type', serializer.instance.os_type)
                arch = serializer.validated_data.get('arch', serializer.instance.arch)
                filename = file_obj.name
                temp_file_path = _persist_temp_file(file_content, filename)
                storage_path = StorageService.generate_storage_path(version, os_type, arch, filename)
                
                # 保存数据
                save_kwargs = {
                    'file_name': filename,
                    'file_size': file_size,
                    'md5_hash': md5_hash,
                    'sha256_hash': sha256_hash,
                    'storage_type': storage_type,
                    'storage_path': storage_path,
                    'validate_status': 'pending',
                    'validate_message': '',
                }
                
                package = serializer.save(**save_kwargs)
                _schedule_package_validation(package.id, {
                    'file_path': temp_file_path,
                    'storage_type': storage_type,
                    'storage_path': storage_path,
                    'file_name': filename,
                    'file_size': file_size,
                    'md5_hash': md5_hash,
                    'sha256_hash': sha256_hash,
                })
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
            if instance.storage_path:
                backend = StorageService.get_backend(instance.storage_type)
                if backend:
                    backend.delete_file(instance.storage_path)
            instance.delete()
            return SycResponse.success(message="安装包删除成功")
        except Exception as e:
            logger.error(f"删除安装包失败: {e}", exc_info=True)
            return SycResponse.error(message=f"删除失败: {str(e)}", code=500)

    @action(detail=True, methods=['get'])
    def download(self, request, pk=None):
        """下载安装包文件"""
        package = self.get_object()
        
        # 如果设置了外部下载地址，重定向到该地址
        if package.download_url:
            from django.http import HttpResponseRedirect
            return HttpResponseRedirect(package.download_url)

        # 从存储后端获取文件
        try:
            backend = StorageService.get_backend(package.storage_type)
            if backend is None:
                return SycResponse.error(message="存储后端不可用", code=500)

            file_obj = backend.get_file(package.storage_path)
            if file_obj is None:
                return SycResponse.error(message="文件不存在", code=404)

            response = FileResponse(
                file_obj,
                content_type='application/octet-stream',
                as_attachment=True
            )

            # 设置文件名，支持中文
            filename = package.file_name or package.storage_path.split('/')[-1]
            response['Content-Disposition'] = f'attachment; filename="{unquote(filename)}"; filename*=UTF-8\'\'{unquote(filename)}'
            response['Content-Length'] = package.file_size
            return response

        except Exception as e:
            logger.error(f"下载文件失败: {e}", exc_info=True)
            return SycResponse.error(message=f"文件下载失败: {str(e)}", code=500)

    @action(detail=False, methods=['get'])
    def versions(self, request):
        """获取所有版本列表（去重）"""
        qs = AgentPackage.objects.filter(is_active=True)
        package_type = request.query_params.get('package_type')
        if package_type:
            qs = qs.filter(package_type=package_type)
        versions = qs.values_list('version', flat=True).distinct().order_by('-version')
        return SycResponse.success(content=list(versions))

    @action(detail=False, methods=['get'])
    def active_packages(self, request):
        """获取启用的安装包列表（用于安装时选择）"""
        qs = AgentPackage.objects.filter(is_active=True)
        package_type = request.query_params.get('package_type')
        if package_type:
            qs = qs.filter(package_type=package_type)
        else:
            qs = qs.filter(package_type='agent')
        packages = qs.order_by('-is_default', '-created_at')
        serializer = self.get_serializer(packages, many=True)
        return SycResponse.success(content=serializer.data)

    @action(detail=False, methods=['get'])
    def default_packages(self, request):
        """获取默认版本的安装包"""
        qs = AgentPackage.objects.filter(is_default=True, is_active=True)
        package_type = request.query_params.get('package_type')
        if package_type:
            qs = qs.filter(package_type=package_type)
        else:
            qs = qs.filter(package_type='agent')
        packages = qs
        serializer = self.get_serializer(packages, many=True)
        return SycResponse.success(content=serializer.data)
