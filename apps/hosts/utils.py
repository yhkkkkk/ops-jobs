"""
主机管理工具函数
包含加密解密、SSH连接等工具函数
"""
import base64
import logging
from django.conf import settings

logger = logging.getLogger(__name__)


def get_encryption_key():
    """获取加密密钥"""
    try:
        from cryptography.fernet import Fernet
        
        # 获取加密密钥
        secret_key = getattr(settings, 'SECRET_KEY', 'default-secret-key')
        key_bytes = secret_key.encode()[:32].ljust(32, b'0')
        key = base64.urlsafe_b64encode(key_bytes)
        
        return Fernet(key)
    except ImportError:
        logger.error("cryptography库未安装，无法进行密码加密")
        return None
    except Exception as e:
        logger.error(f"获取加密密钥失败: {e}")
        return None


def encrypt_password(password: str) -> str:
    """加密密码"""
    if not password:
        return password
    
    try:
        f = get_encryption_key()
        if f is None:
            return password  # 如果加密失败，返回原密码
        
        encrypted = f.encrypt(password.encode())
        return base64.urlsafe_b64encode(encrypted).decode()
    except Exception as e:
        logger.error(f"密码加密失败: {e}")
        return password  # 如果加密失败，返回原密码


def decrypt_password(encrypted_password: str) -> str:
    """解密密码"""
    if not encrypted_password:
        return encrypted_password
    
    try:
        f = get_encryption_key()
        if f is None:
            return encrypted_password  # 如果解密失败，返回原密码
        
        encrypted_bytes = base64.urlsafe_b64decode(encrypted_password.encode())
        decrypted = f.decrypt(encrypted_bytes)
        return decrypted.decode()
    except Exception as e:
        logger.error(f"密码解密失败: {e}")
        return encrypted_password  # 如果解密失败，返回原密码


def test_ssh_connection(host_info: dict) -> dict:
    """测试SSH连接"""
    try:
        from .fabric_ssh_manager import fabric_ssh_manager
        from .models import Host
        
        # 如果传入的是字典，需要转换为Host对象
        if isinstance(host_info, dict):
            host = Host.objects.get(id=host_info['id'])
        else:
            host = host_info
        
        result = fabric_ssh_manager.execute_script(
            host=host,
            script_content='echo "connection_test"',
            script_type='shell',
            timeout=10
        )
        
        return {
            'success': result['success'],
            'message': result.get('message', '连接测试完成'),
            'latency': 0,  # Fabric不提供延迟信息
            'system_info': {}
        }
    except Exception as e:
        logger.error(f"SSH连接测试失败: {e}")
        return {
            'success': False,
            'message': f'连接测试失败: {str(e)}',
            'latency': 0,
            'system_info': {}
        }


def validate_host_connection_info(host_data: dict) -> dict:
    """验证主机连接信息"""
    errors = {}
    
    # 检查必需字段：至少需要内网IP或外网IP之一
    if not host_data.get('internal_ip') and not host_data.get('public_ip'):
        errors['ip'] = '主机至少需要配置内网IP或外网IP之一'
    
    # 检查账号
    if not host_data.get('account'):
        errors['account'] = '主机必须配置服务器账号'
    
    # 检查端口
    port = host_data.get('port', 22)
    if not isinstance(port, int) or port < 1 or port > 65535:
        errors['port'] = '端口必须是1-65535之间的整数'
    
    return errors


def format_host_info(host) -> dict:
    """格式化主机信息用于任务执行"""
    return {
        'id': host.id,
        'name': host.name,
        'ip_address': host.ip_address,  # 使用属性，返回 internal_ip 或 public_ip
        'internal_ip': host.internal_ip,
        'public_ip': host.public_ip,
        'port': host.port or 22,
        'account_id': host.account.id if host.account else None,
        'account_name': host.account.name if host.account else None,
        'description': host.description or '',
        'status': host.status
    }


def get_host_system_info_script() -> str:
    """获取主机系统信息的脚本"""
    return """
echo "=== System Information ==="
echo "OS Release:"
cat /etc/os-release 2>/dev/null || echo "N/A"
echo ""
echo "CPU Info:"
lscpu 2>/dev/null || echo "N/A"
echo ""
echo "Memory Info:"
free -h 2>/dev/null || echo "N/A"
echo ""
echo "Disk Info:"
df -h 2>/dev/null || echo "N/A"
echo ""
echo "Network Info:"
ip addr show 2>/dev/null || ifconfig 2>/dev/null || echo "N/A"
echo ""
echo "Uptime:"
uptime 2>/dev/null || echo "N/A"
"""


def parse_system_info(raw_output: str) -> dict:
    """解析系统信息输出"""
    info = {
        'os_release': '',
        'cpu_info': '',
        'memory_info': '',
        'disk_info': '',
        'network_info': '',
        'uptime': '',
        'raw_output': raw_output
    }
    
    try:
        sections = raw_output.split('===')
        for section in sections:
            if 'OS Release:' in section:
                info['os_release'] = section.split('OS Release:')[1].strip()
            elif 'CPU Info:' in section:
                info['cpu_info'] = section.split('CPU Info:')[1].strip()
            elif 'Memory Info:' in section:
                info['memory_info'] = section.split('Memory Info:')[1].strip()
            elif 'Disk Info:' in section:
                info['disk_info'] = section.split('Disk Info:')[1].strip()
            elif 'Network Info:' in section:
                info['network_info'] = section.split('Network Info:')[1].strip()
            elif 'Uptime:' in section:
                info['uptime'] = section.split('Uptime:')[1].strip()
    except Exception as e:
        logger.warning(f"解析系统信息失败: {e}")
    
    return info
