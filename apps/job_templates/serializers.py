"""
作业模板序列化器
"""
from django.db import models
from rest_framework import serializers
from apps.hosts.models import Host, HostGroup
from .models import JobTemplate, JobStep, ExecutionPlan, PlanStep
from apps.script_templates.models import UserFavorite, ScriptTemplate


class JobStepListSerializer(serializers.ListSerializer):
    """为作业步骤列表序列化器添加执行账号名称"""

    def to_representation(self, data):
        from apps.hosts.models import ServerAccount

        iterable = data.all() if isinstance(data, models.Manager) else data
        representation = super().to_representation(iterable)

        account_ids = {item.get('account_id') for item in representation if item.get('account_id')}

        if not account_ids:
            for item in representation:
                item['account_name'] = None
            return representation

        accounts = ServerAccount.objects.filter(id__in=account_ids).values('id', 'name')
        account_map = {account['id']: account['name'] for account in accounts}

        for item in representation:
            account_id = item.get('account_id')
            if account_id in account_map:
                item['account_name'] = account_map[account_id]
            elif account_id:
                item['account_name'] = f'未知账号 (ID: {account_id})'
            else:
                item['account_name'] = None

        return representation


class JobStepSerializer(serializers.ModelSerializer):
    """作业步骤序列化器"""
    account_name = serializers.CharField(read_only=True, allow_null=True)

    step_type_display = serializers.CharField(source='get_step_type_display', read_only=True)
    target_hosts = serializers.SerializerMethodField()
    target_groups = serializers.SerializerMethodField()

    class Meta:
        model = JobStep
        fields = [
            'id', 'name', 'description', 'step_type', 'step_type_display',
            'order', 'step_parameters', 'timeout', 'ignore_error',
            # 脚本相关字段
            'script_type', 'script_content', 'script_template', 'account_id', 'account_name',
            # 文件传输相关字段
            'remote_path', 'overwrite_policy', 'file_sources', 'bandwidth_limit',
            # 目标主机相关字段
            'target_hosts', 'target_groups'
        ]
        read_only_fields = ['id']
        list_serializer_class = JobStepListSerializer

    def get_target_hosts(self, obj):
        """获取目标主机列表"""
        return [
            {
                'id': host.id,
                'name': host.name,
                'ip_address': host.ip_address,
                'status': host.status
            }
            for host in obj.target_hosts.all()
        ]

    def get_target_groups(self, obj):
        """获取目标分组列表"""
        return [
            {
                'id': group.id,
                'name': group.name,
                'description': group.description,
                # Host.groups 是 ManyToMany 到 HostGroup，反向关系默认是 host_set
                'host_count': group.host_set.count()
            }
            for group in obj.target_groups.all()
        ]

    def validate(self, data):
        """验证步骤数据"""
        step_type = data.get('step_type')

        if step_type == 'script':
            if not data.get('script_content'):
                raise serializers.ValidationError({'script_content': '脚本步骤必须包含脚本内容'})
            if not data.get('script_type'):
                raise serializers.ValidationError({'script_type': '脚本步骤必须指定脚本类型'})
        elif step_type == 'file_transfer':
            # 强制使用 file_sources，必须为非空数组
            fs = data.get('file_sources') or []
            if not isinstance(fs, list) or len(fs) == 0:
                raise serializers.ValidationError({'file_sources': '文件传输步骤必须包含非空的 file_sources'})
            # 简单校验每个 source
            for s in fs:
                if not isinstance(s, dict) or s.get('type') not in ('server', 'artifact'):
                    raise serializers.ValidationError({'file_sources': "每个 source 必须是对象且 type 为 'server' 或 'artifact'"})
                if not s.get('remote_path'):
                    raise serializers.ValidationError({'file_sources': '每个 source 必须包含 remote_path'})
                if s.get('type') == 'server':
                    if not s.get('source_server_host') or not s.get('source_server_path'):
                        raise serializers.ValidationError({'file_sources': 'server source 需要 source_server_host 与 source_server_path'})
                    if s.get('account_id') is None or not isinstance(s.get('account_id'), int):
                        raise serializers.ValidationError({'file_sources': 'server source 需要整数类型的 account_id'})
                else:
                    if not (s.get('download_url') or s.get('storage_path')):
                        raise serializers.ValidationError({'file_sources': 'artifact source 必须提供 download_url 或 storage_path'})

        return data


class JobStepCreateSerializer(serializers.Serializer):
    """作业步骤创建/更新序列化器"""

    name = serializers.CharField(max_length=200, help_text="步骤名称")
    description = serializers.CharField(required=False, allow_blank=True, help_text="步骤描述")
    step_type = serializers.ChoiceField(
        choices=[('script', '脚本'), ('file_transfer', '文件传输')],
        help_text="步骤类型：script(脚本) 或 file_transfer(文件传输)"
    )
    order = serializers.IntegerField(required=False, min_value=1, help_text="步骤顺序")
    step_parameters = serializers.ListField(
        child=serializers.CharField(),
        required=False,
        allow_empty=True,
        help_text="步骤参数列表"
    )
    timeout = serializers.IntegerField(required=False, min_value=1, default=300, help_text="超时时间(秒)")
    ignore_error = serializers.BooleanField(required=False, default=False, help_text="是否忽略错误")

    # 脚本相关字段
    script_type = serializers.CharField(required=False, allow_blank=True, help_text="脚本类型")
    script_content = serializers.CharField(required=False, allow_blank=True, help_text="脚本内容")
    script_template = serializers.IntegerField(required=False, allow_null=True, help_text="脚本模板ID")
    account_id = serializers.IntegerField(required=False, allow_null=True, help_text="执行账号ID")

    # 文件传输相关字段（仅 artifact/server 源）
    remote_path = serializers.CharField(required=False, allow_blank=True, help_text="远程路径")
    overwrite_policy = serializers.CharField(required=False, allow_blank=True, help_text="覆盖策略")
    bandwidth_limit = serializers.IntegerField(required=False, min_value=0, default=0, help_text="带宽限制(MB/s)，0表示不限制")
    # file_sources 对应文件传输步骤，仅在 step_type == 'file_transfer' 时必需
    file_sources = serializers.ListField(
        child=serializers.DictField(),
        required=False,
        allow_empty=True,
        default=list,
        help_text="文件来源数组（仅 file_transfer 步骤需要），示例: {'type':'server','source_server_host':'1.2.3.4','source_server_path':'/data/a.tar.gz','remote_path':'/tmp/a.tar.gz','account_id':1} 或 {'type':'artifact','download_url':'...','remote_path':'/tmp/a.tar.gz'}"
    )

    # 目标选择：主机ID + 分组ID
    target_host_ids = serializers.ListField(
        child=serializers.IntegerField(),
        required=False,
        allow_empty=True,
        help_text="目标主机ID列表"
    )
    target_group_ids = serializers.ListField(
        child=serializers.IntegerField(),
        required=False,
        allow_empty=True,
        help_text="目标主机分组ID列表"
    )

    def validate(self, data):
        """验证步骤数据"""
        step_type = data.get('step_type')

        if step_type == 'script':
            if not data.get('script_content'):
                raise serializers.ValidationError({'script_content': '脚本步骤必须包含脚本内容'})
            if not data.get('script_type'):
                raise serializers.ValidationError({'script_type': '脚本步骤必须指定脚本类型'})
        elif step_type == 'file_transfer':
            # 强制使用 file_sources
            fs = data.get('file_sources') or []
            if not isinstance(fs, list) or len(fs) == 0:
                raise serializers.ValidationError({'file_sources': '文件传输步骤必须包含非空的 file_sources'})
            for s in fs:
                if not isinstance(s, dict) or s.get('type') not in ('server', 'artifact'):
                    raise serializers.ValidationError({'file_sources': "每个 source 必须是对象且 type 为 'server' 或 'artifact'"})
                if not s.get('remote_path'):
                    raise serializers.ValidationError({'file_sources': '每个 source 必须包含 remote_path'})
                if s.get('type') == 'server':
                    if not s.get('source_server_host') or not s.get('source_server_path'):
                        raise serializers.ValidationError({'file_sources': 'server source 需要 source_server_host 与 source_server_path'})
                    if s.get('account_id') is not None and not isinstance(s.get('account_id'), int):
                        raise serializers.ValidationError({'file_sources': 'server source 中 account_id 必须为整数'})
                else:
                    if not (s.get('download_url') or s.get('storage_path')):
                        raise serializers.ValidationError({'file_sources': 'artifact source 必须提供 download_url 或 storage_path'})

        # 脚本模板校验
        script_template_id = data.get('script_template')
        if step_type == 'script':
            if script_template_id:
                if not ScriptTemplate.objects.filter(id=script_template_id).exists():
                    raise serializers.ValidationError({'script_template': '脚本模板不存在'})
        else:
            data['script_template'] = None

        # 验证目标主机/分组ID格式：主机或分组至少要有一个
        target_host_ids = data.get('target_host_ids') or []
        target_group_ids = data.get('target_group_ids') or []

        if not target_host_ids and not target_group_ids:
            raise serializers.ValidationError({'target_host_ids': '必须指定至少一个目标主机或主机分组'})

        for host_id in target_host_ids:
            if not isinstance(host_id, int) or host_id <= 0:
                raise serializers.ValidationError({'target_host_ids': '主机ID必须是正整数'})

        for group_id in target_group_ids:
            if not isinstance(group_id, int) or group_id <= 0:
                raise serializers.ValidationError({'target_group_ids': '分组ID必须是正整数'})

        return data


class PlanStepListSerializer(serializers.ListSerializer):
    """为方案步骤列表序列化器添加执行账号名称"""

    def to_representation(self, data):
        from apps.hosts.models import ServerAccount

        iterable = data.all() if isinstance(data, models.Manager) else data
        representation = super().to_representation(iterable)

        account_ids = {item.get('step_account_id') for item in representation if item.get('step_account_id')}

        if not account_ids:
            for item in representation:
                item['step_account_name'] = None
            return representation

        accounts = ServerAccount.objects.filter(id__in=account_ids).values('id', 'name')
        account_map = {account['id']: account['name'] for account in accounts}

        for item in representation:
            account_id = item.get('step_account_id')
            if account_id in account_map:
                item['step_account_name'] = account_map[account_id]
            elif account_id:
                item['step_account_name'] = f'未知账号 (ID: {account_id})'
            else:
                item['step_account_name'] = None

        return representation


class PlanStepSerializer(serializers.ModelSerializer):
    """方案步骤序列化器 - 优化版本，减少重复数据"""
    step_account_name = serializers.CharField(read_only=True, allow_null=True)
    target_hosts = serializers.SerializerMethodField(read_only=True)
    target_groups = serializers.SerializerMethodField(read_only=True)

    # 基础信息
    template_step_id = serializers.SerializerMethodField()
    is_template_step_deleted = serializers.SerializerMethodField()

    # 只在有覆盖时才显示有效值
    effective_parameters = serializers.SerializerMethodField()
    effective_timeout = serializers.SerializerMethodField()
    effective_script_content = serializers.SerializerMethodField()
    effective_script_type = serializers.SerializerMethodField()

    class Meta:
        model = PlanStep
        fields = [
            'id', 'order', 'template_step_id', 'is_template_step_deleted',
            # 快照数据（执行方案创建时的模板状态）
            'step_name', 'step_description', 'step_type',
            'step_script_content', 'step_script_type',
            'step_parameters', 'step_timeout', 'step_ignore_error',
            'step_target_host_ids', 'step_target_group_ids', 'step_targets',
            'target_hosts', 'target_groups',
            'step_account_name',
            'step_account_id', 'step_file_sources', 'step_bandwidth_limit',
            # 覆盖配置
            'override_parameters', 'override_timeout',
            # 有效值（仅在有覆盖时显示）
            'effective_parameters', 'effective_timeout',
            'effective_script_content', 'effective_script_type'
        ]
        read_only_fields = ['id']
        list_serializer_class = PlanStepListSerializer

    def get_template_step_id(self, obj):
        """获取关联的模板步骤ID"""
        return obj.step.id if obj.step else None

    def get_is_template_step_deleted(self, obj):
        """标记原始模板步骤是否已被删除"""
        return obj.step is None

    def get_effective_parameters(self, obj):
        """获取有效的位置参数（仅在有覆盖时返回）"""
        if obj.override_parameters:
            return obj.get_effective_parameters()
        return None

    def get_effective_timeout(self, obj):
        """获取有效超时时间（仅在有覆盖时返回）"""
        if obj.override_timeout is not None:
            return obj.get_effective_timeout()
        return None

    def get_effective_script_content(self, obj):
        """获取有效的脚本内容（仅在有覆盖时返回）"""
        # 目前脚本内容不支持覆盖，所以总是返回 None
        return None

    def get_effective_script_type(self, obj):
        """获取有效的脚本类型（仅在有覆盖时返回）"""
        # 目前脚本类型不支持覆盖，所以总是返回 None
        return None

    def get_target_hosts(self, obj):
        """根据快照的主机ID列表，返回当前主机详情（名称/IP/状态）"""
        from apps.hosts.models import Host

        host_ids = obj.step_target_host_ids or []
        if not host_ids:
          return []

        hosts = Host.objects.filter(id__in=host_ids)
        host_map = {h.id: h for h in hosts}

        # 按快照顺序返回
        result = []
        for host_id in host_ids:
            host = host_map.get(host_id)
            if host:
                result.append({
                    'id': host.id,
                    'name': host.name,
                    'ip_address': host.ip_address,
                    'status': host.status,
                })
        return result

    def get_target_groups(self, obj):
        """根据快照的分组ID列表，返回当前分组详情"""
        from apps.hosts.models import HostGroup

        group_ids = obj.step_target_group_ids or []
        if not group_ids:
            return []

        groups = HostGroup.objects.filter(id__in=group_ids)
        group_map = {g.id: g for g in groups}

        result = []
        for group_id in group_ids:
            group = group_map.get(group_id)
            if group:
                result.append({
                    'id': group.id,
                    'name': group.name,
                    'description': group.description,
                })
        return result

    def to_representation(self, instance):
        """自定义序列化输出，动态移除不需要的字段"""
        data = super().to_representation(instance)

        # 如果没有参数覆盖，移除 effective_parameters 字段
        if not instance.override_parameters:
            data.pop('effective_parameters', None)

        # 如果没有超时覆盖，移除 effective_timeout 字段
        if instance.override_timeout is None:
            data.pop('effective_timeout', None)

        # 目前脚本内容和类型不支持覆盖，总是移除这些字段
        data.pop('effective_script_content', None)
        data.pop('effective_script_type', None)

        return data


class ExecutionPlanSerializer(serializers.ModelSerializer):
    """执行方案序列化器"""

    created_by_name = serializers.CharField(source='created_by.username', read_only=True)
    updated_by_name = serializers.CharField(source='updated_by.username', read_only=True)
    template_name = serializers.CharField(source='template.name', read_only=True)
    template_global_parameters = serializers.JSONField(source='template.global_parameters', read_only=True)
    global_parameters_snapshot = serializers.JSONField(read_only=True)
    step_count = serializers.ReadOnlyField()
    scheduled_job_ref_count = serializers.IntegerField(read_only=True)
    needs_sync = serializers.ReadOnlyField()
    success_rate = serializers.ReadOnlyField()
    plan_steps = PlanStepSerializer(source='planstep_set', many=True, read_only=True)


    class Meta:
        model = ExecutionPlan
        fields = [
            'id', 'template', 'template_name', 'template_global_parameters', 'global_parameters_snapshot', 'name', 'description',
            'is_synced', 'needs_sync', 'last_sync_at',
            'step_count', 'scheduled_job_ref_count', 'total_executions', 'success_executions', 'failed_executions',
            'success_rate', 'last_executed_at',
            'created_by', 'created_by_name', 'updated_by', 'updated_by_name', 'created_at', 'updated_at',
            'plan_steps'
        ]
        read_only_fields = ['id', 'template', 'is_synced', 'last_sync_at',
                           'total_executions', 'success_executions', 'failed_executions',
                           'last_executed_at', 'created_by', 'updated_by', 'created_at', 'updated_at']


class ExecutionPlanListSerializer(ExecutionPlanSerializer):
    """执行方案列表序列化器（裁剪字段）"""

    class Meta(ExecutionPlanSerializer.Meta):
        fields = [
            'id', 'template', 'template_name', 'name', 'description',
            'is_synced', 'needs_sync', 'last_sync_at',
            'step_count', 'scheduled_job_ref_count', 'total_executions', 'success_executions', 'failed_executions',
            'success_rate', 'last_executed_at',
            'created_by', 'created_by_name', 'updated_by', 'updated_by_name', 'created_at', 'updated_at'
        ]

class JobTemplateSerializer(serializers.ModelSerializer):
    """作业模板序列化器"""

    created_by_name = serializers.CharField(source='created_by.username', read_only=True)
    updated_by_name = serializers.CharField(source='updated_by.username', read_only=True)
    step_count = serializers.ReadOnlyField()
    plan_count = serializers.ReadOnlyField()
    scheduled_job_ref_count = serializers.IntegerField(read_only=True)
    has_unsync_plans = serializers.ReadOnlyField()
    tag_list = serializers.ReadOnlyField()
    steps = JobStepSerializer(many=True, read_only=True)
    plans = ExecutionPlanSerializer(many=True, read_only=True)

    class Meta:
        model = JobTemplate
        fields = [
            'id', 'name', 'description', 'category', 'tags_json', 'tag_list',
            'global_parameters', 'step_count', 'plan_count', 'scheduled_job_ref_count', 'has_unsync_plans',
            'created_by', 'created_by_name', 'updated_by', 'updated_by_name', 'created_at', 'updated_at',
            'steps', 'plans'
        ]
        read_only_fields = ['id', 'created_by', 'updated_by', 'created_at', 'updated_at']


class JobTemplateListSerializer(JobTemplateSerializer):
    """作业模板列表序列化器（裁剪字段）"""

    class Meta(JobTemplateSerializer.Meta):
        fields = [
            'id', 'name', 'description', 'category', 'tags_json', 'tag_list',
            'step_count', 'plan_count', 'scheduled_job_ref_count', 'has_unsync_plans',
            'created_by', 'created_by_name', 'updated_by', 'updated_by_name', 'created_at', 'updated_at'
        ]


class JobTemplateCreateSerializer(serializers.Serializer):
    """作业模板创建序列化器"""

    name = serializers.CharField(max_length=200)
    description = serializers.CharField(required=False, allow_blank=True)
    category = serializers.CharField(max_length=50, required=False, allow_blank=True)
    tags = serializers.ListField(
        child=serializers.DictField(),
        required=False,
        allow_empty=True,
        help_text="标签列表，格式：[{'key': 'env', 'value': 'prod'}, {'key': 'team', 'value': 'ops'}]"
    )

    # 全局变量
    global_parameters = serializers.DictField(
        required=False,
        allow_empty=True,
        help_text="模板级别的全局变量，可在所有步骤中使用"
    )

    # 步骤定义
    steps = serializers.ListField(
        child=JobStepCreateSerializer(),
        min_length=1,
        help_text="步骤列表，每个步骤包含name、step_type、step_parameters、target_host_ids等字段"
    )

    def validate_global_parameters(self, value):
        """
        规范全局变量结构：
        - 兼容旧格式：直接是字符串/数字/布尔
        - 对对象值保留 value / type / description
        """
        if not isinstance(value, dict):
            return value

        normalized = {}
        for key, item in value.items():
            if isinstance(item, (str, int, float, bool)) or item is None:
                normalized[key] = item
                continue

            if isinstance(item, dict):
                cleaned = {}
                if 'value' in item:
                    cleaned['value'] = item['value']
                if 'type' in item:
                    cleaned['type'] = item['type']
                description = item.get('description')
                if isinstance(description, str):
                    cleaned['description'] = description.strip()
                normalized[key] = cleaned
            else:
                normalized[key] = item

        return normalized


class JobTemplateUpdateSerializer(serializers.Serializer):
    """作业模板更新序列化器（与创建保持一致，steps 复用 JobStepCreateSerializer）"""

    name = serializers.CharField(max_length=200, required=False, help_text="模板名称")
    description = serializers.CharField(required=False, allow_blank=True, help_text="模板描述")
    category = serializers.CharField(max_length=50, required=False, allow_blank=True, help_text="分类")
    tags = serializers.ListField(
        child=serializers.DictField(),
        required=False,
        allow_empty=True,
        help_text="标签列表，格式：[{'key': 'env', 'value': 'prod'}, {'key': 'team', 'value': 'ops'}]"
    )

    # 全局变量
    global_parameters = serializers.DictField(
        required=False,
        allow_empty=True,
        help_text="模板级别的全局变量，可在所有步骤中使用"
    )

    # 步骤定义（可选，用于完整更新）
    steps = serializers.ListField(
        child=JobStepCreateSerializer(),
        required=False,
        min_length=1,
        help_text="步骤列表，用于完整更新步骤"
    )

    def validate_name(self, value):
        """验证名称唯一性（排除当前实例）"""
        if self.instance and value != self.instance.name:
            if JobTemplate.objects.filter(name=value).exists():
                raise serializers.ValidationError(f"模板名称 '{value}' 已存在，请使用其他名称")
        return value

    def validate_global_parameters(self, value):
        """
        规范全局变量结构（与创建保持一致）：
        - 兼容旧格式：直接是字符串/数字/布尔
        - 对对象值保留 value / type / description
        """
        if not isinstance(value, dict):
            return value

        normalized = {}
        for key, item in value.items():
            if isinstance(item, (str, int, float, bool)) or item is None:
                normalized[key] = item
                continue

            if isinstance(item, dict):
                cleaned = {}
                if 'value' in item:
                    cleaned['value'] = item['value']
                if 'type' in item:
                    cleaned['type'] = item['type']
                description = item.get('description')
                if isinstance(description, str):
                    cleaned['description'] = description.strip()
                normalized[key] = cleaned
            else:
                normalized[key] = item

        return normalized


class ExecutionPlanCreateSerializer(serializers.Serializer):
    """执行方案创建序列化器"""

    name = serializers.CharField(max_length=200)
    description = serializers.CharField(required=False, allow_blank=True)

    # 包含的步骤
    step_configs = serializers.ListField(
        child=serializers.DictField(),
        min_length=1,
        help_text="步骤配置列表，每个配置包含step_id、order等字段"
    )
    # 全局变量覆盖（只能覆盖已存在的模板全局变量的值）
    global_parameter_overrides = serializers.DictField(
        required=False,
        allow_empty=True,
        help_text="模板级别的全局变量覆盖映射，只允许更新已存在的变量，不能新增或删除"
    )

    def validate_step_configs(self, value):
        """验证步骤配置"""
        step_ids = []
        orders = []

        for i, config in enumerate(value):
            step_id = config.get('step_id')
            if not step_id:
                raise serializers.ValidationError(f"步骤配置{i+1}缺少step_id字段")

            if step_id in step_ids:
                raise serializers.ValidationError(f"步骤ID {step_id} 重复")
            step_ids.append(step_id)

            order = config.get('order')
            if not isinstance(order, int) or order < 1:
                raise serializers.ValidationError(f"步骤配置{i+1}的order必须是大于0的整数")

            if order in orders:
                raise serializers.ValidationError(f"执行顺序 {order} 重复")
            orders.append(order)

        return value

    def validate_global_parameter_overrides(self, value):
        # 保证是 dict
        if not isinstance(value, dict):
            raise serializers.ValidationError("global_parameter_overrides 必须是一个对象")
        return value


class ExecutionPlanUpdateSerializer(serializers.ModelSerializer):
    """执行方案更新序列化器"""

    created_by_name = serializers.CharField(source='created_by.username', read_only=True)
    template_name = serializers.CharField(source='template.name', read_only=True)
    step_count = serializers.ReadOnlyField()
    needs_sync = serializers.ReadOnlyField()
    success_rate = serializers.ReadOnlyField()
    plan_steps = PlanStepSerializer(source='planstep_set', many=True, read_only=True)

    # 步骤配置（用于更新）
    step_configs = serializers.ListField(
        child=serializers.DictField(),
        required=False,
        write_only=True,
        help_text="步骤配置列表，每个配置包含step_id、order等字段"
    )

    # 全局变量覆盖（用于更新）
    global_parameter_overrides = serializers.DictField(
        required=False,
        write_only=True,
        help_text="全局变量覆盖值"
    )

    class Meta:
        model = ExecutionPlan
        fields = [
            'id', 'template', 'template_name', 'name', 'description',
            'is_synced', 'needs_sync', 'last_sync_at',
            'step_count', 'total_executions', 'success_executions', 'failed_executions',
            'success_rate', 'last_executed_at',
            'created_by', 'created_by_name', 'created_at', 'updated_at',
            'plan_steps', 'step_configs', 'global_parameter_overrides'
        ]
        read_only_fields = ['id', 'template', 'is_synced', 'last_sync_at',
                           'total_executions', 'success_executions', 'failed_executions',
                           'last_executed_at', 'created_by', 'created_at', 'updated_at']

    def validate_step_configs(self, value):
        """验证步骤配置"""
        if not value:  # 允许空列表
            return value

        step_ids = []
        orders = []

        for i, config in enumerate(value):
            step_id = config.get('step_id')
            if not step_id:
                raise serializers.ValidationError(f"步骤配置{i+1}缺少step_id字段")

            if step_id in step_ids:
                raise serializers.ValidationError(f"步骤ID {step_id} 重复")
            step_ids.append(step_id)

            order = config.get('order')
            if not isinstance(order, int) or order < 1:
                raise serializers.ValidationError(f"步骤配置{i+1}的order必须是大于0的整数")

            if order in orders:
                raise serializers.ValidationError(f"执行顺序 {order} 重复")
            orders.append(order)

        return value

    def update(self, instance, validated_data):
        """更新执行方案"""
        from django.db import transaction
        from .models import JobStep, PlanStep
        from .sync_service import TemplateChangeDetector
        import copy

        step_configs = validated_data.pop('step_configs', None)
        global_parameter_overrides = validated_data.pop('global_parameter_overrides', None)

        # 更新基本信息
        instance = super().update(instance, validated_data)

        # 处理全局变量覆盖
        if global_parameter_overrides is not None:
            # 深拷贝模板的全局变量作为快照
            snapshot = copy.deepcopy(instance.template.global_parameters or {})
            if global_parameter_overrides:
                for k, v in global_parameter_overrides.items():
                    if k not in snapshot:
                        raise serializers.ValidationError(f"不能覆盖不存在的模板变量: {k}")
                    # 如果模板变量是扩展对象（含 value/type/description），只更新 value 字段；否则直接替换值
                    if isinstance(snapshot[k], dict):
                        snapshot[k]['value'] = v
                    else:
                        snapshot[k] = v
            instance.global_parameters_snapshot = snapshot
            instance.save(update_fields=['global_parameters_snapshot'])

        # 如果提供了步骤配置，则更新步骤
        if step_configs is not None:
            with transaction.atomic():
                # 删除现有的步骤配置
                instance.planstep_set.all().delete()

                # 创建新的步骤配置
                for config in step_configs:
                    step_id = config['step_id']
                    try:
                        step = JobStep.objects.get(id=step_id, template=instance.template)
                        plan_step = PlanStep.objects.create(
                            plan=instance,
                            step=step,
                            order=config['order'],
                            override_parameters=config.get('override_parameters', {}),
                            override_timeout=config.get('override_timeout'),
                            step_hash=TemplateChangeDetector.calculate_step_hash(step)
                        )
                        # 复制快照数据
                        plan_step.copy_from_template_step()
                        plan_step.save()
                    except JobStep.DoesNotExist:
                        raise serializers.ValidationError(f"步骤ID {step_id} 不存在或不属于当前模板")

        return instance


class ExecutionPlanExecuteSerializer(serializers.Serializer):
    """执行方案执行序列化器"""

    name = serializers.CharField(max_length=200, required=False, help_text="执行名称")
    description = serializers.CharField(required=False, allow_blank=True, help_text="执行描述")

    # 执行参数
    execution_parameters = serializers.DictField(
        required=False,
        allow_empty=True,
        help_text="执行参数，用于覆盖步骤中的变量"
    )

    agent_server_id = serializers.IntegerField(
        required=True,
        help_text="Agent-Server ID"
    )

    # 执行配置
    execution_mode = serializers.ChoiceField(
        choices=[
            ('parallel', '并行执行'),
            ('serial', '串行执行'),
            ('rolling', '滚动执行'),
        ],
        default='parallel',
        help_text="执行模式"
    )
    rolling_batch_size = serializers.IntegerField(
        default=1,
        min_value=1,
        help_text="滚动批次大小"
    )
    rolling_batch_delay = serializers.IntegerField(
        default=0,
        min_value=0,
        help_text="批次间延迟(秒)"
    )

    # 触发类型
    trigger_type = serializers.ChoiceField(
        choices=[
            ('manual', '手动执行'),
            ('scheduled', '定时执行'),
            ('debug', '调试执行'),
        ],
        default='manual',
        help_text="触发类型"
    )


class UserFavoriteSerializer(serializers.ModelSerializer):
    """用户收藏序列化器"""
    user_name = serializers.CharField(source='user.username', read_only=True)
    favorite_type_display = serializers.CharField(source='get_favorite_type_display', read_only=True)
    category_display = serializers.CharField(source='get_category_display', read_only=True)

    class Meta:
        model = UserFavorite
        fields = [
            'id', 'user', 'user_name', 'favorite_type', 'favorite_type_display',
            'object_id', 'category', 'category_display', 'note',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'user', 'user_name', 'created_at', 'updated_at']


class UserFavoriteCreateSerializer(serializers.ModelSerializer):
    """创建收藏序列化器"""

    class Meta:
        model = UserFavorite
        fields = ['favorite_type', 'object_id', 'category', 'note']

    def create(self, validated_data):
        validated_data['user'] = self.context['request'].user
        return super().create(validated_data)


class FavoriteToggleSerializer(serializers.Serializer):
    """收藏切换序列化器"""
    favorite_type = serializers.ChoiceField(
        choices=UserFavorite.FAVORITE_TYPE_CHOICES,
        required=True
    )
    object_id = serializers.IntegerField(required=True)
    category = serializers.ChoiceField(
        choices=UserFavorite.CATEGORY_CHOICES,
        default='personal'
    )
    note = serializers.CharField(max_length=200, required=False, allow_blank=True)
