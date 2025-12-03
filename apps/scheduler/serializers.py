"""
调度管理序列化器
"""
from rest_framework import serializers
from .models import ScheduledJob
from utils.validators import validate_cron_expression, validate_timezone


class ScheduledJobSerializer(serializers.ModelSerializer):
    """定时作业序列化器"""

    template_name = serializers.CharField(read_only=True)
    plan_name = serializers.CharField(read_only=True)
    # 方便前端跳转到模板详情
    template_id = serializers.IntegerField(source='execution_plan.template_id', read_only=True)
    success_rate = serializers.FloatField(read_only=True)
    created_by_name = serializers.CharField(source='created_by.username', read_only=True)

    class Meta:
        model = ScheduledJob
        fields = [
            'id', 'name', 'description', 'execution_plan', 'template_id',
            'template_name', 'plan_name',
            'cron_expression', 'timezone', 'is_active',
            'total_runs', 'success_runs', 'failed_runs', 'success_rate',
            'last_run_time', 'next_run_time', 'created_by', 'created_by_name',
            'created_at', 'updated_at'
        ]
        read_only_fields = [
            'total_runs', 'success_runs', 'failed_runs', 'last_run_time',
            'next_run_time', 'created_by', 'created_at', 'updated_at'
        ]


class ScheduledJobCreateSerializer(serializers.ModelSerializer):
    """定时作业创建序列化器"""

    class Meta:
        model = ScheduledJob
        fields = [
            'name', 'description', 'execution_plan', 'cron_expression', 'timezone', 'is_active'
        ]

    def validate_cron_expression(self, value):
        """验证cron表达式"""
        return validate_cron_expression(value)

    def validate_timezone(self, value):
        """验证时区"""
        return validate_timezone(value)
    
    def validate(self, attrs):
        """验证数据"""
        # 检查执行方案是否存在且有步骤
        execution_plan = attrs.get('execution_plan')
        if execution_plan:
            if not execution_plan.planstep_set.exists():
                raise serializers.ValidationError("选择的执行方案没有包含任何步骤")

        return attrs


class ScheduledJobStatisticsSerializer(serializers.Serializer):
    """定时作业统计序列化器"""
    
    total_jobs = serializers.IntegerField()
    active_jobs = serializers.IntegerField()
    inactive_jobs = serializers.IntegerField()
    total_executions = serializers.IntegerField()
    success_executions = serializers.IntegerField()
    failed_executions = serializers.IntegerField()
    success_rate = serializers.FloatField()
    
    # 最近执行统计 - 使用统一的ExecutionRecord
    recent_executions = serializers.ListField()
    
    # 按状态分组的执行统计
    execution_stats_by_status = serializers.DictField()
    
    # 按作业分组的执行统计
    execution_stats_by_job = serializers.DictField()
