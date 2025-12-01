"""
作业调度模型 - 基于django-celery-beat
"""
from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
from utils.validators import validate_cron_expression, validate_timezone
from django_celery_beat.models import PeriodicTask, CrontabSchedule
from apps.job_templates.models import ExecutionPlan
from apps.hosts.models import Host, HostGroup
import json


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
        null=True,  # 临时允许为空，用于迁移
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

    # 关联Celery Beat任务
    periodic_task = models.OneToOneField(
        PeriodicTask,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        verbose_name="周期任务"
    )

    # 元数据
    created_by = models.ForeignKey(User, on_delete=models.CASCADE, verbose_name="创建人")
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

