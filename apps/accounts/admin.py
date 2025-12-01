"""
用户管理Admin配置
"""
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.models import User
from guardian.admin import GuardedModelAdmin
from .models import UserProfile


class UserProfileInline(admin.StackedInline):
    """用户资料内联"""
    model = UserProfile
    can_delete = False
    verbose_name_plural = '用户资料'
    fields = ['phone', 'department', 'position']


class UserAdmin(BaseUserAdmin, GuardedModelAdmin):
    """用户管理"""
    inlines = [UserProfileInline]
    list_display = ['username', 'email', 'first_name', 'last_name', 'is_staff', 'is_active', 'date_joined']
    list_filter = ['is_staff', 'is_superuser', 'is_active', 'groups', 'date_joined']
    search_fields = ['username', 'first_name', 'last_name', 'email']
    ordering = ['username']
    
    fieldsets = (
        (None, {'fields': ('username', 'password')}),
        ('个人信息', {'fields': ('first_name', 'last_name', 'email')}),
        ('权限', {
            'fields': ('is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions'),
        }),
        ('重要日期', {'fields': ('last_login', 'date_joined')}),
    )
    
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('username', 'password1', 'password2'),
        }),
    )


@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    """用户资料管理"""
    list_display = ['user', 'phone', 'department', 'position', 'created_at', 'updated_at']
    list_filter = ['department', 'created_at']
    search_fields = ['user__username', 'user__email', 'phone', 'department']
    readonly_fields = ['created_at', 'updated_at']
    
    fieldsets = (
        ('用户信息', {
            'fields': ('user',)
        }),
        ('基本信息', {
            'fields': ('phone', 'department', 'position')
        }),
        ('时间信息', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        })
    )


# 重新注册User模型，添加我们的自定义配置
admin.site.unregister(User)
admin.site.register(User, UserAdmin)
