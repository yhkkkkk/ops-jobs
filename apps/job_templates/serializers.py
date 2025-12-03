"""
作业模板序列化器
"""
from django.db import models
from rest_framework import serializers
from apps.hosts.models import Host, HostGroup
from .models import JobTemplate, JobStep, ExecutionPlan, PlanStep


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
            'script_type', 'script_content', 'account_id', 'account_name',
            # 文件传输相关字段
            'transfer_type', 'local_path', 'remote_path', 'overwrite_policy',
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
                'host_count': group.hosts.count()
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
            if not data.get('local_path'):
                raise serializers.ValidationError({'local_path': '文件传输步骤必须包含本地路径'})
            if not data.get('remote_path'):
                raise serializers.ValidationError({'remote_path': '文件传输步骤必须包含远程路径'})
            if not data.get('transfer_type'):
                raise serializers.ValidationError({'transfer_type': '文件传输步骤必须指定传输类型'})

        return data


class JobStepCreateSerializer(serializers.Serializer):
    """作业步骤创建序列化器"""
    
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
    account_id = serializers.IntegerField(required=False, allow_null=True, help_text="执行账号ID")
    
    # 文件传输相关字段
    transfer_type = serializers.CharField(required=False, allow_blank=True, help_text="传输类型")
    local_path = serializers.CharField(required=False, allow_blank=True, help_text="本地路径")
    remote_path = serializers.CharField(required=False, allow_blank=True, help_text="远程路径")
    overwrite_policy = serializers.CharField(required=False, allow_blank=True, help_text="覆盖策略")
    
    # 目标选择（统一使用target_host_ids格式）
    target_host_ids = serializers.ListField(
        child=serializers.IntegerField(),
        required=True,
        allow_empty=False,
        help_text="目标主机ID列表"
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
            if not data.get('local_path'):
                raise serializers.ValidationError({'local_path': '文件传输步骤必须包含本地路径'})
            if not data.get('remote_path'):
                raise serializers.ValidationError({'remote_path': '文件传输步骤必须包含远程路径'})
            if not data.get('transfer_type'):
                raise serializers.ValidationError({'transfer_type': '文件传输步骤必须指定传输类型'})
        
        # 验证目标主机ID格式
        target_host_ids = data.get('target_host_ids', [])
        if not target_host_ids:
            raise serializers.ValidationError({'target_host_ids': '必须指定至少一个目标主机'})
        
        for host_id in target_host_ids:
            if not isinstance(host_id, int) or host_id <= 0:
                raise serializers.ValidationError({'target_host_ids': '主机ID必须是正整数'})
        
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
            'step_account_name',
            'step_account_id', 'step_transfer_type', 'step_local_path', 'step_remote_path',
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
    template_name = serializers.CharField(source='template.name', read_only=True)
    template_global_parameters = serializers.JSONField(source='template.global_parameters', read_only=True)
    step_count = serializers.ReadOnlyField()
    needs_sync = serializers.ReadOnlyField()
    success_rate = serializers.ReadOnlyField()
    plan_steps = PlanStepSerializer(source='planstep_set', many=True, read_only=True)


    class Meta:
        model = ExecutionPlan
        fields = [
            'id', 'template', 'template_name', 'template_global_parameters', 'name', 'description',
            'is_synced', 'needs_sync', 'last_sync_at',
            'step_count', 'total_executions', 'success_executions', 'failed_executions',
            'success_rate', 'last_executed_at',
            'created_by', 'created_by_name', 'created_at', 'updated_at',
            'plan_steps'
        ]
        read_only_fields = ['id', 'template', 'is_synced', 'last_sync_at',
                           'total_executions', 'success_executions', 'failed_executions',
                           'last_executed_at', 'created_by', 'created_at', 'updated_at']


class JobTemplateSerializer(serializers.ModelSerializer):
    """作业模板序列化器"""

    created_by_name = serializers.CharField(source='created_by.username', read_only=True)
    step_count = serializers.ReadOnlyField()
    plan_count = serializers.ReadOnlyField()
    has_unsync_plans = serializers.ReadOnlyField()
    tag_list = serializers.ReadOnlyField()
    steps = JobStepSerializer(many=True, read_only=True)
    plans = ExecutionPlanSerializer(many=True, read_only=True)

    class Meta:
        model = JobTemplate
        fields = [
            'id', 'name', 'description', 'category', 'tags_json', 'tag_list',
            'global_parameters', 'step_count', 'plan_count', 'has_unsync_plans',
            'created_by', 'created_by_name', 'created_at', 'updated_at',
            'steps', 'plans'
        ]
        read_only_fields = ['id', 'created_by', 'created_at', 'updated_at']


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

    # 步骤定义（与更新保持一致，复用 JobStepCreateSerializer）
    steps = serializers.ListField(
        child=JobStepCreateSerializer(),
        min_length=1,
        help_text="步骤列表，每个步骤包含name、step_type、step_parameters、target_host_ids等字段"
    )


class JobTemplateUpdateSerializer(serializers.Serializer):
    """作业模板更新序列化器"""
    
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
    
    def validate_steps(self, value):
        """验证步骤定义（如果提供）"""
        if value is not None:
            for i, step in enumerate(value):
                if not step.get('name'):
                    raise serializers.ValidationError(f"步骤{i+1}缺少name字段")

                step_type = step.get('step_type')
                if step_type not in ['script', 'file_transfer']:
                    raise serializers.ValidationError(f"步骤{i+1}的step_type必须是script或file_transfer")

                # 验证脚本步骤的必需字段
                if step_type == 'script':
                    if not step.get('script_content'):
                        raise serializers.ValidationError(f"脚本步骤{i+1}必须包含script_content字段")
                    if not step.get('script_type'):
                        raise serializers.ValidationError(f"脚本步骤{i+1}必须包含script_type字段")
                elif step_type == 'file_transfer':
                    if not step.get('local_path'):
                        raise serializers.ValidationError(f"文件传输步骤{i+1}必须包含local_path字段")
                    if not step.get('remote_path'):
                        raise serializers.ValidationError(f"文件传输步骤{i+1}必须包含remote_path字段")
                    if not step.get('transfer_type'):
                        raise serializers.ValidationError(f"文件传输步骤{i+1}必须包含transfer_type字段")

                # 验证位置参数格式
                step_parameters = step.get('step_parameters', [])
                if not isinstance(step_parameters, list):
                    raise serializers.ValidationError(f"步骤{i+1}的step_parameters必须是数组格式")

        return value


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

    class Meta:
        model = ExecutionPlan
        fields = [
            'id', 'template', 'template_name', 'name', 'description',
            'is_synced', 'needs_sync', 'last_sync_at',
            'step_count', 'total_executions', 'success_executions', 'failed_executions',
            'success_rate', 'last_executed_at',
            'created_by', 'created_by_name', 'created_at', 'updated_at',
            'plan_steps', 'step_configs'
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

        step_configs = validated_data.pop('step_configs', None)

        # 更新基本信息
        instance = super().update(instance, validated_data)

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
