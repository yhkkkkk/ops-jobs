"""
脚本模板模型
"""
from django.db import models
from django.contrib.auth.models import User


class UserFavorite(models.Model):
    """用户收藏"""

    FAVORITE_TYPE_CHOICES = [
        ('job_template', '作业模板'),
        ('execution_plan', '执行方案'),
        ('script_template', '脚本模板'),
    ]

    # 目前只有个人收藏，后续可扩展其他
    CATEGORY_CHOICES = [
        ('personal', '个人'),
        ('team', '团队'),
        ('common', '常用'),
        ('other', '其他'),
    ]

    # 用户
    user = models.ForeignKey(User, on_delete=models.CASCADE, verbose_name="用户")

    # 收藏类型和对象
    favorite_type = models.CharField(max_length=20, choices=FAVORITE_TYPE_CHOICES, verbose_name="收藏类型")
    object_id = models.IntegerField(verbose_name="对象ID")

    # 分类和备注
    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES, default='personal', verbose_name="分类")
    note = models.CharField(max_length=200, blank=True, verbose_name="备注")

    # 时间
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="收藏时间")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="更新时间")

    class Meta:
        verbose_name = "用户收藏"
        verbose_name_plural = "用户收藏"
        unique_together = ['user', 'favorite_type', 'object_id']
        ordering = ['-updated_at']

    def __str__(self):
        return f"{self.user.username} - {self.favorite_type} - {self.object_id}"


class ScriptTemplate(models.Model):
    """脚本模板"""
    
    SCRIPT_TYPE_CHOICES = [
        ('shell', 'Shell'),
        ('python', 'Python'),
        ('powershell', 'PowerShell'),
        ('perl', 'Perl'),
        ('javascript', 'JavaScript'),
        ('go', 'Go'),
    ]
    
    TEMPLATE_TYPE_CHOICES = [
        ('system', '系统模板'),
        ('user', '用户模板'),
        ('shared', '共享模板'),
    ]

    CATEGORY_CHOICES = [
        ('deployment', '部署'),
        ('monitoring', '监控'),
        ('maintenance', '维护'),
        ('backup', '备份'),
        ('security', '安全'),
        ('other', '其他'),
    ]

    name = models.CharField(max_length=200, verbose_name="模板名称")
    description = models.TextField(blank=True, verbose_name="模板描述")
    script_type = models.CharField(max_length=20, choices=SCRIPT_TYPE_CHOICES, verbose_name="脚本类型")
    template_type = models.CharField(max_length=20, choices=TEMPLATE_TYPE_CHOICES, default='user', verbose_name="模板类型")
    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES, blank=True, verbose_name="分类")
    
    # 脚本内容
    script_content = models.TextField(verbose_name="脚本内容")

    # 版本控制
    version = models.CharField(max_length=50, default='1.0.0', verbose_name="版本号")
    is_active = models.BooleanField(default=True, verbose_name="是否启用")

    # 标签字段
    tags_json = models.JSONField(default=dict, blank=True, verbose_name="标签(JSON)",
                               help_text="键值对格式的标签，如 {'env': 'prod', 'team': 'ops'}")

    # 使用统计
    usage_count = models.IntegerField(default=0, verbose_name="使用次数")

    # 权限控制
    created_by = models.ForeignKey(User, on_delete=models.CASCADE, verbose_name="创建人")
    updated_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='updated_script_templates',
        verbose_name="更新人"
    )
    
    # 时间信息
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="创建时间")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="更新时间")
    
    class Meta:
        verbose_name = "脚本模板"
        verbose_name_plural = "脚本模板"
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['script_type', 'template_type']),
            models.Index(fields=['is_active', 'version']),
        ]
    
    def __str__(self):
        return f"{self.name} ({self.get_script_type_display()})"
    
    @property
    def tag_list(self):
        """获取标签列表"""
        if self.tags_json:
            return [{'key': k, 'value': v} for k, v in self.tags_json.items()]
        return []

    @property
    def tag_dict(self):
        """获取标签字典格式"""
        return self.tags_json or {}
    
    def increment_usage(self):
        """增加使用次数"""
        self.usage_count += 1
        self.save(update_fields=['usage_count'])


class ScriptTemplateVersion(models.Model):
    """脚本模板版本历史"""

    template = models.ForeignKey(ScriptTemplate, on_delete=models.CASCADE, related_name='versions', verbose_name="脚本模板")
    version = models.CharField(max_length=50, verbose_name="版本号")
    script_content = models.TextField(verbose_name="脚本内容")
    description = models.TextField(blank=True, verbose_name="版本描述")

    # 版本状态
    is_active = models.BooleanField(default=False, verbose_name="是否为当前版本")

    # 创建信息
    created_by = models.ForeignKey(User, on_delete=models.CASCADE, verbose_name="创建人")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="创建时间")

    class Meta:
        verbose_name = "脚本模板版本"
        verbose_name_plural = "脚本模板版本"
        ordering = ['-created_at']
        unique_together = ['template', 'version']
        indexes = [
            models.Index(fields=['template', 'version']),
            models.Index(fields=['template', 'is_active']),
        ]

    def __str__(self):
        return f"{self.template.name} v{self.version}"
