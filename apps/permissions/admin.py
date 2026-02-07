"""
权限管理后台配置
"""
from django.contrib import admin
from django.contrib.auth.models import Permission, Group, User
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ObjectDoesNotExist
from django.db import transaction
from django.http import JsonResponse
from django.utils.html import format_html
from django.urls import reverse, path
from django.utils.safestring import mark_safe
from django.core.exceptions import ValidationError
from guardian.models import UserObjectPermission, GroupObjectPermission
from guardian.shortcuts import assign_perm

from .models import (
    AuditLog,
    PermissionTemplate,
)
from .forms import GroupObjectPermissionForm


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
admin.site.site_header = "运维作业管理后台"
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
    
    def has_add_permission(self, request):
        """禁止在admin中直接添加内容类型"""
        return False
        
    def has_change_permission(self, request, obj=None):
        """允许编辑已有的内容类型"""
        return False
        
    def has_delete_permission(self, request, obj=None):
        """允许删除已有的内容类型"""
        return False
    
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

    form = GroupObjectPermissionForm
    list_display = ['group', 'permission_name', 'content_type', 'object_name', 'get_object_link']
    list_filter = ['content_type', 'group']
    search_fields = ['group__name']

    def get_fieldsets(self, request, obj=None):
        """根据模式返回不同的字段集"""
        if obj is None:
            # 创建模式：使用表单字段
            return (
                ('授权配置', {
                    'fields': ('group', 'content_type', 'object_selection', 'permissions'),
                    'classes': ('wide', 'extrapretty'),
                }),
            )
        else:
            # 查看模式：对象使用自定义显示方法，权限保持原样
            return (
                ('授权配置', {
                    'fields': ('group', 'content_type', 'object_display', 'permission'),
                    'classes': ('wide', 'extrapretty'),
                }),
            )

    class Media:
        css = {
            'all': ('admin/css/vendor/select2/select2.css', 'admin/css/autocomplete.css')
        }
        js = (
            'admin/js/vendor/select2/select2.full.js',
            'admin/js/jquery.init.js',
            'admin/js/group_perm_admin.js',
        )

    def __init__(self, model, admin_site):
        super().__init__(model, admin_site)
        # 这种修改 Meta 的方式在多线程环境下可能不安全，但在 Admin 中通常可以接受
        # 更好的方式是在 Model 定义中修改 verbose_name
        self.model._meta.get_field('group').verbose_name = '用户组'
        self.model._meta.get_field('permission').verbose_name = '权限'
        self.model._meta.get_field('content_type').verbose_name = '内容类型'
        self.model._meta.get_field('object_pk').verbose_name = '对象ID'

    def get_readonly_fields(self, request, obj=None):
        if obj is None:
            return []
        else:
            # 查看模式下，使用自定义显示方法显示对象名称，权限保持原样
            return ['group', 'content_type', 'object_display', 'permission']

    def object_display(self, obj):
        """显示对象名称（查看模式）"""
        if not obj:
            return "-"
        try:
            if obj.content_type and obj.object_pk:
                model_class = obj.content_type.model_class()
                if model_class:
                    target_obj = model_class.objects.get(pk=obj.object_pk)
                    return str(target_obj)
        except Exception:
            pass
        return f"对象ID: {obj.object_pk}" if obj.object_pk else "-"
    object_display.short_description = "目标对象"

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path('get-content-type-data/',
                 self.admin_site.admin_view(self.get_content_type_data),
                 name='guardian_groupobjectpermission_get_data'),
        ]
        return custom_urls + urls

    def get_content_type_data(self, request):
        ct_id = request.GET.get('ct_id')
        if not ct_id:
            return JsonResponse({'objects': [], 'permissions': []})

        try:
            ct = ContentType.objects.get(id=ct_id)
            model_class = ct.model_class()
            objects = []
            queryset = model_class.objects.all()
            if hasattr(model_class, 'name'):
                queryset = queryset.only('pk', 'name')

            for obj in queryset[:200]:
                objects.append({'id': str(obj.pk), 'text': str(obj)})

            permissions = list(Permission.objects.filter(content_type=ct).values('id', 'name', 'codename'))

            return JsonResponse({
                'objects': objects,
                'permissions': permissions
            })
        except Exception as e:
            return JsonResponse({'error': str(e), 'objects': [], 'permissions': []})

    def save_model(self, request, obj, form, change):
        """
        核心逻辑：拦截保存，批量分配权限
        
        注意：我们没有保存传入的 obj 对象，而是使用 assign_perm 批量创建权限记录。
        这是因为：
        1. 表单允许选择多个权限，需要为每个权限创建一个 GroupObjectPermission 记录
        2. 如果保存 obj，只能创建一个记录（因为 obj.permission 只能是一个值）
        3. 使用 assign_perm 可以批量创建多个权限记录
        """
        # 验证表单数据
        if not form.is_valid():
            raise ValidationError("表单验证失败，请检查输入。")
        
        group = form.cleaned_data.get('group')
        object_pk = form.cleaned_data.get('object_selection')
        content_type = form.cleaned_data.get('content_type')
        perms = form.cleaned_data.get('permissions')

        # 使用事务，确保要么全成功，要么全失败
        try:
            with transaction.atomic():
                model_class = content_type.model_class()
                if not model_class:
                    raise ValidationError(f"无法获取内容类型 {content_type} 对应的模型类。")
                
                target_obj = model_class.objects.get(pk=object_pk)

                # 为每个权限创建一个 GroupObjectPermission 记录
                for perm in perms:
                    assign_perm(perm, group, target_obj)

        except ObjectDoesNotExist:
            raise ValidationError(f"对象不存在 (ID: {object_pk})。")
        except Exception as e:
            raise ValidationError(f"授权失败: {str(e)}")

    def log_addition(self, request, obj, message):
        """重写日志记录，避免访问 obj.__str__() 时出错"""
        # 说明：
        # 1. 我们没有保存传入的 obj 对象（没有调用 super().save_model() 或 obj.save()）
        # 2. 而是通过 assign_perm 批量创建了多个 GroupObjectPermission 记录
        # 3. 由于 obj 没有被保存，它的属性可能不完整（比如 object_pk 可能还是空字符串）
        # 4. Django admin 的 log_addition 会访问 obj.__str__()，如果属性不完整可能会出错
        # 5. 所以我们跳过这个未保存对象的日志记录
        # 注意：实际的权限记录已经通过 assign_perm 创建并保存了，新增功能是成功的
        pass

    def response_add(self, request, obj, post_url_continue=None):
        from django.shortcuts import redirect
        from django.urls import reverse
        return redirect(reverse('admin:guardian_groupobjectpermission_changelist'))

    def permission_name(self, obj):
        return f"{obj.permission.name} ({obj.permission.codename})"

    permission_name.short_description = '权限名称'

    def object_name(self, obj):
        try:
            return str(obj.content_object)
        except:
            return "-"

    object_name.short_description = '对象名称'

    def get_object_link(self, obj):
        try:
            model_class = obj.content_type.model_class()
            if model_class:
                # 尝试构建编辑链接
                app_label = obj.content_type.app_label
                model_name = obj.content_type.model
                admin_url = reverse(f'admin:{app_label}_{model_name}_change', args=[obj.object_pk])
                return format_html('<a href="{}" target="_blank">查看对象</a>', admin_url)
        except Exception:
            pass
        return format_html('<span style="color:#999;">{}: {}</span>', obj.content_type, obj.object_pk)

    get_object_link.short_description = "关联对象"

    def has_change_permission(self, request, obj=None):
        return False
