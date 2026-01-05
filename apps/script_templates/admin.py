"""
脚本模板Admin配置
"""
from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from guardian.admin import GuardedModelAdmin
from guardian.shortcuts import get_objects_for_user, get_perms
from .models import ScriptTemplate


class PermissionActionsMixin:
    """权限操作混入 - 统一处理 permission_actions 的显示逻辑"""
    
    def get_list_display(self, request):
        """动态调整列表显示字段"""
        display = list(super().get_list_display(request))
        # 只有超级管理员才显示 permission_actions
        if not request.user.is_superuser and 'permission_actions' in display:
            display.remove('permission_actions')
        return display


@admin.register(ScriptTemplate)
class ScriptTemplateAdmin(PermissionActionsMixin, GuardedModelAdmin):
    list_display = [
        'name', 'script_type', 'template_type', 'version', 'is_active',
        'usage_count', 'is_public', 'created_by', 'created_at', 'permission_actions'
    ]
    list_filter = ['script_type', 'template_type', 'is_active', 'is_public', 'created_at']
    search_fields = ['name', 'description', 'tags']
    readonly_fields = ['usage_count', 'created_at', 'updated_at']

    fieldsets = (
        ('基本信息', {
            'fields': ('name', 'description', 'script_type', 'template_type')
        }),
        ('脚本内容', {
            'fields': ('script_content',)
        }),
        ('版本控制', {
            'fields': ('version', 'is_active')
        }),
        ('其他设置', {
            'fields': ('tags_json', 'is_public')
        }),
        ('统计信息', {
            'fields': ('usage_count', 'created_by', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        })
    )
    
    def permission_actions(self, obj):
        """显示权限管理操作"""
        if obj:
            url = reverse('admin:script_templates_scripttemplate_change', args=[obj.id])
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
        return get_objects_for_user(request.user, 'script_templates.change_scripttemplate')
    
    def has_change_permission(self, request, obj=None):
        """检查用户是否有修改权限"""
        if request.user.is_superuser:
            return True
        if obj is None:
            return request.user.has_perm('script_templates.change_scripttemplate')
        return request.user.has_perm('script_templates.change_scripttemplate', obj)
    
    def has_delete_permission(self, request, obj=None):
        """检查用户是否有删除权限"""
        if request.user.is_superuser:
            return True
        if obj is None:
            return request.user.has_perm('script_templates.delete_scripttemplate')
        return request.user.has_perm('script_templates.delete_scripttemplate', obj)
