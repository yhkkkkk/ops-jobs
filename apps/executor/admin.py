"""
统一执行记录Admin配置
"""
from django.contrib import admin
from django.db import models
from django.utils.html import format_html
from django.urls import reverse
from django_json_widget.widgets import JSONEditorWidget
from guardian.admin import GuardedModelAdmin
from guardian.shortcuts import get_objects_for_user, get_perms
from .models import ExecutionRecord, ExecutionStep


class ExecutionStepInline(admin.TabularInline):
    """执行步骤内联"""
    model = ExecutionStep
    extra = 0
    can_delete = False
    can_add = False
    readonly_fields = ['step_name', 'step_type', 'step_order', 'status', 'started_at', 'finished_at', 'duration_display']
    fields = ['step_order', 'step_name', 'step_type', 'status', 'started_at', 'finished_at', 'duration_display']
    ordering = ['step_order']
    verbose_name = "执行步骤"
    verbose_name_plural = "执行步骤"

    def duration_display(self, obj):
        """显示执行时长"""
        try:
            duration = obj.duration
            # 确保duration是数值类型
            if duration is not None:
                duration = float(duration)
                if duration < 60:
                    return f"{duration:.1f}秒"
                elif duration < 3600:
                    return f"{duration/60:.1f}分钟"
                else:
                    return f"{duration/3600:.1f}小时"
        except (ValueError, TypeError, AttributeError):
            pass
        return "-"
    duration_display.short_description = "执行时长"
    
    def get_queryset(self, request):
        """优化查询，预取关联数据"""
        qs = super().get_queryset(request)
        return qs.select_related('execution_record')


class PermissionActionsMixin:
    """权限操作混入 - 统一处理 permission_actions 的显示逻辑"""
    
    def get_list_display(self, request):
        """动态调整列表显示字段"""
        display = list(super().get_list_display(request))
        # 只有超级管理员才显示 permission_actions
        if not request.user.is_superuser and 'permission_actions' in display:
            display.remove('permission_actions')
        return display


@admin.register(ExecutionRecord)
class ExecutionRecordAdmin(PermissionActionsMixin, GuardedModelAdmin):
    list_display = [
        'execution_id', 'name', 'execution_type', 'status', 'executed_by',
        'success_rate_display', 'duration_display', 'created_at', 'permission_actions'
    ]
    list_filter = [
        'execution_type', 'status', 'trigger_type', 
        ('created_at', admin.DateFieldListFilter),
        ('started_at', admin.DateFieldListFilter),
        ('finished_at', admin.DateFieldListFilter)
    ]
    search_fields = ['execution_id', 'name', 'executed_by__username']
    readonly_fields = [
        'execution_id', 'created_at', 'started_at', 'finished_at',
        'duration_display'
    ]

    formfield_overrides = {
        models.JSONField: {'widget': JSONEditorWidget},
    }

    fieldsets = (
        ('基本信息', {
            'fields': ('execution_id', 'execution_type', 'name', 'description', 'status')
        }),
        ('执行信息', {
            'fields': ('executed_by', 'trigger_type')
        }),
        ('执行参数', {
            'fields': ('execution_parameters',),
            'classes': ('collapse',)
        }),
        ('执行结果', {
            'fields': ('execution_results', 'error_message'),
            'classes': ('collapse',)
        }),
        ('时间信息', {
            'fields': ('created_at', 'started_at', 'finished_at', 'duration_display')
        }),
        ('其他信息', {
            'fields': ('retry_count', 'client_ip', 'user_agent'),
            'classes': ('collapse',)
        })
    )

    inlines = [ExecutionStepInline]

    def permission_actions(self, obj):
        """显示权限管理操作"""
        if obj:
            url = reverse('admin:executor_executionrecord_change', args=[obj.id])
            return format_html(
                '<a href="{}" class="button">管理权限</a>',
                url
            )
        return "-"
    permission_actions.short_description = "权限管理"

    def success_rate_display(self, obj):
        """显示成功率"""
        try:
            rate = obj.success_rate
            # 确保rate是数值类型
            if rate is not None:
                rate = float(rate)
            else:
                rate = 0
        except (ValueError, TypeError, AttributeError):
            rate = 0
            
        if rate >= 90:
            color = 'green'
        elif rate >= 70:
            color = 'orange'
        else:
            color = 'red'
        
        # 先格式化数值，再传递给format_html
        formatted_rate = f"{rate:.1f}%"
        return format_html(
            '<span style="color: {};">{}</span>',
            color, formatted_rate
        )
    success_rate_display.short_description = "成功率"

    def duration_display(self, obj):
        """显示执行时长"""
        try:
            duration = obj.duration
            # 确保duration是数值类型
            if duration is not None:
                duration = float(duration)
                if duration < 60:
                    return f"{duration:.1f}秒"
                elif duration < 3600:
                    return f"{duration/60:.1f}分钟"
                else:
                    return f"{duration/3600:.1f}小时"
        except (ValueError, TypeError, AttributeError):
            pass
        return "-"
    duration_display.short_description = "执行时长"

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        """检查用户是否有修改权限"""
        if request.user.is_superuser:
            return True
        if obj is None:
            return request.user.has_perm('executor.change_executionrecord')
        return request.user.has_perm('executor.change_executionrecord', obj)
    
    def has_delete_permission(self, request, obj=None):
        """检查用户是否有删除权限"""
        if request.user.is_superuser:
            return True
        if obj is None:
            return request.user.has_perm('executor.delete_executionrecord')
        return request.user.has_perm('executor.delete_executionrecord', obj)
    
    def get_queryset(self, request):
        """根据用户权限过滤查询集"""
        if request.user.is_superuser:
            return super().get_queryset(request)
        return get_objects_for_user(request.user, 'executor.view_executionrecord')
