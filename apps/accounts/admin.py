"""
用户管理Admin配置
"""
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.models import User
from guardian.admin import GuardedModelAdmin
from django.conf import settings
from .models import UserProfile

# 条件导入 2FA 相关模块
TWO_FACTOR_ENABLED = getattr(settings, 'TWO_FACTOR_ENABLED', False)
if TWO_FACTOR_ENABLED:
    from django_otp.plugins.otp_totp.models import TOTPDevice
    from django_otp.plugins.otp_static.models import StaticDevice
    import qrcode
    from io import BytesIO
    import base64
    from django.utils.html import format_html
    from django.utils.safestring import mark_safe


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

# 注册2FA相关模型到admin
if TWO_FACTOR_ENABLED:
    # 设置模型的中文名称
    TOTPDevice._meta.verbose_name = 'TOTP设备'
    TOTPDevice._meta.verbose_name_plural = 'TOTP设备'
    
    StaticDevice._meta.verbose_name = '静态备份令牌设备'
    StaticDevice._meta.verbose_name_plural = '静态备份令牌设备'
    
    @admin.register(TOTPDevice)
    class TOTPDeviceAdmin(admin.ModelAdmin):
        """TOTP设备管理"""
        list_display = ['user', 'name', 'confirmed', 'step', 't0', 'digits', 'created_at', 'last_used_at']
        list_filter = ['confirmed', 'created_at', 'last_used_at', 'step', 'digits']
        search_fields = ['user__username', 'user__email', 'name']
        readonly_fields = ['key', 'qr_code_display', 'config_url_display', 'secret_display',
                          'step', 't0', 'digits', 'created_at', 'last_used_at']
        raw_id_fields = ['user']
        
        def __init__(self, model, admin_site):
            super().__init__(model, admin_site)
            # 设置字段的中文显示名称
            self.model._meta.get_field('user').verbose_name = '用户'
            self.model._meta.get_field('name').verbose_name = '设备名称'
            self.model._meta.get_field('key').verbose_name = '密钥'
            self.model._meta.get_field('confirmed').verbose_name = '已确认'
            self.model._meta.get_field('created_at').verbose_name = '创建时间'
            self.model._meta.get_field('last_used_at').verbose_name = '最后使用时间'
        
        fieldsets = (
            ('基本信息', {
                'fields': ('user', 'name', 'confirmed')
            }),
            ('参数', {
                'fields': ('step', 't0', 'digits'),
                'description': 'step=时间步长(秒)，t0=初始时间戳，digits=验证码位数'
            }),
            ('二维码信息', {
                'fields': ('qr_code_display', 'config_url_display', 'secret_display'),
                'description': '扫描二维码或手动输入密钥到验证器APP（如Google Authenticator）'
            }),
            ('密钥信息', {
                'fields': ('key',),
                'classes': ('collapse',),
                'description': '密钥的十六进制表示'
            }),
            ('时间信息', {
                'fields': ('created_at', 'last_used_at'),
                'classes': ('collapse',)
            }),
        )
        
        def qr_code_display(self, obj):
            """显示二维码（仅详情页显示，不在列表展示）"""
            if not obj or not obj.user:
                return "请先选择用户并保存"
            
            if not obj.key:
                return "设备尚未生成密钥，请保存后查看"
            
            try:
                # 使用TOTPDevice的config_url方法，它会自动生成正确的url
                config_url = obj.config_url
                
                # 替换issuer
                otp_issuer = getattr(settings, 'OTP_TOTP_ISSUER', 'OPS Job Platform')
                if 'otpauth://totp/' in config_url:
                    parts = config_url.split('?')
                    if len(parts) == 2:
                        url_part = parts[0]
                        params = parts[1]
                        # 替换issuer
                        if ':' in url_part:
                            url_part = url_part.split(':', 1)[1]  # 移除旧的issuer
                        config_url = f'otpauth://totp/{otp_issuer}:{obj.user.username}?{params}'
                
                # 生成QR码
                qr = qrcode.QRCode(
                    version=1,
                    error_correction=qrcode.constants.ERROR_CORRECT_L,
                    box_size=10,
                    border=4,
                )
                qr.add_data(config_url)
                qr.make(fit=True)
                
                img = qr.make_image(fill_color="black", back_color="white")
                buffer = BytesIO()
                img.save(buffer, format='PNG')
                buffer.seek(0)
                
                # 转换为base64
                img_base64 = base64.b64encode(buffer.getvalue()).decode('utf-8')
                
                # 返回HTML格式的二维码
                return format_html(
                    '<div style="text-align: center;">'
                    '<div style="display: inline-block; border: 2px solid #ddd; padding: 10px; background: white;">'
                    '<img src="data:image/png;base64,{}" alt="QR Code" style="max-width: 300px; height: auto;" />'
                    '</div>'
                    '<p style="margin-top: 10px; color: #666; font-size: 12px;">'
                    '使用验证器APP（如Google Authenticator）扫描此二维码'
                    '</p>'
                    '</div>',
                    img_base64
                )
            except Exception as e:
                return f"生成二维码失败: {str(e)}"
        
        qr_code_display.short_description = "二维码"
        qr_code_display.allow_tags = True
        
        def config_url_display(self, obj):
            """显示配置URL"""
            if not obj or not obj.user or not obj.key:
                return "-"
            
            try:
                otp_issuer = getattr(settings, 'OTP_TOTP_ISSUER', 'OPS Job Platform')
                config_url = obj.config_url
                # 替换issuer
                if 'otpauth://totp/' in config_url:
                    parts = config_url.split('?')
                    if len(parts) == 2:
                        url_part = parts[0]
                        params = parts[1]
                        if ':' in url_part:
                            url_part = url_part.split(':', 1)[1]
                        config_url = f'otpauth://totp/{otp_issuer}:{obj.user.username}?{params}'
                
                return format_html(
                    '<input type="text" readonly value="{}" style="width: 100%; font-family: monospace; font-size: 11px;" onclick="this.select();" />',
                    config_url
                )
            except Exception as e:
                return f"生成配置URL失败: {str(e)}"
        
        config_url_display.short_description = "配置URL"
        config_url_display.allow_tags = True
        
        def secret_display(self, obj):
            """显示密钥（用于手动输入）"""
            if not obj or not obj.key:
                return "-"
            
            try:
                # TOTPDevice的key字段已经是base32格式的字符串，直接使用
                secret = obj.key.upper()
                # 每4个字符一组显示，更易读（base32格式）
                formatted_secret = ' '.join([secret[i:i+4] for i in range(0, len(secret), 4)])
                return format_html(
                    '<div style="font-family: monospace; font-size: 14px; letter-spacing: 2px; padding: 10px; background: #f5f5f5; border: 1px solid #ddd; border-radius: 4px;">'
                    '<strong>{}</strong>'
                    '</div>'
                    '<p style="margin-top: 5px; color: #666; font-size: 12px;">'
                    '如果无法扫描二维码，可以手动输入此密钥到验证器APP（Base32格式）'
                    '</p>',
                    formatted_secret
                )
            except Exception as e:
                return f"获取密钥失败: {str(e)}"
        
        secret_display.short_description = "密钥"
        secret_display.allow_tags = True
        
        def save_model(self, request, obj, form, change):
            """保存模型时，确保密钥已生成"""
            # TOTPDevice在保存时会自动生成密钥（如果还没有）
            # 但我们需要确保用户已设置
            super().save_model(request, obj, form, change)


    @admin.register(StaticDevice)
    class StaticDeviceAdmin(admin.ModelAdmin):
        """静态备份令牌设备管理"""
        list_display = ['user', 'name', 'created_at']
        list_filter = ['created_at']
        search_fields = ['user__username', 'user__email', 'name']
        readonly_fields = ['created_at']
        raw_id_fields = ['user']
        
        def __init__(self, model, admin_site):
            super().__init__(model, admin_site)
            # 设置字段的中文显示名称
            self.model._meta.get_field('user').verbose_name = '用户'
            self.model._meta.get_field('name').verbose_name = '设备名称'
            self.model._meta.get_field('created_at').verbose_name = '创建时间'
        
        fieldsets = (
            ('基本信息', {
                'fields': ('user', 'name')
            }),
            ('时间信息', {
                'fields': ('created_at',),
                'classes': ('collapse',)
            }),
        )
        
        def has_add_permission(self, request):
            """禁止在admin中直接添加，应该通过API设置"""
            return False
        
        def has_change_permission(self, request, obj=None):
            """允许编辑已有的静态备份令牌设备"""
            return True
        
        def has_delete_permission(self, request, obj=None):
            """允许删除静态备份令牌设备"""
            return True
