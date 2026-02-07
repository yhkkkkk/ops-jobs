"""
系统配置模型
"""
from django.db import models
from django.contrib.auth import get_user_model

User = get_user_model()


class SystemConfig(models.Model):
    """系统配置模型"""
    
    CATEGORY_CHOICES = [
        ('task', '任务执行配置'),
        ('notification', '通知配置'),
        ('cloud', '云厂商配置'),
        ('security', '安全配置'),
        ('system', '系统配置'),
    ]
    
    key = models.CharField(max_length=100, unique=True, verbose_name='配置键')
    value = models.JSONField(verbose_name='配置值')
    description = models.TextField(blank=True, verbose_name='配置描述')
    category = models.CharField(
        max_length=50, 
        choices=CATEGORY_CHOICES,
        default='system',
        verbose_name='配置分类'
    )
    is_active = models.BooleanField(default=True, verbose_name='是否启用')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='更新时间')
    updated_by = models.ForeignKey(
        User, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        verbose_name='更新人'
    )
    
    class Meta:
        db_table = 'system_config'
        verbose_name = '系统配置'
        verbose_name_plural = '系统配置'
        ordering = ['category', 'key']
    
    def __str__(self):
        return f"{self.get_category_display()}: {self.key}"
    
    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)


class ConfigManager:
    """配置管理器"""

    @classmethod
    def get(cls, key, default=None):
        """获取配置值"""
        try:
            config = SystemConfig.objects.get(key=key, is_active=True)
            return config.value
        except SystemConfig.DoesNotExist:
            return default
    
    @classmethod
    def set(cls, key, value, category='system', description='', user=None):
        """设置配置值"""
        config, created = SystemConfig.objects.get_or_create(
            key=key,
            defaults={
                'value': value,
                'category': category,
                'description': description,
                'updated_by': user
            }
        )
        
        if not created:
            config.value = value
            config.description = description
            config.updated_by = user
            config.save()

        return config
    
    @classmethod
    def get_all(cls):
        """获取所有配置"""
        configs = {}
        for config in SystemConfig.objects.filter(is_active=True):
            configs[config.key] = config.value
        return configs
    
    @classmethod
    def get_by_category(cls, category):
        """按分类获取配置"""
        configs = {}
        for config in SystemConfig.objects.filter(category=category, is_active=True):
            configs[config.key] = config.value
        return configs


# 默认配置初始化
def init_default_configs():
    """初始化默认配置"""
    default_configs = [
        # 任务执行配置
        {
            'key': 'task.cleanup_days',
            'value': 30,
            'category': 'task',
            'description': '任务日志保留天数'
        },
        
        # Fabric执行配置
        {
            'key': 'fabric.max_concurrent_hosts',
            'value': 20,
            'category': 'task',
            'description': '单个任务最大并发主机数（适用于并行执行模式）'
        },
        {
            'key': 'fabric.connection_timeout',
            'value': 30,
            'category': 'task',
            'description': 'SSH连接超时时间（秒）'
        },
        {
            'key': 'fabric.command_timeout',
            'value': 300,
            'category': 'task',
            'description': '命令执行超时时间（秒）'
        },
        {
            'key': 'fabric.enable_connection_pool',
            'value': True,
            'category': 'task',
            'description': '是否启用SSH连接池（减少连接开销）'
        },
        
        {
            'key': 'notification.dingtalk_enabled',
            'value': False,
            'category': 'notification',
            'description': '是否启用钉钉通知'
        },
        {
            'key': 'notification.dingtalk_webhook',
            'value': '',
            'category': 'notification',
            'description': '钉钉机器人Webhook地址'
        },
        {
            'key': 'notification.dingtalk_keyword',
            'value': '',
            'category': 'notification',
            'description': '钉钉机器人关键词（可选）'
        },
        {
            'key': 'notification.feishu_enabled',
            'value': False,
            'category': 'notification',
            'description': '是否启用飞书通知'
        },
        {
            'key': 'notification.feishu_webhook',
            'value': '',
            'category': 'notification',
            'description': '飞书机器人Webhook地址'
        },
        {
            'key': 'notification.feishu_keyword',
            'value': '',
            'category': 'notification',
            'description': '飞书机器人关键词（可选）'
        },
        {
            'key': 'notification.wechatwork_enabled',
            'value': False,
            'category': 'notification',
            'description': '是否启用企业微信通知'
        },
        {
            'key': 'notification.wechatwork_webhook',
            'value': '',
            'category': 'notification',
            'description': '企业微信机器人Webhook地址'
        },
        {
            'key': 'notification.wechatwork_keyword',
            'value': '',
            'category': 'notification',
            'description': '企业微信机器人关键词（可选）'
        },
        {
            'key': 'notification.levels',
            'value': ['error', 'warning'],
            'category': 'notification',
            'description': '通知级别'
        },
        # agent 离线判定配置
        {
            'key': 'agent.offline_threshold_seconds',
            'value': 600,
            'category': 'system',
            'description': 'agent 离线判定阈值（秒），默认 600'
        },
        {
            'key': 'agent.offline_threshold_by_env',
            'value': {},
            'category': 'system',
            'description': '按环境的 agent 离线阈值映射，例如 {\"prod\": 300, \"test\": 900}'
        },
        # 云厂商配置示例
        {
            'key': 'cloud.aliyun.access_key',
            'value': '',
            'category': 'cloud',
            'description': '阿里云AccessKey ID'
        },
        {
            'key': 'cloud.aliyun.secret_key',
            'value': '',
            'category': 'cloud',
            'description': '阿里云AccessKey Secret（加密存储）'
        },
        {
            'key': 'cloud.aliyun.region',
            'value': 'cn-hangzhou',
            'category': 'cloud',
            'description': '阿里云默认地域'
        },
        {
            'key': 'cloud.tencent.secret_id',
            'value': '',
            'category': 'cloud',
            'description': '腾讯云SecretId'
        },
        {
            'key': 'cloud.tencent.secret_key',
            'value': '',
            'category': 'cloud',
            'description': '腾讯云SecretKey（加密存储）'
        },
        {
            'key': 'cloud.tencent.region',
            'value': 'ap-guangzhou',
            'category': 'cloud',
            'description': '腾讯云默认地域'
        },
        {
            'key': 'cloud.aws.access_key',
            'value': '',
            'category': 'cloud',
            'description': 'AWS Access Key ID'
        },
        {
            'key': 'cloud.aws.secret_key',
            'value': '',
            'category': 'cloud',
            'description': 'AWS Secret Access Key（加密存储）'
        },
        {
            'key': 'cloud.aws.region',
            'value': 'us-east-1',
            'category': 'cloud',
            'description': 'AWS默认地域'
        },
        # 对象存储配置
        {
            'key': 'storage.type',
            'value': 'local',
            'category': 'cloud',
            'description': '存储类型：local(本地), oss(阿里云OSS), s3(AWS S3), cos(腾讯云COS)'
        },
        {
            'key': 'storage.oss.endpoint',
            'value': '',
            'category': 'cloud',
            'description': '阿里云OSS Endpoint'
        },
        {
            'key': 'storage.oss.bucket',
            'value': '',
            'category': 'cloud',
            'description': '阿里云OSS Bucket名称'
        },
        {
            'key': 'storage.oss.access_key_id',
            'value': '',
            'category': 'cloud',
            'description': '阿里云OSS AccessKey ID'
        },
        {
            'key': 'storage.oss.access_key_secret',
            'value': '',
            'category': 'cloud',
            'description': '阿里云OSS AccessKey Secret（加密存储）'
        },
        {
            'key': 'storage.s3.endpoint',
            'value': '',
            'category': 'cloud',
            'description': 'AWS S3 Endpoint（可选，默认使用AWS标准端点）'
        },
        {
            'key': 'storage.s3.bucket',
            'value': '',
            'category': 'cloud',
            'description': 'AWS S3 Bucket名称'
        },
        {
            'key': 'storage.s3.region',
            'value': 'us-east-1',
            'category': 'cloud',
            'description': 'AWS S3 地域'
        },
        {
            'key': 'storage.cos.region',
            'value': 'ap-guangzhou',
            'category': 'cloud',
            'description': '腾讯云COS 地域'
        },
        {
            'key': 'storage.cos.bucket',
            'value': '',
            'category': 'cloud',
            'description': '腾讯云COS Bucket名称'
        },
        {
            'key': 'storage.cos.secret_id',
            'value': '',
            'category': 'cloud',
            'description': '腾讯云COS SecretId'
        },
        {
            'key': 'storage.cos.secret_key',
            'value': '',
            'category': 'cloud',
            'description': '腾讯云COS SecretKey（加密存储）'
        },
        {
            'key': 'storage.minio.endpoint',
            'value': '',
            'category': 'cloud',
            'description': 'MinIO服务端点（如: minio.example.com:9000）'
        },
        {
            'key': 'storage.minio.bucket',
            'value': '',
            'category': 'cloud',
            'description': 'MinIO Bucket名称'
        },
        {
            'key': 'storage.minio.access_key',
            'value': '',
            'category': 'cloud',
            'description': 'MinIO Access Key'
        },
        {
            'key': 'storage.minio.secret_key',
            'value': '',
            'category': 'cloud',
            'description': 'MinIO Secret Key（加密存储）'
        },
        {
            'key': 'storage.minio.secure',
            'value': True,
            'category': 'cloud',
            'description': 'MinIO是否使用HTTPS'
        },
        {
            'key': 'storage.rustfs.endpoint',
            'value': '',
            'category': 'cloud',
            'description': 'RustFS服务端点（如: http://rustfs.example.com:9000）'
        },
        {
            'key': 'storage.rustfs.bucket',
            'value': '',
            'category': 'cloud',
            'description': 'RustFS Bucket名称'
        },
        {
            'key': 'storage.rustfs.access_key',
            'value': '',
            'category': 'cloud',
            'description': 'RustFS Access Key'
        },
        {
            'key': 'storage.rustfs.secret_key',
            'value': '',
            'category': 'cloud',
            'description': 'RustFS Secret Key（加密存储）'
        },
        {
            'key': 'storage.rustfs.region',
            'value': 'us-east-1',
            'category': 'cloud',
            'description': 'RustFS区域（兼容S3协议，默认us-east-1）'
        },
    ]

    for config_data in default_configs:
        SystemConfig.objects.get_or_create(
            key=config_data['key'],
            defaults=config_data
        )
