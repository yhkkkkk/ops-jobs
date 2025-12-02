"""
脚本模板视图
"""
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django_filters.rest_framework import DjangoFilterBackend
from django.db.models import Q
from utils.pagination import CustomPagination
from utils.responses import SycResponse
from .models import ScriptTemplate, DefaultScriptTemplate, ScriptTemplateVersion
from .serializers import (
    ScriptTemplateSerializer,
    ScriptTemplateCreateSerializer,
    DefaultScriptTemplateSerializer,
    ScriptTemplateVersionSerializer
)
from .services import ScriptTemplateService
from .filters import ScriptTemplateFilter


class ScriptTemplateViewSet(viewsets.ModelViewSet):
    """脚本模板ViewSet"""
    queryset = ScriptTemplate.objects.all()
    serializer_class = ScriptTemplateSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = CustomPagination
    filter_backends = [DjangoFilterBackend]
    filterset_class = ScriptTemplateFilter

    def get_queryset(self):
        user = self.request.user

        # 管理页面：显示所有模板（包括下线的）
        queryset = super().get_queryset().filter(
            Q(created_by=user) | Q(is_public=True)
        )

        return queryset.select_related('created_by').order_by('-created_at')
    
    def get_serializer_class(self):
        if self.action in ['create', 'update', 'partial_update']:
            return ScriptTemplateCreateSerializer
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
        self.perform_destroy(instance)
        return SycResponse.success(message="脚本模板删除成功")

    def list(self, request, *args, **kwargs):
        """获取脚本模板列表"""
        queryset = self.filter_queryset(self.get_queryset())
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)

        serializer = self.get_serializer(queryset, many=True)
        return SycResponse.success(content=serializer.data, message="获取脚本模板列表成功")

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)

    @action(detail=True, methods=['get'])
    def get_content(self, request, pk=None):
        """获取脚本模板内容"""
        template = self.get_object()

        # 检查权限
        if not template.is_public and template.created_by != request.user:
            return SycResponse.error(message="您没有权限访问此模板", code=403)

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
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        
        serializer = self.get_serializer(templates, many=True)
        return SycResponse.success(content=serializer.data, message="获取我的模板成功")

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
    def for_import(self, request):
        """获取可用于导入的模板（只返回启用的模板）"""
        user = request.user
        
        # 只返回启用的模板
        templates = ScriptTemplate.objects.filter(
            Q(created_by=user) | Q(is_public=True),
            is_active=True  # 只显示启用的模板
        ).select_related('created_by').order_by('-created_at')
        
        # 分页
        page = self.paginate_queryset(templates)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        
        serializer = self.get_serializer(templates, many=True)
        return SycResponse.success(content=serializer.data, message="获取可导入模板成功")
