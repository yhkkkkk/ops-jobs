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
        required=True,
        allow_empty=False,
        help_text="目标主机ID列表"
    )
    
    # 执行配置
    timeout = serializers.IntegerField(default=300, min_value=1, max_value=3600, help_text="超时时间(秒)")
    use_fabric = serializers.BooleanField(default=False, help_text="是否使用Fabric执行引擎")
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
        target_host_ids = attrs.get('target_host_ids', [])
        
        # 验证target_host_ids格式
        if not target_host_ids:
            raise serializers.ValidationError("必须指定至少一个目标主机")
        
        for host_id in target_host_ids:
            if not isinstance(host_id, int) or host_id <= 0:
                raise serializers.ValidationError("主机ID必须是正整数")
        
        script_content = attrs.get('script_content', '').strip()
        if not script_content:
            raise serializers.ValidationError("脚本内容不能为空")
        
        return attrs


class QuickFileTransferSerializer(serializers.Serializer):
    """快速文件传输序列化器"""
    
    name = serializers.CharField(max_length=200, default="快速文件传输")
    transfer_type = serializers.ChoiceField(
        choices=[
            ('local_upload', '从本地上传'),
            ('server_upload', '从服务器上传'),
        ],
        default='local_upload',
        help_text="传输类型"
    )

    local_path = serializers.CharField(required=False, allow_blank=True, help_text="本地文件路径（本地上传时使用）")
    remote_path = serializers.CharField(help_text="远程文件路径")

    # 服务器上传相关字段
    source_server_host = serializers.CharField(required=False, allow_blank=True, help_text="源服务器地址")
    source_server_user = serializers.CharField(required=False, allow_blank=True, help_text="源服务器用户名")
    source_server_path = serializers.CharField(required=False, allow_blank=True, help_text="源服务器文件路径")
    
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
        required=True,
        allow_empty=False,
        help_text="目标主机ID列表"
    )
    
    # 执行配置
    timeout = serializers.IntegerField(default=300, min_value=1, max_value=3600, help_text="超时时间(秒)")
    bandwidth_limit = serializers.IntegerField(
        required=False,
        min_value=0,
        max_value=1000000,  # 最大1GB/s
        help_text="带宽限制(KB/s)，0表示不限制",
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
        target_host_ids = attrs.get('target_host_ids', [])
        
        if not target_host_ids:
            raise serializers.ValidationError("必须指定至少一个目标主机")
        
        # 验证主机ID格式
        for host_id in target_host_ids:
            if not isinstance(host_id, int) or host_id <= 0:
                raise serializers.ValidationError("主机ID必须是正整数")
        
        transfer_type = attrs.get('transfer_type')
        local_path = attrs.get('local_path', '').strip()
        remote_path = attrs.get('remote_path', '').strip()

        # 验证远程路径
        if not remote_path:
            raise serializers.ValidationError("远程路径不能为空")

        # 根据传输类型验证必要字段
        if transfer_type == 'local_upload':
            if not local_path:
                raise serializers.ValidationError("本地上传模式下，本地路径不能为空")
        elif transfer_type == 'server_upload':
            source_server_host = attrs.get('source_server_host', '').strip()
            source_server_user = attrs.get('source_server_user', '').strip()
            source_server_path = attrs.get('source_server_path', '').strip()

            if not source_server_host:
                raise serializers.ValidationError("服务器上传模式下，源服务器地址不能为空")
            if not source_server_user:
                raise serializers.ValidationError("服务器上传模式下，源服务器用户名不能为空")
            if not source_server_path:
                raise serializers.ValidationError("服务器上传模式下，源服务器文件路径不能为空")

        return attrs