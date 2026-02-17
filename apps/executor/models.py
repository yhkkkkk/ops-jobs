"""
统一的执行记录模型
"""
from django.db import models
from django.contrib.auth.models import User
from django.contrib.contenttypes.models import ContentType
from django.contrib.contenttypes.fields import GenericForeignKey
from django.utils import timezone
from utils.execution_id import generate_execution_id


class ExecutionRecord(models.Model):
    """统一的执行记录"""

    EXECUTION_TYPE_CHOICES = [
        ('quick_script', '快速脚本执行'),
        ('quick_file_transfer', '快速文件传输'),
        ('job_workflow', 'Job工作流执行'),
        ('scheduled_job', '定时作业执行'),
    ]

    STATUS_CHOICES = [
        ('pending', '等待中'),
        ('running', '执行中'),
        ('success', '成功'),
        ('failed', '失败'),
        ('cancelled', '已取消'),
        ('timeout', '超时'),
        ('paused', '已暂停'),
        ('retrying', '重试中'),
    ]

    TRIGGER_TYPE_CHOICES = [
        ('manual', '手动执行'),
        ('scheduled', '定时执行'),
        ('api', 'api调用'),
    ]

    # 基本信息
    execution_id = models.BigIntegerField(unique=True, verbose_name="执行ID")
    execution_type = models.CharField(max_length=30, choices=EXECUTION_TYPE_CHOICES, verbose_name="执行类型")
    name = models.CharField(max_length=200, verbose_name="执行名称")
    description = models.TextField(blank=True, verbose_name="描述")

    # 关联对象 - 使用GenericForeignKey支持关联不同类型的对象
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE, null=True, blank=True)
    object_id = models.PositiveIntegerField(null=True, blank=True)
    related_object = GenericForeignKey('content_type', 'object_id')

    # 执行状态
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending', verbose_name="状态")
    trigger_type = models.CharField(max_length=20, choices=TRIGGER_TYPE_CHOICES, default='manual', verbose_name="触发类型")

    # 执行用户
    executed_by = models.ForeignKey(User, on_delete=models.CASCADE, verbose_name="执行用户")

    # 执行参数
    execution_parameters = models.JSONField(default=dict, blank=True, verbose_name="执行参数")

    # 执行结果
    execution_results = models.JSONField(default=dict, blank=True, verbose_name="执行结果")
    error_message = models.TextField(blank=True, verbose_name="错误信息")

    # 时间信息
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="创建时间")
    started_at = models.DateTimeField(null=True, blank=True, verbose_name="开始时间")
    finished_at = models.DateTimeField(null=True, blank=True, verbose_name="结束时间")

    # 重试信息
    retry_count = models.IntegerField(default=0, verbose_name="重试次数")
    last_retry_at = models.DateTimeField(null=True, blank=True, verbose_name="最后重试时间")

    # 混合重做模式字段
    parent_execution = models.ForeignKey(
        'self',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='retry_records',
        verbose_name="父执行记录"
    )
    is_latest = models.BooleanField(default=True, verbose_name="是否为最新执行")
    retry_reason = models.TextField(blank=True, verbose_name="重试原因")

    # 额外信息
    client_ip = models.GenericIPAddressField(null=True, blank=True, verbose_name="客户端IP")
    user_agent = models.TextField(blank=True, verbose_name="用户代理")

    class Meta:
        verbose_name = "执行记录"
        verbose_name_plural = "执行记录"
        db_table = 'executor_execution_record'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['execution_type', 'status']),
            models.Index(fields=['executed_by', 'created_at']),
            models.Index(fields=['content_type', 'object_id']),
            models.Index(fields=['content_type', 'object_id', 'execution_type', 'created_at']),
        ]

    def __str__(self):
        return f"{self.name} ({self.execution_id}) - {self.get_status_display()}"

    @property
    def max_retries(self):
        """获取最大重试次数"""
        # 默认允许至少 3 次重试，避免 0 次导致重做功能失效
        return 3

    @property
    def duration(self):
        """执行时长（秒）"""
        if self.started_at and self.finished_at:
            delta = self.finished_at - self.started_at
            return delta.total_seconds()
        return None

    @property
    def is_completed(self):
        """是否已完成"""
        return self.status in ['success', 'failed', 'cancelled', 'timeout']

    @property
    def is_running(self):
        """是否正在运行"""
        return self.status in ['pending', 'running']

    def get_root_execution(self):
        """获取根执行记录（用于重试链）"""
        if self.parent_execution:
            return self.parent_execution.get_root_execution()
        return self

    def get_retry_chain(self):
        """获取完整的重试链"""
        root = self.get_root_execution()
        chain = [root]
        chain.extend(root.retry_records.all().order_by('created_at'))
        return chain

    @property
    def total_retry_count(self):
        """获取总重试次数（包括整个重试链）"""
        return len(self.get_retry_chain()) - 1

    def generate_execution_id(self):
        """生成数字执行ID"""
        if not self.execution_id:
            self.execution_id = generate_execution_id()

    def save(self, *args, **kwargs):
        if not self.execution_id:
            self.generate_execution_id()
        super().save(*args, **kwargs)


class ExecutionStep(models.Model):
    """执行步骤记录"""

    STATUS_CHOICES = [
        ('pending', '等待中'),
        ('running', '执行中'),
        ('success', '成功'),
        ('failed', '失败'),
        ('skipped', '已跳过'),
    ]

    execution_record = models.ForeignKey(
        ExecutionRecord,
        on_delete=models.CASCADE,
        related_name='steps',
        verbose_name="执行记录"
    )

    step_name = models.CharField(max_length=200, verbose_name="步骤名称")
    step_type = models.CharField(max_length=50, verbose_name="步骤类型")
    step_order = models.IntegerField(verbose_name="步骤顺序")

    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending', verbose_name="状态")

    # 步骤参数和结果
    step_parameters = models.JSONField(default=dict, blank=True, verbose_name="步骤参数")
    step_results = models.JSONField(default=dict, blank=True, verbose_name="步骤结果")

    # 主机执行结果
    host_results = models.JSONField(default=list, blank=True, verbose_name="主机执行结果")

    # 时间信息
    started_at = models.DateTimeField(null=True, blank=True, verbose_name="开始时间")
    finished_at = models.DateTimeField(null=True, blank=True, verbose_name="结束时间")

    # 错误信息
    error_message = models.TextField(blank=True, verbose_name="错误信息")

    created_at = models.DateTimeField(auto_now_add=True, verbose_name="创建时间")

    class Meta:
        verbose_name = "执行步骤"
        verbose_name_plural = "执行步骤"
        db_table = 'executor_execution_step'
        ordering = ['execution_record', 'step_order']
        indexes = [
            models.Index(fields=['execution_record', 'step_order']),
            models.Index(fields=['status']),
        ]

    def __str__(self):
        return f"{self.execution_record.execution_id} - {self.step_name}"

    @property
    def duration(self):
        """步骤执行时长（秒）"""
        if self.started_at and self.finished_at:
            delta = self.finished_at - self.started_at
            return delta.total_seconds()
        return None


class ExecutionLog(models.Model):
    """执行日志条目"""

    execution_id = models.BigIntegerField(db_index=True, verbose_name="执行ID")
    task_id = models.CharField(max_length=128, db_index=True, verbose_name="任务ID")
    host_id = models.IntegerField(null=True, blank=True, verbose_name="主机ID")
    step_name = models.CharField(max_length=200, blank=True, verbose_name="步骤名称")
    step_order = models.IntegerField(default=0, verbose_name="步骤顺序")
    log_type = models.CharField(max_length=20, default="info", verbose_name="日志类型")
    content = models.TextField(verbose_name="日志内容")
    timestamp = models.DateTimeField(default=timezone.now, verbose_name="日志时间")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="创建时间")

    class Meta:
        verbose_name = "执行日志"
        verbose_name_plural = "执行日志"
        db_table = "executor_execution_log"
        indexes = [
            models.Index(fields=["execution_id", "task_id"]),
            models.Index(fields=["created_at"]),
        ]

    def __str__(self):
        return f"{self.execution_id} {self.task_id} {self.log_type}"
