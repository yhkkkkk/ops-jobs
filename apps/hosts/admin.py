from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from guardian.admin import GuardedModelAdmin
from guardian.shortcuts import get_objects_for_user, get_perms
from .models import Host, HostGroup


class PermissionActionsMixin:
    """权限操作混入 - 统一处理 permission_actions 的显示逻辑"""
    
    def get_list_display(self, request):
        """动态调整列表显示字段"""
        display = list(super().get_list_display(request))
        # 只有超级管理员才显示 permission_actions
        if not request.user.is_superuser and 'permission_actions' in display:
            display.remove('permission_actions')
        return display
    
    def permission_actions(self, obj):
        """显示权限管理操作 - 只有超级管理员才显示"""
        # 这个方法会在 get_list_display 中已经被过滤，这里作为备用检查
        return "-"
    permission_actions.short_description = "权限管理"


@admin.register(HostGroup)
class HostGroupAdmin(PermissionActionsMixin, GuardedModelAdmin):
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

    def save_model(self, request, obj, form, change):
        if not change:
            obj.created_by = request.user
        super().save_model(request, obj, form, change)
    
    def get_queryset(self, request):
        """根据用户权限过滤查询集"""
        if request.user.is_superuser:
            return super().get_queryset(request)
        # 检查 view 权限，如果没有则检查 change 权限
        if request.user.has_perm('hosts.view_hostgroup'):
            return get_objects_for_user(request.user, 'hosts.view_hostgroup')
        return get_objects_for_user(request.user, 'hosts.change_hostgroup')
    
    def has_view_permission(self, request, obj=None):
        """检查用户是否有查看权限"""
        if request.user.is_superuser:
            return True
        if obj is None:
            return request.user.has_perm('hosts.view_hostgroup') or request.user.has_perm('hosts.change_hostgroup')
        return request.user.has_perm('hosts.view_hostgroup', obj) or request.user.has_perm('hosts.change_hostgroup', obj)


@admin.register(Host)
class HostAdmin(PermissionActionsMixin, GuardedModelAdmin):
    list_display = ['name', 'get_ip_display', 'port', 'os_type', 'account', 'status', 'created_by', 'created_at', 'permission_actions']
    list_filter = ['os_type', 'status', 'created_at', 'groups', 'account']
    search_fields = ['name', 'internal_ip', 'public_ip', 'description']
    filter_horizontal = ['groups']
    readonly_fields = ['created_at', 'updated_at', 'last_check_time']
    fieldsets = (
        ('基本信息', {
            'fields': ('name', 'port', 'os_type', 'description')
        }),
        ('网络信息', {
            'fields': ('internal_ip', 'public_ip', 'gateway', 'dns_servers')
        }),
        ('认证信息', {
            'fields': ('account',),
            'description': '选择用于SSH连接的服务器账号'
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
    
    def get_ip_display(self, obj):
        """显示IP地址（优先内网IP）"""
        if obj.internal_ip:
            return f"{obj.internal_ip} (内网)"
        elif obj.public_ip:
            return f"{obj.public_ip} (外网)"
        return "-"
    get_ip_display.short_description = "IP地址"

    def permission_actions(self, obj):
        """显示权限管理操作"""
        if obj:
            url = reverse('admin:hosts_host_change', args=[obj.id])
            return format_html(
                '<a href="{}" class="button">管理权限</a>',
                url
            )
        return "-"

    def save_model(self, request, obj, form, change):
        if not change:
            obj.created_by = request.user
        super().save_model(request, obj, form, change)
    
    def get_queryset(self, request):
        """根据用户权限过滤查询集"""
        if request.user.is_superuser:
            return super().get_queryset(request)
        # 检查 view 权限，如果没有则检查 change 权限
        if request.user.has_perm('hosts.view_host'):
            return get_objects_for_user(request.user, 'hosts.view_host')
        return get_objects_for_user(request.user, 'hosts.change_host')
    
    def has_view_permission(self, request, obj=None):
        """检查用户是否有查看权限"""
        if request.user.is_superuser:
            return True
        if obj is None:
            return request.user.has_perm('hosts.view_host') or request.user.has_perm('hosts.change_host')
        return request.user.has_perm('hosts.view_host', obj) or request.user.has_perm('hosts.change_host', obj)
    
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
