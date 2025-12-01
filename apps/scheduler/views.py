"""
调度管理API视图
"""
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django_filters.rest_framework import DjangoFilterBackend
from apps.permissions.permissions import ScheduledJobPermission
from django.db.models import Q
from utils.pagination import CustomPagination
from utils.responses import SycResponse
from .models import ScheduledJob
from .serializers import (
    ScheduledJobSerializer,
    ScheduledJobCreateSerializer
)
from .services import SchedulerService
from .filters import ScheduledJobFilter


class ScheduledJobViewSet(viewsets.ModelViewSet):
    """定时作业ViewSet"""

    queryset = ScheduledJob.objects.all()
    serializer_class = ScheduledJobSerializer
    permission_classes = [ScheduledJobPermission]
    pagination_class = CustomPagination
    filter_backends = [DjangoFilterBackend]
    filterset_class = ScheduledJobFilter

    def get_serializer_class(self):
        if self.action == 'create':
            return ScheduledJobCreateSerializer
        return ScheduledJobSerializer

    def get_queryset(self):
        return super().get_queryset().select_related('execution_plan__template', 'created_by')

    def retrieve(self, request, *args, **kwargs):
        """获取定时作业详情"""
        instance = self.get_object()
        serializer = self.get_serializer(instance)

        return SycResponse.success(
            content=serializer.data,
            message="获取定时作业详情成功"
        )

    def create(self, request, *args, **kwargs):
        """创建定时作业"""
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            # 使用服务创建定时作业
            scheduled_job = SchedulerService.create_scheduled_job(
                created_by=request.user,
                **serializer.validated_data
            )

            # 记录审计日志
            from utils.audit_service import AuditLogService
            AuditLogService.log_action(
                user=request.user,
                action='create_scheduled_job',
                description=f"创建定时作业: {scheduled_job.name}",
                request=request,
                resource_id=scheduled_job.id,
                resource_name=scheduled_job.name,
                success=True
            )

            response_serializer = ScheduledJobSerializer(scheduled_job)
            return SycResponse.success(
                content=response_serializer.data,
                message="定时作业创建成功"
            )

        except Exception as e:
            # 记录失败的审计日志
            from utils.audit_service import AuditLogService
            AuditLogService.log_action(
                user=request.user,
                action='create_scheduled_job',
                description=f"创建定时作业失败: {str(e)}",
                request=request,
                success=False,
                error_message=str(e)
            )

            return SycResponse.error(
                message=f'定时作业创建失败: {str(e)}'
            )

    def update(self, request, *args, **kwargs):
        """更新定时作业"""
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)

        try:
            updated_job = SchedulerService.update_scheduled_job(
                scheduled_job=instance,
                **serializer.validated_data
            )

            # 记录审计日志
            from utils.audit_service import AuditLogService
            AuditLogService.log_action(
                user=request.user,
                action='update_scheduled_job',
                description=f"更新定时作业: {updated_job.name}",
                request=request,
                resource_id=updated_job.id,
                resource_name=updated_job.name,
                success=True
            )

            response_serializer = ScheduledJobSerializer(updated_job)
            return SycResponse.success(
                content=response_serializer.data,
                message="定时作业更新成功"
            )

        except Exception as e:
            from utils.audit_service import AuditLogService
            AuditLogService.log_action(
                user=request.user,
                action='update_scheduled_job',
                description=f"更新定时作业失败: {instance.name}",
                request=request,
                resource_id=instance.id,
                resource_name=instance.name,
                success=False,
                error_message=str(e)
            )

            return SycResponse.error(
                message=f'定时作业更新失败: {str(e)}'
            )

    def destroy(self, request, *args, **kwargs):
        """删除定时作业"""
        instance = self.get_object()
        job_name = instance.name
        job_id = instance.id

        try:
            SchedulerService.delete_scheduled_job(instance)

            # 记录审计日志
            from utils.audit_service import AuditLogService
            AuditLogService.log_action(
                user=request.user,
                action='delete_scheduled_job',
                description=f"删除定时作业: {job_name}",
                request=request,
                resource_id=job_id,
                resource_name=job_name,
                success=True
            )

            return SycResponse.success(
                message="定时作业删除成功"
            )

        except Exception as e:
            from utils.audit_service import AuditLogService
            AuditLogService.log_action(
                user=request.user,
                action='delete_scheduled_job',
                description=f"删除定时作业失败: {job_name}",
                request=request,
                resource_id=job_id,
                resource_name=job_name,
                success=False,
                error_message=str(e)
            )

            return SycResponse.error(
                message=f'定时作业删除失败: {str(e)}'
            )

    @action(detail=True, methods=['post'])
    def enable(self, request, pk=None):
        """启用定时作业"""
        instance = self.get_object()

        if instance.is_active:
            return SycResponse.error(message="定时作业已经是启用状态")

        try:
            # 使用服务启用定时作业
            SchedulerService.enable_scheduled_job(instance)

            # 记录审计日志
            from utils.audit_service import AuditLogService
            AuditLogService.log_action(
                user=request.user,
                action='enable_scheduled_job',
                description=f"启用定时作业: {instance.name}",
                request=request,
                resource_id=instance.id,
                resource_name=instance.name,
                success=True
            )

            return SycResponse.success(message="定时作业启用成功")

        except Exception as e:
            from utils.audit_service import AuditLogService
            AuditLogService.log_action(
                user=request.user,
                action='enable_scheduled_job',
                description=f"启用定时作业失败: {instance.name}",
                request=request,
                resource_id=instance.id,
                resource_name=instance.name,
                success=False,
                error_message=str(e)
            )

            return SycResponse.error(message=f'定时作业启用失败: {str(e)}')

    @action(detail=True, methods=['post'])
    def disable(self, request, pk=None):
        """禁用定时作业"""
        instance = self.get_object()

        if not instance.is_active:
            return SycResponse.error(message="定时作业已经是禁用状态")

        try:
            # 使用服务禁用定时作业
            SchedulerService.disable_scheduled_job(instance)

            # 记录审计日志
            from utils.audit_service import AuditLogService
            AuditLogService.log_action(
                user=request.user,
                action='disable_scheduled_job',
                description=f"禁用定时作业: {instance.name}",
                request=request,
                resource_id=instance.id,
                resource_name=instance.name,
                success=True
            )

            return SycResponse.success(message="定时作业禁用成功")

        except Exception as e:
            from utils.audit_service import AuditLogService
            AuditLogService.log_action(
                user=request.user,
                action='disable_scheduled_job',
                description=f"禁用定时作业失败: {instance.name}",
                request=request,
                resource_id=instance.id,
                resource_name=instance.name,
                success=False,
                error_message=str(e)
            )

            return SycResponse.error(message=f'定时作业禁用失败: {str(e)}')
