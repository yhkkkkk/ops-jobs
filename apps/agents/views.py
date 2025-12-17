import logging
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated, AllowAny
from django_filters.rest_framework import DjangoFilterBackend
from django.utils import timezone
from django.db import transaction
from guardian.shortcuts import get_objects_for_user

from utils.responses import SycResponse

logger = logging.getLogger(__name__)
from utils.pagination import CustomPagination
from utils.audit_service import AuditLogService
from apps.permissions.permissions import BasePermissionMixin
from .models import Agent, AgentInstallRecord, AgentUninstallRecord
from .serializers import (
    AgentSerializer,
    AgentDetailSerializer,
    AgentTokenSerializer,
    IssueTokenSerializer,
    AgentEnableSerializer,
    BatchOperationSerializer,
    AgentInstallRecordSerializer,
    GenerateInstallScriptSerializer,
    BatchInstallSerializer,
    AgentUninstallRecordSerializer,
    BatchUninstallSerializer,
    AgentControlSerializer,
)
from .filters import AgentFilter
from .services import AgentService


class AgentPermission(BasePermissionMixin):
    """Agent 权限：列表/详情允许，敏感操作需具备对应模型权限"""

    def has_permission(self, request, view):
        if not request.user.is_authenticated:
            return False
        if getattr(view, "action", None) in ["list", "retrieve"]:
            return True
        return True

    def has_object_permission(self, request, view, obj):
        user = request.user
        if not user.is_authenticated:
            return False
        action = getattr(view, "action", None)
        # 细粒度控制
        if action == "retrieve":
            return user.has_perm("agents.view_agent", obj) or user.is_superuser
        if action == "issue_token":
            return user.has_perm("agents.issue_agent_token", obj) or user.is_superuser
        if action == "revoke_token":
            return user.has_perm("agents.revoke_agent_token", obj) or user.is_superuser
        if action == "enable_agent":
            return user.has_perm("agents.enable_agent", obj) or user.is_superuser
        if action == "disable_agent":
            return user.has_perm("agents.disable_agent", obj) or user.is_superuser
        return user.has_perm("agents.view_agent", obj) or user.is_superuser


class AgentPagination(CustomPagination):
    page_size = 20


class AgentViewSet(viewsets.ModelViewSet):
    """Agent 管理"""

    queryset = Agent.objects.select_related("host").prefetch_related("tokens", "host__groups")
    serializer_class = AgentSerializer
    permission_classes = [IsAuthenticated, AgentPermission]
    pagination_class = AgentPagination
    filter_backends = [DjangoFilterBackend]
    filterset_class = AgentFilter

    def get_queryset(self):
        """基于用户权限过滤查询集"""
        queryset = super().get_queryset()

        # 如果是超级用户，返回所有 Agent
        if self.request.user.is_superuser:
            return queryset.order_by('-created_at')

        # 检查用户是否有模型级别的 view_agent 权限
        if self.request.user.has_perm('agents.view_agent'):
            return queryset.select_related("host").prefetch_related("tokens", "host__groups").order_by('-created_at')

        # 否则，只返回有对象级别权限的 Agent（基于关联的 Host 权限）
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
                message="获取 Agent 列表成功",
            )
        serializer = self.get_serializer(queryset, many=True)
        return SycResponse.success(
            content={
                "results": serializer.data,
                "total": len(serializer.data),
                "page": 1,
                "page_size": len(serializer.data),
            },
            message="获取 Agent 列表成功",
        )

    def retrieve(self, request, *args, **kwargs):
        agent = self.get_object()
        serializer = self.get_serializer(agent)
        return SycResponse.success(content=serializer.data, message="获取 Agent 详情成功")

    @action(detail=False, methods=["get"], url_path="me")
    def me(self, request):
        """
        通过 token 获取当前 Agent 信息（用于 Agent 首次启动时获取自己的 ID）
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
        
        serializer = AgentDetailSerializer(agent)
        return SycResponse.success(
            content={
                'id': str(agent.host_id),  # Agent ID 就是 host_id
                'name': agent.host.name,
                'status': agent.status,
                **serializer.data
            },
            message="获取 Agent 信息成功"
        )

    @action(detail=True, methods=["post"], url_path="issue_token")
    def issue_token(self, request, pk=None):
        agent = self.get_object()
        serializer = IssueTokenSerializer(data=request.data)
        if not serializer.is_valid():
            return SycResponse.validation_error(serializer.errors)
        # 高危操作二次确认
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
        AgentService.audit(request.user, "issue_agent_token", agent, request=request, extra={"token_last4": data["token_last4"]})
        return SycResponse.success(
            content={"token": data["token"], "expired_at": data["expired_at"], "token_last4": data["token_last4"]},
            message="签发 Agent Token 成功（仅本次返回明文）",
        )

    @action(detail=True, methods=["post"], url_path="revoke_token")
    def revoke_token(self, request, pk=None):
        agent = self.get_object()
        # 高危操作二次确认
        confirmed = request.data.get("confirmed", False)
        if not confirmed:
            return SycResponse.error(
                message="高危操作需要二次确认，请设置 confirmed=true",
                code=400
            )
        ok = AgentService.revoke_active_token(agent)
        AgentService.audit(request.user, "revoke_agent_token", agent, request=request, success=ok)
        if not ok:
            return SycResponse.error(message="当前无有效 token", code=404)
        return SycResponse.success(message="吊销 Agent Token 成功")

    @action(detail=True, methods=["post"], url_path="enable")
    def enable_agent(self, request, pk=None):
        agent = self.get_object()
        AgentService.enable_agent(agent)
        AgentService.audit(request.user, "enable_agent", agent, request=request)
        return SycResponse.success(message="启用 Agent 成功")

    @action(detail=True, methods=["post"], url_path="disable")
    def disable_agent(self, request, pk=None):
        agent = self.get_object()
        # 高危操作二次确认
        confirmed = request.data.get("confirmed", False)
        if not confirmed:
            return SycResponse.error(
                message="高危操作需要二次确认，请设置 confirmed=true",
                code=400
            )
        AgentService.disable_agent(agent)
        AgentService.audit(request.user, "disable_agent", agent, request=request)
        return SycResponse.success(message="禁用 Agent 成功")

    # 辅助方法：构造Agent-Server基础url
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
        from django.conf import settings
        if override_url:
            return self._normalize_server_url(override_url)
        if agent.endpoint:
            return self._normalize_server_url(agent.endpoint)
        return self._normalize_server_url(getattr(settings, "AGENT_SERVER_URL", ""))

    @action(detail=True, methods=["get"], url_path="status")
    def status(self, request, pk=None):
        """获取 Agent 运行状态，只返回 Agent-Server 实时数据"""
        agent = self.get_object()
        server_base = self._get_agent_server_base(agent, request.query_params.get("agent_server_url", ""))

        if not server_base:
            return SycResponse.error(message="未配置 Agent-Server，无法查询实时状态")

        import requests
        from django.conf import settings

        api_url = f"{server_base}/api/agents/{agent.host_id}"
        headers = {"Content-Type": "application/json"}
        token = getattr(settings, "AGENT_SERVER_TOKEN", None)
        if token:
            headers["Authorization"] = f"Bearer {token}"

        try:
            resp = requests.get(api_url, headers=headers, timeout=5)
            if resp.status_code == 200:
                return SycResponse.success(content=resp.json(), message="获取 Agent 状态成功")
            logger.warning("查询 Agent 状态失败 %s %s", resp.status_code, resp.text)
            return SycResponse.error(message=f"Agent-Server 返回异常: HTTP {resp.status_code}")
        except Exception as exc:  # noqa: BLE001
            logger.error("查询 Agent 状态异常: %s", exc, exc_info=True)
            return SycResponse.error(message=f"查询 Agent 状态异常: {exc}")

    @action(detail=True, methods=["post"], url_path="control")
    def control(self, request, pk=None):
        """管控 Agent（start/stop/restart），调用 Agent-Server 控制接口"""
        agent = self.get_object()
        serializer = AgentControlSerializer(data=request.data)
        if not serializer.is_valid():
            return SycResponse.validation_error(serializer.errors)

        server_base = self._get_agent_server_base(agent, request.data.get("agent_server_url", ""))
        if not server_base:
            return SycResponse.error(message="未配置 Agent-Server，无法下发管控指令")

        import requests
        from django.conf import settings

        api_url = f"{server_base}/api/agents/{agent.host_id}/control"
        headers = {"Content-Type": "application/json"}
        token = getattr(settings, "AGENT_SERVER_TOKEN", None)
        if token:
            headers["Authorization"] = f"Bearer {token}"

        payload = {
            "action": serializer.validated_data["action"],
            "reason": serializer.validated_data.get("reason", ""),
        }

        try:
            resp = requests.post(api_url, json=payload, headers=headers, timeout=5)
            if resp.status_code == 200:
                AgentService.audit(request.user, f"control_agent_{payload['action']}", agent, request=request)
                return SycResponse.success(content=resp.json(), message="管控指令已下发")
            logger.error("管控 Agent 失败 %s %s", resp.status_code, resp.text)
            return SycResponse.error(message=f"管控失败: HTTP {resp.status_code}")
        except Exception as exc:  # noqa: BLE001
            logger.error("管控 Agent 异常: %s", exc, exc_info=True)
            return SycResponse.error(message=f"管控异常: {exc}")

    def destroy(self, request, *args, **kwargs):
        """删除 Agent（仅允许删除 pending 状态的 Agent）"""
        agent = self.get_object()
        
        # 只允许删除 pending 状态的 Agent
        if agent.status != 'pending':
            return SycResponse.error(
                message=f"只能删除待激活状态的 Agent，当前状态为：{agent.get_status_display()}",
                code=400
            )
        
        # 高危操作二次确认
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
        # 注意：agent 已删除，创建一个临时对象用于审计（仅用于类型检查）
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
        return SycResponse.success(message=f"Agent ({host_name}) 删除成功")

    @action(detail=False, methods=["post"], url_path="batch_disable")
    def batch_disable(self, request):
        """批量禁用 Agent（带限流）"""
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
                message=f"批量操作最多支持 {MAX_BATCH_SIZE} 个 Agent",
                code=400
            )
        agents = Agent.objects.filter(id__in=agent_ids)
        # 权限过滤
        queryset = self.get_queryset()
        allowed_agents = queryset.filter(id__in=agent_ids)
        if allowed_agents.count() != len(agent_ids):
            return SycResponse.error(
                message="部分 Agent 无权限操作",
                code=403
            )
        # 生产环境额外限制
        prod_agents = allowed_agents.filter(host__environment="prod")
        if prod_agents.exists() and len(agent_ids) > 10:
            return SycResponse.error(
                message="生产环境批量操作最多支持 10 个 Agent",
                code=400
            )
        count = 0
        for agent in allowed_agents:
            AgentService.disable_agent(agent)
            AgentService.audit(request.user, "disable_agent", agent, request=request)
            count += 1
        return SycResponse.success(
            content={"count": count},
            message=f"批量禁用 {count} 个 Agent 成功"
        )

    @action(detail=True, methods=["post"], url_path="regenerate_script")
    def regenerate_script(self, request, pk=None):
        """
        为指定 Agent 重新生成安装脚本（用于 pending 状态的 Agent）
        这是备用操作，用于用户生成脚本后没有复制也没有安装的场景
        """
        agent = self.get_object()
        
        # 只有 pending 状态的 Agent 才能重新生成脚本
        if agent.status != 'pending':
            return SycResponse.error(message="只有待激活状态的 Agent 才能重新生成脚本", code=400)
        
        # 查找最新的安装记录
        install_record = AgentInstallRecord.objects.filter(
            agent=agent,
            host=agent.host
        ).order_by('-installed_at').first()
        
        if not install_record:
            return SycResponse.error(message="未找到安装记录，无法重新生成脚本", code=404)
        
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
                package = AgentPackage.objects.get(id=package_id, is_active=True)
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
                    version=package_version,
                    os_type=os_type,
                    arch=arch,
                    is_active=True
                )
            except AgentPackage.DoesNotExist:
                logger.warning(f"安装记录中的 package_version={package_version} (OS: {os_type}, Arch: {arch}) 不存在或未启用，将尝试使用最新的可用包")
                package_version = None
        
        # 生成安装脚本
        try:
            host_scripts = AgentService.generate_install_script(
                host=agent.host,
                agent_token=agent_token,
                install_mode=install_record.install_mode,
                agent_server_url=install_record.agent_server_url,
                agent_server_backup_url=install_record.agent_server_backup_url or '',
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
            message="重新生成安装脚本成功"
        )

    @action(detail=False, methods=["post"], url_path="generate_install_script")
    def generate_install_script(self, request):
        """生成安装脚本"""
        serializer = GenerateInstallScriptSerializer(data=request.data)
        if not serializer.is_valid():
            return SycResponse.validation_error(serializer.errors)

        data = serializer.validated_data
        host_ids = data['host_ids']
        install_mode = data.get('install_mode', 'agent-server')
        agent_server_url = data.get('agent_server_url', '')
        agent_server_backup_url = data.get('agent_server_backup_url', '')
        ws_backoff_initial_ms = data.get('ws_backoff_initial_ms', 1000)
        ws_backoff_max_ms = data.get('ws_backoff_max_ms', 30000)
        ws_max_retries = data.get('ws_max_retries', 6)
        package_version = data.get('package_version')
        package_id = data.get('package_id')

        if install_mode == 'agent-server' and not agent_server_url:
            return SycResponse.error(message="agent_server_url 不能为空（agent-server 模式）", code=400)

        # 获取主机列表
        from apps.hosts.models import Host
        hosts = Host.objects.filter(id__in=host_ids)

        if not hosts.exists():
            return SycResponse.error(message="未找到指定的主机", code=404)

        scripts = {}
        tokens = {}
        errors = []

        for host in hosts:
            try:
                # 先验证安装包是否存在（在生成脚本前验证）
                try:
                    AgentService.get_download_url(
                        host=host,
                        package_version=package_version,
                        package_id=package_id,
                        raise_if_not_found=True,
                    )
                except ValueError as e:
                    errors.append(f"主机 {host.name} ({host.ip_address}): {str(e)}")
                    continue

                # 创建或获取 Agent（status='pending'）
                agent, agent_created = Agent.objects.get_or_create(
                    host=host,
                    defaults={
                        'status': 'pending',
                        'endpoint': agent_server_url or '',
                    }
                )
                
                # 如果 Agent 已存在，更新状态和配置
                if not agent_created:
                    agent.status = 'pending'
                    agent.endpoint = agent_server_url or ''
                    agent.save(update_fields=['status', 'endpoint', 'updated_at'])
                
                # 签发 Agent Token
                token_data = AgentService.issue_token(agent, request.user, note="生成安装脚本")
                agent_token = token_data['token']
                
                # 创建或更新安装记录
                install_record, created = AgentInstallRecord.objects.get_or_create(
                    host=host,
                    agent=agent,
                    status='pending',
                    defaults={
                        'install_mode': install_mode,
                        'agent_server_url': agent_server_url,
                        'agent_server_backup_url': agent_server_backup_url,
                        'ws_backoff_initial_ms': ws_backoff_initial_ms,
                        'ws_backoff_max_ms': ws_backoff_max_ms,
                        'ws_max_retries': ws_max_retries,
                        'package_id': package_id,
                        'package_version': package_version,
                        'installed_by': request.user,
                    }
                )
                if not created:
                    # 更新现有安装记录的配置（允许重新生成脚本）
                    install_record.agent = agent
                    install_record.install_mode = install_mode
                    install_record.agent_server_url = agent_server_url
                    install_record.agent_server_backup_url = agent_server_backup_url
                    install_record.ws_backoff_initial_ms = ws_backoff_initial_ms
                    install_record.ws_backoff_max_ms = ws_backoff_max_ms
                    install_record.ws_max_retries = ws_max_retries
                    install_record.package_id = package_id
                    install_record.package_version = package_version
                    install_record.status = 'pending'
                    install_record.save()

                # 生成安装脚本（使用 Agent Token）
                try:
                    host_scripts = AgentService.generate_install_script(
                        host=host,
                        agent_token=agent_token,
                        install_mode=install_mode,
                        agent_server_url=agent_server_url,
                        agent_server_backup_url=agent_server_backup_url,
                        ws_backoff_initial_ms=ws_backoff_initial_ms,
                        ws_backoff_max_ms=ws_backoff_max_ms,
                        ws_max_retries=ws_max_retries,
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
        install_mode = data.get('install_mode', 'agent-server')
        agent_server_url = data.get('agent_server_url', '')
        agent_server_backup_url = data.get('agent_server_backup_url', '')
        package_version = data.get('package_version')
        package_id = data.get('package_id')
        confirmed = data.get('confirmed', False)
        ws_backoff_initial_ms = data.get('ws_backoff_initial_ms', 1000)
        ws_backoff_max_ms = data.get('ws_backoff_max_ms', 30000)
        ws_max_retries = data.get('ws_max_retries', 6)
        ssh_timeout = data.get('ssh_timeout', 300)
        allow_reinstall = data.get('allow_reinstall', False)

        if not confirmed:
            return SycResponse.error(message="请勾选确认框以执行批量安装操作", code=400)
        if install_mode == 'agent-server' and not agent_server_url:
            return SycResponse.error(message="agent_server_url 不能为空（agent-server 模式）", code=400)

        # 批量操作限流
        MAX_BATCH_SIZE = 50
        PROD_MAX_BATCH_SIZE = 10

        from apps.hosts.models import Host
        hosts = Host.objects.filter(id__in=host_ids)
        
        # 检查是否有生产环境主机
        prod_hosts = hosts.filter(environment='prod')
        is_prod_env = prod_hosts.exists()
        current_max_batch_size = PROD_MAX_BATCH_SIZE if is_prod_env else MAX_BATCH_SIZE

        if len(host_ids) > current_max_batch_size:
            return SycResponse.error(
                message=f"批量安装数量超过限制，当前环境最多允许安装 {current_max_batch_size} 个 Agent",
                code=400
            )

        # 生成安装任务ID
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
                    install_mode=install_mode,
                    agent_server_url=agent_server_url,
                    agent_server_backup_url=agent_server_backup_url,
                    install_task_id=install_task_id,
                    package_version=package_version,
                    package_id=package_id,
                    ws_backoff_initial_ms=ws_backoff_initial_ms,
                    ws_backoff_max_ms=ws_backoff_max_ms,
                    ws_max_retries=ws_max_retries,
                    ssh_timeout=ssh_timeout,
                    allow_reinstall=allow_reinstall
                )
                
                # 记录审计日志
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
                            logger.warning(f"Agent {install_result.get('agent_id')} 不存在，跳过审计日志")
                
                logger.info(f"批量安装任务完成: install_task_id={install_task_id}, 成功={result['success_count']}, 失败={result['failed_count']}")
                
            except Exception as e:
                logger.error(f"批量安装任务失败: install_task_id={install_task_id}, 错误={str(e)}", exc_info=True)
                # 推送错误状态
                from utils.realtime_logs import realtime_log_service
                realtime_log_service.push_status(install_task_id, {
                    'status': 'error',
                    'message': f'批量安装任务失败: {str(e)}'
                })
        
        # 在线程池中执行
        executor = ThreadPoolExecutor(max_workers=1)
        executor.submit(run_batch_install)
        executor.shutdown(wait=False)  # 不等待任务完成，立即返回
        
        logger.info(f"批量安装任务已启动: install_task_id={install_task_id}")

        return SycResponse.success(
            content={
                'install_task_id': install_task_id,  # 返回任务ID用于前端连接SSE
                'total': len(host_ids),
                'status': 'running'
            },
            message=f"批量安装已启动，正在后台执行，可通过 install_task_id 连接 SSE 查看实时进度"
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

        if not confirmed:
            return SycResponse.error(message="请勾选确认框以执行批量卸载操作", code=400)

        # 权限过滤（基于 get_queryset）
        allowed_agents = self.get_queryset().filter(id__in=agent_ids).select_related('host')
        if allowed_agents.count() != len(agent_ids):
            return SycResponse.error(message="部分 Agent 无权限操作", code=403)

        # 批量操作限流（生产环境更严格）
        MAX_BATCH_SIZE = 50
        PROD_MAX_BATCH_SIZE = 10
        prod_agents = allowed_agents.filter(host__environment='prod')
        current_max_batch_size = PROD_MAX_BATCH_SIZE if prod_agents.exists() else MAX_BATCH_SIZE
        if len(agent_ids) > current_max_batch_size:
            return SycResponse.error(
                message=f"批量卸载数量超过限制，当前环境最多允许卸载 {current_max_batch_size} 个 Agent",
                code=400
            )

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

                # 审计日志
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
                            error_message='' if uninstall_result.get('success') else uninstall_result.get('message', ''),
                            extra={
                                'host_id': uninstall_result.get('host_id'),
                                'host_name': uninstall_result.get('host_name'),
                            }
                        )
                    except Agent.DoesNotExist:
                        logger.warning(f"Agent {agent_id} 不存在，跳过审计日志")

                logger.info(
                    f"批量卸载任务完成: uninstall_task_id={uninstall_task_id}, 成功={result.get('success_count')}, 失败={result.get('failed_count')}"
                )
            except Exception as e:
                logger.error(f"批量卸载任务失败: uninstall_task_id={uninstall_task_id}, 错误={str(e)}", exc_info=True)
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
            message="批量卸载已启动，正在后台执行，可通过 uninstall_task_id 连接 SSE 查看实时进度"
        )

    @action(detail=False, methods=["get"], url_path="install_records")
    def install_records(self, request):
        """查询安装记录"""
        from .models import AgentInstallRecord
        from django_filters.rest_framework import DjangoFilterBackend
        from django_filters import rest_framework as filters

        class InstallRecordFilter(filters.FilterSet):
            host_id = filters.NumberFilter(field_name='host_id')
            status = filters.ChoiceFilter(choices=AgentInstallRecord.STATUS_CHOICES)

            class Meta:
                model = AgentInstallRecord
                fields = ['host_id', 'status', 'install_mode']

        queryset = AgentInstallRecord.objects.select_related('host', 'agent', 'installed_by').order_by('-installed_at')
        
        # 权限过滤
        if not request.user.is_superuser:
            from apps.hosts.models import Host
            from guardian.shortcuts import get_objects_for_user
            allowed_hosts = get_objects_for_user(
                request.user,
                'view_host',
                klass=Host,
                accept_global_perms=False
            )
            queryset = queryset.filter(host__in=allowed_hosts)

        # 应用过滤器
        filter_backend = DjangoFilterBackend()
        queryset = filter_backend.filter_queryset(request, queryset, InstallRecordFilter)

        # 分页
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = AgentInstallRecordSerializer(page, many=True)
            paginator = self.paginator
            return SycResponse.success(
                content={
                    "results": serializer.data,
                    "total": paginator.page.paginator.count,
                    "page": paginator.page.number,
                    "page_size": paginator.page_size,
                },
                message="获取安装记录成功",
            )

        serializer = AgentInstallRecordSerializer(queryset, many=True)
        return SycResponse.success(
            content={
                "results": serializer.data,
                "total": len(serializer.data),
                "page": 1,
                "page_size": len(serializer.data),
            },
            message="获取安装记录成功",
        )

    @action(detail=False, methods=["get"], url_path="uninstall_records")
    def uninstall_records(self, request):
        """查询卸载记录"""
        from django_filters.rest_framework import DjangoFilterBackend
        from django_filters import rest_framework as filters

        class UninstallRecordFilter(filters.FilterSet):
            host_id = filters.NumberFilter(field_name='host_id')
            status = filters.ChoiceFilter(choices=AgentUninstallRecord.STATUS_CHOICES)

            class Meta:
                model = AgentUninstallRecord
                fields = ['host_id', 'status']

        queryset = AgentUninstallRecord.objects.select_related('host', 'agent', 'uninstalled_by').order_by('-uninstalled_at')

        # 权限过滤（基于 Host 权限）
        if not request.user.is_superuser:
            from apps.hosts.models import Host
            allowed_hosts = get_objects_for_user(
                request.user,
                'view_host',
                klass=Host,
                accept_global_perms=False
            )
            queryset = queryset.filter(host__in=allowed_hosts)

        filter_backend = DjangoFilterBackend()
        queryset = filter_backend.filter_queryset(request, queryset, UninstallRecordFilter)

        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = AgentUninstallRecordSerializer(page, many=True)
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

        serializer = AgentUninstallRecordSerializer(queryset, many=True)
        return SycResponse.success(
            content={
                "results": serializer.data,
                "total": len(serializer.data),
                "page": 1,
                "page_size": len(serializer.data),
            },
            message="获取卸载记录成功",
        )

    @action(detail=False, methods=["post"], url_path="install_records/regenerate_script")
    def regenerate_script_from_record(self, request):
        """
        基于安装记录重新生成安装脚本
        用于用户想重新查看/获取安装脚本的场景
        请求参数: {"install_record_id": 123}
        """
        from .models import AgentInstallRecord
        
        install_record_id = request.data.get('install_record_id')
        if not install_record_id:
            return SycResponse.error(message="install_record_id 不能为空", code=400)
        
        try:
            install_record = AgentInstallRecord.objects.select_related('host').get(id=install_record_id)
        except AgentInstallRecord.DoesNotExist:
            return SycResponse.error(message="安装记录不存在", code=404)
        
        # 检查权限
        if not request.user.is_superuser:
            from apps.hosts.models import Host
            from guardian.shortcuts import get_objects_for_user
            allowed_hosts = get_objects_for_user(
                request.user,
                'view_host',
                klass=Host,
                accept_global_perms=False
            )
            if install_record.host not in allowed_hosts:
                return SycResponse.error(message="无权限访问此安装记录", code=403)
        
        # 如果安装记录没有关联 Agent，创建一个
        if not install_record.agent:
            agent, _ = Agent.objects.get_or_create(
                host=install_record.host,
                defaults={
                    'status': 'pending',
                    'endpoint': install_record.agent_server_url or '',
                }
            )
            install_record.agent = agent
            install_record.save()
        else:
            agent = install_record.agent
            # 更新 Agent 状态为 pending
            agent.status = 'pending'
            agent.endpoint = install_record.agent_server_url or ''
            agent.save(update_fields=['status', 'endpoint', 'updated_at'])
        
        # 重新签发 Agent Token
        token_data = AgentService.issue_token(agent, request.user, note="基于安装记录重新生成脚本")
        agent_token = token_data['token']
        
        # 更新安装记录状态
        install_record.status = 'pending'
        install_record.save()
        
        # 基于安装记录的配置重新生成脚本
        # 如果安装记录中的 package_id/package_version 无效，尝试使用最新的可用包
        package_id = install_record.package_id
        package_version = install_record.package_version
        
        # 验证安装包是否存在，如果不存在则尝试使用最新的可用包
        if package_id:
            from .models import AgentPackage
            try:
                package = AgentPackage.objects.get(id=package_id, is_active=True)
            except AgentPackage.DoesNotExist:
                logger.warning(f"安装记录中的 package_id={package_id} 不存在或未启用，将尝试使用最新的可用包")
                package_id = None
                package_version = None
        
        if package_version and not package_id:
            from .models import AgentPackage
            os_type = install_record.host.os_type.lower() if install_record.host.os_type else 'linux'
            if 'windows' in os_type:
                os_type = 'windows'
            elif 'darwin' in os_type or 'macos' in os_type:
                os_type = 'darwin'
            else:
                os_type = 'linux'
            arch = 'amd64'
            try:
                package = AgentPackage.objects.get(
                    version=package_version,
                    os_type=os_type,
                    arch=arch,
                    is_active=True
                )
            except AgentPackage.DoesNotExist:
                logger.warning(f"安装记录中的 package_version={package_version} (OS: {os_type}, Arch: {arch}) 不存在或未启用，将尝试使用最新的可用包")
                package_version = None
        
        try:
            host_scripts = AgentService.generate_install_script(
                host=install_record.host,
                agent_token=agent_token,
                install_mode=install_record.install_mode,
                agent_server_url=install_record.agent_server_url,
                agent_server_backup_url=install_record.agent_server_backup_url or '',
                ws_backoff_initial_ms=install_record.ws_backoff_initial_ms,
                ws_backoff_max_ms=install_record.ws_backoff_max_ms,
                ws_max_retries=install_record.ws_max_retries,
                package_version=package_version,
                package_id=package_id,
            )
        except Exception as e:
            logger.error(f"基于安装记录重新生成脚本失败: {str(e)}", exc_info=True)
            return SycResponse.error(message=f"生成脚本失败: {str(e)}", code=500)
        
        # 格式化返回数据
        scripts = {}
        for os_type, script in host_scripts.items():
            if os_type not in scripts:
                scripts[os_type] = []
            scripts[os_type].append({
                'host_id': install_record.host.id,
                'host_name': install_record.host.name,
                'host_ip': install_record.host.ip_address,
                'script': script,
                'agent_token': agent_token,
                'agent_id': agent.id,
                'install_record_id': install_record.id,
            })
        
        return SycResponse.success(
            content={
                'scripts': scripts,
                'install_mode': install_record.install_mode,
                'agent_server_url': install_record.agent_server_url,
                'notice': '这是重新生成的安装脚本，旧的 token 已失效，请使用新的 token'
            },
            message="重新生成安装脚本成功"
        )

    @action(detail=False, methods=["get"], url_path="download_urls")
    def download_urls(self, request):
        """获取 Agent 二进制下载地址"""
        from .models import AgentPackage
        from apps.system_config.models import ConfigManager

        # 优先使用版本管理
        default_packages = AgentPackage.objects.filter(is_default=True, is_active=True)
        
        if default_packages.exists():
            # 从版本管理获取下载地址
            download_urls = {}
            for package in default_packages:
                if package.os_type not in download_urls:
                    download_urls[package.os_type] = {}
                download_urls[package.os_type][package.arch] = package.get_download_url()
            
            # 获取版本号（取第一个默认包的版本）
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
        
        return SycResponse.error(message="未找到可用的 Agent 包", code=404)
