from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models
from django.utils import timezone


class FlowTemplate(models.Model):
    """流程模板."""

    name = models.CharField(max_length=200, unique=True, verbose_name="流程名称")
    description = models.TextField(blank=True, verbose_name="描述")
    variables = models.JSONField(default=dict, blank=True, verbose_name="变量定义")
    encrypted_secret_defaults = models.JSONField(default=dict, blank=True, verbose_name="加密敏感变量默认值")
    is_active = models.BooleanField(default=True, verbose_name="是否启用")
    created_by = models.ForeignKey(User, on_delete=models.CASCADE, verbose_name="创建人")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="创建时间")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="更新时间")

    class Meta:
        db_table = "flows_flow_template"
        ordering = ["-created_at"]
        verbose_name = "流程模板"
        verbose_name_plural = "流程模板"

    def save(self, *args, **kwargs):
        update_fields = kwargs.get("update_fields")
        if self._state.adding or update_fields is None or "variables" in update_fields:
            from .secret_service import prepare_flow_secret_defaults

            self.variables, self.encrypted_secret_defaults = prepare_flow_secret_defaults(
                self.variables, self.encrypted_secret_defaults
            )
            if update_fields is not None:
                kwargs["update_fields"] = set(update_fields) | {"variables", "encrypted_secret_defaults"}
        return super().save(*args, **kwargs)

    def __str__(self):
        return self.name


class FlowNode(models.Model):
    """流程节点."""

    class NodeType(models.TextChoices):
        SCRIPT = "script", "脚本执行"
        FILE_TRANSFER = "file_transfer", "文件传输"
        JOB_PLAN = "job_plan", "作业执行方案"
        MANUAL = "manual", "人工确认"
        CONDITION = "condition", "条件分支"
        PARALLEL = "parallel", "并行网关"
        JOIN = "join", "汇聚网关"
        SUB_PROCESS = "sub_process", "子流程"

    template = models.ForeignKey(
        FlowTemplate,
        on_delete=models.CASCADE,
        related_name="nodes",
        verbose_name="流程模板",
    )
    uuid = models.CharField(max_length=64, verbose_name="节点UUID")
    name = models.CharField(max_length=200, verbose_name="节点名称")
    node_type = models.CharField(max_length=32, choices=NodeType.choices, verbose_name="节点类型")
    config = models.JSONField(default=dict, blank=True, verbose_name="节点配置")
    position = models.JSONField(default=dict, blank=True, verbose_name="画布位置")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="创建时间")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="更新时间")

    class Meta:
        db_table = "flows_flow_node"
        ordering = ["template", "id"]
        unique_together = [["template", "uuid"]]
        indexes = [
            models.Index(fields=["template", "node_type"]),
        ]
        verbose_name = "流程节点"
        verbose_name_plural = "流程节点"

    def __str__(self):
        return f"{self.template.name} - {self.name}"


class FlowEdge(models.Model):
    """流程有向边."""

    template = models.ForeignKey(
        FlowTemplate,
        on_delete=models.CASCADE,
        related_name="edges",
        verbose_name="流程模板",
    )
    source = models.ForeignKey(
        FlowNode,
        on_delete=models.CASCADE,
        related_name="out_edges",
        verbose_name="源节点",
    )
    target = models.ForeignKey(
        FlowNode,
        on_delete=models.CASCADE,
        related_name="in_edges",
        verbose_name="目标节点",
    )
    condition = models.JSONField(default=dict, blank=True, verbose_name="边条件")

    class Meta:
        db_table = "flows_flow_edge"
        unique_together = [["template", "source", "target"]]
        indexes = [
            models.Index(fields=["template", "source"]),
            models.Index(fields=["template", "target"]),
        ]
        verbose_name = "流程边"
        verbose_name_plural = "流程边"

    def __str__(self):
        return f"{self.source.uuid} -> {self.target.uuid}"

    def clean(self):
        super().clean()
        errors = {}

        if self.template_id and self.source_id and self.source.template_id != self.template_id:
            errors["source"] = "Flow edge source must belong to the same template."
        if self.template_id and self.target_id and self.target.template_id != self.template_id:
            errors["target"] = "Flow edge target must belong to the same template."

        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)


class FlowRun(models.Model):
    """流程执行实例."""

    class Status(models.TextChoices):
        PENDING = "pending", "等待中"
        RUNNING = "running", "执行中"
        SUCCESS = "success", "成功"
        FAILED = "failed", "失败"
        PAUSED = "paused", "已暂停"
        CANCELLED = "cancelled", "已取消"

    name = models.CharField(max_length=200, blank=True, verbose_name="任务名称")
    template = models.ForeignKey(
        FlowTemplate,
        on_delete=models.CASCADE,
        related_name="runs",
        verbose_name="流程模板",
    )
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    trigger_type = models.CharField(max_length=20, default="manual", verbose_name="触发类型")
    started_by = models.ForeignKey(User, on_delete=models.CASCADE, verbose_name="执行人")
    inputs = models.JSONField(default=dict, blank=True, verbose_name="输入")
    encrypted_secret_inputs = models.JSONField(default=dict, blank=True, verbose_name="加密敏感输入")
    definition_snapshot = models.JSONField(default=dict, blank=True, verbose_name="流程定义快照")
    outputs = models.JSONField(default=dict, blank=True, verbose_name="输出")
    error_message = models.TextField(blank=True, verbose_name="错误信息")
    started_at = models.DateTimeField(null=True, blank=True, verbose_name="开始时间")
    finished_at = models.DateTimeField(null=True, blank=True, verbose_name="结束时间")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="创建时间")

    class Meta:
        db_table = "flows_flow_run"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["template", "status"]),
            models.Index(fields=["status", "created_at"]),
            models.Index(fields=["started_by", "created_at"]),
        ]
        verbose_name = "流程执行实例"
        verbose_name_plural = "流程执行实例"

    def mark_finished(self, status, error_message=""):
        self.status = status
        self.error_message = error_message
        self.finished_at = timezone.now()
        self.save(update_fields=["status", "error_message", "finished_at"])


class FlowNodeRun(models.Model):
    """流程节点执行实例."""

    flow_run = models.ForeignKey(
        FlowRun,
        on_delete=models.CASCADE,
        related_name="node_runs",
        verbose_name="流程执行",
    )
    node = models.ForeignKey(FlowNode, on_delete=models.CASCADE, verbose_name="流程节点")
    status = models.CharField(max_length=20, choices=FlowRun.Status.choices, default=FlowRun.Status.PENDING)
    inputs = models.JSONField(default=dict, blank=True, verbose_name="输入")
    outputs = models.JSONField(default=dict, blank=True, verbose_name="输出")
    error_message = models.TextField(blank=True, verbose_name="错误信息")
    execution_record = models.ForeignKey(
        "executor.ExecutionRecord",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="flow_node_runs",
        verbose_name="关联执行记录",
    )
    started_at = models.DateTimeField(null=True, blank=True, verbose_name="开始时间")
    finished_at = models.DateTimeField(null=True, blank=True, verbose_name="结束时间")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="创建时间")

    class Meta:
        db_table = "flows_flow_node_run"
        unique_together = [["flow_run", "node"]]
        ordering = ["id"]
        indexes = [
            models.Index(fields=["flow_run", "status"]),
        ]
        verbose_name = "流程节点执行实例"
        verbose_name_plural = "流程节点执行实例"

class FlowSchedule(models.Model):
    """Cron schedule that starts a FlowTemplate with predefined global inputs."""

    class OverlapPolicy(models.TextChoices):
        SKIP = "skip", "跳过重叠触发"
        ALLOW = "allow", "允许并发运行"

    class MisfirePolicy(models.TextChoices):
        SKIP = "skip", "跳过错过触发"
        COALESCE = "coalesce", "合并为一次补跑"

    name = models.CharField(max_length=200, unique=True, verbose_name='调度名称')
    template = models.ForeignKey(FlowTemplate, on_delete=models.CASCADE, related_name='schedules', verbose_name='流程模板')
    cron_expression = models.CharField(max_length=100, verbose_name='Cron表达式')
    timezone = models.CharField(max_length=50, default='Asia/Shanghai', verbose_name='时区')
    inputs = models.JSONField(default=dict, blank=True, verbose_name='启动变量')
    encrypted_secret_inputs = models.JSONField(default=dict, blank=True, verbose_name='加密敏感启动变量')
    overlap_policy = models.CharField(max_length=16, choices=OverlapPolicy.choices, default=OverlapPolicy.SKIP, verbose_name='重叠触发策略')
    misfire_policy = models.CharField(max_length=16, choices=MisfirePolicy.choices, default=MisfirePolicy.SKIP, verbose_name='错过触发策略')
    misfire_grace_seconds = models.PositiveIntegerField(default=60, validators=[MinValueValidator(1)], verbose_name='错过触发宽限秒数')
    is_active = models.BooleanField(default=True, verbose_name='是否启用')
    created_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='created_flow_schedules', verbose_name='创建人')
    updated_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='updated_flow_schedules', verbose_name='更新人')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='更新时间')

    class Meta:
        db_table = 'flows_flow_schedule'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['is_active', 'created_at']),
            models.Index(fields=['template', 'is_active']),
        ]
        verbose_name = '流程定时调度'
        verbose_name_plural = '流程定时调度'

    def clean(self):
        from utils.validators import validate_timezone

        from .validators import validate_flow_schedule_cron_expression

        validate_flow_schedule_cron_expression(self.cron_expression)
        validate_timezone(self.timezone)
        if not isinstance(self.inputs, dict):
            raise ValidationError({'inputs': '流程启动变量必须是对象'})

    def save(self, *args, **kwargs):
        update_fields = kwargs.get("update_fields")
        if self._state.adding or update_fields is None or "inputs" in update_fields:
            from .secret_service import flow_secret_variable_keys, split_flow_secret_values

            secret_keys = flow_secret_variable_keys(self.template.variables or {})
            self.inputs, self.encrypted_secret_inputs = split_flow_secret_values(
                self.inputs, secret_keys, self.encrypted_secret_inputs
            )
            if update_fields is not None:
                kwargs["update_fields"] = set(update_fields) | {"inputs", "encrypted_secret_inputs"}
        self.full_clean()
        return super().save(*args, **kwargs)


class FlowScheduleRun(models.Model):
    """Durable launch claim for one FlowSchedule and one Cron minute."""

    STATUS_CHOICES = [
        ('starting', '启动中'),
        ('launched', '已启动'),
        ('failed', '启动失败'),
        ('skipped', '已跳过'),
    ]

    schedule = models.ForeignKey(FlowSchedule, on_delete=models.CASCADE, related_name='runs', verbose_name='流程调度')
    scheduled_for = models.DateTimeField(verbose_name='计划触发时间')
    flow_run = models.ForeignKey(FlowRun, on_delete=models.SET_NULL, null=True, blank=True, related_name='schedule_runs', verbose_name='流程实例')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='starting', verbose_name='启动状态')
    error_message = models.TextField(blank=True, verbose_name='启动错误')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='更新时间')

    class Meta:
        db_table = 'flows_flow_schedule_run'
        ordering = ['-scheduled_for']
        constraints = [
            models.UniqueConstraint(fields=['schedule', 'scheduled_for'], name='flows_unique_schedule_minute'),
        ]
        indexes = [
            models.Index(fields=['schedule', '-scheduled_for']),
            models.Index(fields=['status', '-scheduled_for']),
        ]
        verbose_name = '流程调度运行'
        verbose_name_plural = '流程调度运行'
