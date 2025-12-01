"""
系统配置序列化器
"""
from rest_framework import serializers
from .models import SystemConfig


class SystemConfigSerializer(serializers.ModelSerializer):
    """系统配置序列化器"""
    
    category_display = serializers.CharField(source='get_category_display', read_only=True)
    updated_by_name = serializers.CharField(source='updated_by.username', read_only=True)
    
    class Meta:
        model = SystemConfig
        fields = [
            'id', 'key', 'value', 'description', 'category', 'category_display',
            'is_active', 'created_at', 'updated_at', 'updated_by_name'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at', 'updated_by_name']
    
    def validate_key(self, value):
        """验证配置键格式"""
        if not value or '.' not in value:
            raise serializers.ValidationError("配置键必须包含分类前缀，如: task.max_concurrent_jobs")
        return value


class SystemConfigUpdateSerializer(serializers.ModelSerializer):
    """系统配置更新序列化器"""
    
    class Meta:
        model = SystemConfig
        fields = ['value', 'description', 'is_active']


class SystemConfigBatchUpdateSerializer(serializers.Serializer):
    """批量更新配置序列化器"""
    
    configs = serializers.ListField(
        child=serializers.DictField(),
        help_text="配置列表，格式: [{'key': 'task.timeout', 'value': 3600}, ...]"
    )
    
    def validate_configs(self, value):
        """验证配置数据"""
        if not value:
            raise serializers.ValidationError("配置列表不能为空")
        
        for config in value:
            if 'key' not in config or 'value' not in config:
                raise serializers.ValidationError("每个配置必须包含key和value字段")
        
        return value


class SystemConfigCategorySerializer(serializers.Serializer):
    """按分类获取配置的序列化器"""
    
    category = serializers.CharField(help_text="配置分类")
    configs = serializers.DictField(help_text="该分类下的所有配置")


class TaskConfigSerializer(serializers.Serializer):
    """任务配置序列化器"""
    
    max_concurrent_jobs = serializers.IntegerField(
        min_value=1, max_value=100,
        help_text="最大并发任务数"
    )
    job_timeout = serializers.IntegerField(
        min_value=60, max_value=86400,
        help_text="任务超时时间（秒）"
    )
    retry_attempts = serializers.IntegerField(
        min_value=0, max_value=10,
        help_text="任务失败重试次数"
    )
    cleanup_days = serializers.IntegerField(
        min_value=1, max_value=365,
        help_text="任务日志保留天数"
    )


class NotificationConfigSerializer(serializers.Serializer):
    """通知配置序列化器"""
    
    email_enabled = serializers.BooleanField(help_text="是否启用邮件通知")
    webhook_enabled = serializers.BooleanField(help_text="是否启用Webhook通知")
    levels = serializers.ListField(
        child=serializers.ChoiceField(choices=['info', 'warning', 'error', 'critical']),
        help_text="通知级别"
    )
    email_recipients = serializers.ListField(
        child=serializers.EmailField(),
        required=False,
        help_text="默认邮件接收人列表"
    )
