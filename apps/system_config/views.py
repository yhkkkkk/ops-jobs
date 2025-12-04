"""
系统配置视图
"""
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from apps.permissions.permissions import IsSuperUser
from django.db import transaction
from drf_spectacular.utils import extend_schema, extend_schema_view
from utils.responses import SycResponse
from .models import SystemConfig, ConfigManager, Credential
from .serializers import (
    SystemConfigSerializer,
    SystemConfigUpdateSerializer,
    SystemConfigBatchUpdateSerializer,
    SystemConfigCategorySerializer,
    TaskConfigSerializer,
    NotificationConfigSerializer,
    CredentialSerializer,
)


@extend_schema_view(
    list=extend_schema(summary="获取系统配置列表", tags=["系统配置"]),
    retrieve=extend_schema(summary="获取单个系统配置", tags=["系统配置"]),
    create=extend_schema(summary="创建系统配置", tags=["系统配置"]),
    update=extend_schema(summary="更新系统配置", tags=["系统配置"]),
    partial_update=extend_schema(summary="部分更新系统配置", tags=["系统配置"]),
    destroy=extend_schema(summary="删除系统配置", tags=["系统配置"]),
)
class SystemConfigViewSet(viewsets.ModelViewSet):
    """系统配置管理视图集"""
    
    queryset = SystemConfig.objects.all()
    serializer_class = SystemConfigSerializer
    permission_classes = [IsAuthenticated, IsSuperUser]
    filterset_fields = ['category', 'is_active']
    search_fields = ['key', 'description']
    ordering = ['category', 'key']
    
    def get_serializer_class(self):
        if self.action in ['update', 'partial_update']:
            return SystemConfigUpdateSerializer
        return SystemConfigSerializer
    
    def perform_create(self, serializer):
        serializer.save(updated_by=self.request.user)
    
    def perform_update(self, serializer):
        serializer.save(updated_by=self.request.user)

    def list(self, request, *args, **kwargs):
        """获取系统配置列表"""
        queryset = self.filter_queryset(self.get_queryset())

        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            paginated_response = self.get_paginated_response(serializer.data)

            return SycResponse.success(
                content={
                    'results': serializer.data,
                    'total': paginated_response.data['count'],
                    'page': request.query_params.get('page', 1),
                    'page_size': len(serializer.data)
                },
                message="获取配置列表成功"
            )

        serializer = self.get_serializer(queryset, many=True)
        return SycResponse.success(
            content={
                'results': serializer.data,
                'total': len(serializer.data)
            },
            message="获取配置列表成功"
        )

    def retrieve(self, request, *args, **kwargs):
        """获取单个配置"""
        instance = self.get_object()
        serializer = self.get_serializer(instance)
        return SycResponse.success(content=serializer.data, message="获取配置成功")

    def create(self, request, *args, **kwargs):
        """创建配置"""
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        return SycResponse.success(content=serializer.data, message="配置创建成功")

    def update(self, request, *args, **kwargs):
        """更新配置"""
        partial = kwargs.pop('partial', False)
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        self.perform_update(serializer)
        return SycResponse.success(content=serializer.data, message="配置更新成功")

    def destroy(self, request, *args, **kwargs):
        """删除配置"""
        instance = self.get_object()
        self.perform_destroy(instance)
        return SycResponse.success(message="配置删除成功")
    
    @extend_schema(
        summary="按分类获取配置",
        tags=["系统配置"],
        responses={200: SystemConfigCategorySerializer}
    )
    @action(detail=False, methods=['get'])
    def by_category(self, request):
        """按分类获取配置"""
        category = request.query_params.get('category')
        if not category:
            return SycResponse.error("请指定配置分类")
        
        configs = ConfigManager.get_by_category(category)
        data = {
            'category': category,
            'configs': configs
        }
        
        return SycResponse.success(content=data, message="获取配置成功")
    
    @extend_schema(
        summary="批量更新配置",
        tags=["系统配置"],
        request=SystemConfigBatchUpdateSerializer,
        responses={200: SystemConfigSerializer(many=True)}
    )
    @action(detail=False, methods=['post'])
    def batch_update(self, request):
        """批量更新配置"""
        serializer = SystemConfigBatchUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        configs_data = serializer.validated_data['configs']
        updated_configs = []
        
        with transaction.atomic():
            for config_data in configs_data:
                key = config_data['key']
                value = config_data['value']
                description = config_data.get('description', '')
                
                try:
                    config = SystemConfig.objects.get(key=key)
                    config.value = value
                    if description:
                        config.description = description
                    config.updated_by = request.user
                    config.save()
                    updated_configs.append(config)
                except SystemConfig.DoesNotExist:
                    return SycResponse.error(f"配置项 {key} 不存在")
        
        serializer = SystemConfigSerializer(updated_configs, many=True)
        return SycResponse.success(content=serializer.data, message="批量更新成功")
    
    @extend_schema(
        summary="获取任务配置",
        tags=["系统配置"],
        responses={200: TaskConfigSerializer}
    )
    @action(detail=False, methods=['get'])
    def task_config(self, request):
        """获取任务配置"""
        configs = ConfigManager.get_by_category('task')
        
        # 转换为前端需要的格式
        task_config = {
            'max_concurrent_jobs': configs.get('task.max_concurrent_jobs', 10),
            'job_timeout': configs.get('task.job_timeout', 3600),
            'retry_attempts': configs.get('task.retry_attempts', 3),
            'cleanup_days': configs.get('task.cleanup_days', 30),
        }
        
        return SycResponse.success(content=task_config, message="获取任务配置成功")
    
    @extend_schema(
        summary="更新任务配置",
        tags=["系统配置"],
        request=TaskConfigSerializer,
        responses={200: TaskConfigSerializer}
    )
    @action(detail=False, methods=['post'])
    def update_task_config(self, request):
        """更新任务配置"""
        serializer = TaskConfigSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        config_data = serializer.validated_data
        
        with transaction.atomic():
            for key, value in config_data.items():
                full_key = f'task.{key}'
                ConfigManager.set(
                    key=full_key,
                    value=value,
                    category='task',
                    user=request.user
                )
        
        return SycResponse.success(content=config_data, message="任务配置更新成功")
    
    @extend_schema(
        summary="获取通知配置",
        tags=["系统配置"],
        responses={200: NotificationConfigSerializer}
    )
    @action(detail=False, methods=['get'])
    def notification_config(self, request):
        """获取通知配置"""
        configs = ConfigManager.get_by_category('notification')
        
        # 转换为前端需要的格式
        notification_config = {
            'email_enabled': configs.get('notification.email_enabled', True),
            'webhook_enabled': configs.get('notification.webhook_enabled', False),
            'levels': configs.get('notification.levels', ['error', 'warning']),
            'email_recipients': configs.get('notification.email_recipients', []),
        }
        
        return SycResponse.success(content=notification_config, message="获取通知配置成功")
    
    @extend_schema(
        summary="更新通知配置",
        tags=["系统配置"],
        request=NotificationConfigSerializer,
        responses={200: NotificationConfigSerializer}
    )
    @action(detail=False, methods=['post'])
    def update_notification_config(self, request):
        """更新通知配置"""
        serializer = NotificationConfigSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        config_data = serializer.validated_data
        
        with transaction.atomic():
            for key, value in config_data.items():
                full_key = f'notification.{key}'
                ConfigManager.set(
                    key=full_key,
                    value=value,
                    category='notification',
                    user=request.user
                )
        
        return SycResponse.success(content=config_data, message="通知配置更新成功")
