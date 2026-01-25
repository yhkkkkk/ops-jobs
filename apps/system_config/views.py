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
from .models import SystemConfig, ConfigManager
from .serializers import (
    SystemConfigSerializer,
    SystemConfigUpdateSerializer,
    SystemConfigBatchUpdateSerializer,
    TaskConfigSerializer,
    NotificationConfigSerializer,
    AgentConfigSerializer,
)
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import filters


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
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
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
            'cleanup_days': configs.get('task.cleanup_days', 30),
            # Fabric执行配置
            'fabric_max_concurrent_hosts': configs.get('fabric.max_concurrent_hosts', 20),
            'fabric_connection_timeout': configs.get('fabric.connection_timeout', 30),
            'fabric_command_timeout': configs.get('fabric.command_timeout', 300),
            'fabric_enable_connection_pool': configs.get('fabric.enable_connection_pool', True),
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
            # 钉钉配置
            'dingtalk_enabled': configs.get('notification.dingtalk_enabled', False),
            'dingtalk_webhook': configs.get('notification.dingtalk_webhook', ''),
            'dingtalk_keyword': configs.get('notification.dingtalk_keyword', ''),
            # 飞书配置
            'feishu_enabled': configs.get('notification.feishu_enabled', False),
            'feishu_webhook': configs.get('notification.feishu_webhook', ''),
            'feishu_keyword': configs.get('notification.feishu_keyword', ''),
            # 企业微信配置
            'wechatwork_enabled': configs.get('notification.wechatwork_enabled', False),
            'wechatwork_webhook': configs.get('notification.wechatwork_webhook', ''),
            'wechatwork_keyword': configs.get('notification.wechatwork_keyword', ''),
            # 通知级别
            'levels': configs.get('notification.levels', ['error', 'warning']),
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
    
    @extend_schema(
        summary="获取Agent配置",
        tags=["系统配置"],
        responses={200: AgentConfigSerializer}
    )
    @action(detail=False, methods=['get'])
    def agent_config(self, request):
        """获取Agent配置"""
        configs = ConfigManager.get_by_category('system')
        
        # 获取按环境的离线阈值
        offline_threshold_by_env = configs.get('agent.offline_threshold_by_env', {})
        if not isinstance(offline_threshold_by_env, dict):
            offline_threshold_by_env = {}
        
        # 转换为前端需要的格式
        agent_config = {
            'offline_threshold_seconds': configs.get('agent.offline_threshold_seconds', 600),
            'offline_threshold_by_env': offline_threshold_by_env,
        }
        
        return SycResponse.success(content=agent_config, message="获取Agent配置成功")
    
    @extend_schema(
        summary="更新Agent配置",
        tags=["系统配置"],
        request=AgentConfigSerializer,
        responses={200: AgentConfigSerializer}
    )
    @action(detail=False, methods=['post'])
    def update_agent_config(self, request):
        """更新Agent配置"""
        serializer = AgentConfigSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        config_data = serializer.validated_data
        
        with transaction.atomic():
            # 更新离线判定阈值
            ConfigManager.set(
                key='agent.offline_threshold_seconds',
                value=config_data['offline_threshold_seconds'],
                category='system',
                description='agent 离线判定阈值（秒），默认 600',
                user=request.user
            )
            
            # 更新按环境的离线阈值
            offline_threshold_by_env = config_data.get('offline_threshold_by_env', {})
            ConfigManager.set(
                key='agent.offline_threshold_by_env',
                value=offline_threshold_by_env,
                category='system',
                description='按环境的 agent 离线阈值映射，例如 {"prod": 300, "test": 900}',
                user=request.user
            )
        
        return SycResponse.success(content=config_data, message="Agent配置更新成功")
