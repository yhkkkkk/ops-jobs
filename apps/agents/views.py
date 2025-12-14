import logging
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from django_filters.rest_framework import DjangoFilterBackend
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
        if self.action == "install_records":
            return AgentInstallRecordSerializer
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
        download_url = data.get('download_url', '')
        package_version = data.get('package_version')
        package_id = data.get('package_id')

        # 获取主机列表
        from apps.hosts.models import Host
        hosts = Host.objects.filter(id__in=host_ids)

        if not hosts.exists():
            return SycResponse.error(message="未找到指定的主机", code=404)

        scripts = {}
        tokens = {}

        for host in hosts:
            # 检查是否已有 Agent
            if hasattr(host, 'agent') and host.agent:
                # 如果已有 Agent，使用现有 Token（如果有）
                if host.agent.active_token_hash:
                    # 无法获取明文 Token，需要重新签发
                    token_data = AgentService.issue_token(host.agent, request.user, note='安装脚本生成')
                    token = token_data['token']
                else:
                    token_data = AgentService.issue_token(host.agent, request.user, note='安装脚本生成')
                    token = token_data['token']
            else:
                # 创建 Agent 对象
                agent, created = Agent.objects.get_or_create(
                    host=host,
                    defaults={'status': 'pending'}
                )
                # 签发 Token
                token_data = AgentService.issue_token(agent, request.user, note='安装脚本生成')
                token = token_data['token']

            # 生成安装脚本
            host_scripts = AgentService.generate_install_script(
                host=host,
                token=token,
                install_mode=install_mode,
                agent_server_url=agent_server_url,
                download_url=download_url,
                package_version=package_version,
                package_id=package_id
            )

            # 合并脚本（按操作系统分组）
            for os_type, script in host_scripts.items():
                if os_type not in scripts:
                    scripts[os_type] = []
                scripts[os_type].append({
                    'host_id': host.id,
                    'host_name': host.name,
                    'host_ip': host.ip_address,
                    'script': script,
                    'token': token  # 注意：这里返回明文 token，前端需要一次性显示
                })

        return SycResponse.success(
            content={
                'scripts': scripts,
                'install_mode': install_mode,
                'agent_server_url': agent_server_url,
                'download_url': download_url
            },
            message="生成安装脚本成功"
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
        download_url = data.get('download_url', '')
        package_version = data.get('package_version')
        package_id = data.get('package_id')
        confirmed = data.get('confirmed', False)

        if not confirmed:
            return SycResponse.error(message="请勾选确认框以执行批量安装操作", code=400)

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
                    download_url=download_url,
                    install_task_id=install_task_id,
                    package_version=package_version,
                    package_id=package_id
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

    @action(detail=False, methods=["get"], url_path="download_urls")
    def download_urls(self, request):
        """获取 Agent 二进制下载地址（兼容旧接口，优先使用版本管理）"""
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
        else:
            # 回退到配置
            base_url = ConfigManager.get('agent.download_url', 'http://localhost:8000/static/agent/')
            version = ConfigManager.get('agent.version', 'latest')

            download_urls = {
                'linux': {
                    'amd64': f"{base_url}ops-job-agent-linux-amd64",
                    'arm64': f"{base_url}ops-job-agent-linux-arm64",
                },
                'windows': {
                    'amd64': f"{base_url}ops-job-agent-windows-amd64.exe",
                }
            }

            return SycResponse.success(
                content={
                    'download_urls': download_urls,
                    'version': version,
                    'base_url': base_url,
                    'from_package_version': False
                },
                message="获取下载地址成功"
            )

