"""
作业模板视图
"""
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from django_filters.rest_framework import DjangoFilterBackend
from django.db import transaction
from utils.responses import SycResponse
from utils.pagination import CustomPagination
from apps.permissions.permissions import JobTemplatePermission, ExecutionPlanPermission
from .models import JobTemplate, JobStep, ExecutionPlan, PlanStep
from .serializers import (
    JobTemplateSerializer,
    JobStepSerializer,
    ExecutionPlanSerializer,
    PlanStepSerializer,
    JobTemplateCreateSerializer,
    JobTemplateUpdateSerializer,
    ExecutionPlanCreateSerializer,
    ExecutionPlanUpdateSerializer
)
from .filters import JobTemplateFilter, ExecutionPlanFilter
from .sync_views import TemplateSyncMixin, ExecutionPlanSyncMixin


class JobTemplateViewSet(TemplateSyncMixin, viewsets.ModelViewSet):
    """作业模板ViewSet"""
    queryset = JobTemplate.objects.all()
    serializer_class = JobTemplateSerializer
    permission_classes = [JobTemplatePermission]
    pagination_class = CustomPagination
    filter_backends = [DjangoFilterBackend]
    filterset_class = JobTemplateFilter

    def get_queryset(self):
        """基础查询集，结合Guardian对象权限进行过滤"""
        base_qs = super().get_queryset().select_related('created_by').prefetch_related('steps', 'plans')

        # 超级用户可以看到所有作业模板
        if self.request.user.is_superuser:
            return base_qs

        # 其他用户只能看到具有 view_jobtemplate 对象权限的作业模板
        from guardian.shortcuts import get_objects_for_user

        permitted_qs = get_objects_for_user(
            user=self.request.user,
            perms='view_jobtemplate',
            klass=JobTemplate,
            accept_global_perms=False
        )

        return base_qs.filter(id__in=permitted_qs.values('id'))

    def get_client_ip(self, request):
        """获取客户端IP地址"""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0]
        else:
            ip = request.META.get('REMOTE_ADDR')
        return ip

    def perform_create(self, serializer):
        """创建模板时设置创建人"""
        serializer.save(created_by=self.request.user)

    def create(self, request, *args, **kwargs):
        """创建作业模板（包含步骤）"""
        serializer = JobTemplateCreateSerializer(data=request.data)
        if not serializer.is_valid():
            return SycResponse.validation_error(errors=serializer.errors)

        data = serializer.validated_data

        # 检查名称唯一性
        name = data.get('name')
        if JobTemplate.objects.filter(name=name).exists():
            return SycResponse.error(message=f"模板名称 '{name}' 已存在，请使用其他名称", code=400)

        with transaction.atomic():
            # 处理标签：将键值对数组转换为JSON格式
            tags_list = data.get('tags', [])
            tags_json = {}

            if isinstance(tags_list, list) and tags_list:
                for tag in tags_list:
                    if isinstance(tag, dict) and 'key' in tag and 'value' in tag:
                        tags_json[tag['key']] = tag['value']

            # 创建模板
            template = JobTemplate.objects.create(
                name=data['name'],
                description=data.get('description', ''),
                category=data.get('category', ''),
                tags_json=tags_json,
                global_parameters=data.get('global_parameters', {}),
                created_by=request.user
            )

            # 创建步骤
            for i, step_data in enumerate(data['steps']):
                # 基本步骤数据（使用验证后的结构，包含 target_host_ids）
                step_kwargs = {
                    'template': template,
                    'name': step_data['name'],
                    'description': step_data.get('description', ''),
                    'step_type': step_data['step_type'],
                    'order': step_data.get('order', i + 1),
                    'step_parameters': step_data.get('step_parameters', []),
                    'timeout': step_data.get('timeout', 300),
                    'ignore_error': step_data.get('ignore_error', False),
                }

                # 添加脚本相关字段
                if step_data['step_type'] == 'script':
                    step_kwargs.update({
                        'script_type': step_data.get('script_type', ''),
                        'script_content': step_data.get('script_content', ''),
                        'account_id': step_data.get('account_id')
                    })
                elif step_data['step_type'] == 'file_transfer':
                    step_kwargs.update({
                        'transfer_type': step_data.get('transfer_type', ''),
                        'local_path': step_data.get('local_path', ''),
                        'remote_path': step_data.get('remote_path', ''),
                        'overwrite_policy': step_data.get('overwrite_policy', '')
                    })

                step = JobStep.objects.create(**step_kwargs)

                # 处理目标主机和分组
                target_host_ids = step_data.get('target_host_ids', []) or []
                target_group_ids = step_data.get('target_group_ids', []) or []
                if target_host_ids:
                    step.target_hosts.set(target_host_ids)
                if target_group_ids:
                    step.target_groups.set(target_group_ids)

            # 创建默认执行方案（包含所有步骤）
            default_plan = ExecutionPlan.objects.create(
                template=template,
                name="默认方案",
                description="包含所有步骤的默认执行方案",
                created_by=request.user,
                global_parameters_snapshot=template.global_parameters  # 保存全局变量快照
            )

            # 添加所有步骤到默认方案
            from .sync_service import TemplateChangeDetector
            for step in template.steps.all():
                plan_step = PlanStep.objects.create(
                    plan=default_plan,
                    step=step,
                    order=step.order,
                    step_hash=TemplateChangeDetector.calculate_step_hash(step)
                )
                # 复制快照数据
                plan_step.copy_from_template_step()
                plan_step.save()

        serializer = JobTemplateSerializer(template)
        return SycResponse.success(content=serializer.data, message="作业模板创建成功")

    def retrieve(self, request, *args, **kwargs):
        """获取作业模板详情"""
        instance = self.get_object()
        serializer = self.get_serializer(instance)

        # 返回统一格式的响应
        return SycResponse.success(
            content=serializer.data,
            message="获取作业模板详情成功"
        )

    def list(self, request, *args, **kwargs):
        """获取作业模板列表"""
        queryset = self.filter_queryset(self.get_queryset())

        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)

        serializer = self.get_serializer(queryset, many=True)
        return SycResponse.success(
            content=serializer.data,
            message="获取作业模板列表成功"
        )

    def update(self, request, *args, **kwargs):
        """更新作业模板"""
        partial = kwargs.pop('partial', False)
        instance = self.get_object()

        # 如果包含步骤数据，使用更新序列化器进行验证
        if 'steps' in request.data:
            update_serializer = JobTemplateUpdateSerializer(instance, data=request.data)
            if not update_serializer.is_valid():
                return SycResponse.validation_error(errors=update_serializer.errors)

            validated_data = update_serializer.validated_data

            with transaction.atomic():
                # 更新基本信息
                instance.name = validated_data.get('name', instance.name)
                instance.description = validated_data.get('description', instance.description)
                instance.category = validated_data.get('category', instance.category)
                instance.global_parameters = validated_data.get('global_parameters', instance.global_parameters)

                # 处理标签
                tags_list = validated_data.get('tags', [])
                tags_json = {}
                if isinstance(tags_list, list) and tags_list:
                    for tag in tags_list:
                        if isinstance(tag, dict) and 'key' in tag and 'value' in tag:
                            tags_json[tag['key']] = tag['value']
                instance.tags_json = tags_json

                instance.save()

                # 更新现有步骤（保持ID不变以维护关联关系）
                existing_steps = list(instance.steps.all().order_by('order'))

                # 处理步骤更新
                for i, step_data in enumerate(validated_data['steps']):
                    # 基本步骤数据
                    step_kwargs = {
                        'name': step_data['name'],
                        'description': step_data.get('description', ''),
                        'step_type': step_data['step_type'],
                        'order': i + 1,
                        'step_parameters': step_data.get('step_parameters', []),
                        'timeout': step_data.get('timeout', 300),
                        'ignore_error': step_data.get('ignore_error', False),
                    }

                    # 添加脚本相关字段
                    if step_data['step_type'] == 'script':
                        step_kwargs.update({
                            'script_type': step_data.get('script_type', ''),
                            'script_content': step_data.get('script_content', ''),
                            'account_id': step_data.get('account_id')
                        })
                    elif step_data['step_type'] == 'file_transfer':
                        step_kwargs.update({
                            'transfer_type': step_data.get('transfer_type', ''),
                            'local_path': step_data.get('local_path', ''),
                            'remote_path': step_data.get('remote_path', ''),
                            'overwrite_policy': step_data.get('overwrite_policy', '')
                        })

                    # 更新现有步骤或创建新步骤
                    if i < len(existing_steps):
                        # 更新现有步骤
                        step = existing_steps[i]
                        for key, value in step_kwargs.items():
                            setattr(step, key, value)
                        step.save()
                    else:
                        # 创建新步骤
                        step_kwargs['template'] = instance
                        step = JobStep.objects.create(**step_kwargs)

                    # 处理目标主机和分组
                    target_host_ids = step_data.get('target_host_ids', [])
                    target_group_ids = step_data.get('target_group_ids', [])

                    # 无论是否为空，都显式设置，以便支持“清空目标”
                    step.target_hosts.set(target_host_ids or [])
                    step.target_groups.set(target_group_ids or [])

                # 删除多余的步骤（如果新步骤数量少于原有步骤数量）
                if len(validated_data['steps']) < len(existing_steps):
                    for step in existing_steps[len(validated_data['steps']):]:
                        step.delete()

                # 标记所有执行方案需要同步（通过设置is_synced=False）
                instance.plans.update(is_synced=False)
        else:
            # 如果没有步骤数据，只更新基本信息
            update_serializer = JobTemplateUpdateSerializer(instance, data=request.data, partial=partial)
            if not update_serializer.is_valid():
                return SycResponse.validation_error(errors=update_serializer.errors)
            
            # 更新基本信息
            instance.name = update_serializer.validated_data.get('name', instance.name)
            instance.description = update_serializer.validated_data.get('description', instance.description)
            instance.category = update_serializer.validated_data.get('category', instance.category)
            instance.global_parameters = update_serializer.validated_data.get('global_parameters', instance.global_parameters)
            
            # 处理标签
            tags_list = update_serializer.validated_data.get('tags', [])
            if tags_list is not None:  # 只有当tags字段存在时才更新
                tags_json = {}
                if isinstance(tags_list, list) and tags_list:
                    for tag in tags_list:
                        if isinstance(tag, dict) and 'key' in tag and 'value' in tag:
                            tags_json[tag['key']] = tag['value']
                instance.tags_json = tags_json
            
            instance.save()

        # 返回更新后的数据
        result_serializer = JobTemplateSerializer(instance)
        return SycResponse.success(
            content=result_serializer.data,
            message="作业模板更新成功"
        )

    def destroy(self, request, *args, **kwargs):
        """删除作业模板"""
        instance = self.get_object()
        template_name = instance.name

        # 检查是否有关联的执行记录
        if hasattr(instance, 'execution_records') and instance.execution_records.exists():
            return SycResponse.error(
                message=f"模板 '{template_name}' 存在关联的执行记录，无法删除",
                code=400
            )

        self.perform_destroy(instance)

        return SycResponse.success(
            content=None,
            message=f"作业模板 '{template_name}' 删除成功"
        )
    
    @action(detail=False, methods=['get'])
    def tags(self, request):
        """获取可用标签列表"""
        queryset = self.get_queryset()
        tags = set()
        
        for tag_json in queryset.values_list('tags_json', flat=True):
            if not tag_json:
                continue
            for key, value in tag_json.items():
                if not key:
                    continue
                value_str = '' if value is None else str(value).strip()
                if value_str:
                    tags.add(f"{key}:{value_str}")
        
        return SycResponse.success(
            content={'tags': sorted(tags)},
            message="获取标签列表成功"
        )

    @action(detail=True, methods=['get'])
    def steps(self, request, pk=None):
        """获取模板的步骤列表"""
        template = self.get_object()
        steps = template.steps.all()
        serializer = JobStepSerializer(steps, many=True)
        return SycResponse.success(content=serializer.data, message="获取步骤列表成功")

    @action(detail=True, methods=['get'])
    def plans(self, request, pk=None):
        """获取模板的执行方案列表"""
        template = self.get_object()
        plans = template.plans.all()
        serializer = ExecutionPlanSerializer(plans, many=True)
        return SycResponse.success(content=serializer.data, message="获取执行方案列表成功")

    @action(detail=True, methods=['post'])
    def batch_sync_all_plans(self, request, pk=None):
        """批量同步模板下的所有执行方案"""
        template = self.get_object()

        # 获取需要同步的执行方案
        plans = template.plans.all()
        unsync_plans = [plan for plan in plans if plan.needs_sync]

        if not unsync_plans:
            return SycResponse.success(content={
                'synced_count': 0,
                'message': '所有执行方案都已是最新状态'
            }, message="无需同步")

        # 批量同步
        success_count = 0
        failed_plans = []

        for plan in unsync_plans:
            result = plan.sync_from_template()
            if result['success']:
                success_count += 1
            else:
                failed_plans.append({
                    'plan_id': plan.id,
                    'plan_name': plan.name,
                    'error': result['message']
                })

        return SycResponse.success(content={
            'total_plans': len(unsync_plans),
            'success_count': success_count,
            'failed_count': len(failed_plans),
            'failed_plans': failed_plans
        }, message=f"批量同步完成，成功 {success_count} 个，失败 {len(failed_plans)} 个")

    @action(detail=True, methods=['post'])
    def debug(self, request, pk=None):
        """调试作业模板 - 直接执行模板，不创建临时执行方案"""
        template = self.get_object()

        from .services import ExecutionPlanService
        from .serializers import ExecutionPlanExecuteSerializer

        # 验证执行参数
        serializer = ExecutionPlanExecuteSerializer(data=request.data)
        if not serializer.is_valid():
            return SycResponse.validation_error(errors=serializer.errors)

        data = serializer.validated_data

        try:
            # 获取客户端信息
            client_ip = self.get_client_ip(request)
            user_agent = request.META.get('HTTP_USER_AGENT', '')

            # 直接执行模板，不创建临时执行方案
            result = ExecutionPlanService.execute_template_debug(
                template=template,
                user=request.user,
                execution_parameters=data.get('execution_parameters', {}),
                execution_mode=data.get('execution_mode', 'parallel'),
                rolling_batch_size=data.get('rolling_batch_size', 1),
                rolling_batch_delay=data.get('rolling_batch_delay', 0),
                client_ip=client_ip,
                user_agent=user_agent
            )

            if result['success']:
                return SycResponse.success(content={
                    **result,
                    'is_debug': True,
                    'message': '模板调试执行已启动，执行完成后调试数据将自动清理'
                }, message="模板调试执行已启动")
            else:
                return SycResponse.error(content=result, message=result.get('error', '模板调试执行启动失败'))

        except Exception as e:
            return SycResponse.error(message=f"模板调试失败: {str(e)}")


class ExecutionPlanViewSet(ExecutionPlanSyncMixin, viewsets.ModelViewSet):
    """执行方案ViewSet"""
    queryset = ExecutionPlan.objects.all()
    serializer_class = ExecutionPlanSerializer
    permission_classes = [ExecutionPlanPermission]
    pagination_class = CustomPagination
    filter_backends = [DjangoFilterBackend]
    filterset_class = ExecutionPlanFilter

    def get_queryset(self):
        """基础查询集，结合Guardian对象权限进行过滤"""
        base_qs = super().get_queryset().select_related('template', 'created_by').prefetch_related(
            'planstep_set__step'
        )

        # 超级用户可以看到所有执行方案
        if self.request.user.is_superuser:
            return base_qs

        # 其他用户只能看到具有 view_executionplan 对象权限的执行方案
        from guardian.shortcuts import get_objects_for_user

        permitted_qs = get_objects_for_user(
            user=self.request.user,
            perms='view_executionplan',
            klass=ExecutionPlan,
            accept_global_perms=False
        )

        return base_qs.filter(id__in=permitted_qs.values('id'))

    def get_client_ip(self, request):
        """获取客户端IP地址"""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0]
        else:
            ip = request.META.get('REMOTE_ADDR')
        return ip

    def create(self, request, *args, **kwargs):
        """创建执行方案（包含步骤配置）"""
        serializer = ExecutionPlanCreateSerializer(data=request.data)
        if not serializer.is_valid():
            return SycResponse.validation_error(errors=serializer.errors)

        data = serializer.validated_data
        template_id = request.data.get('template_id')

        if not template_id:
            return SycResponse.error(message="必须指定template_id", code=400)

        try:
            template = JobTemplate.objects.get(id=template_id)
        except JobTemplate.DoesNotExist:
            return SycResponse.error(message="模板不存在", code=404)

        with transaction.atomic():
            # 创建执行方案
            plan = ExecutionPlan.objects.create(
                template=template,
                name=data['name'],
                description=data.get('description', ''),
                created_by=request.user,
                global_parameters_snapshot=template.global_parameters  # 保存全局变量快照
            )

            # 添加步骤到方案
            from .sync_service import TemplateChangeDetector
            for step_config in data['step_configs']:
                try:
                    step = JobStep.objects.get(
                        id=step_config['step_id'],
                        template=template
                    )
                except JobStep.DoesNotExist:
                    return SycResponse.error(
                        message=f"步骤ID {step_config['step_id']} 不存在或不属于该模板",
                        code=400
                    )

                plan_step = PlanStep.objects.create(
                    plan=plan,
                    step=step,
                    order=step_config['order'],
                    override_parameters=step_config.get('override_parameters', {}),
                    override_timeout=step_config.get('override_timeout'),
                    step_hash=TemplateChangeDetector.calculate_step_hash(step)
                )
                # 复制快照数据
                plan_step.copy_from_template_step()
                plan_step.save()

        serializer = ExecutionPlanSerializer(plan)
        return SycResponse.success(content=serializer.data, message="执行方案创建成功")

    def retrieve(self, request, *args, **kwargs):
        """获取执行方案详情"""
        instance = self.get_object()
        serializer = self.get_serializer(instance)

        # 返回统一格式的响应
        return SycResponse.success(
            content=serializer.data,
            message="获取执行方案详情成功"
        )

    def list(self, request, *args, **kwargs):
        """获取执行方案列表"""
        queryset = self.filter_queryset(self.get_queryset())

        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)

        serializer = self.get_serializer(queryset, many=True)
        return SycResponse.success(
            content=serializer.data,
            message="获取执行方案列表成功"
        )

    def update(self, request, *args, **kwargs):
        """更新执行方案"""
        partial = kwargs.pop('partial', False)
        instance = self.get_object()

        # 使用专门的更新序列化器
        serializer = ExecutionPlanUpdateSerializer(instance, data=request.data, partial=partial)
        if not serializer.is_valid():
            return SycResponse.validation_error(errors=serializer.errors)

        serializer.save()

        # 使用读取序列化器返回完整数据
        response_serializer = ExecutionPlanSerializer(instance)
        return SycResponse.success(
            content=response_serializer.data,
            message="执行方案更新成功"
        )

    def destroy(self, request, *args, **kwargs):
        """删除执行方案"""
        instance = self.get_object()
        plan_name = instance.name

        # 检查是否有关联的执行记录
        if hasattr(instance, 'execution_records') and instance.execution_records.exists():
            return SycResponse.error(
                message=f"执行方案 '{plan_name}' 存在关联的执行记录，无法删除",
                code=400
            )

        self.perform_destroy(instance)

        return SycResponse.success(
            content=None,
            message=f"执行方案 '{plan_name}' 删除成功"
        )

    @action(detail=True, methods=['get'])
    def steps(self, request, pk=None):
        """获取方案的步骤列表"""
        plan = self.get_object()
        plan_steps = plan.planstep_set.all().select_related('step')
        serializer = PlanStepSerializer(plan_steps, many=True)
        return SycResponse.success(content=serializer.data, message="获取方案步骤成功")

    # 这个方法已经在 ExecutionPlanSyncMixin 中实现，删除重复定义

    @action(detail=True, methods=['get'])
    def sync_status_detail(self, request, pk=None):
        """获取执行方案的详细同步状态"""
        plan = self.get_object()
        changes = plan.get_sync_changes()

        return SycResponse.success(content={
            'plan_id': plan.id,
            'plan_name': plan.name,
            'template_name': plan.template.name,
            'is_synced': plan.is_synced,
            'needs_sync': plan.needs_sync,
            'last_sync_at': plan.last_sync_at.isoformat() if plan.last_sync_at else None,
            'template_updated_at': plan.template.updated_at.isoformat(),
            'plan_updated_at': plan.updated_at.isoformat(),
            'changes': changes
        }, message="获取同步状态成功")

    @action(detail=True, methods=['post'])
    def execute(self, request, pk=None):
        """直接执行执行方案"""
        plan = self.get_object()

        from .services import ExecutionPlanService
        from .serializers import ExecutionPlanExecuteSerializer

        # 验证执行参数
        serializer = ExecutionPlanExecuteSerializer(data=request.data)
        if not serializer.is_valid():
            return SycResponse.validation_error(errors=serializer.errors)

        data = serializer.validated_data

        # 获取客户端信息
        client_ip = self.get_client_ip(request)
        user_agent = request.META.get('HTTP_USER_AGENT', '')

        # 直接执行执行方案，创建ExecutionRecord
        result = ExecutionPlanService.execute_plan(
            execution_plan=plan,
            user=request.user,
            trigger_type=data.get('trigger_type', 'manual'),
            execution_parameters=data.get('execution_parameters', {}),
            name=data.get('name', f"执行方案: {plan.name}"),
            description=data.get('description', f"直接执行执行方案 {plan.name}"),
            execution_mode=data.get('execution_mode', 'parallel'),
            rolling_batch_size=data.get('rolling_batch_size', 1),
            rolling_batch_delay=data.get('rolling_batch_delay', 0),
            client_ip=client_ip,
            user_agent=user_agent
        )

        if result['success']:
            return SycResponse.success(content=result, message="执行方案启动成功")
        else:
            return SycResponse.error(content=result, message=result.get('error', '执行方案启动失败'))


class JobStepViewSet(viewsets.ModelViewSet):
    """作业步骤ViewSet"""
    queryset = JobStep.objects.all()
    serializer_class = JobStepSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        """过滤查询集"""
        queryset = super().get_queryset()

        # 按模板过滤
        template_id = self.request.query_params.get('template_id')
        if template_id:
            queryset = queryset.filter(template_id=template_id)

        # 按步骤类型过滤
        step_type = self.request.query_params.get('step_type')
        if step_type:
            queryset = queryset.filter(step_type=step_type)

        return queryset.select_related('template').order_by('order')
