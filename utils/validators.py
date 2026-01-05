from django.core.exceptions import ValidationError
from croniter import croniter
import ipaddress


def validate_cron_expression(value):
    """
    验证cron表达式的有效性
    """
    if not value or not isinstance(value, str):
        raise ValidationError('cron表达式不能为空')
    
    # 去除首尾空格
    value = value.strip()
    
    # 基本格式检查：应该有5个或6个字段（秒 分 时 日 月 周 [年]）
    fields = value.split()
    if len(fields) not in [5, 6]:
        raise ValidationError(
            'cron表达式格式错误，应该包含5个字段（分 时 日 月 周）或6个字段（秒 分 时 日 月 周）'
        )
    
    try:
        # 使用croniter验证表达式
        if croniter.is_valid(value):
            return value
        else:
            raise ValidationError('无效的cron表达式')
    except Exception as e:
        raise ValidationError(f'cron表达式验证失败: {str(e)}')


def validate_timezone(value):
    """
    验证时区字符串的有效性
    """
    if not value:
        return value
    
    try:
        import pytz
        pytz.timezone(value)
        return value
    except pytz.exceptions.UnknownTimeZoneError:
        raise ValidationError(f'无效的时区: {value}')


def validate_host_ip(value):
    """
    验证IP地址格式（支持IPv4和IPv6）
    """
    if not value:
        return value
    
    if not isinstance(value, str):
        raise ValidationError('IP地址必须是字符串类型')
    
    # 去除首尾空格
    value = value.strip()
    
    try:
        # 使用ipaddress库验证IP地址（自动支持IPv4和IPv6）
        ipaddress.ip_address(value)
        return value
    except ValueError:
        raise ValidationError(f'无效的IP地址格式: {value}')


def validate_port(value):
    """
    验证端口号
    """
    if value is None:
        return value
    
    if not isinstance(value, int) or value < 1 or value > 65535:
        raise ValidationError('端口号必须在1-65535之间')
    
    return value


def validate_script_type(value):
    """
    验证脚本类型
    """
    valid_types = ['shell', 'python', 'powershell', 'batch']
    
    if value not in valid_types:
        raise ValidationError(f'无效的脚本类型，支持的类型: {", ".join(valid_types)}')
    
    return value


def validate_json_dict(value):
    """
    验证json字典格式
    """
    if value is None:
        return {}
    
    if not isinstance(value, dict):
        raise ValidationError('必须是字典格式')
    
    return value


def validate_json_list(value):
    """
    验证json列表格式
    """
    if value is None:
        return []
    
    if not isinstance(value, list):
        raise ValidationError('必须是列表格式')
    
    return value
