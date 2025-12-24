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
from apps.hosts.models import Host
from apps.hosts.fabric_ssh_manager import fabric_ssh_manager
from datetime import datetime
import re, shlex


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
        target_host_ids = data.get('target_host_ids') or []
        remote_path = data.get('remote_path') or ''
        max_matches = data.get('max_matches')
        timeout = data.get('timeout', 30)

        if not target_host_ids or not isinstance(target_host_ids, (list, tuple)):
            return SycResponse.validation_error(errors={'target_host_ids': '需要非空的目标主机ID列表'})
        if not remote_path:
            return SycResponse.validation_error(errors={'remote_path': '需要目标路径'})

        results = {}
        for hid in target_host_ids:
            try:
                host = Host.objects.get(id=hid)
            except Host.DoesNotExist:
                results[str(hid)] = {'error': 'host not found'}
                continue

            try:
                conn_info = fabric_ssh_manager._get_connection_info(host)
                with fabric_ssh_manager._create_connection(conn_info, timeout) as conn:
                    rendered = fabric_ssh_manager._render_path_variables(remote_path, now=datetime.now(), target_host=host)
                    if re.search(r'[\*\?\[]', rendered):
                        matches = fabric_ssh_manager._list_remote_matches(conn, rendered)
                    else:
                        # 检查路径是否存在
                        test = conn.run(f'test -e {shlex.quote(rendered)}', warn=True, hide=True)
                        matches = [rendered] if test.ok else []

                    # enforce max_matches if provided
                    if max_matches is not None:
                        try:
                            mm = int(max_matches)
                            if len(matches) > mm:
                                results[str(hid)] = {'error': f'matches ({len(matches)}) > max_matches ({mm})'}
                                continue
                        except Exception:
                            pass

                    results[str(hid)] = {'matches': matches}
            except Exception as e:
                results[str(hid)] = {'error': str(e)}

        return SycResponse.success(content={'matches': results}, message='预览完成')


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
