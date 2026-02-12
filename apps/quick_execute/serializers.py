"""
快速执行序列化器
"""
from rest_framework import serializers
from apps.hosts.models import Host, HostGroup


class QuickScriptExecuteSerializer(serializers.Serializer):
    """快速脚本执行序列化器"""
    
    name = serializers.CharField(max_length=200, default="快速脚本执行")
    script_content = serializers.CharField(help_text="脚本内容")
    script_type = serializers.ChoiceField(
        choices=[
            ('shell', 'Shell'),
            ('python', 'Python'),
            ('powershell', 'PowerShell'),
            ('perl', 'Perl'),
            ('javascript', 'JavaScript'),
            ('go', 'Go'),
        ],
        default='shell',
        help_text="脚本类型"
    )

    # 变量和参数
    global_variables = serializers.DictField(
        required=False,
        allow_empty=True,
        help_text="全局变量，支持在脚本中使用${VAR_NAME}或$VAR_NAME格式"
    )
    positional_args = serializers.ListField(
        child=serializers.CharField(),
        required=False,
        allow_empty=True,
        help_text="位置参数列表，按顺序传递给脚本"
    )

    # 目标选择（统一使用target_host_ids格式）
    target_host_ids = serializers.ListField(
        child=serializers.IntegerField(),
        required=False,
        allow_empty=True,
        help_text="目标主机ID列表"
    )
    
    # 动态IP列表（可选，用于动态IP输入）
    dynamic_ips = serializers.ListField(
        child=serializers.CharField(),
        required=False,
        allow_empty=True,
        help_text="动态IP地址列表"
    )
    
    # 执行配置
    timeout = serializers.IntegerField(default=300, min_value=1, max_value=3600, help_text="超时时间(秒)")
    execution_mode = serializers.ChoiceField(
        choices=[
            ('parallel', '并行执行'),
            ('serial', '串行执行'),
            ('rolling', '滚动执行'),
        ],
        default='parallel',
        help_text="执行模式"
    )
    rolling_strategy = serializers.ChoiceField(
        choices=[
            ('fail_pause', '执行失败就暂停'),
            ('ignore_error', '忽略错误继续执行'),
        ],
        default='fail_pause',
        help_text="滚动执行策略"
    )
    rolling_batch_size = serializers.IntegerField(default=20, min_value=1, max_value=100, help_text="滚动批次大小(百分比)")
    rolling_batch_delay = serializers.IntegerField(default=0, min_value=0, help_text="批次间延迟(秒)")
    
    def validate(self, attrs):
        """验证数据"""
        target_host_ids = attrs.get('target_host_ids', []) or []
        target_group_ids = attrs.get('target_group_ids', []) or []
        
        # 必须至少指定一种目标选择方式
        if not target_host_ids and not target_group_ids:
            raise serializers.ValidationError("必须指定至少一个目标主机或分组")
        
        # 验证target_host_ids格式
        for host_id in target_host_ids:
            if not isinstance(host_id, int) or host_id <= 0:
                raise serializers.ValidationError("主机ID必须是正整数")
        
        # 验证target_group_ids格式
        for group_id in target_group_ids:
            if not isinstance(group_id, int) or group_id <= 0:
                raise serializers.ValidationError("分组ID必须是正整数")
        
        script_content = attrs.get('script_content', '').strip()
        if not script_content:
            raise serializers.ValidationError("脚本内容不能为空")
        
        return attrs


class QuickFileTransferSerializer(serializers.Serializer):
    """快速文件传输序列化器（仅支持 local/server 输入，artifact 为中间产物）"""

    name = serializers.CharField(max_length=200, default="快速文件传输")
    # 统一使用 sources 描述来源；支持 local（multipart 上传）或 server（控制面主动拉取）
    sources = serializers.JSONField(
        required=True,
        help_text="文件来源数组，示例: {type:'local',file_field:'file0',remote_path:'/tmp/x'} 或 {type:'server',source_server_host:'1.1.1.1:80',source_server_path:'/a.tar.gz',account_id:1,remote_path:'/tmp/a.tar.gz'}"
    )
    # 执行账号相关
    global_variables = serializers.DictField(required=False, allow_null=True, help_text="全局变量（包含执行账号信息）")

    # 传输选项
    overwrite_policy = serializers.ChoiceField(
        choices=[
            ('overwrite', '强制覆盖'),
            ('skip', '存在跳过'),
            ('backup', '备份后覆盖'),
            ('fail', '存在则失败'),
        ],
        default='overwrite',
        help_text="覆盖策略"
    )

    # 目标选择（统一使用target_host_ids格式）
    target_host_ids = serializers.ListField(
        child=serializers.IntegerField(),
        required=False,
        allow_empty=True,
        help_text="目标主机ID列表"
    )

    # 动态IP列表（可选，用于动态IP输入）
    dynamic_ips = serializers.ListField(
        child=serializers.CharField(),
        required=False,
        allow_empty=True,
        help_text="动态IP地址列表"
    )

    # 执行配置
    timeout = serializers.IntegerField(default=300, min_value=1, max_value=3600, help_text="超时时间(秒)")
    bandwidth_limit = serializers.IntegerField(
        required=False,
        min_value=0,
        max_value=1000000,  # 最大1GB/s
        help_text="带宽限制(MB/s)，0表示不限制",
        allow_null=True
    )
    execution_mode = serializers.ChoiceField(
        choices=[
            ('parallel', '并行执行'),
            ('serial', '串行执行'),
            ('rolling', '滚动执行'),
        ],
        default='parallel',
        help_text="执行模式"
    )
    rolling_strategy = serializers.ChoiceField(
        choices=[
            ('fail_pause', '执行失败就暂停'),
            ('ignore_error', '忽略错误继续执行'),
        ],
        default='fail_pause',
        help_text="滚动执行策略"
    )
    rolling_batch_size = serializers.IntegerField(default=20, min_value=1, max_value=100, help_text="滚动批次大小(百分比)")
    rolling_batch_delay = serializers.IntegerField(default=0, min_value=0, help_text="批次间延迟(秒)")

    def validate(self, attrs):
        """验证数据"""
        target_host_ids = attrs.get('target_host_ids', []) or []
        dynamic_ips = attrs.get('dynamic_ips', []) or []

        # 扁平化 sources 并校验结构
        sources_raw = attrs.get('sources')
        if sources_raw is None:
            raise serializers.ValidationError("必须提供 sources 字段，描述本地或服务器文件来源")

        flat_sources = []
        if isinstance(sources_raw, list):
            for item in sources_raw:
                if isinstance(item, list):
                    flat_sources.extend(item)
                else:
                    flat_sources.append(item)
        elif isinstance(sources_raw, dict):
            flat_sources = [sources_raw]
        else:
            raise serializers.ValidationError("sources 必须是数组或对象")

        for item in flat_sources:
            if not isinstance(item, dict):
                raise serializers.ValidationError("sources 每一项必须是对象(dict)")

        attrs['sources'] = flat_sources

        # 必须至少指定一种目标选择方式
        if not target_host_ids and not dynamic_ips:
            raise serializers.ValidationError("必须指定至少一个目标主机或IP地址")

        # 验证主机ID格式
        for host_id in target_host_ids:
            if not isinstance(host_id, int) or host_id <= 0:
                raise serializers.ValidationError("主机ID必须是正整数")

        # 验证dynamic_ips格式
        from utils.validators import validate_host_ip
        from django.core.exceptions import ValidationError
        for ip in dynamic_ips:
            try:
                validate_host_ip(ip)
            except ValidationError as e:
                raise serializers.ValidationError(f"无效的IP地址: {ip}")

        # 校验每个 source 的必需字段
        for s in attrs['sources']:
            stype = s.get('type')
            if stype not in ('local', 'server'):
                raise serializers.ValidationError("sources 中的 type 必须是 'local' 或 'server'")
            if stype == 'local':
                if not s.get('file_field'):
                    raise serializers.ValidationError("local 类型必须包含 file_field（multipart 中文件字段名）")
                if not s.get('remote_path'):
                    raise serializers.ValidationError("local 类型必须包含 remote_path")
            else:  # server 拉取
                if not s.get('source_server_host') or not s.get('source_server_path'):
                    raise serializers.ValidationError("server 类型必须包含 source_server_host 与 source_server_path")
                if s.get('account_id') is None or not isinstance(s.get('account_id'), int):
                    raise serializers.ValidationError("server 类型必须包含 account_id（整数）")
                if s.get('auth_headers') and not isinstance(s.get('auth_headers'), dict):
                    raise serializers.ValidationError("server 类型中 auth_headers 必须为对象")

        return attrs
