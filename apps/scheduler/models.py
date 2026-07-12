"""
作业调度模型（APScheduler 持久化配置，不再关联 celery beat）
"""
from django.db import models
from django.contrib.auth.models import User
from utils.validators import validate_cron_expression, validate_timezone


class ScheduledJob(models.Model):
    """定时作业 - 给Job执行方案配置定时调度"""

    name = models.CharField(max_length=200, unique=True, verbose_name="定时作业名称")
    description = models.TextField(blank=True, verbose_name="描述")

    # 关联执行方案
    execution_plan = models.ForeignKey(
        'job_templates.ExecutionPlan',
        on_delete=models.CASCADE,
        related_name='scheduled_jobs',
        verbose_name="执行方案",
        null=True,
        blank=True
    )

    # 调度配置
    cron_expression = models.CharField(
        max_length=100,
        verbose_name="Cron表达式",
        validators=[validate_cron_expression],
        help_text="标准cron表达式，格式：分 时 日 月 周，例如：0 2 * * * 表示每天凌晨2点执行"
    )
    timezone = models.CharField(
        max_length=50,
        default='Asia/Shanghai',
        verbose_name="时区",
        validators=[validate_timezone],
        help_text="时区名称，例如：Asia/Shanghai, UTC, America/New_York"
    )

    # 状态控制
    is_active = models.BooleanField(default=True, verbose_name="是否启用")

    # 执行参数覆盖（可选，用于覆盖执行方案的默认全局变量）
    execution_parameters = models.JSONField(
        default=dict, 
        blank=True, 
        verbose_name="执行参数覆盖",
        help_text="用于覆盖执行方案的默认全局变量，如果为空则使用执行方案的默认全局变量"
    )

    # 元数据
    created_by = models.ForeignKey(User, on_delete=models.CASCADE, verbose_name="创建人")
    updated_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='updated_scheduled_jobs',
        verbose_name="更新人"
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="创建时间")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="更新时间")

    # 统计信息
    total_runs = models.IntegerField(default=0, verbose_name="总执行次数")
    success_runs = models.IntegerField(default=0, verbose_name="成功次数")
    failed_runs = models.IntegerField(default=0, verbose_name="失败次数")

    class Meta:
        verbose_name = "定时作业"
        verbose_name_plural = "定时作业"
        db_table = 'scheduler_scheduled_job'
        ordering = ['-created_at']
        permissions = [
            ('enable_scheduledjob', '启用定时作业'),
            ('disable_scheduledjob', '禁用定时作业'),
        ]
        indexes = [
            models.Index(fields=['execution_plan']),
            models.Index(fields=['is_active', 'created_at']),
            models.Index(fields=['created_by', 'created_at']),
        ]

    def __str__(self):
        return f"{self.name} ({self.cron_expression})"

    @property
    def template_name(self):
        """获取模板名称"""
        return self.execution_plan.template.name if self.execution_plan else ''

    @property
    def plan_name(self):
        """获取方案名称"""
        return self.execution_plan.name if self.execution_plan else ''

    @property
    def success_rate(self):
        """成功率"""
        if self.total_runs == 0:
            return 0
        return round((self.success_runs / self.total_runs) * 100, 2)



class ScheduledJobRun(models.Model):
    """A durable launch claim for one scheduled job and one Cron minute."""

    STATUS_CHOICES = [
        ('starting', '启动中'),
        ('launched', '已启动'),
        ('failed', '启动失败'),
    ]

    scheduled_job = models.ForeignKey(
        ScheduledJob,
        on_delete=models.CASCADE,
        related_name='runs',
        verbose_name='定时作业',
    )
    scheduled_for = models.DateTimeField(verbose_name='计划触发时间')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='starting', verbose_name='启动状态')
    error_message = models.TextField(blank=True, verbose_name='启动错误')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='更新时间')

    class Meta:
        verbose_name = '定时作业运行'
        verbose_name_plural = '定时作业运行'
        ordering = ['-scheduled_for']
        constraints = [
            models.UniqueConstraint(
                fields=['scheduled_job', 'scheduled_for'],
                name='scheduler_unique_job_scheduled_minute',
            ),
        ]
        indexes = [
            models.Index(fields=['scheduled_job', '-scheduled_for']),
            models.Index(fields=['status', '-scheduled_for']),
        ]

    def __str__(self):
        return f'{self.scheduled_job_id}@{self.scheduled_for.isoformat()}'

class SchedulerLease(models.Model):
    """Database-backed ownership lease for the scheduler process."""

    name = models.CharField(max_length=100, primary_key=True, verbose_name='租约名称')
    holder = models.CharField(max_length=64, verbose_name='持有者')
    expires_at = models.DateTimeField(verbose_name='过期时间')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='更新时间')

    class Meta:
        verbose_name = '调度器租约'
        verbose_name_plural = '调度器租约'

    def __str__(self):
        return f'{self.name}:{self.holder}'
