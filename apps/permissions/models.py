"""
权限管理模型 - 基于 Django 内置权限 + Guardian 对象权限
"""
import json
from django.db import models
from django.contrib.auth.models import User, Group, Permission
from django.contrib.contenttypes.models import ContentType
from guardian.models import Permission as ObjectPermission
from guardian.models import UserObjectPermission, GroupObjectPermission


class AuditLog(models.Model):
    """审计日志模型"""
    
    # 操作类型选择
    ACTION_CHOICES = [
        # 认证相关
        ('login', '登录'),

        # 基础操作
        ('create', '创建'),
        ('update', '更新'),
        ('delete', '删除'),
        ('execute', '执行'),
        
        # 脚本和文件操作
        ('execute_script', '执行脚本'),
        ('transfer_file', '传输文件'),
        
        # 作业相关
        ('create_job', '创建作业'),
        ('execute_job', '执行作业'),
        ('cancel_job', '取消作业'),
        
        # 定时作业
        ('create_scheduled_job', '创建定时作业'),
        ('update_scheduled_job', '更新定时作业'),
        ('delete_scheduled_job', '删除定时作业'),
        ('enable_scheduled_job', '启用定时作业'),
        ('disable_scheduled_job', '停用定时作业'),
        
        # 主机管理
        ('manage_host', '管理主机'),
        ('test_connection', '测试连接'),
        
        # 模板管理
        ('manage_template', '管理模板'),
        ('create_template', '创建模板'),
        ('update_template', '更新模板'),
        ('delete_template', '删除模板'),
        
        # 系统管理
        ('system_config', '系统配置'),
        ('user_management', '用户管理'),
        ('collect_system_info', '收集系统信息'),
        ('sync_cloud_hosts', '同步云主机'),
    ]
    
    # 基本信息
    user = models.ForeignKey(
        User, 
        on_delete=models.CASCADE, 
        verbose_name="操作用户",
        related_name='audit_logs'
    )
    action = models.CharField(
        max_length=50, 
        choices=ACTION_CHOICES, 
        verbose_name="操作类型"
    )
    description = models.TextField(verbose_name="操作描述")
    
    # 资源信息（可选）
    resource_type = models.ForeignKey(
        ContentType, 
        on_delete=models.CASCADE, 
        null=True, 
        blank=True, 
        verbose_name="资源类型"
    )
    resource_id = models.PositiveIntegerField(
        null=True, 
        blank=True, 
        verbose_name="资源ID"
    )
    resource_name = models.CharField(
        max_length=255, 
        blank=True, 
        verbose_name="资源名称"
    )
    
    # 请求信息
    ip_address = models.GenericIPAddressField(verbose_name="IP地址")
    user_agent = models.TextField(blank=True, verbose_name="用户代理")
    
    # 操作结果
    success = models.BooleanField(default=True, verbose_name="操作是否成功")
    error_message = models.TextField(blank=True, verbose_name="错误信息")
    
    # 额外数据（JSON格式）
    extra_data = models.JSONField(default=dict, blank=True, verbose_name="额外数据")
    
    # 时间戳
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="创建时间")
    
    class Meta:
        verbose_name = "审计日志"
        verbose_name_plural = "审计日志"
        db_table = 'permissions_audit_log'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', 'action']),
            models.Index(fields=['action', 'created_at']),
            models.Index(fields=['resource_type', 'resource_id']),
            models.Index(fields=['ip_address', 'created_at']),
            models.Index(fields=['success', 'created_at']),
        ]
    
    def __str__(self):
        return f"{self.user.username} - {self.get_action_display()} - {self.created_at}"
    
    def get_extra_data_display(self):
        """获取额外数据的可读显示"""
        if not self.extra_data:
            return ""
        
        try:
            # 尝试格式化显示
            if isinstance(self.extra_data, dict):
                items = []
                for key, value in self.extra_data.items():
                    if isinstance(value, list):
                        items.append(f"{key}: {', '.join(map(str, value))}")
                    else:
                        items.append(f"{key}: {value}")
                return "; ".join(items)
            return str(self.extra_data)
        except:
            return str(self.extra_data)
    
    def get_resource_info(self):
        """获取资源信息"""
        if self.resource_type and self.resource_id:
            try:
                model_class = self.resource_type.model_class()
                if model_class:
                    obj = model_class.objects.get(id=self.resource_id)
                    return obj
            except:
                pass
        return None
    
    @classmethod
    def get_user_actions(cls, user, days=30):
        """获取用户最近的操作统计"""
        from django.utils import timezone
        from datetime import timedelta
        
        start_date = timezone.now() - timedelta(days=days)
        return cls.objects.filter(
            user=user,
            created_at__gte=start_date
        ).values('action').annotate(
            count=models.Count('id')
        ).order_by('-count')
    
    @classmethod
    def get_system_stats(cls, days=30):
        """获取系统操作统计"""
        from django.utils import timezone
        from datetime import timedelta
        
        start_date = timezone.now() - timedelta(days=days)
        return cls.objects.filter(
            created_at__gte=start_date
        ).aggregate(
            total_actions=models.Count('id'),
            successful_actions=models.Count('id', filter=models.Q(success=True)),
            failed_actions=models.Count('id', filter=models.Q(success=False)),
            unique_users=models.Count('user', distinct=True)
        )


class PermissionTemplate(models.Model):
    """权限模板 - 预定义的权限组合"""
    
    name = models.CharField(max_length=100, verbose_name="模板名称", unique=True)
    description = models.TextField(blank=True, verbose_name="模板描述")
    
    # 模型权限
    model_permissions = models.ManyToManyField(
        Permission,
        blank=True,
        verbose_name="模型权限",
        help_text="选择要包含的模型权限"
    )
    
    # 是否启用
    is_active = models.BooleanField(default=True, verbose_name="是否启用")
    
    # 创建和更新时间
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="创建时间")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="更新时间")
    
    class Meta:
        verbose_name = "权限模板"
        verbose_name_plural = "权限模板"
        db_table = 'permissions_permission_template'
        ordering = ['name']
    
    def __str__(self):
        return self.name
    
    def get_permissions_display(self):
        """获取权限的可读显示"""
        perms = []
        for perm in self.model_permissions.all():
            perms.append(f"{perm.content_type.app_label}.{perm.codename}")
        return ", ".join(perms) if perms else "无"
    
    def apply_to_user(self, user):
        """将模板权限应用到用户"""
        user.user_permissions.add(*self.model_permissions.all())
        return True
    
    def apply_to_group(self, group):
        """将模板权限应用到组"""
        group.permissions.add(*self.model_permissions.all())
        return True
