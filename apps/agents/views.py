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
from apps.agents.status_reconciliation_service import status_reconciliation_service
from .filters import AgentFilter, InstallRecordFilter, UninstallRecordFilter
from .mixins import BatchOperationMixin
from .models import Agent, AgentInstallRecord, AgentToken, AgentUninstallRecord, AgentServer
from .pagination import AgentPagination
from .permissions import AgentPermission
from .serializers import (
    AgentControlSerializer,
    AgentDetailSerializer,
    AgentEnableSerializer,
    AgentInstallRecordSerializer,
    AgentSerializer,
    AgentTokenSerializer,
    AgentUpgradeSerializer,
    AgentUpdateServerSerializer,
    BatchInstallSerializer,
    BatchOperationSerializer,
    BatchUninstallSerializer,
    GenerateInstallScriptSerializer,
    IssueTokenSerializer,
    AgentUninstallRecordSerializer,
)
from .services import AgentService
from .status import set_agent_status_cache, invalidate_agent_status_cache
from .utils import build_agent_server_netloc_map, resolve_agent_server_from_url, normalize_agent_server_base_url

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

        # 预取 task_stats 关联
        queryset = queryset.prefetch_related('task_stats')

        # 如果是超级用户，返回全部 Agent
        if self.request.user.is_superuser:
            return queryset.order_by('-created_at')

        # 检查用户是否有模型级别的 view_agent 权限
        if self.request.user.has_perm('agents.view_agent'):
            return queryset.select_related("host").prefetch_related("tokens", "host__groups", "task_stats").order_by('-created_at')

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

    @action(detail=True, methods=["post"], url_path="update_agent_server")
    def update_agent_server(self, request, pk=None):
        agent = self.get_object()
        serializer = AgentUpdateServerSerializer(data=request.data)
        if not serializer.is_valid():
            return SycResponse.validation_error(serializer.errors)

        agent_server_id = serializer.validated_data.get("agent_server_id")
        if agent_server_id is None:
            server = None
        else:
            server = AgentServer.objects.filter(id=agent_server_id, is_active=True).first()
            if not server:
                return SycResponse.error(message="Agent-Server不存在或已禁用", code=404)

        old_agent_server_id = agent.agent_server_id
        new_agent_server_id = server.id if server else None
        if old_agent_server_id == new_agent_server_id:
            return SycResponse.success(
                content={"id": agent.id, "agent_server_id": old_agent_server_id},
                message="Agent-Server 未发生变更"
            )

        agent.agent_server = server
        agent.save(update_fields=["agent_server", "updated_at"])
        AgentService.audit(
            request.user,
            "update_agent_server",
            agent,
            request=request,
            extra={"old_agent_server_id": old_agent_server_id, "new_agent_server_id": new_agent_server_id}
        )
        return SycResponse.success(
            content={"id": agent.id, "agent_server_id": new_agent_server_id},
            message="更新Agent关联Agent-Server成功"
        )

    def _resolve_agent_server(self, request):
        server_id = request.data.get("agent_server_id") or request.query_params.get("agent_server_id")
        if not server_id:
            return None, "请先选择Agent-Server"
        server = AgentServer.objects.filter(id=server_id, is_active=True).first()
        if not server:
            return None, "Agent-Server不存在或已禁用"
        return server, ""

    def _upsert_agent_server_from_base_url(self, base_url: str, auth_shared_secret: str = '', auth_require_signature: bool | None = None):
        normalized = normalize_agent_server_base_url(base_url)
        if not normalized:
            return None
        from urllib.parse import urlparse
        netloc = urlparse(normalized).netloc
        display_name = netloc or normalized

        server = AgentServer.objects.filter(base_url=normalized).first()
        if not server:
            return AgentServer.objects.create(
                name=display_name,
                base_url=normalized,
                shared_secret=auth_shared_secret or '',
                require_signature=bool(auth_require_signature)
            )

        update_fields = []
        if auth_shared_secret:
            server.shared_secret = auth_shared_secret
            update_fields.append('shared_secret')
        if auth_require_signature is not None and server.require_signature != bool(auth_require_signature):
            server.require_signature = bool(auth_require_signature)
            update_fields.append('require_signature')
        if not server.name:
            server.name = display_name
            update_fields.append('name')
        if update_fields:
            server.save(update_fields=update_fields)
        return server

    @action(detail=True, methods=["get"], url_path="status")
    def status(self, request, pk=None):
        """获取agent运行状态，只返回agent-server实时数据（经 HMAC 客户端）"""
        agent = self.get_object()
        server, err = self._resolve_agent_server(request)
        if not server:
            return SycResponse.error(message=err)
        if not server.shared_secret:
            return SycResponse.error(message="Agent-Server未配置shared_secret")

        api_url = f"{server.base_url}/api/agents/{agent.host_id}"
        client = AgentServerClient(shared_secret=server.shared_secret)

        try:
            resp = client.get(api_url, timeout=5)
            if resp.status_code == 200:
                return SycResponse.success(content=resp.json(), message="获取agent状态成功")
            logger.warning("查询agent状态失败 %s %s", resp.status_code, resp.text)
            return SycResponse.error(message=f"agent-server返回异常: HTTP {resp.status_code}")
        except Exception as exc:  # noqa: BLE001
            logger.error("查询agent状态异常 %s", exc, exc_info=True)
            return SycResponse.error(message=f"查询agent状态异常 {exc}")

    @action(detail=True, methods=["post"], url_path="control")
    def control(self, request, pk=None):
        """管控agent（start/stop/restart），调用agent-server控制接口（HMAC）"""
        agent = self.get_object()
        serializer = AgentControlSerializer(data=request.data)
        if not serializer.is_valid():
            return SycResponse.validation_error(serializer.errors)

        action = serializer.validated_data["action"]
        reason = serializer.validated_data.get("reason", "")
        agent_type = agent.agent_type or 'agent'

        # 根据 agent_type 选择不同的控制方式
        if agent_type == 'agent':
            # Agent 控制：通过 agent-server 下发控制指令
            server, err = self._resolve_agent_server(request)
            if not server:
                return SycResponse.error(message=err)
            if not server.shared_secret:
                return SycResponse.error(message="Agent-Server未配置shared_secret")

            api_url = f"{server.base_url}/api/agents/{agent.host_id}/control"
            client = AgentServerClient(shared_secret=server.shared_secret)

            payload = {
                "action": action,
                "reason": reason,
            }

            try:
                resp = client.post(api_url, json=payload, timeout=5)
                if resp.status_code == 200:
                    AgentService.audit(request.user, f"control_agent_{action}", agent, request=request)
                    return SycResponse.success(content=resp.json(), message="管控指令已下发")
                logger.error("管控agent失败 %s %s", resp.status_code, resp.text)
                return SycResponse.error(message=f"管控失败: HTTP {resp.status_code}")
            except Exception as exc:  # noqa: BLE001
                logger.error("管控agent异常: %s", exc, exc_info=True)
                return SycResponse.error(message=f"管控异常: {exc}")

        elif agent_type == 'agent-server':
            # Agent-Server 控制：调用 agent-server 自身的控制接口
            server, err = self._resolve_agent_server(request)
            if not server:
                return SycResponse.error(message=err or "Agent-Server 未配置 endpoint，无法下发控制指令")
            if not server.shared_secret:
                return SycResponse.error(message="Agent-Server未配置shared_secret")

            api_url = f"{server.base_url}/api/self/control"
            client = AgentServerClient(shared_secret=server.shared_secret)

            payload = {
                "action": action,
                "reason": reason,
            }

            try:
                resp = client.post(api_url, json=payload, headers={}, timeout=5)
                if resp.status_code == 200:
                    AgentService.audit(request.user, f"control_agent_server_{action}", agent, request=request)
                    return SycResponse.success(content=resp.json(), message="管控指令已下发")
                logger.error("管控agent-server失败 %s %s", resp.status_code, resp.text)
                return SycResponse.error(message=f"管控失败: HTTP {resp.status_code}")
            except Exception as exc:  # noqa: BLE001
                logger.error("管控agent-server异常: %s", exc, exc_info=True)
                return SycResponse.error(message=f"管控异常: {exc}")

        else:
            return SycResponse.error(message=f"不支持的 agent_type: {agent_type}")

    @action(detail=True, methods=["post"], url_path="upgrade")
    def upgrade_agent(self, request, pk=None):
        """升级 Agent 到指定版本"""
        agent = self.get_object()
        serializer = AgentUpgradeSerializer(data=request.data)
        if not serializer.is_valid():
            return SycResponse.validation_error(serializer.errors)

        # 检查 Agent 是否在线
        if agent.status != 'online' and agent.computed_status != 'online':
            return SycResponse.error(message="只能升级在线状态的 Agent")

        # 确定目标安装包（根据 agent_type 选择对应的 package_type）
        package_id = serializer.validated_data.get("package_id")
        target_version = serializer.validated_data.get("target_version", "")
        package_type = agent.agent_type or 'agent'  # 使用 agent 的类型

        try:
            from apps.agents.models import AgentPackage

            if package_id:
                # 通过 package_id 查找
                package = AgentPackage.objects.filter(
                    id=package_id,
                    is_active=True,
                    package_type=package_type,
                    os_type=agent.host.os_type
                ).first()
                if not package:
                    return SycResponse.error(message=f"指定的 {agent.get_agent_type_display()} 安装包不存在或不可用")
            elif target_version:
                # 通过 version 查找
                package = AgentPackage.objects.filter(
                    version=target_version,
                    is_active=True,
                    package_type=package_type,
                    os_type=agent.host.os_type
                ).first()
                if not package:
                    return SycResponse.error(message=f"未找到 {agent.get_agent_type_display()} 版本 {target_version} 的安装包")
            else:
                # 使用默认版本（最新版本）
                package = AgentPackage.objects.filter(
                    is_default=True,
                    is_active=True,
                    package_type=package_type,
                    os_type=agent.host.os_type
                ).first()
                if not package:
                    return SycResponse.error(message=f"未找到 {agent.get_agent_type_display()} 的默认安装包")

            # 检查版本是否相同
            if agent.version == package.version:
                return SycResponse.error(message=f"{agent.get_agent_type_display()} 已是目标版本 {package.version}")

            # 根据 agent_type 选择不同的升级方式
            if package_type == 'agent':
                # Agent 升级：通过 agent-server 下发升级指令
                server, err = self._resolve_agent_server(request)
                if not server:
                    return SycResponse.error(message=err)
                if not server.shared_secret:
                    return SycResponse.error(message="Agent-Server未配置shared_secret")

                api_url = f"{server.base_url}/api/agents/{agent.host_id}/upgrade"
                client = AgentServerClient(shared_secret=server.shared_secret)

                payload = {
                    "target_version": package.version,
                    "download_url": package.download_url,
                    "md5_hash": package.md5_hash,
                    "sha256_hash": package.sha256_hash,
                }

                resp = client.post(api_url, json=payload, timeout=10)
                if resp.status_code == 200:
                    AgentService.audit(
                        request.user,
                        "upgrade_agent",
                        agent,
                        request=request,
                        extra_data={"from_version": agent.version, "to_version": package.version}
                    )
                    return SycResponse.success(
                        content=resp.json(),
                        message=f"升级指令已下发，Agent 将从 {agent.version} 升级到 {package.version}"
                    )
                logger.error("升级 agent 失败 %s %s", resp.status_code, resp.text)
                return SycResponse.error(message=f"升级失败: HTTP {resp.status_code}")

            elif package_type == 'agent-server':
                # Agent-Server 升级：直接调用 agent-server 自身的升级接口
                server, err = self._resolve_agent_server(request)
                if not server:
                    return SycResponse.error(message=err or "Agent-Server 未配置 endpoint，无法下发升级指令")
                if not server.shared_secret:
                    return SycResponse.error(message="Agent-Server未配置shared_secret")

                api_url = f"{server.base_url}/api/self/upgrade"
                client = AgentServerClient(shared_secret=server.shared_secret)

                payload = {
                    "target_version": package.version,
                    "download_url": package.download_url,
                    "md5_hash": package.md5_hash,
                    "sha256_hash": package.sha256_hash,
                }

                resp = client.post(api_url, json=payload, headers={}, timeout=10)
                if resp.status_code == 200:
                    AgentService.audit(
                        request.user,
                        "upgrade_agent_server",
                        agent,
                        request=request,
                        extra_data={"from_version": agent.version, "to_version": package.version}
                    )
                    return SycResponse.success(
                        content=resp.json(),
                        message=f"升级指令已下发，Agent-Server 将从 {agent.version} 升级到 {package.version}"
                    )
                logger.error("升级 agent-server 失败 %s %s", resp.status_code, resp.text)
                return SycResponse.error(message=f"升级失败: HTTP {resp.status_code}")

            else:
                return SycResponse.error(message=f"不支持的 agent_type: {package_type}")

        except Exception as exc:  # noqa: BLE001
            logger.error("升级 agent 异常: %s", exc, exc_info=True)
            return SycResponse.error(message=f"升级异常: {exc}")

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

    @action(detail=False, methods=["post"], url_path="batch_restart")
    def batch_restart(self, request):
        """批量重启 Agent（带SSE进度监控）"""
        serializer = BatchOperationSerializer(data=request.data)
        if not serializer.is_valid():
            return SycResponse.validation_error(serializer.errors)

        data = serializer.validated_data
        agent_ids = data['agent_ids']
        confirmed = data.get('confirmed', False)
        agent_server_id = data.get('agent_server_id')
        if not agent_server_id:
            return SycResponse.error(message="请先选择Agent-Server", code=400)

        # 使用统一的批量操作校验
        is_valid, error_msg, agents = self.validate_batch_operation_with_agents(
            request=request,
            agent_ids=agent_ids,
            confirmed=confirmed,
        )
        if not is_valid:
            return SycResponse.error(message=error_msg, code=400)

        import uuid
        from utils.thread_pool import get_global_thread_pool

        batch_task_id = str(uuid.uuid4())
        user = request.user

        def run_batch_restart():
            """在后台线程中执行批量重启"""
            try:
                result = AgentService.batch_restart_agents(
                    agent_ids=[a.id for a in agents],
                    user=user,
                    batch_task_id=batch_task_id,
                    agent_server_id=agent_server_id,
                )

                # 记录审计日志
                for restart_result in result.get('results', []):
                    if restart_result.get('success') and restart_result.get('agent_id'):
                        try:
                            agent = Agent.objects.get(id=restart_result['agent_id'])
                            AgentService.audit(
                                user,
                                "restart_agent",
                                agent,
                                request=None,  # 后台线程中没有 request 对象
                                success=True,
                                extra={'host_id': restart_result.get('host_id'), 'host_name': restart_result.get('host_name')}
                            )
                        except Agent.DoesNotExist:
                            logger.warning(f"Agent {restart_result.get('agent_id')} 不存在，跳过审计日志")

                logger.info(
                    f"批量重启任务完成: batch_task_id={batch_task_id}, 成功={result.get('success_count')}, 失败={result.get('failed_count')}"
                )
            except Exception as e:
                logger.error(f"批量重启任务失败: batch_task_id={batch_task_id}, 错误={str(e)}", exc_info=True)
                # 推送错误状态
                from utils.realtime_logs import realtime_log_service
                realtime_log_service.push_status(batch_task_id, {
                    'status': 'error',
                    'message': f'批量重启任务失败: {str(e)}'
                })

        # 使用全局线程池提交后台任务
        pool = get_global_thread_pool()
        pool.submit(run_batch_restart)

        logger.info(f"批量重启任务已启动: batch_task_id={batch_task_id}")

        return SycResponse.success(
            content={
                'batch_task_id': batch_task_id,
                'total': len(agent_ids),
                'status': 'running'
            },
            message="批量重启已启动，正在后台执行，可通过 batch_task_id 连接 SSE 查看实时进度"
        )

    @action(detail=False, methods=["post"], url_path="batch_disable_v2")
    def batch_disable_v2(self, request):
        """批量禁用 Agent（带SSE进度监控）"""
        serializer = BatchOperationSerializer(data=request.data)
        if not serializer.is_valid():
            return SycResponse.validation_error(serializer.errors)

        data = serializer.validated_data
        agent_ids = data['agent_ids']
        confirmed = data.get('confirmed', False)

        # 使用统一的批量操作校验
        is_valid, error_msg, agents = self.validate_batch_operation_with_agents(
            request=request,
            agent_ids=agent_ids,
            confirmed=confirmed,
        )
        if not is_valid:
            return SycResponse.error(message=error_msg, code=400)

        import uuid
        from utils.thread_pool import get_global_thread_pool

        batch_task_id = str(uuid.uuid4())
        user = request.user

        def run_batch_disable():
            """在后台线程中执行批量禁用"""
            try:
                result = AgentService.batch_disable_agents(
                    agent_ids=[a.id for a in agents],
                    user=user,
                    batch_task_id=batch_task_id
                )

                logger.info(
                    f"批量禁用任务完成: batch_task_id={batch_task_id}, 成功={result.get('success_count')}, 失败={result.get('failed_count')}"
                )
            except Exception as e:
                logger.error(f"批量禁用任务失败: batch_task_id={batch_task_id}, 错误={str(e)}", exc_info=True)
                # 推送错误状态
                from utils.realtime_logs import realtime_log_service
                realtime_log_service.push_status(batch_task_id, {
                    'status': 'error',
                    'message': f'批量禁用任务失败: {str(e)}'
                })

        # 使用全局线程池提交后台任务
        pool = get_global_thread_pool()
        pool.submit(run_batch_disable)

        logger.info(f"批量禁用任务已启动: batch_task_id={batch_task_id}")

        return SycResponse.success(
            content={
                'batch_task_id': batch_task_id,
                'total': len(agent_ids),
                'status': 'running'
            },
            message="批量禁用已启动，正在后台执行，可通过 batch_task_id 连接 SSE 查看实时进度"
        )

    @action(detail=False, methods=["post"], url_path="batch_enable_v2")
    def batch_enable_v2(self, request):
        """批量启用 Agent（带SSE进度监控）"""
        serializer = BatchOperationSerializer(data=request.data)
        if not serializer.is_valid():
            return SycResponse.validation_error(serializer.errors)

        data = serializer.validated_data
        agent_ids = data['agent_ids']
        confirmed = data.get('confirmed', False)

        # 使用统一的批量操作校验
        is_valid, error_msg, agents = self.validate_batch_operation_with_agents(
            request=request,
            agent_ids=agent_ids,
            confirmed=confirmed,
        )
        if not is_valid:
            return SycResponse.error(message=error_msg, code=400)

        import uuid
        from utils.thread_pool import get_global_thread_pool

        batch_task_id = str(uuid.uuid4())
        user = request.user

        def run_batch_enable():
            """在后台线程中执行批量启用"""
            try:
                result = AgentService.batch_enable_agents(
                    agent_ids=[a.id for a in agents],
                    user=user,
                    batch_task_id=batch_task_id
                )

                logger.info(
                    f"批量启用任务完成: batch_task_id={batch_task_id}, 成功={result.get('success_count')}, 失败={result.get('failed_count')}"
                )
            except Exception as e:
                logger.error(f"批量启用任务失败: batch_task_id={batch_task_id}, 错误={str(e)}", exc_info=True)
                # 推送错误状态
                from utils.realtime_logs import realtime_log_service
                realtime_log_service.push_status(batch_task_id, {
                    'status': 'error',
                    'message': f'批量启用任务失败: {str(e)}'
                })

        # 使用全局线程池提交后台任务
        pool = get_global_thread_pool()
        pool.submit(run_batch_enable)

        logger.info(f"批量启用任务已启动: batch_task_id={batch_task_id}")

        return SycResponse.success(
            content={
                'batch_task_id': batch_task_id,
                'total': len(agent_ids),
                'status': 'running'
            },
            message="批量启用已启动，正在后台执行，可通过 batch_task_id 连接 SSE 查看实时进度"
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
        if install_type == 'agent' and agent_server_url:
            resolved_server = resolve_agent_server_from_url(agent_server_url)
            if resolved_server and agent.agent_server_id != resolved_server.id:
                agent.agent_server_id = resolved_server.id
                agent.save(update_fields=['agent_server_id', 'updated_at'])

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
                # 最大并发任务数（从安装记录获取）
                max_concurrent_tasks=install_record.max_concurrent_tasks if hasattr(install_record, 'max_concurrent_tasks') else None,
                # agent-server WebSocket 配置
                ws_handshake_timeout=install_record.ws_handshake_timeout if hasattr(install_record, 'ws_handshake_timeout') else None,
                ws_read_buffer_size=install_record.ws_read_buffer_size if hasattr(install_record, 'ws_read_buffer_size') else None,
                ws_write_buffer_size=install_record.ws_write_buffer_size if hasattr(install_record, 'ws_write_buffer_size') else None,
                ws_enable_compression=install_record.ws_enable_compression if hasattr(install_record, 'ws_enable_compression') else True,
                ws_allowed_origins=install_record.ws_allowed_origins if hasattr(install_record, 'ws_allowed_origins') else None,
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
        # agent-server WebSocket 配置
        ws_handshake_timeout = data.get('ws_handshake_timeout', '10s')
        ws_read_buffer_size = data.get('ws_read_buffer_size', 4096)
        ws_write_buffer_size = data.get('ws_write_buffer_size', 4096)
        ws_enable_compression = data.get('ws_enable_compression', True)
        ws_allowed_origins = data.get('ws_allowed_origins', [])
        agent_server_base_url = data.get('agent_server_base_url', '')
        auth_shared_secret = data.get('auth_shared_secret')
        auth_require_signature = data.get('auth_require_signature')
        max_concurrent_tasks = data.get('max_concurrent_tasks')
        control_plane_url = getattr(settings, "CONTROL_PLANE_URL", "") or ""

        # 验证参数
        if install_type == 'agent' and not agent_server_url:
            return SycResponse.error(message="agent_server_url 不能为空（安装 Agent 需要）", code=400)
        if install_type == 'agent-server' and not agent_server_listen_addr:
            return SycResponse.error(message="agent_server_listen_addr 不能为空（安装 Agent-Server 需要）", code=400)
        if install_type == 'agent-server' and not control_plane_url:
            return SycResponse.error(message="控制面未配置 CONTROL_PLANE_URL，无法安装 Agent-Server", code=400)

        if install_type == 'agent-server':
            self._upsert_agent_server_from_base_url(
                agent_server_base_url,
                auth_shared_secret=auth_shared_secret or '',
                auth_require_signature=auth_require_signature,
            )

        # 获取主机列表
        from apps.hosts.models import Host
        hosts = Host.objects.filter(id__in=host_ids)

        if not hosts.exists():
            return SycResponse.error(message="未找到指定的主机", code=404)

        scripts = {}
        errors = []
        agent_server_netloc_map = build_agent_server_netloc_map() if install_type == 'agent' else {}
        resolved_agent_server = resolve_agent_server_from_url(agent_server_url, agent_server_netloc_map) if install_type == 'agent' else None
        resolved_agent_server_id = resolved_agent_server.id if resolved_agent_server else None

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
                        'endpoint': agent_server_url if install_type == 'agent' else agent_server_listen_addr or '',
                        'agent_server_id': resolved_agent_server_id if install_type == 'agent' else None,
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
                    agent.endpoint = agent_server_url if install_type == 'agent' else agent_server_listen_addr or ''
                    update_fields = ['agent_type', 'status', 'endpoint', 'updated_at']
                    if install_type == 'agent' and resolved_agent_server_id:
                        agent.agent_server_id = resolved_agent_server_id
                        update_fields.append('agent_server_id')
                    elif install_type != 'agent' and agent.agent_server_id is not None:
                        agent.agent_server_id = None
                        update_fields.append('agent_server_id')
                    agent.save(update_fields=update_fields)

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
                        'agent_server_url': agent_server_url if install_type == 'agent' else '',
                        'agent_server_backup_url': '',
                        'ws_backoff_initial_ms': ws_backoff_initial_ms,
                        'ws_backoff_max_ms': ws_backoff_max_ms,
                        'ws_max_retries': ws_max_retries,
                        'agent_server_listen_addr': agent_server_listen_addr,
                        'max_connections': max_connections,
                        'heartbeat_timeout': heartbeat_timeout,
                        'package_id': package_id,
                        'package_version': package_version,
                        'control_plane_url': control_plane_url if install_type == 'agent-server' else '',
                        'installed_by': request.user,
                    }
                )
                if not created:
                    # 更新现有安装记录的配置，允许重新生成脚本
                    install_record.agent = agent
                    install_record.install_type = install_type
                    install_record.install_mode = install_mode
                    install_record.agent_server_url = agent_server_url if install_type == 'agent' else ''
                    install_record.agent_server_backup_url = ''
                    install_record.ws_backoff_initial_ms = ws_backoff_initial_ms
                    install_record.ws_backoff_max_ms = ws_backoff_max_ms
                    install_record.ws_max_retries = ws_max_retries
                    install_record.agent_server_listen_addr = agent_server_listen_addr
                    install_record.max_connections = max_connections
                    install_record.heartbeat_timeout = heartbeat_timeout
                    install_record.package_id = package_id
                    install_record.package_version = package_version
                    install_record.control_plane_url = control_plane_url if install_type == 'agent-server' else ''
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
                        # 最大并发任务数
                        max_concurrent_tasks=max_concurrent_tasks,
                        # agent-server WebSocket 配置
                        ws_handshake_timeout=ws_handshake_timeout,
                        ws_read_buffer_size=ws_read_buffer_size,
                        ws_write_buffer_size=ws_write_buffer_size,
                        ws_enable_compression=ws_enable_compression,
                        ws_allowed_origins=ws_allowed_origins,
                        auth_shared_secret=auth_shared_secret,
                        auth_require_signature=auth_require_signature,
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
                        'agent_server_url': agent_server_url if install_type == 'agent' else '',
                        'control_plane_url': control_plane_url if install_type == 'agent-server' else '',
                        'errors': errors,
                        'warning': '部分主机生成脚本失败，请查看 errors 字段'
                    },
                    message="生成安装脚本成功（部分主机失败）"
                )

        return SycResponse.success(
            content={
                'scripts': scripts,
                'install_mode': install_mode,
                'agent_server_url': agent_server_url if install_type == 'agent' else '',
                'control_plane_url': control_plane_url if install_type == 'agent-server' else '',
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
        # agent-server WebSocket 配置
        ws_handshake_timeout = data.get('ws_handshake_timeout', '10s')
        ws_read_buffer_size = data.get('ws_read_buffer_size', 4096)
        ws_write_buffer_size = data.get('ws_write_buffer_size', 4096)
        ws_enable_compression = data.get('ws_enable_compression', True)
        ws_allowed_origins = data.get('ws_allowed_origins', [])
        agent_server_base_url = data.get('agent_server_base_url', '')
        auth_shared_secret = data.get('auth_shared_secret')
        auth_require_signature = data.get('auth_require_signature')
        ssh_timeout = data.get('ssh_timeout', 300)
        allow_reinstall = data.get('allow_reinstall', False)
        max_concurrent_tasks = data.get('max_concurrent_tasks')
        control_plane_url = getattr(settings, "CONTROL_PLANE_URL", "") or ""

        if install_type == 'agent' and not agent_server_url:
            return SycResponse.error(message="agent_server_url 不能为空（安装 Agent 需要）", code=400)
        if install_type == 'agent-server' and not agent_server_listen_addr:
            return SycResponse.error(message="agent_server_listen_addr 不能为空（安装 Agent-Server 需要）", code=400)
        if install_type == 'agent-server' and not control_plane_url:
            return SycResponse.error(message="控制面未配置 CONTROL_PLANE_URL，无法安装 Agent-Server", code=400)

        if install_type == 'agent-server':
            self._upsert_agent_server_from_base_url(
                agent_server_base_url,
                auth_shared_secret=auth_shared_secret or '',
                auth_require_signature=auth_require_signature,
            )

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
        from utils.thread_pool import get_global_thread_pool

        install_task_id = str(uuid.uuid4())

        # 提前获取用户对象，避免在线程中访问 request
        user = request.user

        # 在启动后台线程之前，先为每个主机创建初始的安装记录
        # 这样SSE权限检查就能找到对应的记录
        from apps.hosts.models import Host
        hosts = Host.objects.filter(id__in=host_ids)
        initial_install_records = []
        agent_server_netloc_map = build_agent_server_netloc_map() if install_type == 'agent' else {}
        resolved_agent_server = resolve_agent_server_from_url(agent_server_url, agent_server_netloc_map) if install_type == 'agent' else None
        resolved_agent_server_id = resolved_agent_server.id if resolved_agent_server else None

        for host in hosts:
            # 创建或获取 Agent（status='pending'）
            agent, agent_created = Agent.objects.get_or_create(
                host=host,
                defaults={
                    'agent_type': install_type,
                    'status': 'pending',
                    'endpoint': agent_server_url if install_type == 'agent' else agent_server_listen_addr or '',
                    'agent_server_id': resolved_agent_server_id if install_type == 'agent' else None,
                }
            )
            if not agent_created:
                # 如果Agent已存在，更新状态和类型
                if agent.agent_type != install_type:
                    agent.agent_type = install_type
                agent.status = 'pending'
                agent.endpoint = agent_server_url if install_type == 'agent' else agent_server_listen_addr or ''
                update_fields = ['agent_type', 'status', 'endpoint', 'updated_at']
                if install_type == 'agent' and resolved_agent_server_id:
                    agent.agent_server_id = resolved_agent_server_id
                    update_fields.append('agent_server_id')
                elif install_type != 'agent' and agent.agent_server_id is not None:
                    agent.agent_server_id = None
                    update_fields.append('agent_server_id')
                agent.save(update_fields=update_fields)

            # 创建初始安装记录
            from .models import AgentInstallRecord
            install_record, created = AgentInstallRecord.objects.get_or_create(
                host=host,
                agent=agent,
                status='pending',
                defaults={
                    'install_type': install_type,
                    'install_mode': install_mode,
                    'agent_server_url': agent_server_url if install_type == 'agent' else '',
                    'agent_server_backup_url': '',
                    'ws_backoff_initial_ms': ws_backoff_initial_ms,
                    'ws_backoff_max_ms': ws_backoff_max_ms,
                    'ws_max_retries': ws_max_retries,
                    'agent_server_listen_addr': agent_server_listen_addr,
                    'max_connections': max_connections,
                    'heartbeat_timeout': heartbeat_timeout,
                    'package_id': package_id,
                    'package_version': package_version,
                    'control_plane_url': control_plane_url if install_type == 'agent-server' else '',
                    'installed_by': user,
                    'install_task_id': install_task_id,
                }
            )
            if not created:
                # 更新现有记录
                install_record.install_type = install_type
                install_record.install_mode = install_mode
                install_record.agent_server_url = agent_server_url if install_type == 'agent' else ''
                install_record.agent_server_backup_url = ''
                install_record.ws_backoff_initial_ms = ws_backoff_initial_ms
                install_record.ws_backoff_max_ms = ws_backoff_max_ms
                install_record.ws_max_retries = ws_max_retries
                install_record.agent_server_listen_addr = agent_server_listen_addr
                install_record.max_connections = max_connections
                install_record.heartbeat_timeout = heartbeat_timeout
                install_record.package_id = package_id
                install_record.package_version = package_version
                install_record.control_plane_url = control_plane_url if install_type == 'agent-server' else ''
                install_record.status = 'pending'
                install_record.install_task_id = install_task_id
                install_record.save()

            initial_install_records.append(install_record)

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
                    allow_reinstall=allow_reinstall,
                    # 最大并发任务数
                    max_concurrent_tasks=max_concurrent_tasks,
                    # agent-server WebSocket 配置
                    ws_handshake_timeout=ws_handshake_timeout,
                    ws_read_buffer_size=ws_read_buffer_size,
                    ws_write_buffer_size=ws_write_buffer_size,
                    ws_enable_compression=ws_enable_compression,
                    ws_allowed_origins=ws_allowed_origins,
                    auth_shared_secret=auth_shared_secret,
                    auth_require_signature=auth_require_signature,
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

        # 使用全局线程池提交后台任务
        pool = get_global_thread_pool()
        pool.submit(run_batch_install)

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
        from utils.thread_pool import get_global_thread_pool

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

        # 使用全局线程池提交后台任务
        pool = get_global_thread_pool()
        pool.submit(run_batch_uninstall)

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
        """查询安装记录"""
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

    @action(detail=False, methods=["post"], url_path="retry_install_record")
    def retry_install_record(self, request):
        """重试安装记录中的失败主机"""
        install_record_id = request.data.get('install_record_id')
        if not install_record_id:
            return SycResponse.error(message="缺少 install_record_id 参数", code=400)

        # 获取安装记录
        from .models import AgentInstallRecord
        try:
            install_record = AgentInstallRecord.objects.select_related('host', 'agent', 'installed_by').get(id=install_record_id)
        except AgentInstallRecord.DoesNotExist:
            return SycResponse.error(message="安装记录不存在", code=404)

        # 权限检查
        if not request.user.is_superuser:
            allowed_hosts = get_objects_for_user(
                request.user,
                'view_host',
                accept_global_perms=False
            )
            if install_record.host not in allowed_hosts:
                return SycResponse.error(message="无权限访问此安装记录", code=403)

        # 获取同一批次安装任务中的所有记录
        batch_records = AgentInstallRecord.objects.filter(
            install_task_id=install_record.install_task_id,
            status='failed'  # 只重试失败的记录
        ).select_related('host', 'agent')

        if not batch_records.exists():
            return SycResponse.error(message="该安装任务中没有失败的记录", code=400)

        # 提取失败的主机ID
        failed_host_ids = [record.host_id for record in batch_records]

        # 验证用户确认
        confirmed = request.data.get('confirmed', False)
        if not confirmed:
            return SycResponse.error(message="高危操作需要二次确认，请设置 confirmed=true", code=400)

        # 构造重试参数
        retry_params = {
            'host_ids': failed_host_ids,
            'install_type': install_record.install_type,
            'install_mode': install_record.install_mode,
            'agent_server_url': install_record.agent_server_url,
            'agent_server_backup_url': install_record.agent_server_backup_url,
            'ws_backoff_initial_ms': install_record.ws_backoff_initial_ms,
            'ws_backoff_max_ms': install_record.ws_backoff_max_ms,
            'ws_max_retries': install_record.ws_max_retries,
            'agent_server_listen_addr': install_record.agent_server_listen_addr,
            'max_connections': install_record.max_connections,
            'heartbeat_timeout': install_record.heartbeat_timeout,
            'package_id': install_record.package_id,
            'package_version': install_record.package_version,
            'ssh_timeout': 300,  # 默认超时时间
            'confirmed': True,
            'allow_reinstall': True,  # 允许重新安装
        }

        # 直接调用batch_install方法，构造一个新的request对象
        from django.http import HttpRequest
        from django.contrib.auth.models import AnonymousUser

        # 创建一个新的request对象，包含重试参数
        retry_request = HttpRequest()
        retry_request.method = 'POST'
        retry_request.POST = retry_params
        retry_request.user = request.user
        retry_request.data = retry_params

        # 调用batch_install方法
        return self.batch_install(retry_request)

    @action(detail=False, methods=["get"], url_path="host_agent_status")
    def host_agent_status(self, request):
        """获取主机Agent状态，用于安装时显示主机列表"""
        from apps.hosts.models import Host
        from .serializers import HostAgentStatusSerializer

        queryset = Host.objects.select_related('agent').all()

        # 权限过滤
        if not request.user.is_superuser:
            allowed_hosts = get_objects_for_user(
                request.user,
                'view_host',
                accept_global_perms=False
            )
            queryset = queryset.filter(id__in=[h.id for h in allowed_hosts])

        serializer = HostAgentStatusSerializer(queryset, many=True)
        return SycResponse.success(
            content={"hosts": serializer.data},
            message="获取主机Agent状态成功"
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
