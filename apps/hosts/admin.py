from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from guardian.admin import GuardedModelAdmin
from guardian.shortcuts import get_objects_for_user, get_perms
from .models import Host, HostGroup


@admin.register(HostGroup)
class HostGroupAdmin(GuardedModelAdmin):
    list_display = ['name', 'description', 'created_by', 'created_at', 'permission_actions']
    list_filter = ['created_at', 'created_by']
    search_fields = ['name', 'description']
    readonly_fields = ['created_at', 'updated_at']
    
    def permission_actions(self, obj):
        """显示权限管理操作"""
        if obj:
            url = reverse('admin:hosts_hostgroup_change', args=[obj.id])
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
        return get_objects_for_user(request.user, 'hosts.change_hostgroup')


@admin.register(Host)
class HostAdmin(GuardedModelAdmin):
    list_display = ['name', 'ip_address', 'port', 'os_type', 'status', 'created_by', 'created_at', 'permission_actions']
    list_filter = ['os_type', 'status', 'created_at', 'groups']
    search_fields = ['name', 'ip_address', 'description']
    filter_horizontal = ['groups']
    readonly_fields = ['created_at', 'updated_at', 'last_check_time']
    fieldsets = (
        ('基本信息', {
            'fields': ('name', 'ip_address', 'port', 'os_type', 'description')
        }),
        ('认证信息', {
            'fields': ('username', 'password', 'private_key'),
            'classes': ('collapse',)
        }),
        ('状态信息', {
            'fields': ('status', 'last_check_time')
        }),
        ('分组信息', {
            'fields': ('groups',)
        }),
        ('时间信息', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

    def permission_actions(self, obj):
        """显示权限管理操作"""
        if obj:
            url = reverse('admin:hosts_host_change', args=[obj.id])
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
        return get_objects_for_user(request.user, 'hosts.change_host')
    
    def has_change_permission(self, request, obj=None):
        """检查用户是否有修改权限"""
        if request.user.is_superuser:
            return True
        if obj is None:
            return request.user.has_perm('hosts.change_host')
        return request.user.has_perm('hosts.change_host', obj)
    
    def has_delete_permission(self, request, obj=None):
        """检查用户是否有删除权限"""
        if request.user.is_superuser:
            return True
        if obj is None:
            return request.user.has_perm('hosts.delete_host')
        return request.user.has_perm('hosts.delete_host', obj)
