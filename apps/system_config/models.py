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
            'key': 'task.max_concurrent_jobs',
            'value': 10,
            'category': 'task',
            'description': '最大并发任务数'
        },
        {
            'key': 'task.job_timeout',
            'value': 3600,
            'category': 'task',
            'description': '任务超时时间（秒）'
        },
        {
            'key': 'task.retry_attempts',
            'value': 3,
            'category': 'task',
            'description': '任务失败重试次数'
        },
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
            'key': 'notification.email_enabled',
            'value': True,
            'category': 'notification',
            'description': '是否启用邮件通知'
        },
        {
            'key': 'notification.webhook_enabled',
            'value': False,
            'category': 'notification',
            'description': '是否启用Webhook通知'
        },
        {
            'key': 'notification.levels',
            'value': ['error', 'warning'],
            'category': 'notification',
            'description': '通知级别'
        },
        {
            'key': 'notification.email_recipients',
            'value': [],
            'category': 'notification',
            'description': '默认邮件接收人列表'
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
    ]

    for config_data in default_configs:
        SystemConfig.objects.get_or_create(
            key=config_data['key'],
            defaults=config_data
        )
