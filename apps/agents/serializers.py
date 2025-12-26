"""
Agent 序列化器
"""
from rest_framework import serializers

from apps.hosts.serializers import HostSerializer, HostSimpleSerializer
from apps.system_config.models import ConfigManager
from .models import Agent, AgentToken, AgentInstallRecord, AgentUninstallRecord, AgentPackage
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
    computed_status = serializers.SerializerMethodField()
    computed_status_display = serializers.SerializerMethodField()
    tokens = AgentTokenSerializer(many=True, read_only=True)
    is_version_outdated = serializers.SerializerMethodField()
    expected_min_version = serializers.SerializerMethodField()

    class Meta:
        model = Agent
        fields = [
            'id',
            'host',
            'status',
            'status_display',
            'computed_status',
            'computed_status_display',
            'version',
            'is_version_outdated',
            'expected_min_version',
            'endpoint',
            'last_heartbeat_at',
            'last_error_code',
            'created_at',
            'updated_at',
            'tokens',
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

    @staticmethod
    def _get_expected_min_version(agent: Agent) -> str | None:
        """
        根据环境读取期望最小版本：
          - agent.min_version_by_env: dict, key 为环境（dev/test/staging/prod），可包含 'default'
          - agent.min_version: 全局字符串
        """
        # 按环境配置
        by_env = ConfigManager.get("agent.min_version_by_env", {}) or {}
        env = getattr(agent, "environment", None)
        if isinstance(by_env, dict):
            if env and env in by_env:
                val = by_env.get(env)
                if isinstance(val, str) and val.strip():
                    return val.strip()
            # default 兜底
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
    computed_status = serializers.SerializerMethodField()
    computed_status_display = serializers.SerializerMethodField()
    tokens = AgentTokenSerializer(many=True, read_only=True)
    business_system = serializers.ReadOnlyField()
    environment = serializers.ReadOnlyField()
    is_version_outdated = serializers.SerializerMethodField()
    expected_min_version = serializers.SerializerMethodField()

    class Meta:
        model = Agent
        fields = [
            'id',
            'host',
            'status',
            'status_display',
            'computed_status',
            'computed_status_display',
            'version',
            'is_version_outdated',
            'expected_min_version',
            'endpoint',
            'last_heartbeat_at',
            'last_error_code',
            'business_system',
            'environment',
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


class BatchOperationSerializer(serializers.Serializer):
    agent_ids = serializers.ListField(
        child=serializers.IntegerField(),
        help_text="Agent ID 列表"
    )
    confirmed = serializers.BooleanField(required=True, help_text="批量高危操作二次确认")


class AgentInstallRecordSerializer(serializers.ModelSerializer):
    host_name = serializers.CharField(source='host.name', read_only=True)
    host_ip = serializers.CharField(source='host.ip_address', read_only=True)
    installed_by_name = serializers.CharField(source='installed_by.username', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    agent_id = serializers.IntegerField(source='agent.id', read_only=True, allow_null=True)

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
            'agent_server_listen_addr',
            'max_connections',
            'heartbeat_timeout',
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
        ]


class AgentUninstallRecordSerializer(serializers.ModelSerializer):
    host_name = serializers.CharField(source='host.name', read_only=True)
    host_ip = serializers.CharField(source='host.ip_address', read_only=True)
    uninstalled_by_name = serializers.CharField(source='uninstalled_by.username', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    agent_id = serializers.IntegerField(source='agent.id', read_only=True, allow_null=True)

    class Meta:
        model = AgentUninstallRecord
        fields = [
            'id',
            'host_id',
            'host_name',
            'host_ip',
            'agent_id',
            'status',
            'status_display',
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
            'uninstalled_by',
            'uninstalled_by_name',
            'uninstalled_at',
        ]


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
    download_url = serializers.SerializerMethodField()
    file_name = serializers.SerializerMethodField()
    validate_status = serializers.CharField(read_only=True)
    validate_message = serializers.CharField(read_only=True)

    class Meta:
        model = AgentPackage
        fields = [
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
    file = serializers.FileField(write_only=True, required=False)

    class Meta:
        model = AgentPackage
        fields = ['version', 'description', 'os_type', 'arch', 'file', 'is_default', 'is_active']

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

        if version and os_type and arch:
            # 检查是否已存在相同的组合
            query = AgentPackage.objects.filter(
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
    agent_server_url = serializers.CharField(
        required=False,
        allow_blank=True,
        max_length=500,
        help_text="agent-server地址（agent-server模式需要）"
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
        help_text="agent-server监听地址（agent-server安装需要）"
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
    agent_server_url = serializers.CharField(
        required=False,
        allow_blank=True,
        max_length=500,
        help_text="agent-server地址（agent-server模式需要）"
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
        help_text="agent-server监听地址（agent-server安装需要）"
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
    confirmed = serializers.BooleanField(
        required=True,
        help_text="批量安装高危操作二次确认"
    )


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
