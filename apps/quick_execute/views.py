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

        result = QuickExecuteService.transfer_file(
            user=request.user,
            transfer_data=serializer.validated_data,
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
