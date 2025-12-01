"""
统一执行记录序列化器
"""
from rest_framework import serializers
from drf_spectacular.utils import extend_schema_field
from .models import ExecutionRecord, ExecutionStep


class ExecutionRecordSerializer(serializers.ModelSerializer):
    """执行记录序列化器"""

    execution_id = serializers.CharField(read_only=True)  # 将execution_id作为字符串返回，避免JavaScript精度问题
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    execution_type_display = serializers.CharField(source='get_execution_type_display', read_only=True)
    trigger_type_display = serializers.CharField(source='get_trigger_type_display', read_only=True)
    executed_by_name = serializers.CharField(source='executed_by.username', read_only=True)

    duration = serializers.SerializerMethodField()
    success_rate = serializers.SerializerMethodField()
    is_completed = serializers.SerializerMethodField()
    is_running = serializers.SerializerMethodField()

    # 混合重做模式字段
    total_retry_count = serializers.SerializerMethodField()
    has_retries = serializers.SerializerMethodField()
    parent_execution_id = serializers.CharField(source='parent_execution.execution_id', read_only=True)

    @extend_schema_field(serializers.FloatField(allow_null=True))
    def get_duration(self, obj):
        """获取执行时长"""
        return obj.duration

    @extend_schema_field(serializers.FloatField())
    def get_success_rate(self, obj):
        """获取成功率"""
        return obj.success_rate

    @extend_schema_field(serializers.BooleanField())
    def get_is_completed(self, obj):
        """是否已完成"""
        return obj.is_completed

    @extend_schema_field(serializers.BooleanField())
    def get_is_running(self, obj):
        """是否正在运行"""
        return obj.is_running

    @extend_schema_field(serializers.IntegerField())
    def get_total_retry_count(self, obj):
        """获取总重试次数"""
        return obj.total_retry_count

    @extend_schema_field(serializers.BooleanField())
    def get_has_retries(self, obj):
        """是否有重试记录"""
        return obj.total_retry_count > 0

    # 关联对象信息
    related_object_info = serializers.SerializerMethodField()

    class Meta:
        model = ExecutionRecord
        fields = [
            'id', 'execution_id', 'execution_type', 'execution_type_display',
            'name', 'description', 'status', 'status_display',
            'trigger_type', 'trigger_type_display', 'executed_by', 'executed_by_name',
            'celery_task_id', 'execution_parameters', 'target_hosts',
            'total_hosts', 'success_hosts', 'failed_hosts', 'success_rate',
            'execution_results', 'error_message', 'created_at', 'started_at',
            'finished_at', 'duration', 'retry_count', 'max_retries',
            'client_ip', 'user_agent', 'is_completed', 'is_running',
            'related_object_info', 'total_retry_count', 'has_retries',
            'parent_execution_id', 'is_latest', 'retry_reason'
        ]
        read_only_fields = ['id', 'execution_id', 'created_at']

    @extend_schema_field(serializers.DictField(allow_null=True))
    def get_related_object_info(self, obj):
        """获取关联对象信息"""
        if obj.related_object:
            return {
                'type': obj.content_type.model,
                'id': obj.object_id,
                'name': str(obj.related_object)
            }
        return None


class ExecutionRecordDetailSerializer(serializers.ModelSerializer):
    """执行记录详情序列化器 - 包含日志信息"""
    
    execution_id = serializers.CharField(read_only=True)  # 将execution_id作为字符串返回
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    execution_type_display = serializers.CharField(source='get_execution_type_display', read_only=True)
    trigger_type_display = serializers.CharField(source='get_trigger_type_display', read_only=True)
    executed_by_name = serializers.CharField(source='executed_by.username', read_only=True)
    
    duration = serializers.SerializerMethodField()
    success_rate = serializers.SerializerMethodField()
    is_completed = serializers.SerializerMethodField()
    is_running = serializers.SerializerMethodField()
    
    # 实时日志相关字段
    realtime_urls = serializers.SerializerMethodField()
    
    # 处理execution_results字段，移除其中的logs字段
    execution_results = serializers.SerializerMethodField()
    
    class Meta:
        model = ExecutionRecord
        fields = [
            'id', 'execution_id', 'execution_type', 'execution_type_display',
            'name', 'description', 'status', 'status_display',
            'trigger_type', 'trigger_type_display', 'executed_by', 'executed_by_name',
            'celery_task_id', 'execution_parameters', 'target_hosts',
            'total_hosts', 'success_hosts', 'failed_hosts', 'success_rate',
            'execution_results', 'error_message', 'created_at', 'started_at',
            'finished_at', 'duration', 'retry_count', 'max_retries',
            'is_completed', 'is_running',
            'realtime_urls'
        ]
        read_only_fields = ['id', 'execution_id', 'created_at']
    
    def __init__(self, *args, **kwargs):
        # 从context中获取额外的数据
        self.log_data = kwargs.pop('log_data', None)
        super().__init__(*args, **kwargs)
    
    @extend_schema_field(serializers.FloatField(allow_null=True))
    def get_duration(self, obj):
        """获取执行时长"""
        return obj.duration
    
    @extend_schema_field(serializers.FloatField())
    def get_success_rate(self, obj):
        """获取成功率"""
        return obj.success_rate
    
    @extend_schema_field(serializers.BooleanField())
    def get_is_completed(self, obj):
        """是否已完成"""
        return obj.is_completed
    
    @extend_schema_field(serializers.BooleanField())
    def get_is_running(self, obj):
        """是否正在运行"""
        return obj.is_running
    
    @extend_schema_field(serializers.DictField(allow_null=True))
    def get_realtime_urls(self, obj):
        """获取实时日志URLs"""
        if obj.is_running and obj.celery_task_id:
            task_id = obj.celery_task_id
            return {
                'logs': f'/api/realtime/sse/logs/{task_id}/',
                'status': f'/api/realtime/sse/status/{task_id}/',
                'combined': f'/api/realtime/sse/combined/{task_id}/'
            }
        return None
    
    @extend_schema_field(serializers.DictField(allow_null=True))
    def get_execution_results(self, obj):
        """获取执行结果，包含step_logs和summary"""
        execution_results = obj.execution_results or {}
        # 创建副本并移除重复的日志字段
        if isinstance(execution_results, dict):
            execution_results = execution_results.copy()
            execution_results.pop('logs', None)
            execution_results.pop('step_logs', None)  # 移除重复的step_logs字段
            execution_results.pop('log_summary', None)  # 移除重复的log_summary字段
            
            # 添加步骤日志和摘要到execution_results中
            if self.log_data:
                if 'step_logs' in self.log_data:
                    execution_results['step_logs'] = self.log_data['step_logs']
                if 'summary' in self.log_data:
                    # 移除log_summary中的started_at和finished_at字段，因为与主记录重复
                    summary = self.log_data['summary'].copy()
                    summary.pop('started_at', None)
                    summary.pop('finished_at', None)
                    execution_results['log_summary'] = summary
        return execution_results
