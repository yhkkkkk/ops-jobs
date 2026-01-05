"""
主机管理序列化器
"""
from rest_framework import serializers
from drf_spectacular.utils import extend_schema_field
from .models import Host, HostGroup, ServerAccount
from .utils import encrypt_password


class HostGroupSerializer(serializers.ModelSerializer):
    """主机分组序列化器"""
    created_by_name = serializers.CharField(source='created_by.username', read_only=True)
    parent_name = serializers.CharField(source='parent.name', read_only=True)
    full_path = serializers.CharField(read_only=True)
    level = serializers.IntegerField(read_only=True)
    host_count = serializers.SerializerMethodField()
    online_count = serializers.SerializerMethodField()
    offline_count = serializers.SerializerMethodField()
    children_count = serializers.SerializerMethodField()
    has_children = serializers.SerializerMethodField()

    class Meta:
        model = HostGroup
        fields = ['id', 'name', 'description', 'parent', 'parent_name', 'sort_order',
                 'full_path', 'level', 'created_by', 'created_by_name', 'created_at',
                 'updated_at', 'host_count', 'online_count', 'offline_count',
                 'children_count', 'has_children']
        read_only_fields = ['created_by', 'created_at', 'updated_at']

    @extend_schema_field(serializers.IntegerField())
    def get_host_count(self, obj):
        """获取直接关联的主机数量"""
        return obj.host_set.count()

    @extend_schema_field(serializers.IntegerField())
    def get_online_count(self, obj):
        """获取在线主机数量"""
        return obj.host_set.filter(status='online').count()

    @extend_schema_field(serializers.IntegerField())
    def get_offline_count(self, obj):
        """获取离线主机数量"""
        return obj.host_set.exclude(status='online').count()

    @extend_schema_field(serializers.IntegerField())
    def get_children_count(self, obj):
        """获取子分组数量"""
        return obj.children.count()

    @extend_schema_field(serializers.BooleanField())
    def get_has_children(self, obj):
        """是否有子分组"""
        return obj.children.exists()

    def validate_parent(self, value):
        """验证父分组"""
        if value is None:
            return value

        # 如果是更新操作，检查是否会形成循环引用
        if self.instance:
            if not self.instance.can_move_to(value):
                raise serializers.ValidationError("不能移动到自己或自己的子分组")

        return value


class HostGroupTreeSerializer(serializers.ModelSerializer):
    """主机分组树形序列化器"""
    children = serializers.SerializerMethodField()
    host_count = serializers.SerializerMethodField()
    total_host_count = serializers.SerializerMethodField()
    online_count = serializers.SerializerMethodField()
    total_online_count = serializers.SerializerMethodField()

    class Meta:
        model = HostGroup
        fields = ['id', 'name', 'description', 'parent', 'sort_order', 'level',
                 'host_count', 'total_host_count', 'online_count', 'total_online_count', 'children']

    @extend_schema_field(serializers.ListField(child=serializers.DictField()))
    def get_children(self, obj):
        """获取子分组"""
        children = obj.children.all().order_by('sort_order', 'name')
        return HostGroupTreeSerializer(children, many=True, context=self.context).data

    @extend_schema_field(serializers.IntegerField())
    def get_host_count(self, obj):
        """获取直接关联的主机数量"""
        return obj.host_set.count()

    @extend_schema_field(serializers.IntegerField())
    def get_total_host_count(self, obj):
        """获取包含子分组的总主机数量"""
        total = obj.host_set.count()
        for descendant in obj.get_descendants():
            total += descendant.host_set.count()
        return total

    @extend_schema_field(serializers.IntegerField())
    def get_online_count(self, obj):
        """获取直接关联的在线主机数量"""
        return obj.host_set.filter(status='online').count()

    @extend_schema_field(serializers.IntegerField())
    def get_total_online_count(self, obj):
        """获取包含子分组的总在线主机数量"""
        total = obj.host_set.filter(status='online').count()
        for descendant in obj.get_descendants():
            total += descendant.host_set.filter(status='online').count()
        return total


class HostGroupSimpleSerializer(serializers.ModelSerializer):
    """主机分组简单序列化器（用于下拉选择）"""
    full_path = serializers.CharField(read_only=True)
    level = serializers.IntegerField(read_only=True)

    class Meta:
        model = HostGroup
        fields = ['id', 'name', 'full_path', 'level', 'parent']


class HostSerializer(serializers.ModelSerializer):
    """主机序列化器"""
    created_by_name = serializers.CharField(source='created_by.username', read_only=True)
    groups_info = HostGroupSerializer(source='groups', many=True, read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    os_type_display = serializers.CharField(source='get_os_type_display', read_only=True)
    cloud_provider_display = serializers.CharField(source='get_cloud_provider_display', read_only=True)
    device_type_display = serializers.CharField(source='get_device_type_display', read_only=True)
    tags = serializers.ListField(
        child=serializers.DictField(child=serializers.CharField(allow_blank=True)),
        required=False,
        default=list
    )
    account_info = serializers.SerializerMethodField()
    ip_address = serializers.SerializerMethodField()
    agent_info = serializers.SerializerMethodField()

    class Meta:
        model = Host
        fields = [
            # 基本信息
            'id', 'name', 'ip_address', 'port', 'os_type', 'os_type_display',
            'account', 'account_info',
            'status', 'status_display', 'groups', 'groups_info', 'description',
            # Agent信息
            'agent_info',
            # 网络信息
            'public_ip', 'internal_ip', 'internal_mac', 'external_mac', 'gateway', 'dns_servers',
            # 云厂商信息
            'cloud_provider', 'cloud_provider_display', 'instance_id', 'region', 'zone',
            'instance_type', 'network_type',
            # 硬件信息
            'device_type', 'device_type_display', 'cpu_cores', 'memory_gb', 'disk_gb',
            # 系统详细信息
            'os_version', 'kernel_version', 'hostname', 'cpu_model', 'os_arch', 'cpu_arch', 'boot_time',
            # 业务信息
            'tags', 'service_role', 'remarks',
            # 管理信息
            'owner', 'department',
            # 时间信息
            'created_by', 'created_by_name', 'created_at', 'updated_at', 'last_check_time'
        ]
        read_only_fields = ['created_by', 'created_at', 'updated_at', 'last_check_time', 'status']
    
    def get_ip_address(self, obj):
        """获取IP地址（优先内网IP）"""
        return obj.ip_address
    
    def get_account_info(self, obj):
        """获取账号信息"""
        if obj.account:
            return {
                'id': obj.account.id,
                'name': obj.account.name,
                'username': obj.account.username,
                'auth_type': 'password' if obj.account.password else ('key' if obj.account.private_key else 'none'),
            }
        return None

    def validate_tags(self, value):
        if value is None:
            return []
        if not isinstance(value, (list, tuple)):
            raise serializers.ValidationError("标签需为键值对列表")
        cleaned = []
        for item in value:
            if not isinstance(item, dict):
                raise serializers.ValidationError("每个标签需为对象 {key, value}")
            key = str(item.get('key', '')).strip()
            if not key:
                continue
            val_raw = item.get('value', '')
            val = '' if val_raw is None else str(val_raw).strip()
            cleaned.append({'key': key, 'value': val})
        return cleaned
    
    def get_agent_info(self, obj):
        """获取Agent信息"""
        try:
            agent = obj.agent
            return {
                'id': agent.id,
                'status': agent.status,
                'status_display': agent.get_status_display(),
                'version': agent.version or '',
                'last_heartbeat_at': agent.last_heartbeat_at.isoformat() if agent.last_heartbeat_at else None,
            }
        except:
            # 如果没有关联的Agent，返回None
            return None


class HostSimpleSerializer(serializers.ModelSerializer):
    """主机简单序列化器（用于列表显示）"""
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    os_type_display = serializers.CharField(source='get_os_type_display', read_only=True)

    class Meta:
        model = Host
        fields = ['id', 'name', 'ip_address', 'port', 'os_type', 'os_type_display',
                 'status', 'status_display', 'tags', 'last_check_time']


class HostConnectionTestSerializer(serializers.Serializer):
    """主机连接测试序列化器"""
    host_ids = serializers.ListField(
        child=serializers.IntegerField(),
        help_text="主机ID列表"
    )


class HostCommandExecuteSerializer(serializers.Serializer):
    """主机命令执行序列化器"""
    command = serializers.CharField(help_text="要执行的命令")
    timeout = serializers.IntegerField(default=30, help_text="超时时间（秒）")
    
    def validate_command(self, value):
        if not value.strip():
            raise serializers.ValidationError("命令不能为空")
        return value.strip()


class HostGroupHostsSerializer(serializers.Serializer):
    """主机分组主机操作序列化器"""
    host_ids = serializers.ListField(
        child=serializers.IntegerField(),
        help_text="主机ID列表"
    )
    
    def validate_host_ids(self, value):
        if not value:
            raise serializers.ValidationError("主机ID列表不能为空")
        return value


class FileTransferSerializer(serializers.Serializer):
    """文件传输序列化器"""
    local_path = serializers.CharField(help_text="本地文件路径")
    remote_path = serializers.CharField(help_text="远程文件路径")

    def validate_local_path(self, value):
        if not value.strip():
            raise serializers.ValidationError("本地路径不能为空")
        return value.strip()

    def validate_remote_path(self, value):
        if not value.strip():
            raise serializers.ValidationError("远程路径不能为空")
        return value.strip()


class BatchFileUploadSerializer(serializers.Serializer):
    """批量文件上传序列化器"""
    host_ids = serializers.ListField(
        child=serializers.IntegerField(),
        help_text="主机ID列表"
    )
    local_path = serializers.CharField(help_text="本地文件路径")
    remote_path = serializers.CharField(help_text="远程文件路径")

    def validate_host_ids(self, value):
        if not value:
            raise serializers.ValidationError("主机ID列表不能为空")
        return value


class BatchFileDownloadSerializer(serializers.Serializer):
    """批量文件下载序列化器"""
    host_ids = serializers.ListField(
        child=serializers.IntegerField(),
        help_text="主机ID列表"
    )
    remote_path = serializers.CharField(help_text="远程文件路径")
    local_base_path = serializers.CharField(help_text="本地基础路径")

    def validate_host_ids(self, value):
        if not value:
            raise serializers.ValidationError("主机ID列表不能为空")
        return value


class HostToHostTransferSerializer(serializers.Serializer):
    """主机间文件传输序列化器"""
    source_host_id = serializers.IntegerField(help_text="源主机ID")
    target_host_id = serializers.IntegerField(help_text="目标主机ID")
    source_path = serializers.CharField(help_text="源文件路径")
    target_path = serializers.CharField(help_text="目标文件路径")
    overwrite_policy = serializers.ChoiceField(
        choices=['overwrite', 'skip', 'backup', 'fail'],
        default='overwrite',
        help_text="覆盖策略：overwrite(覆盖)、skip(跳过)、backup(备份)、fail(冲突时报错)"
    )

    def validate(self, attrs):
        if attrs['source_host_id'] == attrs['target_host_id']:
            raise serializers.ValidationError("源主机和目标主机不能相同")
        return attrs

    def validate_source_path(self, value):
        if not value.strip():
            raise serializers.ValidationError("源文件路径不能为空")
        return value.strip()

    def validate_target_path(self, value):
        if not value.strip():
            raise serializers.ValidationError("目标文件路径不能为空")
        return value.strip()


class ServerAccountSerializer(serializers.ModelSerializer):
    """服务器账号序列化器"""
    auth_type = serializers.SerializerMethodField()
    has_password = serializers.SerializerMethodField()
    has_private_key = serializers.SerializerMethodField()

    class Meta:
        model = ServerAccount
        fields = ['id', 'name', 'username', 'password', 'private_key', 'description',
                 'auth_type', 'has_password', 'has_private_key']
        extra_kwargs = {
            'password': {'write_only': True},
            'private_key': {'write_only': True},
        }

    def get_auth_type(self, obj):
        """获取认证方式"""
        has_password = bool(obj.password)
        has_private_key = bool(obj.private_key)

        if has_password:
            return 'password'
        elif has_private_key:
            return 'key'
        else:
            return 'none'

    def get_has_password(self, obj):
        """是否配置了密码"""
        return bool(obj.password)

    def get_has_private_key(self, obj):
        """是否配置了私钥"""
        return bool(obj.private_key)

    def create(self, validated_data):
        pwd = validated_data.get('password')
        key = validated_data.get('private_key')
        if pwd and key:
            raise serializers.ValidationError("密码和私钥只能填一个")
        if pwd:
            validated_data['password'] = encrypt_password(pwd)
        if key:
            validated_data['private_key'] = encrypt_password(key)

        return super().create(validated_data)

    def update(self, instance, validated_data):
        pwd = validated_data.get('password')
        key = validated_data.get('private_key')
        if pwd and key:
            raise serializers.ValidationError("密码和私钥只能填一个")
        if 'password' in validated_data:
            if pwd:
                validated_data['password'] = encrypt_password(pwd)
                validated_data['private_key'] = ''
            else:
                validated_data.pop('password')
        if 'private_key' in validated_data:
            if key:
                validated_data['private_key'] = encrypt_password(key)
                validated_data['password'] = ''
            else:
                validated_data.pop('private_key')

        return super().update(instance, validated_data)


class CloudSyncSerializer(serializers.Serializer):
    """云同步序列化器"""
    provider = serializers.ChoiceField(
        choices=['aliyun', 'tencent', 'aws'],
        help_text="云厂商"
    )
    region = serializers.CharField(
        required=False,
        allow_blank=True,
        help_text="地域（可选）"
    )


class BatchMoveToGroupSerializer(serializers.Serializer):
    """批量移动主机到分组序列化器"""
    host_ids = serializers.ListField(
        child=serializers.IntegerField(),
        help_text="主机ID列表"
    )
    group_id = serializers.IntegerField(
        required=False,
        allow_null=True,
        help_text="目标分组ID，null表示移出所有分组"
    )

    def validate_host_ids(self, value):
        if not value:
            raise serializers.ValidationError("主机ID列表不能为空")
        return value


class HostExcelImportSerializer(serializers.Serializer):
    """主机Excel导入序列化器"""

    file = serializers.FileField(help_text="包含主机数据的Excel文件（.xlsx/.xlsm）")
    default_group_id = serializers.IntegerField(
        required=False,
        allow_null=True,
        help_text="可选：未匹配到任何分组时，默认加入的分组ID"
    )
    overwrite_existing = serializers.BooleanField(
        default=False,
        help_text="当IP+端口已存在时是否覆盖原有主机"
    )

    def validate_file(self, value):
        filename = (value.name or '').lower()
        if not filename.endswith(('.xlsx', '.xlsm', '.xltx', '.xltm')):
            raise serializers.ValidationError("仅支持 .xlsx / .xlsm Excel 文件")

        max_size = 5 * 1024 * 1024  # 5MB
        if value.size and value.size > max_size:
            raise serializers.ValidationError("Excel 文件不能超过 5MB")
        return value

    def validate_default_group_id(self, value):
        if value is None:
            return value
        if not HostGroup.objects.filter(id=value).exists():
            raise serializers.ValidationError("指定的分组不存在")
        return value


class HostBatchUpdateSerializer(serializers.Serializer):
    """
    主机批量编辑序列化器
    说明：
    - host_ids：需要批量修改的主机 ID 列表
    - data：要更新的字段键值对，只会更新允许的字段
    """
    host_ids = serializers.ListField(
        child=serializers.IntegerField(),
        help_text="主机ID列表"
    )
    data = serializers.DictField(
        help_text="要更新的字段键值对（例如：{'os_type': 'linux', 'tags': ['prod','core']}）"
    )

    # 允许批量编辑的字段白名单，避免误改系统字段
    ALLOWED_FIELDS = {
        # 基本信息
        'name', 'port', 'os_type', 'account', 'description',
        # 网络信息
        'public_ip', 'internal_ip', 'internal_mac', 'external_mac',
        'gateway', 'dns_servers',
        # 云厂商信息
        'cloud_provider', 'instance_id', 'region', 'zone',
        'instance_type', 'network_type',
        # 硬件信息
        'device_type', 'cpu_cores', 'memory_gb', 'disk_gb',
        # 系统详细信息
        'os_version', 'kernel_version', 'hostname', 'cpu_model',
        'os_arch', 'cpu_arch',
        # 业务信息
        'tags', 'service_role', 'remarks',
        # 管理信息
        'owner', 'department',
    }

    def validate_host_ids(self, value):
        if not value:
            raise serializers.ValidationError("主机ID列表不能为空")
        return value

    def validate_data(self, value):
        if not value:
            raise serializers.ValidationError("更新数据不能为空")

        invalid_fields = [key for key in value.keys() if key not in self.ALLOWED_FIELDS]
        if invalid_fields:
            raise serializers.ValidationError(
                f"不支持批量编辑以下字段: {', '.join(invalid_fields)}"
            )
        if 'tags' in value:
            tags_value = value.get('tags')
            if tags_value is None:
                value['tags'] = []
            elif not isinstance(tags_value, (list, tuple)):
                raise serializers.ValidationError("tags 需要为字符串列表")
            else:
                cleaned = [str(item).strip() for item in tags_value if str(item).strip()]
                value['tags'] = cleaned
        return value
