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
    last_run_time = models.DateTimeField(null=True, blank=True, verbose_name="最后执行时间")
    next_run_time = models.DateTimeField(null=True, blank=True, verbose_name="下次执行时间")

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

