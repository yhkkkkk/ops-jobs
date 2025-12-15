"""
Agent 序列化器
"""
from rest_framework import serializers

from apps.hosts.serializers import HostSerializer, HostSimpleSerializer
from .models import Agent, AgentToken, AgentInstallRecord, AgentUninstallRecord, AgentPackage


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
    tokens = AgentTokenSerializer(many=True, read_only=True)

    class Meta:
        model = Agent
        fields = [
            'id',
            'host',
            'status',
            'status_display',
            'version',
            'endpoint',
            'last_heartbeat_at',
            'last_error_code',
            'created_at',
            'updated_at',
            'tokens',
        ]
        read_only_fields = fields


class AgentDetailSerializer(serializers.ModelSerializer):
    host = HostSerializer(read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    tokens = AgentTokenSerializer(many=True, read_only=True)
    business_system = serializers.ReadOnlyField()
    environment = serializers.ReadOnlyField()

    class Meta:
        model = Agent
        fields = [
            'id',
            'host',
            'status',
            'status_display',
            'version',
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
            'host',
            'host_id',
            'host_name',
            'host_ip',
            'agent',
            'agent_id',
            'install_mode',
            'status',
            'status_display',
            'error_message',
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
            'host',
            'host_id',
            'host_name',
            'host_ip',
            'agent',
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
            'file',
            'file_name',
            'file_size',
            'md5_hash',
            'sha256_hash',
            'download_url',
            'is_default',
            'is_active',
            'created_by',
            'created_by_name',
            'created_at',
            'updated_at',
        ]
        read_only_fields = ['id', 'created_by', 'created_by_name', 'file_name', 'created_at', 'updated_at']

    def get_download_url(self, obj):
        """获取下载地址"""
        return obj.get_download_url()

    def get_file_name(self, obj):
        """获取文件名"""
        if obj.file:
            return obj.file.name.split('/')[-1]
        return ''


class AgentPackageCreateSerializer(serializers.ModelSerializer):
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
    install_mode = serializers.ChoiceField(
        choices=['direct', 'agent-server'],
        default='agent-server',
        required=False,
        help_text="安装模式"
    )
    agent_server_url = serializers.CharField(
        required=False,
        allow_blank=True,
        max_length=500,
        help_text="Agent-Server 地址（agent-server 模式需要）"
    )
    agent_server_backup_url = serializers.CharField(
        required=False,
        allow_blank=True,
        max_length=500,
        help_text="Agent-Server 备用地址（可选）"
    )
    ws_backoff_initial_ms = serializers.IntegerField(
        required=False,
        min_value=100,
        max_value=60000,
        default=1000,
        help_text="WS 重连初始退避毫秒（可选，100~60000）"
    )
    ws_backoff_max_ms = serializers.IntegerField(
        required=False,
        min_value=1000,
        max_value=600000,
        default=30000,
        help_text="WS 重连最大退避毫秒（可选，1000~600000）"
    )
    ws_max_retries = serializers.IntegerField(
        required=False,
        min_value=1,
        max_value=20,
        default=6,
        help_text="WS 重连最大次数（可选，1~20）"
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
        help_text="用于SSH的账号ID（可选）"
    )
    install_mode = serializers.ChoiceField(
        choices=['direct', 'agent-server'],
        default='agent-server',
        required=False,
        help_text="安装模式"
    )
    agent_server_url = serializers.CharField(
        required=False,
        allow_blank=True,
        max_length=500,
        help_text="Agent-Server 地址（agent-server 模式需要）"
    )
    agent_server_backup_url = serializers.CharField(
        required=False,
        allow_blank=True,
        max_length=500,
        help_text="Agent-Server 备用地址（可选）"
    )
    ws_backoff_initial_ms = serializers.IntegerField(
        required=False,
        min_value=100,
        max_value=60000,
        default=1000,
        help_text="WS 重连初始退避毫秒（可选，100~60000）"
    )
    ws_backoff_max_ms = serializers.IntegerField(
        required=False,
        min_value=1000,
        max_value=600000,
        default=30000,
        help_text="WS 重连最大退避毫秒（可选，1000~600000）"
    )
    ws_max_retries = serializers.IntegerField(
        required=False,
        min_value=1,
        max_value=20,
        default=6,
        help_text="WS 重连最大次数（可选，1~20）"
    )
    ssh_timeout = serializers.IntegerField(
        required=False,
        min_value=60,
        max_value=900,
        default=300,
        help_text="SSH 安装超时（秒，60~900）"
    )
    allow_reinstall = serializers.BooleanField(
        required=False,
        default=False,
        help_text="如主机已有 Agent 时是否允许覆盖安装"
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
