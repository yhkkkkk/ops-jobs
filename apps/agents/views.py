import logging
from django.conf import settings
from django.utils import timezone
from django_filters.rest_framework import DjangoFilterBackend
from guardian.shortcuts import get_objects_for_user
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.views import APIView
from rest_framework.parsers import MultiPartParser, FormParser

from utils.agent_server_client import AgentServerClient
from utils.audit_service import AuditLogService
from utils.responses import SycResponse
from apps.agents.execution_service import AgentExecutionService
from .filters import AgentFilter, InstallRecordFilter, UninstallRecordFilter
from .mixins import BatchOperationMixin
from .models import Agent, AgentInstallRecord, AgentToken, AgentUninstallRecord
from .pagination import AgentPagination
from .permissions import AgentPermission
from .serializers import (
    AgentControlSerializer,
    AgentDetailSerializer,
    AgentEnableSerializer,
    AgentInstallRecordSerializer,
    AgentSerializer,
    AgentTokenSerializer,
    BatchInstallSerializer,
    BatchOperationSerializer,
    BatchUninstallSerializer,
    GenerateInstallScriptSerializer,
    IssueTokenSerializer,
    AgentUninstallRecordSerializer,
)
from .services import AgentService
from .status import set_agent_status_cache, invalidate_agent_status_cache

logger = logging.getLogger(__name__)


class AgentViewSet(BatchOperationMixin, viewsets.ModelViewSet):
    """Agent 管理"""

    queryset = Agent.objects.select_related("host").prefetch_related("tokens", "host__groups")
    serializer_class = AgentSerializer
    permission_classes = [IsAuthenticated, AgentPermission]
    pagination_class = AgentPagination
    filter_backends = [DjangoFilterBackend]
    filterset_class = AgentFilter

    def get_filterset_class(self):
        if self.action == 'install_records':
            return InstallRecordFilter
        elif self.action == 'uninstall_records':
            return UninstallRecordFilter
        return self.filterset_class

    def get_queryset(self):
        """基于用户权限过滤查询集"""
        queryset = super().get_queryset()

        # 如果是超级用户，返回全部 Agent
        if self.request.user.is_superuser:
            return queryset.order_by('-created_at')

        # 检查用户是否有模型级别的 view_agent 权限
        if self.request.user.has_perm('agents.view_agent'):
            return queryset.select_related("host").prefetch_related("tokens", "host__groups").order_by('-created_at')

        # 否则，只返回具有对象级权限的 Agent
        from apps.hosts.models import Host
        allowed_hosts = get_objects_for_user(
            self.request.user,
            'view_host',
            klass=Host,
            accept_global_perms=False
        )
        return queryset.filter(host__in=allowed_hosts).order_by('-created_at')

    def get_serializer_class(self):
        if self.action == "retrieve":
            return AgentDetailSerializer
        if self.action == "generate_install_script":
            return GenerateInstallScriptSerializer
        if self.action == "batch_install":
            return BatchInstallSerializer
        if self.action == "batch_uninstall":
            return BatchUninstallSerializer
        if self.action == "install_records":
            return AgentInstallRecordSerializer
        if self.action == "uninstall_records":
            return AgentUninstallRecordSerializer
        return super().get_serializer_class()

    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            paginator = self.paginator
            return SycResponse.success(
                content={
                    "results": serializer.data,
                    "total": paginator.page.paginator.count,
                    "page": paginator.page.number,
                    "page_size": paginator.page_size,
                },
                message="获取agent列表成功",
            )
        serializer = self.get_serializer(queryset, many=True)
        return SycResponse.success(
            content={
                "results": serializer.data,
                "total": len(serializer.data),
                "page": 1,
                "page_size": len(serializer.data),
            },
            message="获取agent列表成功",
        )

    def retrieve(self, request, *args, **kwargs):
        agent = self.get_object()
        serializer = self.get_serializer(agent)
        return SycResponse.success(content=serializer.data, message="获取agent详情成功")

    @action(detail=False, methods=["get"], url_path="me")
    def me(self, request):
        """
        通过 token 获取当前 agent 信息（用于 agent 首次启动时获取自己的 ID）
        """
        # 从 Authorization header 读取 token
        auth_header = request.META.get('HTTP_AUTHORIZATION', '')
        if not auth_header.startswith('Bearer '):
            return SycResponse.error(message="缺少 Authorization Bearer token", code=401)
        token = auth_header.replace('Bearer ', '').strip()

        if not token:
            return SycResponse.error(message="token 不能为空", code=400)

        # 通过 token 查找 Agent
        from .models import AgentToken
        import hashlib

        token_hash = hashlib.sha256(token.encode('utf-8')).hexdigest()

        # 查找有效的 token
        agent_token = AgentToken.objects.filter(
            token_hash=token_hash,
            revoked_at__isnull=True
        ).first()

        if not agent_token:
            return SycResponse.error(message="token 无效或已吊销", code=403)

        # 检查 token 是否过期
        if agent_token.expired_at and agent_token.expired_at <= timezone.now():
            return SycResponse.error(message="token 已过期", code=403)

        agent = agent_token.agent

        # 更新 Agent 状态为 online（如果之前是 pending）
        if agent.status == 'pending':
            agent.status = 'online'
            agent.save(update_fields=['status', 'updated_at'])
            try:
                set_agent_status_cache(agent.id, 'online')
            except Exception:
                pass

        serializer = AgentDetailSerializer(agent)
        return SycResponse.success(
            content={
                'id': str(agent.host_id),  # Agent ID 就是 host_id
                'name': agent.host.name,
                'status': agent.status,
                **serializer.data
            },
            message="获取agent信息成功"
        )

    @action(detail=True, methods=["post"], url_path="issue_token")
    def issue_token(self, request, pk=None):
        agent = self.get_object()
        serializer = IssueTokenSerializer(data=request.data)
        if not serializer.is_valid():
            return SycResponse.validation_error(serializer.errors)
        # 高危操作需要二次确认
        if not serializer.validated_data.get("confirmed", False):
            return SycResponse.error(
                message="高危操作需要二次确认，请设置 confirmed=true",
                code=400
            )
        data = AgentService.issue_token(
            agent=agent,
            user=request.user,
            expired_at=serializer.validated_data.get("expired_at"),
            note=serializer.validated_data.get("note", ""),
        )
        AgentService.audit(request.user, "issue_agent_token", agent, request=request,
                           extra={"token_last4": data["token_last4"]})
        return SycResponse.success(
            content={"token": data["token"], "expired_at": data["expired_at"], "token_last4": data["token_last4"]},
            message="签发 agent token 成功（仅本次返回明文）",
        )

    @action(detail=True, methods=["post"], url_path="revoke_token")
    def revoke_token(self, request, pk=None):
        agent = self.get_object()
        # 高危操作需要二次确认
        confirmed = request.data.get("confirmed", False)
        if not confirmed:
            return SycResponse.error(
                message="高危操作需要二次确认，请设置 confirmed=true",
                code=400
            )
        ok = AgentService.revoke_active_token(agent)
        AgentService.audit(request.user, "revoke_agent_token", agent, request=request, success=ok)
        if not ok:
            return SycResponse.error(message="当前没有有效 token", code=404)
        return SycResponse.success(message="吊销agent token成功")

    @action(detail=True, methods=["post"], url_path="enable")
    def enable_agent(self, request, pk=None):
        agent = self.get_object()
        AgentService.enable_agent(agent)
        AgentService.audit(request.user, "enable_agent", agent, request=request)
        try:
            invalidate_agent_status_cache(agent.id)
        except Exception:
            pass
        return SycResponse.success(message="启用agent成功")

    @action(detail=True, methods=["post"], url_path="disable")
    def disable_agent(self, request, pk=None):
        agent = self.get_object()
        # 高危操作需要二次确认
        confirmed = request.data.get("confirmed", False)
        if not confirmed:
            return SycResponse.error(
                message="高危操作需要二次确认，请设置 confirmed=true",
                code=400
            )
        AgentService.disable_agent(agent)
        AgentService.audit(request.user, "disable_agent", agent, request=request)
        try:
            set_agent_status_cache(agent.id, 'disabled')
        except Exception:
            pass
        return SycResponse.success(message="禁用agent成功")

    # 辅助方法：构造Agent-Server基url
    def _normalize_server_url(self, raw_url: str) -> str:
        if not raw_url:
            return ""
        url = raw_url.replace("ws://", "http://").replace("wss://", "https://")
        if "://" in url:
            scheme_end = url.find("://") + 3
            slash_idx = url.find("/", scheme_end)
            if slash_idx != -1:
                url = url[:slash_idx]
        return url.rstrip("/")

    def _get_agent_server_base(self, agent, override_url: str = "") -> str:
        if override_url:
            return self._normalize_server_url(override_url)
        if agent.endpoint:
            return self._normalize_server_url(agent.endpoint)
        return ""

    @action(detail=True, methods=["get"], url_path="status")
    def status(self, request, pk=None):
        """获取agent运行状态，只返回agent-server实时数据（经 HMAC 客户端 + X-Scope）"""
        agent = self.get_object()
        server_base = self._get_agent_server_base(agent, request.query_params.get("agent_server_url", ""))

        if not server_base:
            return SycResponse.error(message="未配置agent-server，无法查询实时状态")

        api_url = f"{server_base}/api/agents/{agent.host_id}"
        # 使用统一的 Agent-Server HMAC 客户端，并按 Agent 设置 X-Scope
        client = AgentServerClient.from_settings()
        scope = AgentExecutionService._get_agent_server_scope(agent)
        headers = {"X-Scope": scope} if scope else {}

        try:
            resp = client.get(api_url, headers=headers, timeout=5)
            if resp.status_code == 200:
                return SycResponse.success(content=resp.json(), message="获取agent状态成功")
            logger.warning("查询agent状态失败 %s %s", resp.status_code, resp.text)
            return SycResponse.error(message=f"agent-server返回异常: HTTP {resp.status_code}")
        except Exception as exc:  # noqa: BLE001
            logger.error("查询agent状态异常 %s", exc, exc_info=True)
            return SycResponse.error(message=f"查询agent状态异常 {exc}")

    @action(detail=True, methods=["post"], url_path="control")
    def control(self, request, pk=None):
        """管控agent（start/stop/restart），调用agent-server控制接口（HMAC + X-Scope）"""
        agent = self.get_object()
        serializer = AgentControlSerializer(data=request.data)
        if not serializer.is_valid():
            return SycResponse.validation_error(serializer.errors)

        server_base = self._get_agent_server_base(agent, request.data.get("agent_server_url", ""))
        if not server_base:
            return SycResponse.error(message="未配置agent-server，无法下发控制指令")

        api_url = f"{server_base}/api/agents/{agent.host_id}/control"
        # 使用统一 HMAC 客户端，并附加 X-Scope
        client = AgentServerClient.from_settings()
        scope = AgentExecutionService._get_agent_server_scope(agent)
        headers = {}
        if scope:
            headers["X-Scope"] = scope

        payload = {
            "action": serializer.validated_data["action"],
            "reason": serializer.validated_data.get("reason", ""),
        }

        try:
            resp = client.post(api_url, json=payload, headers=headers, timeout=5)
            if resp.status_code == 200:
                AgentService.audit(request.user, f"control_agent_{payload['action']}", agent, request=request)
                return SycResponse.success(content=resp.json(), message="管控指令已下发")
            logger.error("管控agent失败 %s %s", resp.status_code, resp.text)
            return SycResponse.error(message=f"管控失败: HTTP {resp.status_code}")
        except Exception as exc:  # noqa: BLE001
            logger.error("管控agent异常: %s", exc, exc_info=True)
            return SycResponse.error(message=f"管控异常: {exc}")

    def destroy(self, request, *args, **kwargs):
        """删除agent（仅允许删除 pending 状态的 agent）"""
        agent = self.get_object()

        # 只允许删除 pending 状态的 Agent
        if agent.status != 'pending':
            return SycResponse.error(
                message=f"只能删除待激活状态的agent，当前状态为：{agent.get_status_display()}",
                code=400
            )

        # 高危操作需要二次确认
        confirmed = request.data.get("confirmed", False)
        if not confirmed:
            return SycResponse.error(
                message="高危操作需要二次确认，请设置 confirmed=true",
                code=400
            )

        host_name = agent.host.name
        host_id = agent.host_id
        agent_id = agent.id
        # 在删除前保存信息用于审计日志
        agent.delete()
        # 注意：agent 已删除，创建临时对象用于审计（仅用于类型校验）
        from .models import Agent
        temp_agent = Agent(id=agent_id, host_id=host_id)
        AgentService.audit(
            request.user,
            "delete_agent",
            temp_agent,
            request=request,
            success=True,
            extra={"host_name": host_name, "host_id": host_id, "agent_id": agent_id}
        )
        return SycResponse.success(message=f"agent ({host_name}) 删除成功")

    @action(detail=False, methods=["post"], url_path="batch_disable")
    def batch_disable(self, request):
        """批量禁用agent（带限流）"""
        serializer = BatchOperationSerializer(data=request.data)
        if not serializer.is_valid():
            return SycResponse.validation_error(serializer.errors)
        agent_ids = serializer.validated_data["agent_ids"]
        confirmed = serializer.validated_data.get("confirmed", False)
        if not confirmed:
            return SycResponse.error(
                message="批量高危操作需要二次确认，请设置 confirmed=true",
                code=400
            )
        # 批量操作限流：最多 50 个
        MAX_BATCH_SIZE = 50
        if len(agent_ids) > MAX_BATCH_SIZE:
            return SycResponse.error(
                message=f"批量操作最多支持{MAX_BATCH_SIZE}个agent",
                code=400
            )
        # 权限过滤
        queryset = self.get_queryset()
        allowed_agents = queryset.filter(id__in=agent_ids)
        if allowed_agents.count() != len(agent_ids):
            return SycResponse.error(
                message="部分agent无权限操作",
                code=403
            )
        # 生产额限制
        prod_agents = allowed_agents.filter(host__tags__icontains="prod")
        if prod_agents.exists() and len(agent_ids) > 10:
            return SycResponse.error(
                message="生产批量操作最多支持10个agent",
                code=400
            )
        count = 0
        for agent in allowed_agents:
            AgentService.disable_agent(agent)
            AgentService.audit(request.user, "disable_agent", agent, request=request)
            count += 1
        return SycResponse.success(
            content={"count": count},
            message=f"批量禁用{count}个agent成功"
        )

    @action(detail=False, methods=["post"], url_path="batch_enable")
    def batch_enable(self, request):
        """批量启用agent（带限流）"""
        serializer = BatchOperationSerializer(data=request.data)
        if not serializer.is_valid():
            return SycResponse.validation_error(serializer.errors)
        agent_ids = serializer.validated_data["agent_ids"]
        confirmed = serializer.validated_data.get("confirmed", False)
        if not confirmed:
            return SycResponse.error(
                message="批量高危操作需要二次确认，请设置 confirmed=true",
                code=400
            )
        # 批量操作限流：最多 50 个
        MAX_BATCH_SIZE = 50
        if len(agent_ids) > MAX_BATCH_SIZE:
            return SycResponse.error(
                message=f"批量操作最多支持{MAX_BATCH_SIZE}个agent",
                code=400
            )
        # 权限过滤
        queryset = self.get_queryset()
        allowed_agents = queryset.filter(id__in=agent_ids)
        if allowed_agents.count() != len(agent_ids):
            return SycResponse.error(
                message="部分agent无权限操作",
                code=403
            )
        # 生产额限制
        prod_agents = allowed_agents.filter(host__tags__icontains="prod")
        if prod_agents.exists() and len(agent_ids) > 10:
            return SycResponse.error(
                message="生产批量操作最多支持10个agent",
                code=400
            )
        count = 0
        for agent in allowed_agents:
            AgentService.enable_agent(agent)
            AgentService.audit(request.user, "enable_agent", agent, request=request)
            count += 1
        return SycResponse.success(
            content={"count": count},
            message=f"批量启用{count}个agent成功"
        )

    @action(detail=True, methods=["post"], url_path="regenerate_script")
    def regenerate_script(self, request, pk=None):
        """
        为指定agent重新生成安装脚本（用于 pending 状态的 agent）
        这是备用操作，用于用户生成脚本后没有复制也没有安装的场景
        """
        agent = self.get_object()

        # 只有 pending 状态的 Agent 才能重新生成脚本
        if agent.status != 'pending':
            return SycResponse.error(message="只有待激活状态的agent才能重新生成脚本", code=400)

        # 查找最新的安装记录
        install_record = AgentInstallRecord.objects.filter(
            agent=agent,
            host=agent.host
        ).order_by('-installed_at').first()

        if not install_record:
            return SycResponse.error(message="未找到安装记录，无法重新生成安装脚本", code=404)

        # 重新签发 token
        token_data = AgentService.issue_token(agent, request.user, note="重新生成安装脚本")
        agent_token = token_data['token']

        # 验证安装包是否存在
        package_id = install_record.package_id
        package_version = install_record.package_version

        # 如果安装记录中的 package_id/package_version 无效，尝试使用最新的可用包
        if package_id:
            from .models import AgentPackage
            try:
                package = AgentPackage.objects.get(id=package_id, is_active=True, package_type=install_record.install_type or 'agent')
            except AgentPackage.DoesNotExist:
                logger.warning(f"安装记录中的 package_id={package_id} 不存在或未启用，将尝试使用最新的可用包")
                package_id = None
                package_version = None

        if package_version and not package_id:
            from .models import AgentPackage
            os_type = agent.host.os_type.lower() if agent.host.os_type else 'linux'
            if 'windows' in os_type:
                os_type = 'windows'
            elif 'darwin' in os_type or 'macos' in os_type:
                os_type = 'darwin'
            else:
                os_type = 'linux'
            arch = 'amd64'
            try:
                package = AgentPackage.objects.get(
                    package_type=install_record.install_type or 'agent',
                    version=package_version,
                    os_type=os_type,
                    arch=arch,
                    is_active=True
                )
            except AgentPackage.DoesNotExist:
                logger.warning(
                    f"安装记录中的 package_version={package_version} (OS: {os_type}, Arch: {arch}) 不存在或未启用，将尝试使用最新的可用包"
                )
                package_version = None

        install_type = install_record.install_type or 'agent'
        # 计算 agent_server_url 及备用地址：安装记录 > 请求覆盖 > Agent.endpoint
        override_url = request.data.get("agent_server_url", "")
        agent_server_url = install_record.agent_server_url or self._get_agent_server_base(agent, override_url)
        agent_server_backup_url = ""
        if install_type == 'agent' and not agent_server_url:
            return SycResponse.error(message="未配置 agent_server_url，无法重新生成安装脚本", code=400)

        # 生成安装脚本
        try:
            host_scripts = AgentService.generate_install_script(
                host=agent.host,
                agent_token=agent_token,
                install_type=install_type,
                install_mode=install_record.install_mode,
                agent_server_url=agent_server_url,
                ws_backoff_initial_ms=install_record.ws_backoff_initial_ms,
                ws_backoff_max_ms=install_record.ws_backoff_max_ms,
                ws_max_retries=install_record.ws_max_retries,
                package_version=package_version,
                package_id=package_id,
            )
        except Exception as e:
            logger.error(f"为 Agent {agent.id} 重新生成脚本失败: {str(e)}", exc_info=True)
            return SycResponse.error(message=f"生成脚本失败: {str(e)}", code=500)

        # 格式化返回数据
        scripts = {}
        for os_type, script in host_scripts.items():
            if os_type not in scripts:
                scripts[os_type] = []
            scripts[os_type].append({
                'host_id': agent.host.id,
                'host_name': agent.host.name,
                'host_ip': agent.host.ip_address,
                'script': script,
                'agent_token': agent_token,
                'agent_id': agent.id,
            })

        return SycResponse.success(
            content={
                'scripts': scripts,
                'install_mode': install_record.install_mode,
                'agent_server_url': install_record.agent_server_url,
                'notice': '这是重新生成的安装脚本，旧的 token 已失效，请使用新的 token'
            },
            message="重新生成安脚本成功"
        )

    @action(detail=False, methods=["post"], url_path="generate_install_script")
    def generate_install_script(self, request):
        """生成安装脚本"""
        serializer = GenerateInstallScriptSerializer(data=request.data)
        if not serializer.is_valid():
            return SycResponse.validation_error(serializer.errors)

        data = serializer.validated_data
        host_ids = data['host_ids']
        install_type = data.get('install_type', 'agent')
        install_mode = data.get('install_mode', 'agent-server')
        agent_server_url = data.get('agent_server_url', '')
        agent_server_backup_url = ''
        ws_backoff_initial_ms = data.get('ws_backoff_initial_ms', 1000)
        ws_backoff_max_ms = data.get('ws_backoff_max_ms', 30000)
        ws_max_retries = data.get('ws_max_retries', 6)
        agent_server_listen_addr = data.get('agent_server_listen_addr', '0.0.0.0:8080')
        max_connections = data.get('max_connections', 1000)
        heartbeat_timeout = data.get('heartbeat_timeout', 60)
        package_version = data.get('package_version')
        package_id = data.get('package_id')
        package_type = 'agent' if install_type == 'agent' else 'agent-server'

        # 验证参数
        if install_type == 'agent' and not agent_server_url:
            return SycResponse.error(message="agent_server_url 不能为空（安装 Agent 需要）", code=400)
        if install_type == 'agent-server' and not agent_server_listen_addr:
            return SycResponse.error(message="agent_server_listen_addr 不能为空（安装 Agent-Server 需要）", code=400)

        # 获取主机列表
        from apps.hosts.models import Host
        hosts = Host.objects.filter(id__in=host_ids)

        if not hosts.exists():
            return SycResponse.error(message="未找到指定的主机", code=404)

        scripts = {}
        errors = []

        for host in hosts:
            try:
                # 先验证安装包是否存在（在生成脚本前验证）
                try:
                    AgentService.get_download_url(
                        host=host,
                        package_version=package_version,
                        package_id=package_id,
                        package_type=package_type,
                        raise_if_not_found=True,
                    )
                except ValueError as e:
                    errors.append(f"主机 {host.name} ({host.ip_address}): {str(e)}")
                    continue

                # 创建或获取 Agent（status='pending'），确保 agent_type 与前端选择一致
                agent, agent_created = Agent.objects.get_or_create(
                    host=host,
                    defaults={
                        'agent_type': install_type,
                        'status': 'pending',
                        'endpoint': agent_server_url or '',
                    }
                )
                try:
                    set_agent_status_cache(agent.id, 'pending')
                except Exception:
                    pass

                # 如果 Agent 已存在，更新状态、类型和配置
                if not agent_created:
                    # 保证 agent_type 与前端选择一致（支持 agent -> agent-server 的切换）
                    if agent.agent_type != install_type:
                        agent.agent_type = install_type
                    agent.status = 'pending'
                    agent.endpoint = agent_server_url or ''
                    agent.save(update_fields=['agent_type', 'status', 'endpoint', 'updated_at'])

                now = timezone.now()
                active_token = AgentToken.objects.filter(
                    agent=agent,
                    revoked_at__isnull=True,
                ).order_by('-created_at').first()
                if active_token and (not active_token.expired_at or active_token.expired_at > now):
                    last4 = active_token.token_last4 or '****'
                    errors.append(
                        f"主机 {host.name} ({host.ip_address}): 已有有效 token（尾号 {last4}），请在列表或安装记录中使用“重新生成脚本”获取新 token"
                    )
                    continue

                token_data = AgentService.issue_token(agent, request.user, note="生成安装脚本")
                agent_token = token_data['token']

                # 创建或更新安装记录
                install_record, created = AgentInstallRecord.objects.get_or_create(
                    host=host,
                    agent=agent,
                    status='pending',
                    defaults={
                        'install_type': install_type,
                        'install_mode': install_mode,
                        'agent_server_url': agent_server_url,
                        'agent_server_backup_url': '',
                        'ws_backoff_initial_ms': ws_backoff_initial_ms,
                        'ws_backoff_max_ms': ws_backoff_max_ms,
                        'ws_max_retries': ws_max_retries,
                        'agent_server_listen_addr': agent_server_listen_addr,
                        'max_connections': max_connections,
                        'heartbeat_timeout': heartbeat_timeout,
                        'package_id': package_id,
                        'package_version': package_version,
                        'installed_by': request.user,
                    }
                )
                if not created:
                    # 更新现有安装记录的配置，允许重新生成脚本
                    install_record.agent = agent
                    install_record.install_type = install_type
                    install_record.install_mode = install_mode
                    install_record.agent_server_url = agent_server_url
                    install_record.agent_server_backup_url = ''
                    install_record.ws_backoff_initial_ms = ws_backoff_initial_ms
                    install_record.ws_backoff_max_ms = ws_backoff_max_ms
                    install_record.ws_max_retries = ws_max_retries
                    install_record.agent_server_listen_addr = agent_server_listen_addr
                    install_record.max_connections = max_connections
                    install_record.heartbeat_timeout = heartbeat_timeout
                    install_record.package_id = package_id
                    install_record.package_version = package_version
                    install_record.status = 'pending'
                    install_record.save()

                # 生成安装脚本（使用 Agent Token）
                try:
                    host_scripts = AgentService.generate_install_script(
                        host=host,
                        agent_token=agent_token,
                        install_type=install_type,
                        install_mode=install_mode,
                        agent_server_url=agent_server_url,
                        ws_backoff_initial_ms=ws_backoff_initial_ms,
                        ws_backoff_max_ms=ws_backoff_max_ms,
                        ws_max_retries=ws_max_retries,
                        agent_server_listen_addr=agent_server_listen_addr,
                        max_connections=max_connections,
                        heartbeat_timeout=heartbeat_timeout,
                        package_version=package_version,
                        package_id=package_id,
                    )
                except Exception as e:
                    logger.error(
                        f"为主机 {host.name} 生成安装脚本失败: {str(e)}", exc_info=True
                    )
                    errors.append(
                        f"主机 {host.name} ({host.ip_address}): 生成脚本失败 - {str(e)}"
                    )
                    continue

                # 合并脚本（按操作系统分组）
                for os_type, script in host_scripts.items():
                    if os_type not in scripts:
                        scripts[os_type] = []
                    scripts[os_type].append({
                        'host_id': host.id,
                        'host_name': host.name,
                        'host_ip': host.ip_address,
                        'script': script,
                        'agent_token': agent_token,  # Agent Token
                        'agent_id': agent.id,  # Agent ID（用于重新生成脚本）
                        'install_record_id': install_record.id,
                    })
            except Exception as e:
                logger.error(f"处理主机 {host.name} 生成脚本异常: {str(e)}", exc_info=True)
                errors.append(f"主机 {host.name} ({host.ip_address}): 生成脚本失败 - {str(e)}")
                continue

        if errors:
            if not scripts:
                # 全部失败
                return SycResponse.error(
                    message="生成安装脚本失败",
                    code=400,
                    content={'errors': errors}
                )
            else:
                # 部分成功
                return SycResponse.success(
                    content={
                        'scripts': scripts,
                        'install_mode': install_mode,
                        'agent_server_url': agent_server_url,
                        'errors': errors,
                        'warning': '部分主机生成脚本失败，请查看 errors 字段'
                    },
                    message="生成安装脚本成功（部分主机失败）"
                )

        return SycResponse.success(
            content={
                'scripts': scripts,
                'install_mode': install_mode,
                'agent_server_url': agent_server_url,
                'notice': '这只是生成安装脚本，您需要手动在主机上执行脚本或使用"批量安装（SSH）"功能进行安装'
            },
            message="生成安装脚本成功（请手动执行脚本或使用批量安装功能）"
        )

    @action(detail=False, methods=["post"], url_path="batch_install")
    def batch_install(self, request):
        """批量安装 Agent（通过 SSH）"""
        serializer = BatchInstallSerializer(data=request.data)
        if not serializer.is_valid():
            return SycResponse.validation_error(serializer.errors)

        data = serializer.validated_data
        host_ids = data['host_ids']
        account_id = data.get('account_id')
        install_type = data.get('install_type', 'agent')
        install_mode = data.get('install_mode', install_type or 'agent-server')
        agent_server_url = data.get('agent_server_url', '')
        agent_server_backup_url = ''
        agent_server_listen_addr = data.get('agent_server_listen_addr', '0.0.0.0:8080')
        max_connections = data.get('max_connections', 1000)
        heartbeat_timeout = data.get('heartbeat_timeout', 60)
        package_version = data.get('package_version')
        package_id = data.get('package_id')
        confirmed = data.get('confirmed', False)
        ws_backoff_initial_ms = data.get('ws_backoff_initial_ms', 1000)
        ws_backoff_max_ms = data.get('ws_backoff_max_ms', 30000)
        ws_max_retries = data.get('ws_max_retries', 6)
        ssh_timeout = data.get('ssh_timeout', 300)
        allow_reinstall = data.get('allow_reinstall', False)

        if install_type == 'agent' and not agent_server_url:
            return SycResponse.error(message="agent_server_url 不能为空（安装 Agent 需要）", code=400)
        if install_type == 'agent-server' and not agent_server_listen_addr:
            return SycResponse.error(message="agent_server_listen_addr 不能为空（安装 Agent-Server 需要）", code=400)

        # 使用统一的批量操作校验
        is_valid, error_msg, hosts = self.validate_batch_operation_with_hosts(
            request=request,
            host_ids=host_ids,
            confirmed=confirmed,
        )
        if not is_valid:
            return SycResponse.error(message=error_msg, code=400)

        # 生成安任务ID
        import uuid
        from concurrent.futures import ThreadPoolExecutor

        install_task_id = str(uuid.uuid4())

        # 提前获取用户对象，避免在线程中访问 request
        user = request.user

        # 使用线程池异步执行批量安装
        def run_batch_install():
            """在后台线程中执行批量安装"""
            try:
                result = AgentService.batch_install_agents(
                    host_ids=host_ids,
                    user=user,
                    account_id=account_id,
                    install_type=install_type,
                    install_mode=install_mode,
                    agent_server_url=agent_server_url,
                    agent_server_listen_addr=agent_server_listen_addr,
                    max_connections=max_connections,
                    heartbeat_timeout=heartbeat_timeout,
                    install_task_id=install_task_id,
                    package_version=package_version,
                    package_id=package_id,
                    ws_backoff_initial_ms=ws_backoff_initial_ms,
                    ws_backoff_max_ms=ws_backoff_max_ms,
                    ws_max_retries=ws_max_retries,
                    ssh_timeout=ssh_timeout,
                    allow_reinstall=allow_reinstall
                )

                # 记录审日志
                for install_result in result['results']:
                    if install_result['success'] and install_result.get('agent_id'):
                        try:
                            agent = Agent.objects.get(id=install_result['agent_id'])
                            AgentService.audit(
                                user,
                                "install_agent",
                                agent,
                                request=None,  # 后台线程中没有 request 对象
                                success=True,
                                extra={'host_id': install_result['host_id'], 'host_name': install_result['host_name']}
                            )
                        except Agent.DoesNotExist:
                            logger.warning(f"Agent {install_result.get('agent_id')} 不存圼跳过审日志")

                logger.info(
                    f"批量安装任务完成: install_task_id={install_task_id}, 成功={result['success_count']}, 失败={result['failed_count']}")

            except Exception as e:
                logger.error(f"批量安装任务失败: install_task_id={install_task_id}, 错误={str(e)}", exc_info=True)
                # 推送错误状态
                from utils.realtime_logs import realtime_log_service
                realtime_log_service.push_status(install_task_id, {
                    'status': 'error',
                    'message': f'批量安装任务失败: {str(e)}'
                })

        # 在线程池中
        executor = ThreadPoolExecutor(max_workers=1)
        executor.submit(run_batch_install)
        executor.shutdown(wait=False)  # 不等待任务完成，立即返回

        logger.info(f"批量安装任务已启动: install_task_id={install_task_id}")

        return SycResponse.success(
            content={
                'install_task_id': install_task_id,  # 返回任务ID用于前端连接sse
                'total': len(host_ids),
                'status': 'running'
            },
            message=f"批量安装已启动，正在后台执行，可通过install_task_id连接sse查看实时进度"
        )

    @action(detail=False, methods=["post"], url_path="batch_uninstall")
    def batch_uninstall(self, request):
        """批量卸载 Agent（通过 SSH）"""
        serializer = BatchUninstallSerializer(data=request.data)
        if not serializer.is_valid():
            return SycResponse.validation_error(serializer.errors)

        data = serializer.validated_data
        agent_ids = data['agent_ids']
        account_id = data.get('account_id')
        confirmed = data.get('confirmed', False)

        # 权限过滤
        allowed_agents = self.get_queryset().filter(id__in=agent_ids).select_related('host')
        if allowed_agents.count() != len(agent_ids):
            return SycResponse.error(message="部分agent无权限操作", code=403)

        # 使用统一的批量操作校验
        is_valid, error_msg, _ = self.validate_batch_operation_with_agents(
            request=request,
            agent_ids=agent_ids,
            confirmed=confirmed,
        )
        if not is_valid:
            return SycResponse.error(message=error_msg, code=400)

        import uuid
        from concurrent.futures import ThreadPoolExecutor

        uninstall_task_id = str(uuid.uuid4())
        user = request.user

        def run_batch_uninstall():
            try:
                result = AgentService.batch_uninstall_agents(
                    agent_ids=agent_ids,
                    user=user,
                    account_id=account_id,
                    uninstall_task_id=uninstall_task_id
                )

                # 审日志
                for uninstall_result in result.get('results', []):
                    agent_id = uninstall_result.get('agent_id')
                    if not agent_id:
                        continue
                    try:
                        agent = Agent.objects.get(id=agent_id)
                        AgentService.audit(
                            user,
                            "uninstall_agent",
                            agent,
                            request=None,
                            success=bool(uninstall_result.get('success')),
                            error_message='' if uninstall_result.get('success') else uninstall_result.get('message',
                                                                                                          ''),
                            extra={
                                'host_id': uninstall_result.get('host_id'),
                                'host_name': uninstall_result.get('host_name'),
                            }
                        )
                    except Agent.DoesNotExist:
                        logger.warning(f"Agent {agent_id} 不存圼跳过审日志")

                logger.info(
                    f"批量卸载任务完成: uninstall_task_id={uninstall_task_id}, 成功={result.get('success_count')}, 失败={result.get('failed_count')}"
                )
            except Exception as e:
                logger.error(f"批量卸载任务失败: uninstall_task_id={uninstall_task_id}, 错={str(e)}", exc_info=True)
                from utils.realtime_logs import realtime_log_service
                realtime_log_service.push_status(uninstall_task_id, {
                    'status': 'error',
                    'message': f'批量卸载任务失败: {str(e)}'
                })

        executor = ThreadPoolExecutor(max_workers=1)
        executor.submit(run_batch_uninstall)
        executor.shutdown(wait=False)

        logger.info(f"批量卸载任务已启动: uninstall_task_id={uninstall_task_id}")

        return SycResponse.success(
            content={
                'results': [],
                'total': len(agent_ids),
                'success_count': 0,
                'failed_count': 0,
                'uninstall_task_id': uninstall_task_id,
                'status': 'running'
            },
            message="批量卸载已启劼正在后台执，可通过uninstall_task_id连接sse查看实时进度"
        )

    @action(detail=False, methods=["get"], url_path="install_records")
    def install_records(self, request):
        """查安记录"""
        queryset = AgentInstallRecord.objects.select_related('host', 'agent', 'installed_by').order_by('-installed_at')

        # 权限过滤
        if not request.user.is_superuser:
            allowed_hosts = get_objects_for_user(
                request.user,
                'view_host',
                accept_global_perms=False
            )
            queryset = queryset.filter(host__in=allowed_hosts)

        # 应用过滤器（使用专门的FilterSet）
        filterset_class = self.get_filterset_class()
        if filterset_class:
            filterset = filterset_class(request.query_params, queryset=queryset)
            queryset = filterset.qs

        # 分页与序列化
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            paginator = self.paginator
            return SycResponse.success(
                content={
                    "results": serializer.data,
                    "total": paginator.page.paginator.count,
                    "page": paginator.page.number,
                    "page_size": paginator.page_size,
                },
                message="获取安记录成功",
            )

        serializer = self.get_serializer(queryset, many=True)
        return SycResponse.success(
            content={
                "results": serializer.data,
                "total": len(serializer.data),
                "page": 1,
                "page_size": len(serializer.data),
            },
            message="获取安记录成功",
        )

    @action(detail=False, methods=["get"], url_path="uninstall_records")
    def uninstall_records(self, request):
        """查卸载记录"""
        queryset = AgentUninstallRecord.objects.select_related('host', 'agent', 'uninstalled_by').order_by(
            '-uninstalled_at')

        # 权限过滤（基于 Host 权限）
        if not request.user.is_superuser:
            allowed_hosts = get_objects_for_user(
                request.user,
                'view_host',
                accept_global_perms=False
            )
            queryset = queryset.filter(host__in=allowed_hosts)

        # 应用过滤器
        filterset_class = self.get_filterset_class()
        if filterset_class:
            filterset = filterset_class(request.query_params, queryset=queryset)
            queryset = filterset.qs

        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            paginator = self.paginator
            return SycResponse.success(
                content={
                    "results": serializer.data,
                    "total": paginator.page.paginator.count,
                    "page": paginator.page.number,
                    "page_size": paginator.page_size,
                },
                message="获取卸载记录成功",
            )

        serializer = self.get_serializer(queryset, many=True)
        return SycResponse.success(
            content={
                "results": serializer.data,
                "total": len(serializer.data),
                "page": 1,
                "page_size": len(serializer.data),
            },
            message="获取卸载记录成功",
        )

    @action(detail=False, methods=["get"], url_path="download_urls")
    def download_urls(self, request):
        """获取agent二进制下载地"""
        from .models import AgentPackage

        # 优先使用版本管理
        default_packages = AgentPackage.objects.filter(is_default=True, is_active=True, package_type='agent')

        if default_packages.exists():
            # 从版理获取下载地
            download_urls = {}
            for package in default_packages:
                if package.os_type not in download_urls:
                    download_urls[package.os_type] = {}
                download_urls[package.os_type][package.arch] = package.get_download_url()

            # 获取版本号（取主认包的版朼
            version = default_packages.first().version if default_packages else 'latest'

            return SycResponse.success(
                content={
                    'download_urls': download_urls,
                    'version': version,
                    'base_url': '',
                    'from_package_version': True
                },
                message="获取下载地址成功"
            )

        return SycResponse.error(message="未找到可用的agent包", code=404)


class ArtifactUploadView(APIView):
    """制品上传（供前端直接上传本地文件到对象存储并返回 metadata）"""
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]

    def post(self, request):
        """
        接收 multipart/form-data 的文件上传，参数:
        - file: 上传的文件（必需）
        - storage_path (可选): 希望存储的路径（若不提供则后端生成）
        返回:
        {
          'storage_path': 'path/in/storage',
          'download_url': 'https://...',
          'checksum': 'sha256hex',
          'size': 12345
        }
        """
        try:
            uploaded_file = request.FILES.get('file')
            if not uploaded_file:
                return SycResponse.error(message="缺少上传文件字 'file'")

            storage_path = request.data.get('storage_path')

            # 获取默存储后
            from apps.agents.storage_service import StorageService
            from apps.system_config.models import ConfigManager
            import hashlib
            import uuid

            default_storage_type = ConfigManager.get('storage.type', 'local')
            storage_backend = StorageService.get_backend(default_storage_type)
            if not storage_backend:
                return SycResponse.error(message=f"无法初始化存储后端 {default_storage_type}")

            # 生成存储路径如果未指定
            if not storage_path:
                user_id = request.user.id if request.user and hasattr(request.user, 'id') else 'anonymous'
                storage_path = f"uploads/{user_id}/{uuid.uuid4().hex}/{uploaded_file.name}"

            # 计算 sha256 和大小
            uploaded_file.seek(0)
            file_content = uploaded_file.read()
            sha256_hex = hashlib.sha256(file_content).hexdigest()
            size = uploaded_file.size
            uploaded_file.seek(0)

            success, err = storage_backend.upload_file(uploaded_file, storage_path)
            if not success:
                return SycResponse.error(message=f"上传到对象存储失败: {err}")

            download_url = None
            try:
                download_url = storage_backend.generate_url(storage_path, expires_in=3600)
            except Exception:
                download_url = None

            # auth_headers: 留空或由存储后端扩展以支持需要额外 Header 的对象存储
            auth_headers = {}
            return SycResponse.success(content={
                'storage_path': storage_path,
                'download_url': download_url,
                'checksum': sha256_hex,
                'size': size,
                'auth_headers': auth_headers,
            }, message="文件已上传到制品库")
        except Exception as exc:
            logger.exception("制品上传失败")
            return SycResponse.error(message=f"制品上传失败: {str(exc)}")
