"""
权限管理序列化器 - 基于 Django 内置权限 + Guardian 对象权限
"""
from rest_framework import serializers
from django.contrib.auth.models import User, Group, Permission
from django.contrib.contenttypes.models import ContentType
from guardian.models import UserObjectPermission, GroupObjectPermission
from .models import (
    AuditLog, PermissionTemplate
)


class AuditLogSerializer(serializers.ModelSerializer):
    """审计日志序列化器"""

    user_name = serializers.CharField(source='user.username', read_only=True)
    user_full_name = serializers.SerializerMethodField()
    resource_type_name = serializers.CharField(source='resource_type.name', read_only=True)
    action_display = serializers.CharField(source='get_action_display', read_only=True)

    class Meta:
        model = AuditLog
        fields = [
            'id', 'user', 'user_name', 'user_full_name', 'action', 'action_display',
            'resource_type', 'resource_type_name', 'resource_id', 'resource_name',
            'description', 'ip_address', 'user_agent', 'success', 'error_message',
            'extra_data', 'created_at'
        ]
        read_only_fields = ['id', 'created_at']

    def get_user_full_name(self, obj):
        """获取用户全名"""
        if obj.user.first_name or obj.user.last_name:
            return f"{obj.user.first_name} {obj.user.last_name}".strip()
        return obj.user.username


class PermissionTemplateSerializer(serializers.ModelSerializer):
    """权限模板序列化器"""
    
    permissions_display = serializers.SerializerMethodField()
    permission_count = serializers.SerializerMethodField()
    
    class Meta:
        model = PermissionTemplate
        fields = [
            'id', 'name', 'description', 'model_permissions', 
            'permissions_display', 'permission_count', 'is_active',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['created_at', 'updated_at']
    
    def get_permissions_display(self, obj):
        """获取权限的可读显示"""
        return obj.get_permissions_display()
    
    def get_permission_count(self, obj):
        """获取权限数量"""
        return obj.model_permissions.count()


class UserPermissionSummarySerializer(serializers.Serializer):
    """用户权限摘要序列化器"""
    
    user_id = serializers.IntegerField()
    username = serializers.CharField()
    is_superuser = serializers.BooleanField()
    is_staff = serializers.BooleanField()
    groups = serializers.ListField(child=serializers.CharField())
    model_permissions = serializers.DictField(
        child=serializers.ListField(child=serializers.CharField()),
        help_text='模型级权限，key为应用名.模型名，value为权限列表'
    )
    object_permissions = serializers.DictField(
        child=serializers.DictField(
            child=serializers.ListField(child=serializers.CharField())
        ),
        help_text='对象级权限，key为应用名.模型名，value为{对象ID: 权限列表}'
    )
    permission_count = serializers.IntegerField(help_text='总权限数量')


# ==================== 权限检查序列化器 ====================

class PermissionCheckSerializer(serializers.Serializer):
    """权限检查序列化器"""
    
    resource_type = serializers.CharField(help_text='资源类型，如 host, job, script')
    resource_id = serializers.IntegerField(required=False, help_text='具体资源ID，可选')
    permissions = serializers.ListField(
        child=serializers.CharField(),
        default=['view', 'change', 'delete'],
        help_text='要检查的权限列表'
    )


class PermissionResultSerializer(serializers.Serializer):
    """权限检查结果序列化器"""
    
    user_id = serializers.IntegerField()
    username = serializers.CharField()
    resource_type = serializers.CharField()
    resource_id = serializers.IntegerField(allow_null=True)
    permissions = serializers.DictField(
        child=serializers.BooleanField(),
        help_text='权限检查结果，key为权限名，value为是否有权限'
    )


class ResourcePermissionResultSerializer(serializers.Serializer):
    """资源权限检查结果序列化器"""
    
    user_id = serializers.IntegerField()
    username = serializers.CharField()
    resource_type = serializers.CharField()
    permissions = serializers.DictField(
        help_text='权限检查结果，key为资源ID，value为权限字典'
    )
    level = serializers.CharField(help_text='权限级别：model 或 object')


class BatchPermissionCheckSerializer(serializers.Serializer):
    """批量权限检查序列化器"""
    
    permissions = serializers.ListField(
        child=serializers.CharField(),
        help_text='要检查的权限列表'
    )


class BatchPermissionResultSerializer(serializers.Serializer):
    """批量权限检查结果序列化器"""
    
    user_id = serializers.IntegerField()
    username = serializers.CharField()
    permissions = serializers.DictField(
        child=serializers.BooleanField(),
        help_text='权限检查结果，key为权限名，value为是否有权限'
    )
