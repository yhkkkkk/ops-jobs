from django.contrib import admin
from django.db import models
from django_json_widget.widgets import JSONEditorWidget
from django.utils.html import format_html
from django.urls import reverse
from guardian.admin import GuardedModelAdmin
from guardian.shortcuts import get_objects_for_user, get_perms
from .models import JobTemplate, JobStep, ExecutionPlan, PlanStep


class PermissionActionsMixin:
    """权限操作混入 - 统一处理 permission_actions 的显示逻辑"""
    
    def get_list_display(self, request):
        """动态调整列表显示字段"""
        display = list(super().get_list_display(request))
        # 只有超级管理员才显示 permission_actions
        if not request.user.is_superuser and 'permission_actions' in display:
            display.remove('permission_actions')
        return display


class JobStepInline(admin.StackedInline):
    """作业步骤内联编辑 - 使用StackedInline提供更好的布局"""
    model = JobStep
    extra = 1
    fields = [
        ('name', 'step_type', 'order'),
        ('timeout', 'ignore_error'),
        'description',
        ('script_type', 'script_content'),
        ('remote_path', 'overwrite_policy'),
        'step_parameters',
        ('target_hosts', 'target_groups'),
    ]
    ordering = ['order']
    
    # 根据步骤类型动态显示/隐藏字段
    def get_fields(self, request, obj=None):
        fields = list(super().get_fields(request, obj))
        return fields

    formfield_overrides = {
        models.JSONField: {'widget': JSONEditorWidget},
        models.TextField: {'widget': admin.widgets.AdminTextareaWidget(attrs={'rows': 3})},
    }

    def get_formset(self, request, obj=None, **kwargs):
        formset = super().get_formset(request, obj, **kwargs)
        
        # 自定义表单集，添加JavaScript来动态显示/隐藏字段
        class CustomFormSet(formset):
            class Media:
                js = ('admin/js/job_step_dynamic_fields.js',)
        
        return CustomFormSet


class PlanStepInline(admin.StackedInline):
    """方案步骤内联编辑 - 使用StackedInline提供更好的布局（参考作业模板）"""
    model = PlanStep
    extra = 0
    fields = [
        ('step', 'order'),
        'override_timeout',
        'override_parameters',
    ]
    ordering = ['order']
    verbose_name = "执行步骤"
    verbose_name_plural = "执行步骤"

    formfield_overrides = {
        models.JSONField: {'widget': JSONEditorWidget},
    }


@admin.register(JobTemplate)
class JobTemplateAdmin(PermissionActionsMixin, GuardedModelAdmin):
    list_display = ['name', 'category', 'step_count', 'plan_count', 'created_by', 'created_at', 'permission_actions']
    list_filter = ['category', 'created_at']
    search_fields = ['name', 'description']
    readonly_fields = ['created_at', 'updated_at', 'step_count', 'plan_count']
    formfield_overrides = {
        models.JSONField: {'widget': JSONEditorWidget},
    }
    inlines = [JobStepInline]  # 添加步骤内联编辑

    fieldsets = (
        ('基本信息', {
            'fields': ('name', 'description', 'category', 'tags_json')
        }),
        ('全局变量', {
            'fields': ('global_parameters',),
            'classes': ('collapse',)
        }),
        ('统计信息', {
            'fields': ('step_count', 'plan_count'),
            'classes': ('collapse',)
        }),
        ('时间信息', {
            'fields': ('created_by', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        })
    )

    def permission_actions(self, obj):
        """显示权限管理操作"""
        if obj:
            url = reverse('admin:job_templates_jobtemplate_change', args=[obj.id])
            return format_html(
                '<a href="{}" class="button">管理权限</a>',
                url
            )
        return "-"
    permission_actions.short_description = "权限管理"

    def save_model(self, request, obj, form, change):
        if not change:
            obj.created_by = request.user
        super().save_model(request, obj, form, change)
    
    def get_queryset(self, request):
        """根据用户权限过滤查询集"""
        if request.user.is_superuser:
            return super().get_queryset(request)
        return get_objects_for_user(request.user, 'job_templates.change_jobtemplate')
    
    def has_change_permission(self, request, obj=None):
        """检查用户是否有修改权限"""
        if request.user.is_superuser:
            return True
        if obj is None:
            return request.user.has_perm('job_templates.change_jobtemplate')
        return request.user.has_perm('job_templates.change_jobtemplate', obj)
    
    def has_delete_permission(self, request, obj=None):
        """检查用户是否有删除权限"""
        if request.user.is_superuser:
            return True
        if obj is None:
            return request.user.has_perm('job_templates.delete_jobtemplate')
        return request.user.has_perm('job_templates.delete_jobtemplate', obj)

    class Media:
        css = {
            'all': ('admin/css/job_template_admin.css',)
        }
        js = ('admin/js/job_template_admin.js',)


@admin.register(JobStep)
class JobStepAdmin(GuardedModelAdmin):
    list_display = ['name', 'template', 'step_type', 'order', 'timeout', 'ignore_error']
    list_filter = ['step_type', 'ignore_error', 'template']
    search_fields = ['name', 'description', 'template__name']
    list_select_related = ['template']  # 优化查询
    ordering = ['template', 'order']  # 按模板和顺序排序
    filter_horizontal = ['target_hosts', 'target_groups']

    formfield_overrides = {
        models.JSONField: {'widget': JSONEditorWidget},
    }

    fieldsets = (
        ('基本信息', {
            'fields': ('template', 'name', 'description', 'step_type', 'order')
        }),
        ('目标主机', {
            'fields': ('target_hosts', 'target_groups')
        }),
        ('步骤参数', {
            'fields': ('step_parameters',),
            'classes': ('collapse',)
        }),
        ('执行配置', {
            'fields': ('timeout', 'ignore_error')
        })
    )

    def get_readonly_fields(self, request, obj=None):
        """编辑时模板字段只读"""
        if obj:  # 编辑现有对象
            return ['template']
        return []  # 新建时可以选择模板
    
    def get_queryset(self, request):
        """根据用户权限过滤查询集"""
        if request.user.is_superuser:
            return super().get_queryset(request)
        return get_objects_for_user(request.user, 'job_templates.change_jobstep')


@admin.register(ExecutionPlan)
class ExecutionPlanAdmin(PermissionActionsMixin, GuardedModelAdmin):
    list_display = ['template', 'name', 'step_count', 'created_by', 'created_at', 'permission_actions']
    list_filter = ['template', 'created_at']
    search_fields = ['name', 'description', 'template__name']
    readonly_fields = ['created_at', 'updated_at', 'step_count']
    inlines = [PlanStepInline]  # 添加步骤内联编辑

    fieldsets = (
        ('基本信息', {
            'fields': ('template', 'name', 'description')
        }),
        ('全局变量快照', {
            'fields': ('global_parameters_snapshot',),
            'classes': ('collapse',)
        }),
        ('统计信息', {
            'fields': ('step_count',),
            'classes': ('collapse',)
        }),
        ('时间信息', {
            'fields': ('created_by', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        })
    )
    
    formfield_overrides = {
        models.JSONField: {'widget': JSONEditorWidget},
    }

    def permission_actions(self, obj):
        """显示权限管理操作"""
        if obj:
            url = reverse('admin:job_templates_executionplan_change', args=[obj.id])
            return format_html(
                '<a href="{}" class="button">管理权限</a>',
                url
            )
        return "-"
    permission_actions.short_description = "权限管理"

    def save_model(self, request, obj, form, change):
        if not change:
            obj.created_by = request.user
        super().save_model(request, obj, form, change)
    
    def get_queryset(self, request):
        """根据用户权限过滤查询集"""
        if request.user.is_superuser:
            return super().get_queryset(request)
        return get_objects_for_user(request.user, 'job_templates.change_executionplan')
    
    def has_change_permission(self, request, obj=None):
        """检查用户是否有修改权限"""
        if request.user.is_superuser:
            return True
        if obj is None:
            return request.user.has_perm('job_templates.change_executionplan')
        return request.user.has_perm('job_templates.change_executionplan', obj)
    
    def has_delete_permission(self, request, obj=None):
        """检查用户是否有删除权限"""
        if request.user.is_superuser:
            return True
        if obj is None:
            return request.user.has_perm('job_templates.delete_executionplan')
        return request.user.has_perm('job_templates.delete_executionplan', obj)


@admin.register(PlanStep)
class PlanStepAdmin(GuardedModelAdmin):
    list_display = ['plan', 'step', 'order', 'override_timeout']
    list_filter = ['plan__template', 'step__step_type']
    search_fields = ['plan__name', 'step__name']

    formfield_overrides = {
        models.JSONField: {'widget': JSONEditorWidget},
    }

    fieldsets = (
        ('基本信息', {
            'fields': ('plan', 'step', 'order')
        }),
        ('参数覆盖', {
            'fields': ('override_parameters', 'override_timeout'),
            'classes': ('collapse',)
        })
    )
    
    def get_queryset(self, request):
        """根据用户权限过滤查询集"""
        if request.user.is_superuser:
            return super().get_queryset(request)
        return get_objects_for_user(request.user, 'job_templates.change_planstep')
