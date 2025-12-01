"""
作业模板模型
"""
from django.db import models
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError


class JobTemplate(models.Model):
    """作业模板 - 完整的流程定义"""

    name = models.CharField(max_length=200, unique=True, verbose_name="模板名称")
    description = models.TextField(blank=True, verbose_name="模板描述")

    # 分类标签
    category = models.CharField(max_length=50, blank=True, verbose_name="分类")
    tags_json = models.JSONField(default=dict, blank=True, verbose_name="标签",
                               help_text="键值对格式的标签，如 {'env': 'prod', 'team': 'ops'}")

    # 全局变量（模板级别的参数）
    # 支持两种格式：
    # 1. 简单格式（向后兼容）: {"key": "value"}
    # 2. 扩展格式: {"key": {"value": "value", "type": "text|secret", "description": "desc"}}
    global_parameters = models.JSONField(default=dict, blank=True, verbose_name="全局变量",
                                       help_text="模板级别的全局变量，可在所有步骤中使用")

    # 创建信息
    created_by = models.ForeignKey(User, on_delete=models.CASCADE, verbose_name="创建人")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="创建时间")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="更新时间")

    class Meta:
        verbose_name = "作业模板"
        verbose_name_plural = "作业模板"
        ordering = ['-created_at']
        permissions = [
            ('execute_jobtemplate', '执行作业模板'),
        ]

    def __str__(self):
        return self.name

    @property
    def tag_list(self):
        """获取标签列表（键值对格式）"""
        if self.tags_json:
            return [{'key': k, 'value': v} for k, v in self.tags_json.items()]
        return []

    @property
    def step_count(self):
        """步骤数量"""
        return self.steps.count()

    @property
    def plan_count(self):
        """执行方案数量"""
        # 使用related manager直接查询，避免预取缓存问题
        return self.plans.all().count()

    def mark_plans_as_unsynced(self):
        """标记所有执行方案为未同步状态"""
        self.plans.update(is_synced=False)

    @property
    def has_unsync_plans(self):
        """是否有未同步的执行方案"""
        from .sync_service import TemplateSyncService
        sync_status = TemplateSyncService.check_all_plans_sync_status(self)
        return sync_status['unsynced_plans'] > 0

    def get_sync_status(self):
        """获取所有执行方案的同步状态"""
        from .sync_service import TemplateSyncService
        return TemplateSyncService.check_all_plans_sync_status(self)


class JobStep(models.Model):
    """作业步骤 - 可以是脚本执行或文件传输"""

    STEP_TYPE_CHOICES = [
        ('script', '脚本执行'),
        ('file_transfer', '文件传输'),
    ]

    # 关联模板
    template = models.ForeignKey(JobTemplate, on_delete=models.CASCADE, related_name='steps', verbose_name="所属模板")

    # 基本信息
    name = models.CharField(max_length=200, verbose_name="步骤名称")
    description = models.TextField(blank=True, verbose_name="步骤描述")
    step_type = models.CharField(max_length=20, choices=STEP_TYPE_CHOICES, verbose_name="步骤类型")
    order = models.IntegerField(verbose_name="执行顺序")

    # 位置参数 (数组格式存储，如 ["参数1", "参数2", "参数3"])
    step_parameters = models.JSONField(default=list, verbose_name="位置参数")

    # 脚本配置 (仅当 step_type='script' 时使用)
    script_type = models.CharField(max_length=20, blank=True, verbose_name="脚本类型",
                                 help_text="shell, python, powershell 等")
    script_content = models.TextField(blank=True, verbose_name="脚本内容")
    account_id = models.IntegerField(null=True, blank=True, verbose_name="执行账号ID")

    # 文件传输配置 (仅当 step_type='file_transfer' 时使用)
    transfer_type = models.CharField(max_length=20, blank=True, verbose_name="传输类型",
                                   help_text="upload 或 download")
    local_path = models.TextField(blank=True, verbose_name="本地路径")
    remote_path = models.TextField(blank=True, verbose_name="远程路径")
    overwrite_policy = models.CharField(max_length=20, blank=True, verbose_name="覆盖策略",
                                      help_text="overwrite, skip, backup")

    # 目标主机配置（每个步骤有自己的目标主机）
    target_hosts = models.ManyToManyField('hosts.Host', blank=True, verbose_name="目标主机")
    target_groups = models.ManyToManyField('hosts.HostGroup', blank=True, verbose_name="目标分组")

    # 执行配置
    timeout = models.IntegerField(default=300, verbose_name="超时时间(秒)")
    ignore_error = models.BooleanField(default=False, verbose_name="忽略错误继续执行")

    class Meta:
        verbose_name = "作业步骤"
        verbose_name_plural = "作业步骤"
        ordering = ['order']
        unique_together = ['template', 'order']

    def __str__(self):
        return f"{self.template.name} - 步骤{self.order}: {self.name}"

    def clean(self):
        """验证步骤配置"""
        if self.step_type == 'script':
            if not self.script_content:
                raise ValidationError({'script_content': '脚本步骤必须包含脚本内容'})
            if not self.script_type:
                raise ValidationError({'script_type': '脚本步骤必须指定脚本类型'})
        elif self.step_type == 'file_transfer':
            if not self.local_path:
                raise ValidationError({'local_path': '文件传输步骤必须包含本地路径'})
            if not self.remote_path:
                raise ValidationError({'remote_path': '文件传输步骤必须包含远程路径'})
            if not self.transfer_type:
                raise ValidationError({'transfer_type': '文件传输步骤必须指定传输类型'})

        # 验证位置参数格式
        if not isinstance(self.step_parameters, list):
            raise ValidationError({'step_parameters': '位置参数必须是数组格式'})


class ExecutionPlan(models.Model):
    """执行方案 - 模板的子集，可以选择性执行某些步骤"""

    # 关联模板
    template = models.ForeignKey(JobTemplate, on_delete=models.CASCADE, related_name='plans', verbose_name="所属模板")

    # 基本信息
    name = models.CharField(max_length=200, verbose_name="方案名称")
    description = models.TextField(blank=True, verbose_name="方案描述")

    # 包含的步骤 (通过中间表关联)
    steps = models.ManyToManyField(JobStep, through='PlanStep', verbose_name="包含步骤")

    # 同步信息
    is_synced = models.BooleanField(default=True, verbose_name="是否已同步")
    global_parameters_snapshot = models.JSONField(default=dict, blank=True, verbose_name="全局变量快照")
    last_sync_at = models.DateTimeField(null=True, blank=True, verbose_name="最后同步时间")

    # 创建信息
    created_by = models.ForeignKey(User, on_delete=models.CASCADE, verbose_name="创建人")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="创建时间")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="更新时间")

    # 执行统计信息
    total_executions = models.IntegerField(default=0, verbose_name="总执行次数")
    success_executions = models.IntegerField(default=0, verbose_name="成功执行次数")
    failed_executions = models.IntegerField(default=0, verbose_name="失败执行次数")
    last_executed_at = models.DateTimeField(null=True, blank=True, verbose_name="最后执行时间")

    class Meta:
        verbose_name = "执行方案"
        verbose_name_plural = "执行方案"
        ordering = ['-created_at']
        permissions = [
            ('execute_executionplan', '执行执行方案'),
        ]

    def __str__(self):
        return f"{self.template.name} - {self.name}"

    @property
    def step_count(self):
        """包含的步骤数量"""
        return self.planstep_set.count()

    @property
    def scheduled_job_count(self):
        """定时作业数量"""
        return self.scheduled_jobs.count()

    @property
    def has_active_schedules(self):
        """是否有活跃的定时作业"""
        return self.scheduled_jobs.filter(is_active=True).exists()

    @property
    def success_rate(self):
        """成功率"""
        if self.total_executions == 0:
            return 0
        return round(self.success_executions / self.total_executions * 100, 2)

    @property
    def needs_sync(self):
        """是否需要同步 - 使用新的变更检测机制"""
        from .sync_service import TemplateChangeDetector
        try:
            changes = TemplateChangeDetector.detect_changes(self)
            return changes['has_changes']
        except Exception:
            # 如果检测失败，保守地认为需要同步
            return not self.is_synced

    def get_sync_changes(self):
        """获取同步变更详情"""
        from .sync_service import TemplateChangeDetector
        return TemplateChangeDetector.detect_changes(self)

    def sync_from_template(self, force=False):
        """从模板同步步骤 - 使用新的同步服务"""
        from .sync_service import TemplateSyncService
        return TemplateSyncService.sync_plan_from_template(self, force=force)

    def save(self, *args, **kwargs):
        # 删除is_default相关逻辑，因为字段已删除
        super().save(*args, **kwargs)


class PlanStep(models.Model):
    """执行方案包含的步骤 - 中间表"""
    plan = models.ForeignKey(ExecutionPlan, on_delete=models.CASCADE, verbose_name="执行方案")
    step = models.ForeignKey(JobStep, on_delete=models.SET_NULL, null=True, blank=True, verbose_name="作业步骤")
    order = models.IntegerField(verbose_name="在方案中的执行顺序")

    # 步骤快照数据（创建时从模板步骤复制，独立存储）
    step_name = models.CharField(max_length=200, verbose_name="步骤名称快照")
    step_description = models.TextField(blank=True, verbose_name="步骤描述快照")
    step_type = models.CharField(max_length=50, verbose_name="步骤类型快照")
    step_script_content = models.TextField(blank=True, verbose_name="脚本内容快照")
    step_script_type = models.CharField(max_length=20, default='shell', verbose_name="脚本类型快照")
    step_parameters = models.JSONField(default=list, verbose_name="位置参数快照")
    step_timeout = models.IntegerField(default=300, verbose_name="超时时间快照")
    step_ignore_error = models.BooleanField(default=False, verbose_name="忽略错误快照")
    step_target_host_ids = models.JSONField(default=list, verbose_name="目标主机ID快照")
    step_target_group_ids = models.JSONField(default=list, verbose_name="目标分组ID快照")
    step_targets = models.JSONField(default=list, verbose_name="目标快照（统一格式）", 
                                   help_text="格式：[{'type': 'host', 'id': 1}, {'type': 'group', 'id': 2}]")

    # 新增快照字段
    step_account_id = models.IntegerField(null=True, blank=True, verbose_name="执行账号ID快照")
    step_transfer_type = models.CharField(max_length=20, blank=True, verbose_name="传输类型快照")
    step_local_path = models.TextField(blank=True, verbose_name="本地路径快照")
    step_remote_path = models.TextField(blank=True, verbose_name="远程路径快照")

    # 可以在方案中覆盖步骤的某些参数
    override_parameters = models.JSONField(default=dict, blank=True, verbose_name="参数覆盖")
    override_timeout = models.IntegerField(null=True, blank=True, verbose_name="超时覆盖")

    # 步骤内容哈希值，用于变更检测
    step_hash = models.CharField(max_length=32, blank=True, verbose_name="步骤哈希值")

    class Meta:
        verbose_name = "方案步骤"
        verbose_name_plural = "方案步骤"
        ordering = ['order']
        unique_together = ['plan', 'step']

    def __str__(self):
        step_name = self.step.name if self.step else self.step_name
        return f"{self.plan.name} - 步骤{self.order}: {step_name}"

    def get_effective_parameters(self):
        """获取有效的参数 (位置参数 + 覆盖参数)"""
        # 位置参数现在是数组格式，如果有覆盖参数则使用覆盖的，否则使用快照的
        if 'step_parameters' in self.override_parameters:
            return self.override_parameters['step_parameters']
        return self.step_parameters

    def get_effective_timeout(self):
        """获取有效的超时时间"""
        return self.override_timeout if self.override_timeout else self.step_timeout

    def get_effective_script_content(self):
        """获取有效的脚本内容"""
        # 如果有覆盖的脚本内容，使用覆盖的，否则使用快照的
        if 'script_content' in self.override_parameters:
            return self.override_parameters['script_content']
        return self.step_script_content

    def get_effective_script_type(self):
        """获取有效的脚本类型"""
        if 'script_type' in self.override_parameters:
            return self.override_parameters['script_type']
        return self.step_script_type

    def copy_from_template_step(self):
        """从模板步骤复制快照数据（根据步骤类型）"""
        if self.step:
            # 复制通用字段
            self.step_name = self.step.name
            self.step_description = self.step.description
            self.step_type = self.step.step_type
            self.step_parameters = self.step.step_parameters
            self.step_timeout = self.step.timeout
            self.step_ignore_error = self.step.ignore_error
            self.step_target_host_ids = sorted(list(self.step.target_hosts.values_list('id', flat=True)))
            self.step_target_group_ids = sorted(list(self.step.target_groups.values_list('id', flat=True)))
            
            # 生成统一格式的目标快照
            targets = []
            for host_id in self.step_target_host_ids:
                targets.append({'type': 'host', 'id': host_id})
            for group_id in self.step_target_group_ids:
                targets.append({'type': 'group', 'id': group_id})
            self.step_targets = targets

            # 根据步骤类型复制特定字段
            if self.step.step_type == 'script':
                self.step_script_content = self.step.script_content
                self.step_script_type = self.step.script_type
                self.step_account_id = self.step.account_id
            elif self.step.step_type == 'file_transfer':
                self.step_transfer_type = self.step.transfer_type
                self.step_local_path = self.step.local_path
                self.step_remote_path = self.step.remote_path
