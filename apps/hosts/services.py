"""
主机管理服务
提供主机连接测试、状态检查、批量操作等功能
基于Fabric SSH管理器
"""
import logging
from typing import List, Dict, Any
from django.utils import timezone
from django.db import transaction
from django.contrib.contenttypes.models import ContentType
from .models import Host, HostGroup
from .fabric_ssh_manager import fabric_ssh_manager, FabricSSHError
from utils.audit_service import AuditLogService

logger = logging.getLogger(__name__)


class HostService:
    """主机管理服务"""
    
    @staticmethod
    def test_host_connection(host: Host, user=None) -> Dict[str, Any]:
        """测试主机连接"""
        try:
            # 使用Fabric执行简单的echo命令测试连接
            result = fabric_ssh_manager.execute_script(
                host=host,
                script_content='echo "connection_test"',
                script_type='shell',
                timeout=10
            )
            
            # 更新主机状态
            if result['success']:
                host.status = 'online'
                host.last_check_time = timezone.now()
            else:
                host.status = 'offline'
            
            host.save(update_fields=['status', 'last_check_time'])
            
            # 记录操作日志
            if user:
                AuditLogService.log_action(
                    user=user,
                    action='test_connection',
                    description=f'测试主机连接: {host.name} - {"成功" if result["success"] else "失败"}',
                    ip_address='127.0.0.1',
                    success=result["success"],
                    resource_type=ContentType.objects.get_for_model(host),
                    resource_id=host.id,
                    resource_name=host.name
                )
            
            return {
                'success': result['success'],
                'message': result.get('message', '连接测试完成'),
                'stdout': result.get('stdout', ''),
                'stderr': result.get('stderr', '')
            }
            
        except FabricSSHError as e:
            # 更新主机状态为离线
            host.status = 'offline'
            host.save(update_fields=['status'])
            
            result = {
                'success': False,
                'message': str(e),
                'error_type': 'connection_error'
            }
            
            # 记录操作日志
            if user:
                AuditLogService.log_action(
                    user=user,
                    action='test_connection',
                    description=f'测试主机连接失败: {host.name} - {str(e)}',
                    ip_address='127.0.0.1',
                    success=False,
                    resource_type=ContentType.objects.get_for_model(host),
                    resource_id=host.id,
                    resource_name=host.name
                )
            
            return result
        except Exception as e:
            logger.error(f"测试主机连接失败: {host.name} - {e}")
            host.status = 'offline'
            host.save(update_fields=['status'])
            
            return {
                'success': False,
                'message': f'连接测试异常: {e}',
                'latency': 0,
                'system_info': {}
            }
    
    @staticmethod
    def batch_test_connections(hosts: List[Host], user=None) -> Dict[str, Any]:
        """批量测试主机连接"""
        results = {
            'total': len(hosts),
            'success': 0,
            'failed': 0,
            'details': []
        }
        
        for host in hosts:
            result = HostService.test_host_connection(host, user)
            
            if result['success']:
                results['success'] += 1
            else:
                results['failed'] += 1
            
            results['details'].append({
                'host_id': host.id,
                'host_name': host.name,
                'ip_address': host.ip_address,
                'result': result
            })
        
        return results
    
    @staticmethod
    def check_host_status(host: Host) -> str:
        """检查主机状态"""
        try:
            result = fabric_ssh_manager.execute_script(
                host=host,
                script_content='echo "status_check"',
                script_type='shell',
                timeout=10
            )
            return 'online' if result['success'] else 'offline'
        except Exception:
            return 'offline'
    
    @staticmethod
    def batch_check_status(hosts: List[Host]) -> Dict[str, int]:
        """批量检查主机状态"""
        status_count = {
            'online': 0,
            'offline': 0,
            'unknown': 0
        }
        
        for host in hosts:
            status = HostService.check_host_status(host)
            host.status = status
            host.last_check_time = timezone.now()
            host.save(update_fields=['status', 'last_check_time'])
            
            status_count[status] += 1
        
        return status_count
    
    @staticmethod
    def get_host_system_info(host: Host) -> Dict[str, Any]:
        """获取主机系统信息"""
        try:
            # 使用Fabric获取系统信息
            script_content = """
echo "=== OS Release ==="
cat /etc/os-release 2>/dev/null || echo "N/A"
echo "=== CPU Info ==="
lscpu 2>/dev/null || echo "N/A"
echo "=== Memory Info ==="
free -h 2>/dev/null || echo "N/A"
echo "=== Disk Info ==="
df -h 2>/dev/null || echo "N/A"
"""
            
            result = fabric_ssh_manager.execute_script(
                host=host,
                script_content=script_content,
                script_type='shell',
                timeout=30
            )
            
            if result['success']:
                return {
                    'success': True,
                    'system_info': {
                        'raw_output': result['stdout']
                    }
                }
            else:
                return {
                    'success': False,
                    'message': result.get('message', '获取系统信息失败'),
                    'system_info': {}
                }
                
        except Exception as e:
            logger.error(f"获取主机系统信息失败: {host.name} - {e}")
            return {
                'success': False,
                'message': f'获取系统信息失败: {e}',
                'system_info': {}
            }
    
    @staticmethod
    def collect_system_info(host: Host, user=None) -> Dict[str, Any]:
        """收集主机系统信息"""
        try:
            # 系统信息收集脚本 - 优化版本，增强兼容性
            collect_script = """
#!/bin/bash
echo "=== SYSTEM_INFO_START ==="

# 基本系统信息
echo "HOSTNAME=$(hostname 2>/dev/null || echo 'unknown')"

# 操作系统版本检测 - 多种方式兼容
if [ -f /etc/os-release ]; then
    OS_VERSION=$(grep PRETTY_NAME /etc/os-release | cut -d'"' -f2 2>/dev/null)
elif [ -f /etc/redhat-release ]; then
    OS_VERSION=$(cat /etc/redhat-release 2>/dev/null)
elif [ -f /etc/debian_version ]; then
    OS_VERSION="Debian $(cat /etc/debian_version 2>/dev/null)"
else
    OS_VERSION=$(uname -s 2>/dev/null || echo 'unknown')
fi
echo "OS_VERSION=$OS_VERSION"

echo "KERNEL_VERSION=$(uname -r 2>/dev/null || echo 'unknown')"

# 硬件信息 - 多种方式兼容
# CPU核心数
if command -v nproc >/dev/null 2>&1; then
    CPU_CORES=$(nproc)
elif [ -f /proc/cpuinfo ]; then
    CPU_CORES=$(grep -c ^processor /proc/cpuinfo 2>/dev/null || echo 'unknown')
else
    CPU_CORES='unknown'
fi
echo "CPU_CORES=$CPU_CORES"

# CPU模型和架构
CPU_MODEL='unknown'
CPU_ARCH='unknown'
OS_ARCH='unknown'

if [ -f /proc/cpuinfo ]; then
    CPU_MODEL=$(grep "model name" /proc/cpuinfo | head -1 | cut -d: -f2 | sed 's/^ *//' 2>/dev/null || echo 'unknown')
fi

if command -v lscpu >/dev/null 2>&1; then
    if [ "$CPU_MODEL" = "unknown" ]; then
        CPU_MODEL=$(lscpu | grep "Model name:" | cut -d: -f2 | sed 's/^ *//' 2>/dev/null || echo 'unknown')
    fi
    CPU_ARCH=$(lscpu | grep "Architecture:" | awk '{print $2}' 2>/dev/null || echo 'unknown')
fi

if command -v uname >/dev/null 2>&1; then
    if [ "$CPU_ARCH" = "unknown" ]; then
        CPU_ARCH=$(uname -m 2>/dev/null || echo 'unknown')
    fi
    OS_ARCH=$(uname -m 2>/dev/null || echo 'unknown')
fi

echo "CPU_MODEL=$CPU_MODEL"
echo "CPU_ARCH=$CPU_ARCH"
echo "OS_ARCH=$OS_ARCH"

# 内存信息
if [ -f /proc/meminfo ]; then
    MEMORY_KB=$(grep MemTotal /proc/meminfo | awk '{print $2}' 2>/dev/null)
    if [ -n "$MEMORY_KB" ] && [ "$MEMORY_KB" != "" ]; then
        MEMORY_GB=$((MEMORY_KB / 1024 / 1024))
    else
        MEMORY_GB='unknown'
    fi
else
    MEMORY_GB='unknown'
fi
echo "MEMORY_GB=$MEMORY_GB"

# 磁盘信息
if command -v df >/dev/null 2>&1; then
    DISK_GB=$(df / 2>/dev/null | awk 'NR==2{printf "%.0f", $2/1024/1024}' 2>/dev/null || echo 'unknown')
else
    DISK_GB='unknown'
fi
echo "DISK_GB=$DISK_GB"

# 网络信息 - 多种方式获取内网IP
INTERNAL_IP='unknown'
if command -v hostname >/dev/null 2>&1; then
    INTERNAL_IP=$(hostname -I 2>/dev/null | awk '{print $1}')
fi
if [ "$INTERNAL_IP" = "" ] || [ "$INTERNAL_IP" = "unknown" ]; then
    if command -v ip >/dev/null 2>&1; then
        INTERNAL_IP=$(ip route get 1 2>/dev/null | awk '{print $NF;exit}' 2>/dev/null || echo 'unknown')
    fi
fi
if [ "$INTERNAL_IP" = "" ] || [ "$INTERNAL_IP" = "unknown" ]; then
    if command -v ifconfig >/dev/null 2>&1; then
        INTERNAL_IP=$(ifconfig 2>/dev/null | grep -E 'inet.*192\\.168\\.|inet.*10\\.|inet.*172\\.' | head -1 | awk '{print $2}' | cut -d: -f2 2>/dev/null || echo 'unknown')
    fi
fi
echo "INTERNAL_IP=$INTERNAL_IP"

# 获取更多网络信息
PUBLIC_IP='unknown'
INTERNAL_MAC='unknown'
EXTERNAL_MAC='unknown'
GATEWAY='unknown'
DNS_SERVERS='unknown'

# 获取公网IP
if command -v curl >/dev/null 2>&1; then
    PUBLIC_IP=$(timeout 5 curl -s http://ipinfo.io/ip 2>/dev/null || timeout 5 curl -s http://icanhazip.com 2>/dev/null || echo 'unknown')
fi

# 获取MAC地址
if command -v ip >/dev/null 2>&1; then
    # 获取默认路由接口的MAC地址作为内网MAC
    DEFAULT_INTERFACE=$(ip route | grep default | awk '{print $5}' | head -1)
    if [ -n "$DEFAULT_INTERFACE" ]; then
        INTERNAL_MAC=$(ip link show $DEFAULT_INTERFACE 2>/dev/null | grep "link/ether" | awk '{print $2}' || echo 'unknown')
    fi

    # 获取网关
    GATEWAY=$(ip route | grep default | awk '{print $3}' | head -1 || echo 'unknown')
elif command -v ifconfig >/dev/null 2>&1; then
    # 使用ifconfig获取第一个非lo接口的MAC地址
    INTERNAL_MAC=$(ifconfig 2>/dev/null | grep -E "ether|HWaddr" | head -1 | awk '{print $2}' | cut -d: -f1-6 || echo 'unknown')

    # 获取网关
    if command -v route >/dev/null 2>&1; then
        GATEWAY=$(route -n 2>/dev/null | grep "^0.0.0.0" | awk '{print $2}' | head -1 || echo 'unknown')
    fi
fi

# 获取DNS服务器
if [ -f /etc/resolv.conf ]; then
    DNS_SERVERS=$(grep nameserver /etc/resolv.conf 2>/dev/null | awk '{print $2}' | tr '\n' ',' | sed 's/,$//' || echo 'unknown')
fi

echo "PUBLIC_IP=$PUBLIC_IP"
echo "INTERNAL_MAC=$INTERNAL_MAC"
echo "EXTERNAL_MAC=$EXTERNAL_MAC"
echo "GATEWAY=$GATEWAY"
echo "DNS_SERVERS=$DNS_SERVERS"

# 云厂商检测 - 简化版本，减少网络依赖
CLOUD_PROVIDER='unknown'
INSTANCE_ID='unknown'
REGION='unknown'
ZONE='unknown'

# AWS检测
if [ -f /sys/hypervisor/uuid ] && [ "$(head -c 3 /sys/hypervisor/uuid 2>/dev/null)" = "ec2" ]; then
    CLOUD_PROVIDER='aws'
    # 尝试获取AWS元数据，但不依赖网络
    if command -v curl >/dev/null 2>&1; then
        INSTANCE_ID=$(timeout 3 curl -s http://169.254.169.254/latest/meta-data/instance-id 2>/dev/null || echo 'unknown')
        REGION=$(timeout 3 curl -s http://169.254.169.254/latest/meta-data/placement/region 2>/dev/null || echo 'unknown')
        ZONE=$(timeout 3 curl -s http://169.254.169.254/latest/meta-data/placement/availability-zone 2>/dev/null || echo 'unknown')
    fi
# 阿里云检测
elif [ -f /sys/class/dmi/id/sys_vendor ] && grep -q "Alibaba" /sys/class/dmi/id/sys_vendor 2>/dev/null; then
    CLOUD_PROVIDER='aliyun'
    if command -v curl >/dev/null 2>&1; then
        INSTANCE_ID=$(timeout 3 curl -s http://100.100.100.200/latest/meta-data/instance-id 2>/dev/null || echo 'unknown')
        REGION=$(timeout 3 curl -s http://100.100.100.200/latest/meta-data/region-id 2>/dev/null || echo 'unknown')
        ZONE=$(timeout 3 curl -s http://100.100.100.200/latest/meta-data/zone-id 2>/dev/null || echo 'unknown')
    fi
# 腾讯云检测
elif [ -f /sys/class/dmi/id/sys_vendor ] && grep -q "Tencent" /sys/class/dmi/id/sys_vendor 2>/dev/null; then
    CLOUD_PROVIDER='tencent'
    if command -v curl >/dev/null 2>&1; then
        INSTANCE_ID=$(timeout 3 curl -s http://metadata.tencentyun.com/latest/meta-data/instance-id 2>/dev/null || echo 'unknown')
        REGION=$(timeout 3 curl -s http://metadata.tencentyun.com/latest/meta-data/placement/region 2>/dev/null || echo 'unknown')
        ZONE=$(timeout 3 curl -s http://metadata.tencentyun.com/latest/meta-data/placement/zone 2>/dev/null || echo 'unknown')
    fi
fi

echo "CLOUD_PROVIDER=$CLOUD_PROVIDER"
echo "INSTANCE_ID=$INSTANCE_ID"
echo "REGION=$REGION"
echo "ZONE=$ZONE"

echo "=== SYSTEM_INFO_END ==="
"""

            # 执行收集脚本
            result = fabric_ssh_manager.execute_script(
                host=host,
                script_content=collect_script,
                script_type='shell',
                timeout=60
            )

            if not result['success']:
                error_msg = result.get('message') or result.get('error') or '未知错误'
                return {
                    'success': False,
                    'message': f'系统信息收集失败: {error_msg}',
                    'system_info': {}
                }

            # 解析输出
            output = result.get('stdout', '') or result.get('output', '')
            system_info = {}

            # 提取系统信息
            lines = output.split('\n')
            in_info_section = False

            for line in lines:
                line = line.strip()
                if line == "=== SYSTEM_INFO_START ===":
                    in_info_section = True
                    continue
                elif line == "=== SYSTEM_INFO_END ===":
                    break
                elif in_info_section and '=' in line:
                    key, value = line.split('=', 1)
                    if value and value != 'unknown':
                        system_info[key] = value

            # 更新主机信息
            update_fields = []

            if 'HOSTNAME' in system_info:
                host.hostname = system_info['HOSTNAME']
                update_fields.append('hostname')

            if 'OS_VERSION' in system_info:
                host.os_version = system_info['OS_VERSION']
                update_fields.append('os_version')

            if 'KERNEL_VERSION' in system_info:
                host.kernel_version = system_info['KERNEL_VERSION']
                update_fields.append('kernel_version')

            if 'CPU_CORES' in system_info and system_info['CPU_CORES'].isdigit():
                host.cpu_cores = int(system_info['CPU_CORES'])
                update_fields.append('cpu_cores')

            if 'MEMORY_GB' in system_info and system_info['MEMORY_GB'].isdigit():
                host.memory_gb = float(system_info['MEMORY_GB'])
                update_fields.append('memory_gb')

            if 'DISK_GB' in system_info and system_info['DISK_GB'].isdigit():
                host.disk_gb = float(system_info['DISK_GB'])
                update_fields.append('disk_gb')

            if 'INTERNAL_IP' in system_info:
                host.internal_ip = system_info['INTERNAL_IP']
                update_fields.append('internal_ip')

            if 'CLOUD_PROVIDER' in system_info and system_info['CLOUD_PROVIDER'] != 'unknown':
                host.cloud_provider = system_info['CLOUD_PROVIDER']
                update_fields.append('cloud_provider')

            if 'INSTANCE_ID' in system_info:
                host.instance_id = system_info['INSTANCE_ID']
                update_fields.append('instance_id')

            if 'REGION' in system_info:
                host.region = system_info['REGION']
                update_fields.append('region')

            if 'ZONE' in system_info:
                host.zone = system_info['ZONE']
                update_fields.append('zone')

            # 网络信息
            if 'PUBLIC_IP' in system_info:
                host.public_ip = system_info['PUBLIC_IP']
                update_fields.append('public_ip')

            if 'INTERNAL_MAC' in system_info:
                host.internal_mac = system_info['INTERNAL_MAC']
                update_fields.append('internal_mac')

            if 'EXTERNAL_MAC' in system_info:
                host.external_mac = system_info['EXTERNAL_MAC']
                update_fields.append('external_mac')

            if 'GATEWAY' in system_info:
                host.gateway = system_info['GATEWAY']
                update_fields.append('gateway')

            if 'DNS_SERVERS' in system_info:
                host.dns_servers = system_info['DNS_SERVERS']
                update_fields.append('dns_servers')

            # 系统详细信息
            if 'CPU_MODEL' in system_info:
                host.cpu_model = system_info['CPU_MODEL'][:200]  # 限制长度
                update_fields.append('cpu_model')

            if 'OS_ARCH' in system_info:
                host.os_arch = system_info['OS_ARCH']
                update_fields.append('os_arch')

            if 'CPU_ARCH' in system_info:
                host.cpu_arch = system_info['CPU_ARCH']
                update_fields.append('cpu_arch')

            # 更新最后检查时间
            host.last_check_time = timezone.now()
            update_fields.append('last_check_time')

            # 保存更新
            if update_fields:
                host.save(update_fields=update_fields)

            # 记录操作日志
            if user:
                AuditLogService.log_action(
                    user=user,
                    action='collect_system_info',
                    description=f'收集主机系统信息: {host.name} - 成功更新 {len(update_fields)} 个字段',
                    ip_address='127.0.0.1',
                    success=True,
                    resource_type=ContentType.objects.get_for_model(host),
                    resource_id=host.id,
                    resource_name=host.name,
                    extra_data={'updated_fields': update_fields, 'system_info': system_info}
                )

            return {
                'success': True,
                'message': f'系统信息收集成功，更新了 {len(update_fields)} 个字段',
                'system_info': system_info,
                'updated_fields': update_fields
            }

        except Exception as e:
            logger.error(f"收集主机系统信息失败: {host.name} - {e}")
            return {
                'success': False,
                'message': f'收集系统信息失败: {e}',
                'system_info': {}
            }

    @staticmethod
    def execute_command_on_host(host: Host, command: str, timeout: int = 30, user=None) -> Dict[str, Any]:
        """在主机上执行命令"""
        try:
            result = fabric_ssh_manager.execute_script(
                host=host,
                script_content=command,
                script_type='shell',
                timeout=timeout
            )
            
            # 记录操作日志
            if user:
                AuditLogService.log_action(
                    user=user,
                    action='execute_script',
                    description=f'执行命令: {command} (退出码: {result["exit_code"]})',
                    ip_address='127.0.0.1',
                    success=result['success'],
                    resource_type=ContentType.objects.get_for_model(host),
                    resource_id=host.id,
                    resource_name=host.name,
                    extra_data={'command': command, 'exit_code': result['exit_code']}
                )
            
            return {
                'success': result['success'],
                'exit_code': result['exit_code'],
                'stdout': result['stdout'],
                'stderr': result['stderr'],
                'command': command
            }
            
        except Exception as e:
            logger.error(f"执行命令失败: {host.name} - {e}")
            return {
                'success': False,
                'error': str(e),
                'command': command
            }


class HostGroupService:
    """主机分组管理服务"""
    
    @staticmethod
    def create_group(name: str, description: str = '', parent: HostGroup = None, 
                    sort_order: int = 0, user=None) -> HostGroup:
        """创建主机分组"""
        with transaction.atomic():
            group = HostGroup.objects.create(
                name=name,
                description=description,
                parent=parent,
                sort_order=sort_order,
                created_by=user
            )
            
            # 记录操作日志
            if user:
                AuditLogService.log_action(
                    user=user,
                    action='create',
                    description=f'创建主机分组: {name}',
                    ip_address='127.0.0.1',
                    resource_type=ContentType.objects.get_for_model(group),
                    resource_id=group.id,
                    resource_name=group.name
                )
            
            return group
