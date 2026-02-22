from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone

from apps.hosts.models import Host


class Agent(models.Model):
    """Agent 信息"""

    STATUS_CHOICES = [
        ('pending', '待激活'),
        ('online', '在线'),
        ('offline', '离线'),
        ('disabled', '禁用'),
    ]

    AGENT_TYPE_CHOICES = [
        ('agent', 'Agent客户端'),
        ('agent-server', 'Agent-Server'),
    ]

    host = models.OneToOneField(Host, on_delete=models.CASCADE, related_name='agent', verbose_name="关联主机")
    agent_type = models.CharField(max_length=20, choices=AGENT_TYPE_CHOICES, default='agent', verbose_name="Agent类型")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending', verbose_name="状态")
    version = models.CharField(max_length=50, blank=True, verbose_name="Agent版本")
    endpoint = models.CharField(max_length=255, blank=True, verbose_name="接入点/上报地址")
    agent_server = models.ForeignKey(
        'AgentServer',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='agents',
        verbose_name="关联Agent-Server"
    )
    last_heartbeat_at = models.DateTimeField(null=True, blank=True, verbose_name="最后心跳时间")
    last_error_code = models.CharField(max_length=100, blank=True, verbose_name="最近错误码")
    active_token_hash = models.CharField(max_length=128, blank=True, verbose_name="当前token哈希")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="创建时间")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="更新时间")

    class Meta:
        verbose_name = "Agent"
        verbose_name_plural = "Agent"
        permissions = [
            ('issue_agent_token', '签发 Agent Token'),
            ('revoke_agent_token', '吊销 Agent Token'),
            ('enable_agent', '启用 Agent'),
            ('disable_agent', '禁用 Agent'),
        ]
        indexes = [
            models.Index(fields=['status']),
            models.Index(fields=['last_heartbeat_at']),
        ]

    def __str__(self):
        return f"Agent({self.host_id})-{self.get_agent_type_display()}-{self.get_status_display()}"


class AgentToken(models.Model):
    """Agent Token 记录（仅存哈希，不存明文）"""

    agent = models.ForeignKey(Agent, on_delete=models.CASCADE, related_name='tokens', verbose_name="Agent")
    token_hash = models.CharField(max_length=128, verbose_name="Token哈希")
    token_last4 = models.CharField(max_length=8, blank=True, default='', verbose_name="Token末尾标识")
    issued_by = models.ForeignKey(User, on_delete=models.PROTECT, verbose_name="签发人")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="创建时间")
    expired_at = models.DateTimeField(null=True, blank=True, verbose_name="过期时间")
    revoked_at = models.DateTimeField(null=True, blank=True, verbose_name="吊销时间")
    note = models.CharField(max_length=255, blank=True, verbose_name="备注")

    class Meta:
        verbose_name = "Agent Token"
        verbose_name_plural = "Agent Token"
        indexes = [
            models.Index(fields=['token_hash']),
            models.Index(fields=['revoked_at']),
        ]

    def __str__(self):
        return f"Token({self.agent_id})"

    @property
    def is_active(self):
        """是否未吊销且未过期"""
        if self.revoked_at:
            return False
        if self.expired_at and self.expired_at <= timezone.now():
            return False
        return True


class AgentInstallRecord(models.Model):
    """Agent 安装记录"""

    STATUS_CHOICES = [
        ('pending', '安装中'),
        ('success', '成功'),
        ('failed', '失败'),
    ]

    INSTALL_TYPE_CHOICES = [
        ('agent', '安装 Agent'),
        ('agent-server', '安装 Agent-Server'),
    ]

    INSTALL_MODE_CHOICES = [
        ('agent-server', 'Agent-Server 模式'),
    ]

    host = models.ForeignKey(Host, on_delete=models.CASCADE, related_name='agent_install_records', verbose_name="主机")
    agent = models.ForeignKey(Agent, on_delete=models.SET_NULL, null=True, blank=True, related_name='install_record', verbose_name="Agent")
    install_type = models.CharField(max_length=20, choices=INSTALL_TYPE_CHOICES, default='agent', verbose_name="安装类型")
    install_mode = models.CharField(max_length=20, choices=INSTALL_MODE_CHOICES, default='agent-server', verbose_name="安装模式(当前只支持Agent-Server)")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending', verbose_name="状态")
    agent_version = models.CharField(max_length=50, blank=True, verbose_name="Agent版本")
    agent_server_url = models.CharField(max_length=255, blank=True, verbose_name="Agent-Server地址")
    agent_server_backup_url = models.CharField(max_length=255, blank=True, verbose_name="Agent-Server备用地址")
    ws_backoff_initial_ms = models.IntegerField(default=1000, verbose_name="WS初始退避(ms)")
    ws_backoff_max_ms = models.IntegerField(default=30000, verbose_name="WS最大退避(ms)")
    ws_max_retries = models.IntegerField(default=6, verbose_name="WS最大重试次数")
    agent_server_listen_addr = models.CharField(max_length=50, default='0.0.0.0:8080', verbose_name="Agent-Server监听地址")
    max_connections = models.IntegerField(default=1000, verbose_name="最大连接数")
    heartbeat_timeout = models.IntegerField(default=60, verbose_name="心跳超时(秒)")
    # agent-server WebSocket 配置
    ws_handshake_timeout = models.CharField(max_length=20, default='10s', verbose_name="WebSocket握手超时")
    ws_read_buffer_size = models.IntegerField(default=4096, verbose_name="WebSocket读取缓冲区大小")
    ws_write_buffer_size = models.IntegerField(default=4096, verbose_name="WebSocket写入缓冲区大小")
    ws_enable_compression = models.BooleanField(default=True, verbose_name="WebSocket启用压缩")
    ws_allowed_origins = models.JSONField(default=list, verbose_name="WebSocket允许的来源")
    package_id = models.IntegerField(null=True, blank=True, verbose_name="安装包ID")
    package_version = models.CharField(max_length=50, blank=True, verbose_name="安装包版本")
    control_plane_url = models.CharField(max_length=500, blank=True, default='', verbose_name="控制面URL")
    installed_by = models.ForeignKey(User, on_delete=models.PROTECT, verbose_name="安装人")
    installed_at = models.DateTimeField(auto_now_add=True, verbose_name="安装时间")
    message = models.TextField(blank=True, verbose_name="消息")
    error_message = models.TextField(blank=True, verbose_name="错误信息")
    error_detail = models.TextField(blank=True, verbose_name="错误详情")
    install_task_id = models.CharField(max_length=255, blank=True, verbose_name="安装任务ID", help_text="用于SSE进度推送")

    class Meta:
        verbose_name = "Agent 安装记录"
        verbose_name_plural = "Agent 安装记录"
        ordering = ['-installed_at']
        indexes = [
            models.Index(fields=['host', '-installed_at']),
            models.Index(fields=['status']),
        ]

    def __str__(self):
        return f"安装记录({self.host_id})-{self.get_status_display()}"


class AgentUninstallRecord(models.Model):
    """Agent 卸载记录"""

    STATUS_CHOICES = [
        ('pending', '卸载中'),
        ('success', '成功'),
        ('failed', '失败'),
    ]

    UNINSTALL_TYPE_CHOICES = [
        ('agent', 'Agent'),
        ('agent-server', 'Agent-Server'),
    ]

    host = models.ForeignKey(Host, on_delete=models.CASCADE, related_name='agent_uninstall_records', verbose_name="主机")
    agent = models.ForeignKey(Agent, on_delete=models.SET_NULL, null=True, blank=True, related_name='uninstall_record', verbose_name="Agent")
    agent_type = models.CharField(max_length=20, choices=UNINSTALL_TYPE_CHOICES, default='agent', verbose_name="卸载类型")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending', verbose_name="状态")
    uninstalled_by = models.ForeignKey(User, on_delete=models.PROTECT, verbose_name="卸载人")
    uninstalled_at = models.DateTimeField(auto_now_add=True, verbose_name="卸载时间")
    message = models.TextField(blank=True, verbose_name="消息")
    error_message = models.TextField(blank=True, verbose_name="错误信息")
    error_detail = models.TextField(blank=True, verbose_name="错误详情")
    uninstall_task_id = models.CharField(max_length=255, blank=True, verbose_name="卸载任务ID", help_text="用于SSE进度推送")

    class Meta:
        verbose_name = "Agent 卸载记录"
        verbose_name_plural = "Agent 卸载记录"
        ordering = ['-uninstalled_at']
        indexes = [
            models.Index(fields=['host', '-uninstalled_at']),
            models.Index(fields=['status']),
        ]

    def __str__(self):
        return f"卸载记录({self.host_id})-{self.get_status_display()}"


class AgentServer(models.Model):
    """Agent-Server 配置"""

    name = models.CharField(max_length=100, verbose_name="名称")
    base_url = models.CharField(max_length=255, unique=True, verbose_name="基础URL")
    shared_secret = models.CharField(max_length=255, blank=True, verbose_name="HMAC共享密钥")
    require_signature = models.BooleanField(default=False, verbose_name="是否强制签名校验")
    is_active = models.BooleanField(default=True, verbose_name="是否启用")
    description = models.TextField(blank=True, verbose_name="描述")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="创建时间")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="更新时间")

    class Meta:
        verbose_name = "Agent-Server"
        verbose_name_plural = "Agent-Server"
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['base_url']),
            models.Index(fields=['is_active']),
        ]

    def __str__(self):
        return f"Agent-Server({self.name})"


def agent_package_upload_path(instance, filename):
    """生成安装包文件上传路径"""
    # 路径格式: agent_packages/{version}/{os_type}/{arch}/{filename}
    return f'agent_packages/{instance.version}/{instance.os_type}/{instance.arch}/{filename}'


class AgentPackage(models.Model):
    """Agent 安装包"""

    PACKAGE_TYPE_CHOICES = [
        ('agent', 'Agent'),
        ('agent-server', 'Agent-Server'),
    ]

    OS_TYPE_CHOICES = [
        ('linux', 'Linux'),
        ('windows', 'Windows'),
        ('darwin', 'macOS'),
    ]

    ARCH_CHOICES = [
        ('amd64', 'AMD64/x86_64'),
        ('arm64', 'ARM64'),
        ('386', 'i386'),
    ]

    STORAGE_TYPE_CHOICES = [
        ('local', '本地存储'),
        ('oss', '阿里云OSS'),
        ('s3', 'AWS S3'),
        ('cos', '腾讯云COS'),
        ('minio', 'MinIO'),
        ('rustfs', 'RustFS'),
    ]

    package_type = models.CharField(
        max_length=20,
        choices=PACKAGE_TYPE_CHOICES,
        default='agent',
        verbose_name="安装包类型",
        help_text="agent 或 agent-server",
    )
    version = models.CharField(max_length=50, verbose_name="版本号", help_text="例如: 1.0.0, v1.0.0")
    description = models.TextField(blank=True, verbose_name="版本描述")
    os_type = models.CharField(max_length=20, choices=OS_TYPE_CHOICES, verbose_name="操作系统")
    arch = models.CharField(max_length=20, choices=ARCH_CHOICES, verbose_name="架构")
    storage_type = models.CharField(
        max_length=20,
        choices=STORAGE_TYPE_CHOICES,
        default='local',
        verbose_name="存储类型"
    )
    storage_path = models.CharField(
        max_length=500,
        blank=True,
        verbose_name="存储路径",
        help_text="文件在存储中的路径，用于动态生成下载URL"
    )
    file_name = models.CharField(
        max_length=255,
        blank=True,
        verbose_name="文件名",
        help_text="文件的原始名称"
    )
    file_size = models.BigIntegerField(verbose_name="文件大小（字节）")
    md5_hash = models.CharField(max_length=32, blank=True, verbose_name="MD5哈希值")
    sha256_hash = models.CharField(max_length=64, blank=True, verbose_name="SHA256哈希值")
    is_default = models.BooleanField(default=False, verbose_name="是否默认版本", help_text="该版本+操作系统+架构组合是否为默认")
    is_active = models.BooleanField(default=True, verbose_name="是否启用")
    validate_status = models.CharField(
        max_length=20,
        default="pending",
        verbose_name="校验状态",
        help_text="安装包完整性校验状态：pending/running/passed/failed",
    )
    validate_message = models.TextField(
        blank=True,
        verbose_name="校验结果说明",
        help_text="校验失败原因或校验详情",
    )
    created_by = models.ForeignKey(User, on_delete=models.PROTECT, verbose_name="创建人")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="创建时间")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="更新时间")

    class Meta:
        verbose_name = "Agent 安装包"
        verbose_name_plural = "Agent 安装包"
        unique_together = [['package_type', 'version', 'os_type', 'arch']]
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['package_type', 'version', 'os_type', 'arch']),
            models.Index(fields=['package_type', 'is_default', 'is_active']),
            models.Index(fields=['package_type', 'version']),
        ]

    def __str__(self):
        return f"{self.get_package_type_display()} {self.version} - {self.get_os_type_display()} - {self.get_arch_display()}"

    def get_download_url(self, expires_in: int = 3600):
        """
        根据存储类型和路径动态生成下载地址
        Args:
            expires_in: url过期时间（秒），用于私有存储的预签名url
        Returns:
            下载url
        """
        from apps.agents.storage_service import StorageService

        # 如果没有存储路径，返回空
        if not self.storage_path:
            return ''

        # 根据存储类型生成url
        import logging
        logger_instance = logging.getLogger(__name__)
        backend = StorageService.get_backend(self.storage_type)
        if backend is None:
            logger_instance.error(f"无法获取存储后端: {self.storage_type}")
            return ''

        url = backend.generate_url(self.storage_path, expires_in=expires_in)
        return url or ''

    def save(self, *args, **kwargs):
        # 如果设置为默认版本，取消同版本其他组合的默认状态
        if self.is_default:
            AgentPackage.objects.filter(
                package_type=self.package_type,
                os_type=self.os_type,
                arch=self.arch,
                version=self.version,
                is_default=True
            ).exclude(pk=self.pk).update(is_default=False)
        super().save(*args, **kwargs)


class AgentTaskStats(models.Model):
    """Agent 任务执行统计"""

    agent = models.OneToOneField(
        Agent,
        on_delete=models.CASCADE,
        related_name='task_stats',
        primary_key=True,
        verbose_name='关联 Agent'
    )

    total_tasks = models.PositiveIntegerField(default=0, verbose_name='总任务数')
    success_tasks = models.PositiveIntegerField(default=0, verbose_name='成功任务数')
    failed_tasks = models.PositiveIntegerField(default=0, verbose_name='失败任务数')
    cancelled_tasks = models.PositiveIntegerField(default=0, verbose_name='取消任务数')

    avg_duration_ms = models.FloatField(default=0.0, verbose_name='平均执行时长(毫秒)')

    last_updated = models.DateTimeField(auto_now=True, verbose_name='最后更新时间')

    class Meta:
        db_table = 'ops_agent_task_stats'
        verbose_name = 'Agent 任务统计'
        verbose_name_plural = verbose_name
        indexes = [
            models.Index(fields=['last_updated']),
        ]

    def __str__(self):
        return f"AgentTaskStats({self.agent_id})"

    @property
    def success_rate(self) -> float:
        """计算成功率"""
        if self.total_tasks == 0:
            return 0.0
        return round(self.success_tasks / self.total_tasks * 100, 2)

    @property
    def health_status(self) -> str:
        """获取健康状态"""
        if self.total_tasks == 0:
            return 'unknown'
        rate = self.success_rate
        if rate >= 95:
            return 'healthy'
        elif rate >= 80:
            return 'warning'
        else:
            return 'critical'
