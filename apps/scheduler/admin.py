"""
调度管理Admin配置
"""
from django.contrib import admin
from django.db import models
from django.utils.html import format_html
from django.urls import reverse
from django_json_widget.widgets import JSONEditorWidget
from guardian.admin import GuardedModelAdmin
from guardian.shortcuts import get_objects_for_user, get_perms
from .models import ScheduledJob
from .services import SchedulerService


class PermissionActionsMixin:
    """权限操作混入 - 统一处理 permission_actions 的显示逻辑"""
    
    def get_list_display(self, request):
        """动态调整列表显示字段"""
        display = list(super().get_list_display(request))
        # 只有超级管理员才显示 permission_actions
        if not request.user.is_superuser and 'permission_actions' in display:
            display.remove('permission_actions')
        return display


@admin.register(ScheduledJob)
class ScheduledJobAdmin(PermissionActionsMixin, GuardedModelAdmin):
    list_display = [
        'name', 'execution_plan', 'template_name', 'plan_name', 'cron_expression',
        'is_active', 'success_rate', 'total_runs', 'last_run_time', 'permission_actions'
    ]
    list_filter = ['is_active', 'created_at']
    search_fields = ['name', 'description', 'execution_plan__name', 'execution_plan__template__name']
    readonly_fields = [
        'created_at', 'updated_at', 'total_runs', 'success_runs',
        'failed_runs', 'last_run_time', 'next_run_time', 'periodic_task'
    ]
    # 删除filter_horizontal，因为ScheduledJob不再有target_hosts和target_groups字段

    fieldsets = (
        ('基本信息', {
            'fields': ('name', 'description', 'execution_plan', 'is_active')
        }),
        # 删除目标主机配置，因为目标主机在JobStep中配置
        ('调度配置', {
            'fields': ('cron_expression', 'timezone')
        }),
        ('统计信息', {
            'fields': (
                'total_runs', 'success_runs', 'failed_runs',
                'last_run_time', 'next_run_time'
            ),
            'classes': ('collapse',)
        }),
        ('系统信息', {
            'fields': ('periodic_task', 'created_by', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        })
    )

    actions = ['enable_jobs', 'disable_jobs', 'execute_now']
    
    def permission_actions(self, obj):
        """显示权限管理操作"""
        if obj:
            url = reverse('admin:scheduler_scheduledjob_change', args=[obj.id])
            return format_html(
                '<a href="{}" class="button">管理权限</a>',
                url
            )
        return "-"
    permission_actions.short_description = "权限管理"

    def save_model(self, request, obj, form, change):
        if not change:
            obj.created_by = request.user

        if change:
            # 更新定时作业
            SchedulerService.update_scheduled_job(obj, **form.cleaned_data)
        else:
            # 创建定时作业时需要特殊处理
            super().save_model(request, obj, form, change)
            # 创建Celery Beat任务
            if obj.is_active:
                SchedulerService._create_periodic_task(obj)
    
    def get_queryset(self, request):
        """根据用户权限过滤查询集"""
        if request.user.is_superuser:
            return super().get_queryset(request)
        return get_objects_for_user(request.user, 'scheduler.change_scheduledjob')
    
    def has_change_permission(self, request, obj=None):
        """检查用户是否有修改权限"""
        if request.user.is_superuser:
            return True
        if obj is None:
            return request.user.has_perm('scheduler.change_scheduledjob')
        return request.user.has_perm('scheduler.change_scheduledjob', obj)
    
    def has_delete_permission(self, request, obj=None):
        """检查用户是否有删除权限"""
        if request.user.is_superuser:
            return True
        if obj is None:
            return request.user.has_perm('scheduler.delete_scheduledjob')
        return request.user.has_perm('scheduler.delete_scheduledjob', obj)

    def enable_jobs(self, request, queryset):
        """启用定时作业"""
        count = 0
        for job in queryset:
            if not job.is_active:
                SchedulerService.update_scheduled_job(job, is_active=True)
                count += 1

        self.message_user(request, f'成功启用 {count} 个定时作业')
    enable_jobs.short_description = '启用选中的定时作业'

    def disable_jobs(self, request, queryset):
        """禁用定时作业"""
        count = 0
        for job in queryset:
            if job.is_active:
                SchedulerService.update_scheduled_job(job, is_active=False)
                count += 1

        self.message_user(request, f'成功禁用 {count} 个定时作业')
    disable_jobs.short_description = '禁用选中的定时作业'

    # 注意：移除了execute_now方法
    # 定时作业不应该有"立即执行"功能，这在逻辑上是矛盾的
    # 如果需要立即执行，应该直接执行ExecutionPlan：POST /api/templates/plans/{id}/execute/


# ScheduledJobExecution管理已移除，统一使用executor.models.ExecutionRecord


# JobScheduleRuleAdmin已删除，因为JobScheduleRule模型已删除
