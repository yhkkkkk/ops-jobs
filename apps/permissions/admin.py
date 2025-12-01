"""
权限管理后台配置
"""
from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from django.utils.safestring import mark_safe
from .models import AuditLog


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
