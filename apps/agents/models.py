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

    host = models.OneToOneField(Host, on_delete=models.CASCADE, related_name='agent', verbose_name="关联主机")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending', verbose_name="状态")
    version = models.CharField(max_length=50, blank=True, verbose_name="Agent版本")
    endpoint = models.CharField(max_length=255, blank=True, verbose_name="接入点/上报地址")
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
        return f"Agent({self.host_id})-{self.get_status_display()}"

    @property
    def business_system(self):
        """通过关联 Host 获取业务系统"""
        return self.host.business_system if self.host else None

    @property
    def environment(self):
        """通过关联 Host 获取环境"""
        return self.host.environment if self.host else None


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

    INSTALL_MODE_CHOICES = [
        ('direct', '直连模式'),
        ('agent-server', 'Agent-Server 模式'),
    ]

    host = models.ForeignKey(Host, on_delete=models.CASCADE, related_name='agent_install_records', verbose_name="主机")
    agent = models.ForeignKey(Agent, on_delete=models.SET_NULL, null=True, blank=True, related_name='install_record', verbose_name="Agent")
    install_mode = models.CharField(max_length=20, choices=INSTALL_MODE_CHOICES, default='agent-server', verbose_name="安装模式")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending', verbose_name="状态")
    agent_version = models.CharField(max_length=50, blank=True, verbose_name="Agent版本")
    agent_server_url = models.CharField(max_length=255, blank=True, verbose_name="Agent-Server地址")
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

    host = models.ForeignKey(Host, on_delete=models.CASCADE, related_name='agent_uninstall_records', verbose_name="主机")
    agent = models.ForeignKey(Agent, on_delete=models.SET_NULL, null=True, blank=True, related_name='uninstall_record', verbose_name="Agent")
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


def agent_package_upload_path(instance, filename):
    """生成安装包文件上传路径"""
    # 路径格式: agent_packages/{version}/{os_type}/{arch}/{filename}
    return f'agent_packages/{instance.version}/{instance.os_type}/{instance.arch}/{filename}'


class AgentPackage(models.Model):
    """Agent 安装包"""

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

    version = models.CharField(max_length=50, verbose_name="版本号", help_text="例如: 1.0.0, v1.0.0")
    description = models.TextField(blank=True, verbose_name="版本描述")
    os_type = models.CharField(max_length=20, choices=OS_TYPE_CHOICES, verbose_name="操作系统")
    arch = models.CharField(max_length=20, choices=ARCH_CHOICES, verbose_name="架构")
    file = models.FileField(upload_to=agent_package_upload_path, verbose_name="文件")
    file_size = models.BigIntegerField(verbose_name="文件大小（字节）")
    md5_hash = models.CharField(max_length=32, blank=True, verbose_name="MD5哈希值")
    sha256_hash = models.CharField(max_length=64, blank=True, verbose_name="SHA256哈希值")
    download_url = models.URLField(blank=True, verbose_name="下载地址", help_text="如果使用对象存储，可以设置公开URL")
    is_default = models.BooleanField(default=False, verbose_name="是否默认版本", help_text="该版本+操作系统+架构组合是否为默认")
    is_active = models.BooleanField(default=True, verbose_name="是否启用")
    created_by = models.ForeignKey(User, on_delete=models.PROTECT, verbose_name="创建人")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="创建时间")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="更新时间")

    class Meta:
        verbose_name = "Agent 安装包"
        verbose_name_plural = "Agent 安装包"
        unique_together = [['version', 'os_type', 'arch']]
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['version', 'os_type', 'arch']),
            models.Index(fields=['is_default', 'is_active']),
            models.Index(fields=['version']),
        ]

    def __str__(self):
        return f"Agent {self.version} - {self.get_os_type_display()} - {self.get_arch_display()}"

    def get_download_url(self):
        """获取下载地址"""
        if self.download_url:
            return self.download_url
        # 如果使用本地存储，返回文件URL
        if self.file:
            return self.file.url
        return ''

    def save(self, *args, **kwargs):
        # 如果设置为默认版本，取消同版本其他组合的默认状态
        if self.is_default:
            AgentPackage.objects.filter(
                version=self.version,
                is_default=True
            ).exclude(pk=self.pk).update(is_default=False)
        super().save(*args, **kwargs)
