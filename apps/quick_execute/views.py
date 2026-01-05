"""
快速执行视图
"""
from rest_framework import status
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from apps.permissions.permissions import ScriptExecutionPermission
from drf_spectacular.utils import extend_schema, extend_schema_view
from utils.responses import SycResponse
from .serializers import (
    QuickScriptExecuteSerializer,
    QuickFileTransferSerializer,
)
from .services import QuickExecuteService


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

        if result['success']:
            return SycResponse.success(content=result, message="脚本执行已启动")
        else:
            return SycResponse.error(content=result, message=result['message'])

    def get_client_ip(self, request):
        """获取客户端IP地址"""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0]
        else:
            ip = request.META.get('REMOTE_ADDR')
        return ip


class QuickFileTransferPreviewView(APIView):
    """预览快速文件传输在各目标主机上会匹配到的目标路径（支持目标路径通配符预览）"""
    permission_classes = [IsAuthenticated]

    def post(self, request):
        data = request.data or {}
        # SSH 路径预览已禁用，统一走 Agent 文件传输
        return SycResponse.error(message='已禁用 SSH 预览，请直接使用 Agent 文件传输')


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

    def post(self, request):
        """快速文件传输"""
        serializer = QuickFileTransferSerializer(data=request.data)
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

        if result['success']:
            return SycResponse.success(content=result, message="文件传输已启动")
        else:
            return SycResponse.error(content=result, message=result['message'])

    def get_client_ip(self, request):
        """获取客户端IP地址"""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0]
        else:
            ip = request.META.get('REMOTE_ADDR')
        return ip
