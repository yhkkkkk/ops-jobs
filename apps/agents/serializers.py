"""
Agent 序列化器
"""
from django.conf import settings
from rest_framework import serializers

from apps.hosts.serializers import HostSerializer, HostSimpleSerializer
from apps.system_config.models import ConfigManager
from .models import Agent, AgentToken, AgentInstallRecord, AgentUninstallRecord, AgentPackage, AgentTaskStats, AgentServer
from .status import get_cached_agent_status


class AgentTokenSerializer(serializers.ModelSerializer):
    issued_by_name = serializers.CharField(source='issued_by.username', read_only=True)

    class Meta:
        model = AgentToken
        fields = [
            'id',
            'token_last4',
            'issued_by',
            'issued_by_name',
            'created_at',
            'expired_at',
            'revoked_at',
            'note',
        ]
        read_only_fields = ['id', 'issued_by', 'issued_by_name', 'created_at', 'revoked_at']


class AgentSerializer(serializers.ModelSerializer):
    host = HostSimpleSerializer(read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    agent_type_display = serializers.CharField(source='get_agent_type_display', read_only=True)
    computed_status = serializers.SerializerMethodField()
    computed_status_display = serializers.SerializerMethodField()
    tokens = AgentTokenSerializer(many=True, read_only=True)
    is_version_outdated = serializers.SerializerMethodField()
    expected_min_version = serializers.SerializerMethodField()
    task_stats = serializers.SerializerMethodField()

    class Meta:
        model = Agent
        fields = [
            'id',
            'host',
            'agent_type',
            'agent_type_display',
            'status',
            'status_display',
            'computed_status',
            'computed_status_display',
            'version',
            'is_version_outdated',
            'expected_min_version',
            'endpoint',
            'agent_server_id',
            'last_heartbeat_at',
            'last_error_code',
            'created_at',
            'updated_at',
            'tokens',
            'task_stats',
        ]
        read_only_fields = fields

    def get_is_version_outdated(self, obj: Agent) -> bool:
        """
        判断 Agent 版本是否落后于期望版本。
        期望版本来源（按优先级）：
          1) SystemConfig.agent.min_version_by_env: {"prod": "1.2.0", "default": "1.0.0"}
          2) SystemConfig.agent.min_version: "1.0.0"
        未配置或 Agent 未上报版本则视为不落后。
        """
        expected = self._get_expected_min_version(obj)
        if not expected:
            return False

    def get_computed_status(self, obj: Agent) -> str | None:
        """Return cached computed status (online/offline/pending/disabled)."""
        try:
            status = get_cached_agent_status(obj.id, obj)
            return status or obj.status
        except Exception:
            return obj.status

    def get_computed_status_display(self, obj: Agent) -> str:
        mapping = {
            'pending': '待激活',
            'online': '在线',
            'offline': '离线',
            'disabled': '已禁用'
        }
        status = self.get_computed_status(obj) or obj.status
        return mapping.get(status, status)
        if not obj.version:
            # 未上报版本，保守视为不落后，只在 UI 提示“未知版本”
            return False
        try:
            return _compare_semver(obj.version, expected) < 0
        except Exception:
            # 格式异常时不做判定，避免影响接口
            return False

    def get_expected_min_version(self, obj: Agent) -> str | None:
        return self._get_expected_min_version(obj)

    def get_task_stats(self, obj: Agent) -> dict | None:
        """获取 Agent 任务统计信息"""
        try:
            stats = getattr(obj, 'task_stats', None)
            if stats:
                return {
                    'total': stats.total_tasks,
                    'success': stats.success_tasks,
                    'failed': stats.failed_tasks,
                    'cancelled': stats.cancelled_tasks,
                    'avg_duration_ms': round(stats.avg_duration_ms, 2),
                    'success_rate': stats.success_rate,
                    'health_status': stats.health_status,
                    'last_updated': stats.last_updated.isoformat() if stats.last_updated else None,
                }
        except AgentTaskStats.DoesNotExist:
            pass
        return None

    @staticmethod
    def _get_expected_min_version(agent: Agent) -> str | None:
        """
        根据环境读取期望最小版本：
          - agent.min_version_by_env: dict, key 为环境（dev/test/staging/prod），可包含 'default'
          - agent.min_version: 全局字符串
        """
        # 按环境配置
        by_env = ConfigManager.get("agent.min_version_by_env", {}) or {}
        tags = []
        try:
            raw = getattr(getattr(agent, "host", None), "tags", []) or []
            if isinstance(raw, dict):
                for k, v in raw.items():
                    tags.append(str(k))
                    if isinstance(v, str):
                        tags.append(v)
            elif isinstance(raw, (list, tuple)):
                for item in raw:
                    if isinstance(item, dict):
                        k = str(item.get('key', '')).strip()
                        v = str(item.get('value', '')).strip()
                        if k:
                            tags.append(k)
                        if v:
                            tags.append(v)
                    else:
                        tags.append(str(item))
        except Exception:
            tags = []
        tags_lower = {str(t).strip().lower() for t in tags if str(t).strip()}

        if isinstance(by_env, dict):
            for env_key, min_ver in by_env.items():
                if not isinstance(env_key, str):
                    continue
                if not isinstance(min_ver, str) or not min_ver.strip():
                    continue
                if env_key.lower() in tags_lower:
                    return min_ver.strip()
            default_val = by_env.get("default")
            if isinstance(default_val, str) and default_val.strip():
                return default_val.strip()

        # 全局配置
        global_min = ConfigManager.get("agent.min_version", None)
        if isinstance(global_min, str) and global_min.strip():
            return global_min.strip()
        return None


class AgentDetailSerializer(serializers.ModelSerializer):
    host = HostSerializer(read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    agent_type_display = serializers.CharField(source='get_agent_type_display', read_only=True)
    computed_status = serializers.SerializerMethodField()
    computed_status_display = serializers.SerializerMethodField()
    tokens = AgentTokenSerializer(many=True, read_only=True)
    tags = serializers.ListField(source='host.tags', read_only=True)
    is_version_outdated = serializers.SerializerMethodField()
    expected_min_version = serializers.SerializerMethodField()

    class Meta:
        model = Agent
        fields = [
            'id',
            'host',
            'agent_type',
            'agent_type_display',
            'status',
            'status_display',
            'computed_status',
            'computed_status_display',
            'version',
            'is_version_outdated',
            'expected_min_version',
            'endpoint',
            'agent_server_id',
            'last_heartbeat_at',
            'last_error_code',
            'tags',
            'created_at',
            'updated_at',
            'tokens',
        ]
        read_only_fields = fields

    def get_is_version_outdated(self, obj: Agent) -> bool:
        # 与列表序列化保持一致的逻辑
        return AgentSerializer(context=self.context).get_is_version_outdated(obj)

    def get_expected_min_version(self, obj: Agent) -> str | None:
        return AgentSerializer._get_expected_min_version(obj)

    def get_computed_status(self, obj: Agent) -> str | None:
        return AgentSerializer(context=self.context).get_computed_status(obj)

    def get_computed_status_display(self, obj: Agent) -> str:
        return AgentSerializer(context=self.context).get_computed_status_display(obj)


def _parse_semver(ver: str) -> tuple[int, int, int]:
    """
    解析简单的语义化版本号：major.minor.patch
    非法或缺失部分按 0 处理，不支持预发布/构建后缀，但足够用于“是否落后”的粗略比较。
    """
    if not ver:
        return 0, 0, 0
    parts = ver.strip().split(".")
    nums: list[int] = []
    for i in range(3):
        if i < len(parts):
            p = parts[i]
            # 去掉可能的后缀，例如 "1.2.3-beta" -> 只取数字前缀
            num_str = ""
            for ch in p:
                if ch.isdigit():
                    num_str += ch
                else:
                    break
            try:
                nums.append(int(num_str) if num_str else 0)
            except ValueError:
                nums.append(0)
        else:
            nums.append(0)
    return nums[0], nums[1], nums[2]


def _compare_semver(a: str, b: str) -> int:
    """
    比较两个简单语义化版本：
      - 返回 -1 表示 a < b
      - 返回 0  表示 a == b
      - 返回 1  表示 a > b
    """
    ma, na, pa = _parse_semver(a)
    mb, nb, pb = _parse_semver(b)
    if (ma, na, pa) < (mb, nb, pb):
        return -1
    if (ma, na, pa) > (mb, nb, pb):
        return 1
    return 0


class IssueTokenSerializer(serializers.Serializer):
    expired_at = serializers.DateTimeField(required=False, allow_null=True)
    note = serializers.CharField(required=False, allow_blank=True, max_length=255)
    confirmed = serializers.BooleanField(required=True, help_text="高危操作二次确认")


class AgentEnableSerializer(serializers.Serializer):
    note = serializers.CharField(required=False, allow_blank=True, max_length=255)


class AgentUpdateServerSerializer(serializers.Serializer):
    agent_server_id = serializers.IntegerField(required=False, allow_null=True)


class BatchOperationSerializer(serializers.Serializer):
    agent_ids = serializers.ListField(
        child=serializers.IntegerField(),
        help_text="Agent ID 列表"
    )
    confirmed = serializers.BooleanField(required=True, help_text="批量高危操作二次确认")
    agent_server_id = serializers.IntegerField(required=False, allow_null=True, help_text="Agent-Server ID")


class AgentInstallRecordSerializer(serializers.ModelSerializer):
    host_name = serializers.CharField(source='host.name', read_only=True)
    host_ip = serializers.CharField(source='host.ip_address', read_only=True)
    installed_by_name = serializers.CharField(source='installed_by.username', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    agent_id = serializers.IntegerField(source='agent.id', read_only=True, allow_null=True)

    # 包信息字段
    package_os_type = serializers.SerializerMethodField()
    package_arch = serializers.SerializerMethodField()
    package_version_display = serializers.SerializerMethodField()

    # 任务统计字段
    task_total_hosts = serializers.SerializerMethodField()
    task_success_count = serializers.SerializerMethodField()
    task_failed_count = serializers.SerializerMethodField()

    def get_package_os_type(self, obj):
        if obj.package_id:
            try:
                from .models import AgentPackage
                package = AgentPackage.objects.get(id=obj.package_id)
                return package.get_os_type_display()
            except AgentPackage.DoesNotExist:
                pass
        return obj.package_version or ''

    def get_package_arch(self, obj):
        if obj.package_id:
            try:
                from .models import AgentPackage
                package = AgentPackage.objects.get(id=obj.package_id)
                return package.get_arch_display()
            except AgentPackage.DoesNotExist:
                pass
        return ''

    def get_package_version_display(self, obj):
        if obj.package_id:
            try:
                from .models import AgentPackage
                package = AgentPackage.objects.get(id=obj.package_id)
                return package.version
            except AgentPackage.DoesNotExist:
                pass
        return obj.package_version or ''

    def get_task_total_hosts(self, obj):
        """获取该安装任务涉及的总主机数"""
        if obj.install_task_id:
            return AgentInstallRecord.objects.filter(install_task_id=obj.install_task_id).count()
        return 1

    def get_task_success_count(self, obj):
        """获取该安装任务成功的记录数"""
        if obj.install_task_id:
            return AgentInstallRecord.objects.filter(
                install_task_id=obj.install_task_id,
                status='success'
            ).count()
        return 1 if obj.status == 'success' else 0

    def get_task_failed_count(self, obj):
        """获取该安装任务失败的记录数"""
        if obj.install_task_id:
            return AgentInstallRecord.objects.filter(
                install_task_id=obj.install_task_id,
                status='failed'
            ).count()
        return 1 if obj.status == 'failed' else 0

    class Meta:
        model = AgentInstallRecord
        fields = [
            'id',
            'host_id',
            'host_name',
            'host_ip',
            'agent_id',
            'install_type',
            'status',
            'status_display',
            'package_version_display',
            'package_os_type',
            'package_arch',
            'task_total_hosts',
            'task_success_count',
            'task_failed_count',
            'agent_server_listen_addr',
            'max_connections',
            'heartbeat_timeout',
            'control_plane_url',
            'error_message',
            'error_detail',
            'message',
            'installed_by',
            'installed_by_name',
            'installed_at',
            'install_task_id',
        ]
        read_only_fields = [
            'id',
            'host_name',
            'host_ip',
            'agent_id',
            'installed_by',
            'installed_by_name',
            'installed_at',
            'control_plane_url',
        ]


class AgentUninstallRecordSerializer(serializers.ModelSerializer):
    host_name = serializers.CharField(source='host.name', read_only=True)
    host_ip = serializers.CharField(source='host.ip_address', read_only=True)
    uninstalled_by_name = serializers.CharField(source='uninstalled_by.username', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    agent_type_display = serializers.CharField(source='get_agent_type_display', read_only=True)
    agent_id = serializers.IntegerField(source='agent.id', read_only=True, allow_null=True)
    agent_type = serializers.CharField(read_only=True)

    # 包信息字段（通过agent.install_record关联获取）
    package_version = serializers.SerializerMethodField()
    package_os_type = serializers.SerializerMethodField()
    package_arch = serializers.SerializerMethodField()

    # 任务统计字段
    task_total_hosts = serializers.SerializerMethodField()
    task_success_count = serializers.SerializerMethodField()
    task_failed_count = serializers.SerializerMethodField()

    def get_package_version(self, obj):
        if obj.agent and hasattr(obj.agent, 'install_record') and obj.agent.install_record:
            return obj.agent.install_record.package_version or ''
        return ''

    def get_package_os_type(self, obj):
        if obj.agent and hasattr(obj.agent, 'install_record') and obj.agent.install_record and obj.agent.install_record.package_id:
            try:
                from .models import AgentPackage
                package = AgentPackage.objects.get(id=obj.agent.install_record.package_id)
                return package.get_os_type_display()
            except AgentPackage.DoesNotExist:
                pass
        return ''

    def get_package_arch(self, obj):
        if obj.agent and hasattr(obj.agent, 'install_record') and obj.agent.install_record and obj.agent.install_record.package_id:
            try:
                from .models import AgentPackage
                package = AgentPackage.objects.get(id=obj.agent.install_record.package_id)
                return package.get_arch_display()
            except AgentPackage.DoesNotExist:
                pass
        return ''

    def get_task_total_hosts(self, obj):
        """获取该卸载任务涉及的总主机数"""
        if obj.uninstall_task_id:
            return AgentUninstallRecord.objects.filter(uninstall_task_id=obj.uninstall_task_id).count()
        return 1

    def get_task_success_count(self, obj):
        """获取该卸载任务成功的记录数"""
        if obj.uninstall_task_id:
            return AgentUninstallRecord.objects.filter(
                uninstall_task_id=obj.uninstall_task_id,
                status='success'
            ).count()
        return 1 if obj.status == 'success' else 0

    def get_task_failed_count(self, obj):
        """获取该卸载任务失败的记录数"""
        if obj.uninstall_task_id:
            return AgentUninstallRecord.objects.filter(
                uninstall_task_id=obj.uninstall_task_id,
                status='failed'
            ).count()
        return 1 if obj.status == 'failed' else 0

    class Meta:
        model = AgentUninstallRecord
        fields = [
            'id',
            'host_id',
            'host_name',
            'host_ip',
            'agent_id',
            'agent_type',
            'agent_type_display',
            'status',
            'status_display',
            'package_version',
            'package_os_type',
            'package_arch',
            'task_total_hosts',
            'task_success_count',
            'task_failed_count',
            'error_message',
            'uninstalled_by',
            'uninstalled_by_name',
            'uninstalled_at',
            'uninstall_task_id',
        ]
        read_only_fields = [
            'id',
            'host_name',
            'host_ip',
            'agent_id',
            'agent_type',
            'agent_type_display',
            'uninstalled_by',
            'uninstalled_by_name',
            'uninstalled_at',
        ]


class AgentServerSerializer(serializers.ModelSerializer):
    shared_secret = serializers.CharField(write_only=True, required=False, allow_blank=True)
    has_secret = serializers.SerializerMethodField()
    shared_secret_last4 = serializers.SerializerMethodField()

    class Meta:
        model = AgentServer
        fields = [
            'id',
            'name',
            'base_url',
            'shared_secret',
            'require_signature',
            'has_secret',
            'shared_secret_last4',
            'is_active',
            'description',
            'created_at',
            'updated_at',
        ]
        read_only_fields = ['id', 'has_secret', 'shared_secret_last4', 'created_at', 'updated_at']

    def get_has_secret(self, obj: AgentServer) -> bool:
        return bool(obj.shared_secret)

    def get_shared_secret_last4(self, obj: AgentServer) -> str:
        if not obj.shared_secret:
            return ''
        return obj.shared_secret[-4:]

    def validate(self, attrs):
        if 'base_url' in attrs:
            from apps.agents.utils import normalize_agent_server_base_url

            normalized = normalize_agent_server_base_url(attrs.get('base_url'))
            if not normalized:
                raise serializers.ValidationError({'base_url': ['无效的 Agent-Server 地址']})
            attrs['base_url'] = normalized

        if self.instance is None and not attrs.get('shared_secret'):
            raise serializers.ValidationError({'shared_secret': ['shared_secret 不能为空']})

        require_signature = attrs.get(
            'require_signature',
            getattr(self.instance, 'require_signature', False) if self.instance else False
        )
        if require_signature:
            has_secret = bool(attrs.get('shared_secret'))
            if not has_secret and self.instance:
                has_secret = bool(self.instance.shared_secret)
            if not has_secret:
                raise serializers.ValidationError({'shared_secret': ['启用签名校验必须提供 shared_secret']})

        return attrs

    def update(self, instance, validated_data):
        if 'shared_secret' not in validated_data:
            validated_data.pop('shared_secret', None)
        return super().update(instance, validated_data)


class BatchUninstallSerializer(serializers.Serializer):
    agent_ids = serializers.ListField(
        child=serializers.IntegerField(),
        min_length=1,
        help_text="要卸载的 Agent ID 列表"
    )
    account_id = serializers.IntegerField(required=False, allow_null=True, help_text="用于SSH的账号ID（可选）")
    confirmed = serializers.BooleanField(help_text="确认执行卸载操作")


class AgentPackageSerializer(serializers.ModelSerializer):
    created_by_name = serializers.CharField(source='created_by.username', read_only=True)
    os_type_display = serializers.CharField(source='get_os_type_display', read_only=True)
    arch_display = serializers.CharField(source='get_arch_display', read_only=True)
    package_type_display = serializers.CharField(source='get_package_type_display', read_only=True)
    download_url = serializers.SerializerMethodField()
    file_name = serializers.SerializerMethodField()
    validate_status = serializers.CharField(read_only=True)
    validate_message = serializers.CharField(read_only=True)

    class Meta:
        model = AgentPackage
        fields = [
            'package_type',
            'package_type_display',
            'id',
            'version',
            'description',
            'os_type',
            'os_type_display',
            'arch',
            'arch_display',
            'storage_type',
            'storage_path',
            'file_name',
            'file_size',
            'md5_hash',
            'sha256_hash',
            'download_url',
            'is_default',
            'is_active',
            'validate_status',
            'validate_message',
            'created_by',
            'created_by_name',
            'created_at',
            'updated_at',
        ]
        read_only_fields = [
            'package_type_display',
            'id',
            'created_by',
            'created_by_name',
            'file_name',
            'created_at',
            'updated_at',
            'validate_status',
            'validate_message',
        ]

    def get_download_url(self, obj):
        """获取下载地址"""
        return obj.get_download_url()

    def get_file_name(self, obj):
        """获取文件名"""
        # 优先使用file_name字段
        if obj.file_name:
            return obj.file_name
        # 如果使用对象存储，从storage_path中提取文件名
        if obj.storage_path:
            return obj.storage_path.split('/')[-1]
        return ''


class AgentPackageCreateSerializer(serializers.ModelSerializer):
    package_type = serializers.ChoiceField(choices=AgentPackage.PACKAGE_TYPE_CHOICES, default='agent')
    file = serializers.FileField(write_only=True, required=False)

    class Meta:
        model = AgentPackage
        fields = ['package_type', 'version', 'description', 'os_type', 'arch', 'file', 'is_default', 'is_active']

    def validate(self, attrs):
        """验证文件有效性并检查唯一性约束"""
        file_obj = attrs.get('file')
        if self.instance is None:
            if not file_obj:
                raise serializers.ValidationError({'file': ['File is required.']})
        elif 'file' in attrs and not file_obj:
            raise serializers.ValidationError({'file': ['File is required.']})

        if file_obj:
            size = getattr(file_obj, 'size', None)
            if size == 0:
                raise serializers.ValidationError({'file': ['File content is empty.']})

        version = attrs.get('version')
        os_type = attrs.get('os_type')
        arch = attrs.get('arch')
        package_type = attrs.get('package_type') or 'agent'

        if version and os_type and arch:
            # 检查是否已存在相同的组合
            query = AgentPackage.objects.filter(
                package_type=package_type,
                version=version,
                os_type=os_type,
                arch=arch
            )

            # 如果是更新操作，排除当前记录
            if self.instance:
                query = query.exclude(pk=self.instance.pk)

            if query.exists():
                raise serializers.ValidationError({
                    'non_field_errors': ['字段 version, os_type, arch 必须能构成唯一集合。']
                })

        return attrs

    def create(self, validated_data):
        # file 字段仅用于上传，不存储到模型
        validated_data.pop('file', None)
        return super().create(validated_data)

    def update(self, instance, validated_data):
        # file 字段仅用于上传，不存储到模型
        validated_data.pop('file', None)
        return super().update(instance, validated_data)


class GenerateInstallScriptSerializer(serializers.Serializer):
    host_ids = serializers.ListField(
        child=serializers.IntegerField(),
        help_text="主机ID列表"
    )
    install_type = serializers.ChoiceField(
        choices=['agent', 'agent-server'],
        default='agent',
        required=False,
        help_text="安装类型：agent/agent-server"
    )
    agent_server_base_url = serializers.CharField(
        required=False,
        allow_blank=True,
        max_length=500,
        help_text="控制面访问 Agent-Server 的地址(base_url)，安装 agent-server 时需要"
    )
    agent_server_url = serializers.CharField(
        required=False,
        allow_blank=True,
        max_length=500,
        help_text="Agent 连接 Agent-Server 的 WS 地址（仅安装agent时需要）"
    )
    agent_server_backup_url = serializers.CharField(
        required=False,
        allow_blank=True,
        max_length=500,
        help_text="agent-server备用地址（可选）"
    )
    ws_backoff_initial_ms = serializers.IntegerField(
        required=False,
        min_value=100,
        max_value=60000,
        default=1000,
        help_text="ws重连初始退避毫秒（可选，100~60000）"
    )
    ws_backoff_max_ms = serializers.IntegerField(
        required=False,
        min_value=1000,
        max_value=600000,
        default=30000,
        help_text="ws重连最大退避毫秒（可选，1000~600000）"
    )
    ws_max_retries = serializers.IntegerField(
        required=False,
        min_value=1,
        max_value=20,
        default=6,
        help_text="ws重连最大次数（可选，1~20）"
    )
    agent_server_listen_addr = serializers.CharField(
        required=False,
        allow_blank=True,
        max_length=100,
        default='0.0.0.0:8080',
        help_text="Agent-Server 服务监听地址（写入agent-server配置）"
    )
    max_connections = serializers.IntegerField(
        required=False,
        min_value=100,
        max_value=10000,
        default=1000,
        help_text="最大连接数（agent-server安装需要，100~10000）"
    )
    heartbeat_timeout = serializers.IntegerField(
        required=False,
        min_value=30,
        max_value=300,
        default=60,
        help_text="心跳超时秒数（agent-server安装需要，30~300）"
    )
    package_id = serializers.IntegerField(required=False, allow_null=True, help_text="Agent package ID（可选）")
    package_version = serializers.CharField(required=False, allow_blank=True, max_length=50, help_text="Agent package version（可选）")
    max_concurrent_tasks = serializers.IntegerField(
        required=False,
        min_value=1,
        max_value=20,
        allow_null=True,
        help_text="最大并发任务数（可选，1~20）"
    )
    auth_shared_secret = serializers.CharField(
        required=False,
        allow_blank=True,
        max_length=255,
        help_text="agent-server HMAC shared secret（可选）"
    )
    auth_require_signature = serializers.BooleanField(
        required=False,
        default=False,
        help_text="agent-server 是否强制签名校验（可选）"
    )

    def validate(self, attrs):
        install_type = attrs.get('install_type', 'agent')
        if install_type == 'agent':
            if not attrs.get('agent_server_url'):
                raise serializers.ValidationError({'agent_server_url': ['安装 Agent 需要 agent_server_url']})
        else:
            # Agent-Server 仅依赖控制面配置，忽略前端传入的 agent_server_url
            attrs['agent_server_url'] = ''
            control_plane_url = getattr(settings, "CONTROL_PLANE_URL", "") or ""
            if not control_plane_url:
                raise serializers.ValidationError({'non_field_errors': ['控制面未配置 CONTROL_PLANE_URL，无法安装 Agent-Server']})
            base_url = attrs.get('agent_server_base_url') or attrs.get('agent_server_listen_addr') or ''
            from apps.agents.utils import normalize_agent_server_base_url
            normalized = normalize_agent_server_base_url(base_url)
            if not normalized:
                raise serializers.ValidationError({'agent_server_base_url': ['安装 Agent-Server 需要控制面访问地址']})
            attrs['agent_server_base_url'] = normalized
            if attrs.get('auth_require_signature') and not attrs.get('auth_shared_secret'):
                raise serializers.ValidationError({'auth_shared_secret': ['启用签名校验必须提供 shared_secret']})
        return attrs


class BatchInstallSerializer(serializers.Serializer):
    host_ids = serializers.ListField(
        child=serializers.IntegerField(),
        help_text="主机ID列表"
    )
    account_id = serializers.IntegerField(
        required=False,
        allow_null=True,
        help_text="用于ssh的账号ID（可选）"
    )
    install_type = serializers.ChoiceField(
        choices=['agent', 'agent-server'],
        default='agent',
        required=False,
        help_text="安装类型：agent/agent-server"
    )
    agent_server_base_url = serializers.CharField(
        required=False,
        allow_blank=True,
        max_length=500,
        help_text="控制面访问 Agent-Server 的地址(base_url)，安装 agent-server 时需要"
    )
    agent_server_url = serializers.CharField(
        required=False,
        allow_blank=True,
        max_length=500,
        help_text="Agent 连接 Agent-Server 的 WS 地址（仅安装agent时需要）"
    )
    agent_server_backup_url = serializers.CharField(
        required=False,
        allow_blank=True,
        max_length=500,
        help_text="agent-server备用地址（可选）"
    )
    ws_backoff_initial_ms = serializers.IntegerField(
        required=False,
        min_value=100,
        max_value=60000,
        default=1000,
        help_text="ws重连初始退避毫秒（可选，100~60000）"
    )
    ws_backoff_max_ms = serializers.IntegerField(
        required=False,
        min_value=1000,
        max_value=600000,
        default=30000,
        help_text="ws重连最大退避毫秒（可选，1000~600000）"
    )
    ws_max_retries = serializers.IntegerField(
        required=False,
        min_value=1,
        max_value=20,
        default=6,
        help_text="ws重连最大次数（可选，1~20）"
    )
    agent_server_listen_addr = serializers.CharField(
        required=False,
        allow_blank=True,
        max_length=100,
        default='0.0.0.0:8080',
        help_text="Agent-Server 服务监听地址（写入agent-server配置）"
    )
    max_connections = serializers.IntegerField(
        required=False,
        min_value=100,
        max_value=10000,
        default=1000,
        help_text="最大连接数（agent-server安装需要，100~10000）"
    )
    heartbeat_timeout = serializers.IntegerField(
        required=False,
        min_value=30,
        max_value=300,
        default=60,
        help_text="心跳超时秒数（agent-server安装需要，30~300）"
    )
    ssh_timeout = serializers.IntegerField(
        required=False,
        min_value=60,
        max_value=900,
        default=300,
        help_text="ssh安装超时（秒，60~900）"
    )
    allow_reinstall = serializers.BooleanField(
        required=False,
        default=False,
        help_text="如主机已有agent，是否允许覆盖安装"
    )
    package_id = serializers.IntegerField(required=False, allow_null=True, help_text="Agent package ID（可选）")
    package_version = serializers.CharField(required=False, allow_blank=True, max_length=50, help_text="Agent package version（可选）")
    auth_shared_secret = serializers.CharField(
        required=False,
        allow_blank=True,
        max_length=255,
        help_text="agent-server HMAC shared secret（可选）"
    )
    auth_require_signature = serializers.BooleanField(
        required=False,
        default=False,
        help_text="agent-server 是否强制签名校验（可选）"
    )
    confirmed = serializers.BooleanField(
        required=True,
        help_text="批量安装高危操作二次确认"
    )

    def validate(self, attrs):
        install_type = attrs.get('install_type', 'agent')
        if install_type == 'agent':
            if not attrs.get('agent_server_url'):
                raise serializers.ValidationError({'agent_server_url': ['安装 Agent 需要 agent_server_url']})
        else:
            attrs['agent_server_url'] = ''
            control_plane_url = getattr(settings, "CONTROL_PLANE_URL", "") or ""
            if not control_plane_url:
                raise serializers.ValidationError({'non_field_errors': ['控制面未配置 CONTROL_PLANE_URL，无法安装 Agent-Server']})
            base_url = attrs.get('agent_server_base_url') or attrs.get('agent_server_listen_addr') or ''
            from apps.agents.utils import normalize_agent_server_base_url
            normalized = normalize_agent_server_base_url(base_url)
            if not normalized:
                raise serializers.ValidationError({'agent_server_base_url': ['安装 Agent-Server 需要控制面访问地址']})
            attrs['agent_server_base_url'] = normalized
            if attrs.get('auth_require_signature') and not attrs.get('auth_shared_secret'):
                raise serializers.ValidationError({'auth_shared_secret': ['启用签名校验必须提供 shared_secret']})
        return attrs


class HostAgentStatusSerializer(serializers.Serializer):
    """主机Agent状态序列化器"""

    id = serializers.IntegerField()
    name = serializers.CharField()
    ip_address = serializers.CharField()
    agent_status = serializers.SerializerMethodField()
    agent_type = serializers.SerializerMethodField()
    agent_type_display = serializers.SerializerMethodField()
    agent_id = serializers.SerializerMethodField()
    agent_version = serializers.SerializerMethodField()
    computed_status = serializers.SerializerMethodField()
    computed_status_display = serializers.SerializerMethodField()
    can_install = serializers.SerializerMethodField()

    def get_agent_status(self, obj):
        """获取主机的Agent状态"""
        if hasattr(obj, 'agent') and obj.agent:
            return obj.agent.status
        return None

    def get_agent_type(self, obj):
        """获取主机的Agent类型"""
        if hasattr(obj, 'agent') and obj.agent:
            return obj.agent.agent_type
        return None

    def get_agent_type_display(self, obj):
        """获取主机的Agent类型显示名"""
        if hasattr(obj, 'agent') and obj.agent:
            return obj.agent.get_agent_type_display()
        return None

    def get_agent_id(self, obj):
        """获取主机的Agent ID"""
        if hasattr(obj, 'agent') and obj.agent:
            return obj.agent.id
        return None

    def get_agent_version(self, obj):
        """获取主机的Agent版本"""
        if hasattr(obj, 'agent') and obj.agent:
            return obj.agent.version
        return None

    def get_computed_status(self, obj):
        """获取主机的Agent计算状态"""
        if hasattr(obj, 'agent') and obj.agent:
            return AgentSerializer(context=self.context).get_computed_status(obj.agent)
        return None

    def get_computed_status_display(self, obj):
        """获取主机的Agent计算状态显示名"""
        if hasattr(obj, 'agent') and obj.agent:
            return AgentSerializer(context=self.context).get_computed_status_display(obj.agent)
        return None

    def get_can_install(self, obj):
        """判断是否可以安装（没有在线Agent或Agent不在线）"""
        if hasattr(obj, 'agent') and obj.agent:
            return obj.agent.status != 'online'
        return True


class AgentControlSerializer(serializers.Serializer):
    """Agent 管控请求序列化器"""

    action = serializers.ChoiceField(
        choices=['start', 'stop', 'restart'],
        help_text="管控动作：start/stop/restart"
    )
    reason = serializers.CharField(
        required=False,
        allow_blank=True,
        max_length=255,
        help_text="可选备注"
    )


class AgentUpgradeSerializer(serializers.Serializer):
    """Agent 升级请求序列化器"""

    target_version = serializers.CharField(
        required=False,
        allow_blank=True,
        max_length=50,
        help_text="目标版本号，留空则升级到最新版本"
    )
    package_id = serializers.IntegerField(
        required=False,
        help_text="指定安装包ID，优先于 target_version"
    )
    confirmed = serializers.BooleanField(
        required=True,
        help_text="二次确认标志"
    )
