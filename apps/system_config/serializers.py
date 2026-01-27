"""
系统配置 & 凭证 序列化器
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
            raise serializers.ValidationError("配置键必须包含分类前缀，如: task.cleanup_days")
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

    cleanup_days = serializers.IntegerField(
        min_value=1, max_value=365,
        help_text="任务日志保留天数"
    )
    # Fabric执行配置
    fabric_max_concurrent_hosts = serializers.IntegerField(
        min_value=1, max_value=100,
        required=False,
        help_text="单个任务最大并发主机数"
    )
    fabric_connection_timeout = serializers.IntegerField(
        min_value=5, max_value=300,
        required=False,
        help_text="SSH连接超时时间（秒）"
    )
    fabric_command_timeout = serializers.IntegerField(
        min_value=30, max_value=3600,
        required=False,
        help_text="命令执行超时时间（秒）"
    )
    fabric_enable_connection_pool = serializers.BooleanField(
        required=False,
        help_text="是否启用SSH连接池"
    )


class NotificationConfigSerializer(serializers.Serializer):
    """通知配置序列化器"""

    # 钉钉配置
    dingtalk_enabled = serializers.BooleanField(help_text="是否启用钉钉通知")
    dingtalk_webhook = serializers.URLField(help_text="钉钉Webhook地址", required=False, allow_blank=True)
    dingtalk_keyword = serializers.CharField(help_text="钉钉关键词", required=False, allow_blank=True)
    
    # 飞书配置
    feishu_enabled = serializers.BooleanField(help_text="是否启用飞书通知")
    feishu_webhook = serializers.URLField(help_text="飞书Webhook地址", required=False, allow_blank=True)
    feishu_keyword = serializers.CharField(help_text="飞书关键词", required=False, allow_blank=True)
    
    # 企业微信配置
    wechatwork_enabled = serializers.BooleanField(help_text="是否启用企业微信通知")
    wechatwork_webhook = serializers.URLField(help_text="企业微信Webhook地址", required=False, allow_blank=True)
    wechatwork_keyword = serializers.CharField(help_text="企业微信关键词", required=False, allow_blank=True)
    
    # 通知级别
    levels = serializers.ListField(
        child=serializers.ChoiceField(choices=['info', 'warning', 'error', 'critical']),
        help_text="通知级别"
    )


class AgentConfigSerializer(serializers.Serializer):
    """Agent配置序列化器"""

    offline_threshold_seconds = serializers.IntegerField(
        min_value=60, max_value=3600,
        help_text="Agent离线判定阈值（秒）"
    )
    offline_threshold_by_env = serializers.DictField(
        child=serializers.IntegerField(min_value=60, max_value=3600),
        required=False,
        help_text="按环境的Agent离线阈值映射"
    )
