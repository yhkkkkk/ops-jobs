"""
权限管理后台配置
"""
from django.contrib import admin
from django.contrib.auth.models import Permission, Group, User
from django.contrib.contenttypes.models import ContentType
from django.utils.html import format_html
from django.urls import reverse, path
from django.utils.safestring import mark_safe
from guardian.models import UserObjectPermission, GroupObjectPermission
from .models import (
    AuditLog,
    PermissionTemplate,
)


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    """审计日志管理"""
    
    list_display = [
        'user', 'action', 'resource_info', 'ip_address', 
        'success', 'created_at', 'description_preview'
    ]
    
    list_filter = [
        'action', 'success', 'created_at', 'user', 'ip_address'
    ]
    
    search_fields = [
        'user__username', 'description', 'resource_name', 
        'ip_address', 'error_message'
    ]
    
    readonly_fields = [
        'user', 'action', 'description', 'resource_type', 
        'resource_id', 'resource_name', 'ip_address', 
        'user_agent', 'success', 'error_message', 
        'extra_data', 'created_at'
    ]
    
    fieldsets = [
        ('基本信息', {
            'fields': ['user', 'action', 'description', 'created_at']
        }),
        ('资源信息', {
            'fields': ['resource_type', 'resource_id', 'resource_name'],
            'classes': ['collapse']
        }),
        ('请求信息', {
            'fields': ['ip_address', 'user_agent'],
            'classes': ['collapse']
        }),
        ('操作结果', {
            'fields': ['success', 'error_message']
        }),
        ('额外数据', {
            'fields': ['extra_data_display'],
            'classes': ['collapse']
        })
    ]
    
    def resource_info(self, obj):
        """显示资源信息"""
        if obj.resource_type and obj.resource_id:
            try:
                model_class = obj.resource_type.model_class()
                if model_class:
                    obj_instance = model_class.objects.get(id=obj.resource_id)
                    admin_url = reverse(
                        f'admin:{obj.resource_type.app_label}_{obj.resource_type.model}_change',
                        args=[obj.resource_id]
                    )
                    return format_html(
                        '<a href="{}" target="_blank">{}</a>',
                        admin_url,
                        obj.resource_name or str(obj_instance)
                    )
            except:
                pass
        return obj.resource_name or '-'
    
    resource_info.short_description = "资源信息"
    
    def description_preview(self, obj):
        """描述预览"""
        if len(obj.description) > 50:
            return f"{obj.description[:50]}..."
        return obj.description
    
    description_preview.short_description = "描述预览"
    
    def extra_data_display(self, obj):
        """显示额外数据"""
        if not obj.extra_data:
            return "-"
        
        try:
            if isinstance(obj.extra_data, dict):
                html_parts = []
                for key, value in obj.extra_data.items():
                    if isinstance(value, list):
                        display_value = ', '.join(map(str, value))
                    else:
                        display_value = str(value)
                    html_parts.append(f"<strong>{key}:</strong> {display_value}")
                return mark_safe('<br>'.join(html_parts))
            return str(obj.extra_data)
        except:
            return str(obj.extra_data)
    
    extra_data_display.short_description = "额外数据"
    
    def has_add_permission(self, request):
        """禁止手动添加审计日志"""
        return False
    
    def has_change_permission(self, request, obj=None):
        """禁止修改审计日志"""
        return False
    
    def has_delete_permission(self, request, obj=None):
        """允许删除审计日志（管理员）"""
        return request.user.is_superuser
    
    def get_queryset(self, request):
        """优化查询"""
        return super().get_queryset(request).select_related(
            'user', 'resource_type'
        )
    
    def get_list_display(self, request):
        """根据用户权限调整显示字段"""
        if request.user.is_superuser:
            return self.list_display
        else:
            # 普通用户看不到IP地址等敏感信息
            return [f for f in self.list_display if f != 'ip_address']
    
    def get_fieldsets(self, request, obj=None):
        """根据用户权限调整字段集"""
        if request.user.is_superuser:
            return self.fieldsets
        else:
            # 普通用户看不到敏感信息
            filtered_fieldsets = []
            for name, options in self.fieldsets:
                if name == '请求信息':
                    continue
                filtered_fieldsets.append((name, options))
            return filtered_fieldsets
    
    actions = ['export_audit_logs']
    
    def export_audit_logs(self, request, queryset):
        """导出审计日志"""
        import csv
        from django.http import HttpResponse
        from django.utils import timezone
        
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = f'attachment; filename="audit_logs_{timezone.now().strftime("%Y%m%d_%H%M%S")}.csv"'
        
        writer = csv.writer(response)
        writer.writerow([
            '用户', '操作', '描述', '资源类型', '资源名称', 
            'IP地址', '成功', '错误信息', '创建时间'
        ])
        
        for log in queryset:
            writer.writerow([
                log.user.username,
                log.get_action_display(),
                log.description,
                log.resource_type.model if log.resource_type else '',
                log.resource_name,
                log.ip_address,
                '是' if log.success else '否',
                log.error_message,
                log.created_at.strftime('%Y-%m-%d %H:%M:%S')
            ])
        
        return response
    
    export_audit_logs.short_description = "导出选中的审计日志"


# 自定义管理站点标题
admin.site.site_header = "运维作业平台"
admin.site.site_title = "运维作业管理"
admin.site.index_title = "运维作业管理后台"


# Group admin - 支持 autocomplete_fields
try:
    admin.site.unregister(Group)
except admin.sites.NotRegistered:
    pass

class GroupAdmin(admin.ModelAdmin):
    """用户组管理 - 支持 autocomplete_fields 搜索"""
    search_fields = ['name']
    list_display = ['name']
    
    def has_view_permission(self, request, obj=None):
        """允许所有已登录用户查看（autocomplete 需要）"""
        return request.user.is_authenticated
    
    def has_module_permission(self, request):
        """允许所有已登录用户访问模块"""
        return request.user.is_authenticated

admin.site.register(Group, GroupAdmin)


# Permission admin - 支持 autocomplete_fields
try:
    admin.site.unregister(Permission)
except admin.sites.NotRegistered:
    pass

class PermissionAdmin(admin.ModelAdmin):
    """权限管理 - 支持 autocomplete_fields 搜索"""
    search_fields = ['codename', 'name', 'content_type__app_label', 'content_type__model']
    list_display = ['codename', 'name', 'content_type']
    list_filter = ['content_type']
    
    def has_view_permission(self, request, obj=None):
        """允许所有已登录用户查看（autocomplete 需要）"""
        return request.user.is_authenticated
    
    def has_module_permission(self, request):
        """允许所有已登录用户访问模块"""
        return request.user.is_authenticated
    
    def get_queryset(self, request):
        """优化查询"""
        return super().get_queryset(request).select_related('content_type')
    
    def get_search_results(self, request, queryset, search_term):
        """优化搜索"""
        queryset, use_distinct = super().get_search_results(request, queryset, search_term)
        return queryset, use_distinct

admin.site.register(Permission, PermissionAdmin)


# ContentType admin - 支持 autocomplete_fields
try:
    admin.site.unregister(ContentType)
except admin.sites.NotRegistered:
    pass

class ContentTypeAdmin(admin.ModelAdmin):
    """内容类型管理 - 支持 autocomplete_fields 搜索"""
    search_fields = ['app_label', 'model']
    list_display = ['app_label', 'model']
    list_filter = ['app_label']
    
    def has_view_permission(self, request, obj=None):
        """允许所有已登录用户查看（autocomplete 需要）"""
        return request.user.is_authenticated
    
    def has_module_permission(self, request):
        """允许所有已登录用户访问模块"""
        return request.user.is_authenticated
    
    def get_queryset(self, request):
        """优化查询，添加排序以避免警告"""
        return super().get_queryset(request).order_by('app_label', 'model')

admin.site.register(ContentType, ContentTypeAdmin)


@admin.register(PermissionTemplate)
class PermissionTemplateAdmin(admin.ModelAdmin):
    """权限模板管理"""

    list_display = ("name", "is_active", "permission_count", "created_at", "updated_at")
    search_fields = ("name", "description")
    list_filter = ("is_active",)
    filter_horizontal = ("model_permissions",)

    def permission_count(self, obj):
        return obj.model_permissions.count()


UserObjectPermission._meta.verbose_name = '用户对象权限'
UserObjectPermission._meta.verbose_name_plural = '用户对象权限'


@admin.register(UserObjectPermission)
class UserObjectPermissionAdmin(admin.ModelAdmin):
    """用户对象权限管理 - 全局查看和管理所有用户对象权限"""
    
    list_display = ['user', 'permission', 'content_type', 'object_pk', 'get_object_link']
    list_filter = ['permission', 'content_type', 'user']
    search_fields = ['user__username', 'object_pk', 'permission__codename']
    autocomplete_fields = ['user', 'permission', 'content_type']
    
    fieldsets = (
        ('基本信息', {
            'fields': (('user', 'permission'), ('content_type', 'object_pk'))
        }),
    )
    
    def __init__(self, model, admin_site):
        super().__init__(model, admin_site)
        # 设置字段的中文显示名称
        self.model._meta.get_field('user').verbose_name = '用户'
        self.model._meta.get_field('permission').verbose_name = '权限'
        self.model._meta.get_field('content_type').verbose_name = '内容类型'
        self.model._meta.get_field('object_pk').verbose_name = '对象ID'

    def get_readonly_fields(self, request, obj=None):
        """设置只读字段：添加时可编辑所有字段，编辑时所有字段只读（因为对象权限通常不应该修改）"""
        if obj is None:
            # 添加时，所有字段可编辑
            return []
        else:
            # 编辑时，所有字段只读（建议删除后重新添加）
            return ['user', 'permission', 'content_type', 'object_pk']
    
    def changelist_view(self, request, extra_context=None):
        """重写列表视图，设置页面标题"""
        extra_context = extra_context or {}
        extra_context['title'] = '用户对象权限'
        return super().changelist_view(request, extra_context)
    
    def add_view(self, request, form_url='', extra_context=None):
        """重写添加视图，设置页面标题"""
        extra_context = extra_context or {}
        extra_context['title'] = '添加用户对象权限'
        return super().add_view(request, form_url, extra_context)
    
    def change_view(self, request, object_id, form_url='', extra_context=None):
        """重写修改视图，设置页面标题"""
        extra_context = extra_context or {}
        extra_context['title'] = '修改用户对象权限'
        return super().change_view(request, object_id, form_url, extra_context)
    
    def get_object_link(self, obj):
        """获取关联对象的链接"""
        try:
            model_class = obj.content_type.model_class()
            if model_class:
                obj_instance = model_class.objects.get(pk=obj.object_pk)
                app_label = obj.content_type.app_label
                model_name = obj.content_type.model
                admin_url = reverse(
                    f'admin:{app_label}_{model_name}_change',
                    args=[obj.object_pk]
                )
                return format_html(
                    '<a href="{}" target="_blank">{}</a>',
                    admin_url,
                    str(obj_instance)
                )
        except Exception as e:
            return f"对象不存在或已删除 (ID: {obj.object_pk})"
        return "-"
    get_object_link.short_description = "关联对象"

    def has_view_permission(self, request, obj=None):
        """允许所有已登录用户查看（autocomplete 需要）"""
        return request.user.is_authenticated
    
    def has_add_permission(self, request):
        """建议通过 GuardedModelAdmin 或服务层添加对象权限"""
        return request.user.is_superuser
    
    def has_change_permission(self, request, obj=None):
        """建议通过 GuardedModelAdmin 或服务层修改对象权限"""
        return request.user.is_superuser
    
    def has_module_permission(self, request):
        """允许所有已登录用户访问模块"""
        return request.user.is_authenticated


GroupObjectPermission._meta.verbose_name = '组对象权限'
GroupObjectPermission._meta.verbose_name_plural = '组对象权限'


@admin.register(GroupObjectPermission)
class GroupObjectPermissionAdmin(admin.ModelAdmin):
    """组对象权限管理 - 全局查看和管理所有组对象权限"""
    
    list_display = ['group', 'permission', 'content_type', 'object_pk', 'get_object_link']
    list_filter = ['permission', 'content_type', 'group']
    search_fields = ['group__name', 'object_pk', 'permission__codename']
    autocomplete_fields = ['group', 'content_type']
    
    fieldsets = (
        ('基本信息', {
            'fields': (('group', 'permission'), ('content_type', 'object_pk'))
        }),
    )
    
    def __init__(self, model, admin_site):
        super().__init__(model, admin_site)
        # 设置字段的中文显示名称
        self.model._meta.get_field('group').verbose_name = '用户组'
        self.model._meta.get_field('permission').verbose_name = '权限'
        self.model._meta.get_field('content_type').verbose_name = '内容类型'
        self.model._meta.get_field('object_pk').verbose_name = '对象ID'

    def get_readonly_fields(self, request, obj=None):
        """设置只读字段"""
        if obj is None:
            # 添加时，object_display 通过表单 widget 设置为只读，不需要在这里声明
            # 因为它是表单字段，不是模型字段
            return []
        else:
            # 编辑时，所有模型字段只读（建议删除后重新添加）
            # 注意：object_display 和 permissions 是表单字段，不需要在这里声明
            return ['group', 'content_type', 'object_pk']
    
    def response_add(self, request, obj, post_url_continue=None):
        """添加后重定向到列表页"""
        from django.contrib import messages
        from django.shortcuts import redirect
        from django.urls import reverse
        
        # 重定向到列表页
        return redirect(reverse('admin:guardian_groupobjectpermission_changelist'))
    
    def changelist_view(self, request, extra_context=None):
        """重写列表视图，设置页面标题"""
        extra_context = extra_context or {}
        extra_context['title'] = '组对象权限'
        return super().changelist_view(request, extra_context)
    
    def add_view(self, request, form_url='', extra_context=None):
        """重写添加视图，设置页面标题"""
        extra_context = extra_context or {}
        extra_context['title'] = '添加组对象权限'
        return super().add_view(request, form_url, extra_context)
    
    def change_view(self, request, object_id, form_url='', extra_context=None):
        """重写修改视图，设置页面标题"""
        extra_context = extra_context or {}
        extra_context['title'] = '修改组对象权限'
        return super().change_view(request, object_id, form_url, extra_context)
    
    def get_object_link(self, obj):
        """获取关联对象的链接"""
        try:
            model_class = obj.content_type.model_class()
            if model_class:
                obj_instance = model_class.objects.get(pk=obj.object_pk)
                app_label = obj.content_type.app_label
                model_name = obj.content_type.model
                admin_url = reverse(
                    f'admin:{app_label}_{model_name}_change',
                    args=[obj.object_pk]
                )
                return format_html(
                    '<a href="{}" target="_blank">{}</a>',
                    admin_url,
                    str(obj_instance)
                )
        except Exception as e:
            return f"对象不存在或已删除 (ID: {obj.object_pk})"
        return "-"
    get_object_link.short_description = "关联对象"
    
    def has_view_permission(self, request, obj=None):
        """允许所有已登录用户查看（autocomplete 需要）"""
        return request.user.is_authenticated
    
    def has_add_permission(self, request):
        """建议通过 GuardedModelAdmin 或服务层添加对象权限"""
        return request.user.is_superuser
    
    def has_change_permission(self, request, obj=None):
        """建议通过 GuardedModelAdmin 或服务层修改对象权限"""
        return request.user.is_superuser
    
    def has_module_permission(self, request):
        """允许所有已登录用户访问模块"""
        return request.user.is_authenticated
