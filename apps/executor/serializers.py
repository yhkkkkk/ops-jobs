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
            'celery_task_id', 'execution_parameters',
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
    
    execution_id = serializers.CharField(read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    execution_type_display = serializers.CharField(source='get_execution_type_display', read_only=True)
    trigger_type_display = serializers.CharField(source='get_trigger_type_display', read_only=True)
    executed_by_name = serializers.CharField(source='executed_by.username', read_only=True)
    
    duration = serializers.SerializerMethodField()
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
            'celery_task_id', 'execution_parameters',
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
        """
        获取执行结果，对外只返回按步骤组织的结构：

        {
            "steps": [
                {
                    "id": "step_1_init",
                    "order": 1,
                    "name": "初始化环境",
                    "status": "success",
                    "hosts": [
                        {
                            "id": 1,
                            "name": "web-01",
                            "ip": "10.0.0.11",
                            "status": "success",
                            "stdout": "...",
                            "stderr": "..."
                        }
                    ]
                }
            ]
        }

        兼容来源：
        - log_archive_service.get_execution_logs 返回的 step_logs（通过 self.log_data 传入）
        - ExecutionRecord.execution_results 中已有的 step_logs（例如模拟数据）
        """
        raw_results = obj.execution_results or {}

        # 1. 优先从 log_data 中获取步骤日志（归档后的标准结构）
        step_logs = None
        if self.log_data and isinstance(self.log_data, dict):
            step_logs = self.log_data.get('step_logs')

        # 2. 如果 log_data 中没有步骤日志，尝试从 execution_results 中获取
        if step_logs is None and isinstance(raw_results, dict):
            step_logs = raw_results.get('step_logs')

        # 安全兜底
        if not isinstance(step_logs, dict):
            step_logs = {}

        # 3. 将 step_logs 统一转换为前端友好的 steps 结构
        steps = []
        for idx, (step_id, step_data) in enumerate(step_logs.items(), start=1):
            if not isinstance(step_data, dict):
                continue

            step_name = step_data.get('step_name') or step_id
            step_order = step_data.get('step_order') or idx
            step_status = step_data.get('status') or 'unknown'

            # 兼容 hosts / host_logs 两种字段
            hosts_mapping = step_data.get('hosts') or step_data.get('host_logs') or {}
            if not isinstance(hosts_mapping, dict):
                hosts_mapping = {}

            hosts = []
            for host_key, host_data in hosts_mapping.items():
                if not isinstance(host_data, dict):
                    continue

                host_id = host_data.get('host_id') or host_key
                host_name = host_data.get('host_name') or host_data.get('hostname') or str(host_id)
                host_ip = host_data.get('host_ip') or ''
                host_status = host_data.get('status') or 'unknown'

                # 统一 stdout/stderr 字段，兼容 logs / error_logs
                stdout = host_data.get('stdout') or host_data.get('logs') or ''
                stderr = host_data.get('stderr') or host_data.get('error_logs') or ''

                hosts.append({
                    'id': host_id,
                    'name': host_name,
                    'ip': host_ip,
                    'status': host_status,
                    'stdout': stdout,
                    'stderr': stderr,
                })

            steps.append({
                'id': step_id,
                'order': step_order,
                'name': step_name,
                'status': step_status,
                'hosts': hosts,
            })

        return {'steps': steps}
