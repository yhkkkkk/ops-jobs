"""
脚本模板视图
"""
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.filters import OrderingFilter
from django_filters.rest_framework import DjangoFilterBackend
from django.db.models import Count
from utils.pagination import CustomPagination
from utils.responses import SycResponse
from .models import ScriptTemplate, ScriptTemplateVersion, UserFavorite
from .serializers import (
    ScriptTemplateSerializer,
    ScriptTemplateListSerializer,
    ScriptTemplateCreateSerializer,
    ScriptTemplateVersionSerializer,
    UserFavoriteSerializer,
    UserFavoriteCreateSerializer,
    FavoriteToggleSerializer
)
from .services import ScriptTemplateService
from .filters import ScriptTemplateFilter, UserFavoriteFilter


class ScriptTemplateViewSet(viewsets.ModelViewSet):
    """脚本模板ViewSet"""
    queryset = ScriptTemplate.objects.all()
    serializer_class = ScriptTemplateSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = CustomPagination
    filter_backends = [DjangoFilterBackend, OrderingFilter]
    filterset_class = ScriptTemplateFilter
    ordering_fields = ['created_at', 'updated_at', 'name', 'version', 'script_type']
    ordering = ['-created_at']

    def get_queryset(self):
        # 管理页面：显示所有模板（包括下线的）
        queryset = super().get_queryset().select_related('created_by', 'updated_by')

        if self.action in ['list', 'my_templates']:
            return queryset.order_by('-created_at')

        return queryset.annotate(
            job_template_ref_count=Count('job_steps__template', distinct=True),
            execution_plan_ref_count=Count('job_steps__planstep__plan', distinct=True)
        ).order_by('-created_at')

    def _attach_reference_counts(self, templates):
        template_ids = [template.id for template in templates]
        if not template_ids:
            return

        from apps.job_templates.models import JobStep, PlanStep

        job_counts = JobStep.objects.filter(
            script_template_id__in=template_ids
        ).values('script_template_id').annotate(
            count=Count('template_id', distinct=True)
        )
        plan_counts = PlanStep.objects.filter(
            step__script_template_id__in=template_ids
        ).values('step__script_template_id').annotate(
            count=Count('plan_id', distinct=True)
        )

        job_count_map = {item['script_template_id']: item['count'] for item in job_counts}
        plan_count_map = {item['step__script_template_id']: item['count'] for item in plan_counts}

        for template in templates:
            template.job_template_ref_count = job_count_map.get(template.id, 0)
            template.execution_plan_ref_count = plan_count_map.get(template.id, 0)
    
    def get_serializer_class(self):
        if self.action in ['create', 'update', 'partial_update']:
            return ScriptTemplateCreateSerializer
        if self.action == 'list':
            return ScriptTemplateListSerializer
        return ScriptTemplateSerializer
    
    def create(self, request, *args, **kwargs):
        """创建脚本模板"""
        serializer = self.get_serializer(data=request.data)
        if serializer.is_valid():
            self.perform_create(serializer)
            return SycResponse.success(content=serializer.data, message="脚本模板创建成功")
        else:
            return SycResponse.validation_error(serializer.errors)

    def update(self, request, *args, **kwargs):
        """更新脚本模板"""
        partial = kwargs.pop('partial', False)
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        if serializer.is_valid():
            self.perform_update(serializer)
            return SycResponse.success(content=serializer.data, message="脚本模板更新成功")
        else:
            return SycResponse.validation_error(serializer.errors)

    def perform_update(self, serializer):
        serializer.save(updated_by=self.request.user)

    def retrieve(self, request, *args, **kwargs):
        """获取脚本模板详情"""
        instance = self.get_object()
        serializer = self.get_serializer(instance)

        return SycResponse.success(
            content=serializer.data,
            message="获取脚本模板详情成功"
        )

    def destroy(self, request, *args, **kwargs):
        """删除脚本模板"""
        instance = self.get_object()

        # 检查是否被作业模板/执行方案引用
        from apps.job_templates.models import PlanStep
        job_count = instance.job_steps.values('template_id').distinct().count()
        plan_count = PlanStep.objects.filter(step__script_template=instance).values('plan_id').distinct().count()
        if job_count > 0 or plan_count > 0:
            return SycResponse.error(
                message=f"该脚本模板已被 {job_count} 个作业模板、{plan_count} 个执行方案引用，无法删除",
                code=400
            )

        self.perform_destroy(instance)
        return SycResponse.success(message="脚本模板删除成功")

    def list(self, request, *args, **kwargs):
        """获取脚本模板列表"""
        queryset = self.filter_queryset(self.get_queryset())
        page = self.paginate_queryset(queryset)
        if page is not None:
            self._attach_reference_counts(page)
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)

        self._attach_reference_counts(queryset)
        serializer = self.get_serializer(queryset, many=True)
        return SycResponse.success(content=serializer.data, message="获取脚本模板列表成功")

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user, updated_by=self.request.user)

    @action(detail=True, methods=['get'])
    def get_content(self, request, pk=None):
        """获取脚本模板内容"""
        template = self.get_object()

        # 检查是否启用
        if not template.is_active:
            return SycResponse.error(message="此模板已被禁用", code=400)

        result = ScriptTemplateService.get_template_content(template)

        if result['success']:
            # 增加使用次数
            template.increment_usage()

            return SycResponse.success(content=result['data'], message="获取模板内容成功")
        else:
            return SycResponse.error(message=result['message'])
    
    @action(detail=False, methods=['get'])
    def my_templates(self, request):
        """获取我的模板"""
        # 使用get_queryset()方法，它会根据action自动处理状态过滤
        templates = self.get_queryset().filter(created_by=request.user)
        
        # 分页
        page = self.paginate_queryset(templates)
        if page is not None:
            self._attach_reference_counts(page)
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        
        self._attach_reference_counts(templates)
        serializer = self.get_serializer(templates, many=True)
        return SycResponse.success(content=serializer.data, message="获取我的模板成功")

    @action(detail=True, methods=['get'])
    def references(self, request, pk=None):
        """获取脚本模板引用关系"""
        template = self.get_object()
        from apps.job_templates.models import JobTemplate, ExecutionPlan

        job_templates = JobTemplate.objects.filter(
            steps__script_template=template
        ).distinct().values('id', 'name')

        execution_plans = ExecutionPlan.objects.filter(
            steps__script_template=template
        ).distinct().values('id', 'name')

        return SycResponse.success(content={
            'job_templates': list(job_templates),
            'execution_plans': list(execution_plans)
        }, message="获取引用关系成功")

    @action(detail=True, methods=['get'])
    def versions(self, request, pk=None):
        """获取脚本模板的版本历史"""
        template = self.get_object()
        versions = template.versions.all()
        serializer = ScriptTemplateVersionSerializer(versions, many=True)
        return SycResponse.success(
            content=serializer.data,
            message="获取版本历史成功"
        )

    @action(detail=True, methods=['post'])
    def create_version(self, request, pk=None):
        """创建新版本"""
        template = self.get_object()

        # 获取版本号和描述
        version = request.data.get('version')
        description = request.data.get('description', '')

        if not version:
            return SycResponse.error(message="版本号不能为空")

        # 检查版本号是否已存在
        if template.versions.filter(version=version).exists():
            return SycResponse.error(message="版本号已存在")

        # 将当前版本设为非活跃
        template.versions.update(is_active=False)

        # 创建新版本
        new_version = ScriptTemplateVersion.objects.create(
            template=template,
            version=version,
            script_content=template.script_content,
            description=description,
            is_active=True,
            created_by=request.user
        )

        # 更新模板的版本号
        template.version = version
        template.save(update_fields=['version'])

        serializer = ScriptTemplateVersionSerializer(new_version)
        return SycResponse.success(
            content=serializer.data,
            message="创建版本成功"
        )

    @action(detail=True, methods=['put'], url_path=r'versions/(?P<version_id>[^/.]+)')
    def update_version(self, request, pk=None, version_id=None):
        """更新指定版本内容"""
        template = self.get_object()

        if not version_id:
            return SycResponse.error(message="版本ID不能为空")

        try:
            target_version = template.versions.get(id=version_id)
        except ScriptTemplateVersion.DoesNotExist:
            return SycResponse.error(message="版本不存在")

        data = request.data or {}
        update_fields = []

        if 'script_content' in data:
            script_content = str(data.get('script_content', '')).strip()
            if not script_content:
                return SycResponse.error(message="脚本内容不能为空")
            target_version.script_content = script_content
            update_fields.append('script_content')

        if 'description' in data:
            target_version.description = data.get('description', '') or ''
            update_fields.append('description')

        if 'version' in data:
            new_version = data.get('version')
            if not new_version:
                return SycResponse.error(message="版本号不能为空")
            if template.versions.exclude(id=target_version.id).filter(version=new_version).exists():
                return SycResponse.error(message="版本号已存在")
            target_version.version = new_version
            update_fields.append('version')

        if not update_fields:
            return SycResponse.error(message="没有可更新字段")

        target_version.save(update_fields=update_fields)

        # 若更新的是当前版本，同步更新模板内容/版本号
        template_update_fields = []
        if target_version.is_active:
            if 'script_content' in data:
                template.script_content = target_version.script_content
                template_update_fields.append('script_content')
            if 'version' in data:
                template.version = target_version.version
                template_update_fields.append('version')
            if template_update_fields:
                template.updated_by = request.user
                template_update_fields.append('updated_by')
                template.save(update_fields=template_update_fields)

        serializer = ScriptTemplateVersionSerializer(target_version)
        return SycResponse.success(
            content=serializer.data,
            message="版本更新成功"
        )

    @action(detail=True, methods=['post'])
    def rollback_version(self, request, pk=None):
        """回滚到指定版本"""
        template = self.get_object()
        version_id = request.data.get('version_id')

        if not version_id:
            return SycResponse.error(message="版本ID不能为空")

        try:
            target_version = template.versions.get(id=version_id)
        except ScriptTemplateVersion.DoesNotExist:
            return SycResponse.error(message="版本不存在")

        # 更新模板内容和版本
        template.script_content = target_version.script_content
        template.version = target_version.version
        template.save(update_fields=['script_content', 'version'])

        # 更新版本活跃状态
        template.versions.update(is_active=False)
        target_version.is_active = True
        target_version.save(update_fields=['is_active'])

        return SycResponse.success(message="版本回滚成功")

    @action(detail=True, methods=['post'])
    def toggle_status(self, request, pk=None):
        """切换模板上线/下线状态"""
        template = self.get_object()
        template.is_active = not template.is_active
        template.save(update_fields=['is_active'])

        status_text = "上线" if template.is_active else "下线"
        return SycResponse.success(
            content={'is_active': template.is_active},
            message=f"模板已{status_text}"
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
                if key and value not in (None, ''):
                    tags.add(f"{key}={value}")

        return SycResponse.success(
            content={'tags': sorted(tags)},
            message="获取标签列表成功"
        )

    @action(detail=False, methods=['get'])
    def for_import(self, request):
        """获取可用于导入的模板（只返回启用的模板）"""
        user = request.user
        
        # 只返回启用的模板
        templates = ScriptTemplate.objects.filter(
            is_active=True  # 只显示启用的模板
        ).select_related('created_by').order_by('-created_at')
        
        # 分页
        page = self.paginate_queryset(templates)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        
        serializer = self.get_serializer(templates, many=True)
        return SycResponse.success(content=serializer.data, message="获取可导入模板成功")


class UserFavoriteViewSet(viewsets.ModelViewSet):
    """用户收藏ViewSet"""
    serializer_class = UserFavoriteSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = CustomPagination
    filter_backends = [DjangoFilterBackend]
    filterset_class = UserFavoriteFilter

    def get_queryset(self):
        """只返回当前用户的收藏"""
        return UserFavorite.objects.filter(user=self.request.user).select_related('user')

    def get_serializer_class(self):
        if self.action == 'create':
            return UserFavoriteCreateSerializer
        return UserFavoriteSerializer

    @action(detail=False, methods=['post'], url_path='toggle')
    def toggle_favorite(self, request):
        """切换收藏状态"""
        serializer = FavoriteToggleSerializer(data=request.data)
        if not serializer.is_valid():
            return SycResponse.validation_error(serializer.errors)

        favorite_type = serializer.validated_data['favorite_type']
        object_id = serializer.validated_data['object_id']
        category = serializer.validated_data.get('category', 'personal')
        note = serializer.validated_data.get('note', '')

        # 检查是否已收藏
        favorite = UserFavorite.objects.filter(
            user=request.user,
            favorite_type=favorite_type,
            object_id=object_id
        ).first()

        if favorite:
            # 取消收藏
            favorite.delete()
            return SycResponse.success(
                content={'is_favorited': False},
                message="已取消收藏"
            )
        else:
            # 添加收藏
            favorite = UserFavorite.objects.create(
                user=request.user,
                favorite_type=favorite_type,
                object_id=object_id,
                category=category,
                note=note
            )
            serializer = self.get_serializer(favorite)
            return SycResponse.success(
                content={
                    'is_favorited': True,
                    'favorite': serializer.data
                },
                message="已添加到收藏"
            )

    @action(detail=False, methods=['get'], url_path='check')
    def check_favorite(self, request):
        """检查收藏状态"""
        favorite_type = request.query_params.get('favorite_type')
        object_id = request.query_params.get('object_id')

        if not favorite_type or not object_id:
            return SycResponse.error(message="缺少参数 favorite_type 或 object_id")

        try:
            object_id = int(object_id)
        except ValueError:
            return SycResponse.error(message="object_id 必须是整数")

        favorite = UserFavorite.objects.filter(
            user=request.user,
            favorite_type=favorite_type,
            object_id=object_id
        ).first()

        return SycResponse.success(
            content={
                'is_favorited': favorite is not None,
                'favorite': self.get_serializer(favorite).data if favorite else None
            }
        )

    @action(detail=False, methods=['get'], url_path='by-category')
    def get_by_category(self, request):
        """按分类获取收藏"""
        category = request.query_params.get('category')
        favorite_type = request.query_params.get('favorite_type')

        queryset = self.get_queryset()

        if category:
            queryset = queryset.filter(category=category)
        if favorite_type:
            queryset = queryset.filter(favorite_type=favorite_type)

        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)

        serializer = self.get_serializer(queryset, many=True)
        return SycResponse.success(content=serializer.data)
