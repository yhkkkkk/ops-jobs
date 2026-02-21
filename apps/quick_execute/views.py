"""
快速执行视图
"""
import json
from rest_framework.views import APIView
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser
from rest_framework.permissions import IsAuthenticated
from apps.permissions.permissions import ScriptExecutionPermission
from drf_spectacular.utils import extend_schema, extend_schema_view
from utils.responses import SycResponse
from utils.audit_service import AuditLogService
from .serializers import (
    QuickScriptExecuteSerializer,
    QuickFileTransferSerializer,
)
from .services import QuickExecuteService
import logging

logger = logging.getLogger(__name__)


@extend_schema_view(
    post=extend_schema(
        summary="快速执行脚本",
        description="快速执行脚本，不保存配置，直接执行",
        tags=["快速执行"]
    )
)
class QuickScriptExecuteView(APIView):
    """快速脚本执行视图"""

    permission_classes = [ScriptExecutionPermission]
    serializer_class = QuickScriptExecuteSerializer

    def post(self, request):
        """快速执行脚本"""
        serializer = QuickScriptExecuteSerializer(data=request.data)
        if not serializer.is_valid():
            return SycResponse.validation_error(errors=serializer.errors)

        # 获取客户端信息
        client_ip = self.get_client_ip(request)
        user_agent = request.META.get('HTTP_USER_AGENT', '')

        result = QuickExecuteService.execute_script(
            user=request.user,
            script_data=serializer.validated_data,
            client_ip=client_ip,
            user_agent=user_agent
        )

        meta = {
            'name': serializer.validated_data.get('name'),
            'script_type': serializer.validated_data.get('script_type'),
            'execution_mode': serializer.validated_data.get('execution_mode'),
            'target_host_count': len(serializer.validated_data.get('target_host_ids') or []),
            'dynamic_ip_count': len(serializer.validated_data.get('dynamic_ips') or []),
        }

        if result['success']:
            AuditLogService.log_action(
                user=request.user,
                action='execute_script',
                description='快速执行脚本',
                request=request,
                success=True,
                extra_data=meta
            )
            return SycResponse.success(content=result, message="脚本执行已启动")
        else:
            message = result.get('message') or result.get('error') or "脚本执行启动失败"
            AuditLogService.log_action(
                user=request.user,
                action='execute_script',
                description='快速执行脚本失败',
                request=request,
                success=False,
                error_message=message,
                extra_data=meta
            )
            return SycResponse.error(content=result, message=message)

    def get_client_ip(self, request):
        """获取客户端IP地址"""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0]
        else:
            ip = request.META.get('REMOTE_ADDR')
        return ip


@extend_schema_view(
    post=extend_schema(
        summary="快速文件传输",
        description="快速文件传输，不保存配置，直接执行",
        tags=["快速执行"]
    )
)
class QuickFileTransferView(APIView):
    """快速文件传输视图"""
    permission_classes = [IsAuthenticated]
    serializer_class = QuickFileTransferSerializer
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    def post(self, request):
        """快速文件传输"""

        data = request.data.copy()
        logger.debug(f"[quick_transfer] request.data keys={list(request.data.keys())}, files={list(request.FILES.keys())}, raw_files={getattr(getattr(request, '_request', None), 'FILES', {})}")

        # 兼容 multipart/form-data：sources 可能是重复字段列表，也可能是单个 JSON 字符串
        raw_sources = None
        if hasattr(request.data, "getlist"):
            raw_sources = request.data.getlist("sources")
            if not raw_sources:
                raw_sources = request.data.get("sources")
        else:
            raw_sources = request.data.get("sources")

        try:
            if isinstance(raw_sources, list):
                parsed = []
                for item in raw_sources:
                    loaded = json.loads(item) if isinstance(item, str) else item
                    if isinstance(loaded, list):
                        parsed.extend(loaded)
                    else:
                        parsed.append(loaded)
                data["sources"] = parsed
            elif isinstance(raw_sources, str):
                loaded = json.loads(raw_sources)
                data["sources"] = loaded if isinstance(loaded, list) else [loaded]
        except Exception:
            return SycResponse.validation_error(errors={"sources": ["sources 字段 json 解析失败"]})

        # 再做一层扁平化，避免 [[...]] 导致子项校验失败
        if isinstance(data.get("sources"), list):
            flattened = []
            for item in data["sources"]:
                if isinstance(item, list):
                    flattened.extend(item)
                else:
                    flattened.append(item)
            data["sources"] = flattened

        # 仅提取序列化器需要的字段，避免文件字段干扰 json 解析
        serializer_fields = {
            "name", "sources", "global_variables", "overwrite_policy",
            "target_host_ids", "dynamic_ips", "timeout", "bandwidth_limit",
            "execution_mode", "rolling_strategy", "rolling_batch_size",
            "rolling_batch_delay", "agent_server_url", "account_id"
        }
        serializer_data = {}
        for key in serializer_fields:
            if key in ("target_host_ids", "dynamic_ips") and hasattr(data, "getlist"):
                serializer_data[key] = data.getlist(key)
            elif key in data:
                serializer_data[key] = data.get(key)

        serializer = QuickFileTransferSerializer(data=serializer_data)
        if not serializer.is_valid():
            return SycResponse.validation_error(errors=serializer.errors)

        # 获取客户端信息
        client_ip = self.get_client_ip(request)
        user_agent = request.META.get('HTTP_USER_AGENT', '')
        # 支持 multipart/form-data 上传本地文件：把 request.FILES 一并传给 service
        transfer_data = serializer.validated_data
        # request.FILES 是类似 MultiValueDict，直接传递供 service 使用（file_field 对应的 key）
        transfer_data['uploaded_files'] = request.FILES

        result = QuickExecuteService.transfer_file(
            user=request.user,
            transfer_data=transfer_data,
            client_ip=client_ip,
            user_agent=user_agent
        )

        meta = {
            'name': serializer.validated_data.get('name'),
            'execution_mode': serializer.validated_data.get('execution_mode'),
            'target_host_count': len(serializer.validated_data.get('target_host_ids') or []),
            'dynamic_ip_count': len(serializer.validated_data.get('dynamic_ips') or []),
            'sources_count': len(serializer.validated_data.get('sources') or []),
        }

        if result['success']:
            AuditLogService.log_action(
                user=request.user,
                action='transfer_file',
                description='快速文件传输',
                request=request,
                success=True,
                extra_data=meta
            )
            return SycResponse.success(content=result, message="文件传输已启动")
        else:
            message = result.get('message') or result.get('error') or "文件传输启动失败"
            AuditLogService.log_action(
                user=request.user,
                action='transfer_file',
                description='快速文件传输失败',
                request=request,
                success=False,
                error_message=message,
                extra_data=meta
            )
            return SycResponse.error(
                content=result,
                message=message
            )

    def get_client_ip(self, request):
        """获取客户端IP地址"""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0]
        else:
            ip = request.META.get('REMOTE_ADDR')
        return ip
