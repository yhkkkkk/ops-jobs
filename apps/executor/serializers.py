"""
统一执行记录序列化器
"""
from rest_framework import serializers
from drf_spectacular.utils import extend_schema_field
from .models import ExecutionRecord, ExecutionStep
from apps.permissions.models import AuditLog


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
            'execution_parameters',
            'error_message', 'created_at', 'started_at',
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

    # 关联对象信息
    related_object_info = serializers.SerializerMethodField()

    # 步骤简要信息（仅元数据，日志按需加载）
    steps = serializers.SerializerMethodField()

    # 处理execution_results字段，移除其中的logs字段，并暴露日志指针/摘录元信息
    execution_results = serializers.SerializerMethodField()

    class Meta:
        model = ExecutionRecord
        fields = [
            'id', 'execution_id', 'execution_type', 'execution_type_display',
            'name', 'description', 'status', 'status_display',
            'trigger_type', 'trigger_type_display', 'executed_by', 'executed_by_name',
            'execution_parameters',
            'execution_results', 'error_message', 'created_at', 'started_at',
            'finished_at', 'duration', 'retry_count', 'max_retries',
            'is_completed', 'is_running',
            'steps', 'realtime_urls', 'related_object_info'
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
        if obj.is_running:
            task_id = str(obj.execution_id)
            return {
                'logs': f'/api/realtime/sse/logs/{task_id}/',
                'status': f'/api/realtime/sse/status/{task_id}/',
                'combined': f'/api/realtime/sse/combined/{task_id}/'
            }
        return None
    
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

    @extend_schema_field(serializers.ListField())
    def get_steps(self, obj):
        steps_qs = obj.steps.all().order_by('step_order')
        return ExecutionStepBriefSerializer(steps_qs, many=True).data

    @extend_schema_field(serializers.DictField(allow_null=True))
    def get_execution_results(self, obj):
        """
        返回轻量化执行结果，仅包含 logs_meta/summary 等小字段。
        详细步骤/主机日志通过按需接口获取。
        """
        raw_results = obj.execution_results or {}
        if not isinstance(raw_results, dict):
            return {}

        logs_meta = raw_results.get('logs_meta') if isinstance(raw_results.get('logs_meta'), dict) else {}
        summary = raw_results.get('summary') or raw_results.get('log_summary')

        result = {}
        if logs_meta:
            result['logs_meta'] = logs_meta
        if summary:
            result['summary'] = summary
        return result


def _extract_step_host_results(step: ExecutionStep):
    host_results = step.host_results or []
    if isinstance(host_results, dict):
        host_results = list(host_results.values())

    if host_results:
        return host_results

    results = step.execution_record.execution_results or {}
    if not isinstance(results, dict):
        return []

    step_logs = results.get('step_logs') or {}
    if not isinstance(step_logs, dict):
        return []

    for _, step_data in step_logs.items():
        if not isinstance(step_data, dict):
            continue
        if step_data.get('step_order') != step.step_order and step_data.get('step_name') != step.step_name:
            continue
        host_map = step_data.get('host_logs') or step_data.get('hosts') or {}
        if isinstance(host_map, dict):
            return list(host_map.values())
    return []


class ExecutionStepBriefSerializer(serializers.ModelSerializer):
    duration = serializers.SerializerMethodField()
    host_count = serializers.SerializerMethodField()

    class Meta:
        model = ExecutionStep
        fields = [
            'id',
            'step_name',
            'step_type',
            'step_order',
            'status',
            'started_at',
            'finished_at',
            'duration',
            'host_count',
        ]

    @extend_schema_field(serializers.FloatField(allow_null=True))
    def get_duration(self, obj):
        return obj.duration

    @extend_schema_field(serializers.IntegerField())
    def get_host_count(self, obj):
        return len(_extract_step_host_results(obj))


class MaskedParameterSerializer(serializers.Serializer):
    key = serializers.CharField()
    value = serializers.SerializerMethodField()
    is_masked = serializers.BooleanField()

    def get_value(self, obj):
        return obj.get('display_value')


class ExecutionStepResultSerializer(serializers.ModelSerializer):
    hosts = serializers.SerializerMethodField()
    duration = serializers.SerializerMethodField()

    class Meta:
        model = ExecutionStep
        fields = [
            'id',
            'step_name',
            'step_order',
            'status',
            'started_at',
            'finished_at',
            'duration',
            'hosts',
        ]

    @extend_schema_field(serializers.FloatField(allow_null=True))
    def get_duration(self, obj):
        return obj.duration

    @extend_schema_field(serializers.ListField())
    def get_hosts(self, obj):
        host_results = _extract_step_host_results(obj)

        results = []
        for item in host_results:
            if not isinstance(item, dict):
                continue
            host_id = item.get('host_id') or item.get('id') or item.get('host')
            results.append({
                'id': host_id,
                'name': item.get('host_name') or item.get('hostname') or item.get('name'),
                'ip': item.get('host_ip') or item.get('ip'),
                'status': item.get('status') or ('success' if item.get('exit_code') == 0 else 'failed'),
                'exit_code': item.get('exit_code'),
                'started_at': item.get('started_at') or item.get('start_time'),
                'finished_at': item.get('finished_at') or item.get('end_time'),
            })
        return results


class ExecutionStepContentSerializer(serializers.ModelSerializer):
    """步骤内容（脚本/参数）"""

    SYSTEM_PARAM_KEYS = {
        'script_content',
        'script_type',
        'timeout',
        'ignore_error',
        'file_sources',
        'execution_mode',
        'rolling_strategy',
        'rolling_batch_size',
        'rolling_batch_delay',
        'account_id',
        'target_host_ids',
        'agent_server_url',
        'positional_args',
        'file_items',
        'target_hosts',
        'target_ips',
    }

    script_type = serializers.SerializerMethodField()
    script_content = serializers.SerializerMethodField()
    timeout = serializers.SerializerMethodField()
    ignore_error = serializers.SerializerMethodField()
    file_sources = serializers.SerializerMethodField()
    rendered_parameters = serializers.SerializerMethodField()

    class Meta:
        model = ExecutionStep
        fields = [
            'id',
            'step_name',
            'step_type',
            'step_order',
            'status',
            'script_type',
            'script_content',
            'timeout',
            'ignore_error',
            'file_sources',
            'rendered_parameters',
        ]

    def _get_step_params(self, obj):
        params = obj.step_parameters or {}
        return params if isinstance(params, dict) else {}

    def _mask_value(self, key, value, is_secret=False):
        import re
        key_lower = (key or '').lower()
        if is_secret:
            return '****', True
        if re.search(r'(password|secret|token|key|credential|pwd)', key_lower):
            return '****', True
        return value, False

    def get_script_type(self, obj):
        return self._get_step_params(obj).get('script_type') or ''

    def get_script_content(self, obj):
        return self._get_step_params(obj).get('script_content') or ''

    def get_timeout(self, obj):
        return self._get_step_params(obj).get('timeout')

    def get_ignore_error(self, obj):
        return self._get_step_params(obj).get('ignore_error', False)

    def get_file_sources(self, obj):
        return self._get_step_params(obj).get('file_sources') or []

    def _extract_variables(self, raw, exclude_keys=None):
        result = {}
        exclude = set(exclude_keys or [])
        if not raw:
            return result

        if isinstance(raw, list):
            for item in raw:
                if not isinstance(item, dict):
                    continue
                key = item.get('name') or item.get('key')
                if not key or key in exclude:
                    continue
                value = item.get('value')
                is_secret = bool(item.get('is_secret')) or (item.get('type') == 'secret')
                result[key] = {
                    'value': value,
                    'is_secret': is_secret,
                }
            return result

        if isinstance(raw, dict):
            for key, value in raw.items():
                if key in exclude:
                    continue
                if isinstance(value, dict) and 'value' in value:
                    is_secret = bool(value.get('is_secret')) or (value.get('type') == 'secret')
                    result[key] = {
                        'value': value.get('value'),
                        'is_secret': is_secret,
                    }
                else:
                    result[key] = {
                        'value': value,
                        'is_secret': False,
                    }
        return result

    @extend_schema_field(MaskedParameterSerializer(many=True))
    def get_rendered_parameters(self, obj):
        merged = {}
        exec_params = None
        if obj.execution_record and isinstance(obj.execution_record.execution_parameters, dict):
            exec_params = obj.execution_record.execution_parameters

        if isinstance(exec_params, dict):
            global_vars = exec_params.get('global_variables')
            if isinstance(global_vars, list):
                merged.update(self._extract_variables(global_vars))
            extra = {
                key: value
                for key, value in exec_params.items()
                if key not in self.SYSTEM_PARAM_KEYS and key != 'global_variables'
            }
            merged.update(self._extract_variables(extra))
        else:
            merged.update(self._extract_variables(exec_params, self.SYSTEM_PARAM_KEYS))

        step_exec_params = self._get_step_params(obj).get('execution_parameters')
        merged.update(self._extract_variables(step_exec_params))

        rendered = []
        for key, payload in merged.items():
            value = payload.get('value')
            is_secret = payload.get('is_secret', False)
            masked_value, is_masked = self._mask_value(key, value, is_secret)
            rendered.append({
                'key': key,
                'value': value,
                'display_value': masked_value,
                'is_secret': is_secret,
                'is_masked': is_masked,
            })
        return rendered


class ExecutionOperationLogSerializer(serializers.ModelSerializer):
    action_display = serializers.CharField(source='get_action_display', read_only=True)
    user_name = serializers.CharField(source='user.username', read_only=True)

    class Meta:
        model = AuditLog
        fields = [
            'id',
            'action',
            'action_display',
            'user_name',
            'created_at',
            'success',
            'description',
            'extra_data',
        ]
