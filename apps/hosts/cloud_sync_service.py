"""
云厂商主机同步服务
支持从阿里云、腾讯云、AWS等云厂商同步主机信息
"""
import logging
from typing import Dict, List, Any, Optional
from django.utils import timezone
from django.contrib.contenttypes.models import ContentType

from apps.system_config.models import ConfigManager
from .models import Host, HostGroup
from utils.audit_service import AuditLogService

logger = logging.getLogger(__name__)


class CloudSyncService:
    """云厂商同步服务"""
    
    @staticmethod
    def get_cloud_credentials(provider: str) -> Dict[str, str]:
        """获取云厂商凭证"""
        credentials = {}
        
        if provider == 'aliyun':
            credentials = {
                'access_key': ConfigManager.get('cloud.aliyun.access_key', ''),
                'secret_key': ConfigManager.get('cloud.aliyun.secret_key', ''),
                'region': ConfigManager.get('cloud.aliyun.region', 'cn-hangzhou')
            }
        elif provider == 'tencent':
            credentials = {
                'secret_id': ConfigManager.get('cloud.tencent.secret_id', ''),
                'secret_key': ConfigManager.get('cloud.tencent.secret_key', ''),
                'region': ConfigManager.get('cloud.tencent.region', 'ap-guangzhou')
            }
        elif provider == 'aws':
            credentials = {
                'access_key': ConfigManager.get('cloud.aws.access_key', ''),
                'secret_key': ConfigManager.get('cloud.aws.secret_key', ''),
                'region': ConfigManager.get('cloud.aws.region', 'us-east-1')
            }
        
        return credentials
    
    @staticmethod
    def sync_aliyun_hosts(region: Optional[str] = None, user=None) -> Dict[str, Any]:
        """同步阿里云主机"""
        try:
            credentials = CloudSyncService.get_cloud_credentials('aliyun')
            if not credentials.get('access_key') or not credentials.get('secret_key'):
                return {
                    'success': False,
                    'message': '阿里云凭证未配置，请先在系统配置中设置AccessKey'
                }
            
            # 这里需要安装阿里云SDK: pip install alibabacloud_ecs20140526
            try:
                from alibabacloud_ecs20140526.client import Client as EcsClient
                from alibabacloud_tea_openapi import models as open_api_models
                from alibabacloud_ecs20140526 import models as ecs_models
            except ImportError:
                return {
                    'success': False,
                    'message': '阿里云SDK未安装，请运行: pip install alibabacloud_ecs20140526'
                }
            
            # 配置客户端
            config = open_api_models.Config(
                access_key_id=credentials['access_key'],
                access_key_secret=credentials['secret_key']
            )
            config.endpoint = f'ecs.{region or credentials["region"]}.aliyuncs.com'
            client = EcsClient(config)
            
            # 查询实例
            request = ecs_models.DescribeInstancesRequest()
            response = client.describe_instances(request)
            
            synced_hosts = []
            updated_hosts = []
            
            for instance in response.body.instances.instance:
                # 解析实例信息
                host_data = {
                    'name': instance.instance_name or instance.instance_id,
                    'cloud_provider': 'aliyun',
                    'instance_id': instance.instance_id,
                    'region': instance.region_id,
                    'zone': instance.zone_id,
                    'instance_type': instance.instance_type,
                    'os_type': 'linux' if 'linux' in instance.os_name.lower() else 'windows',
                    'os_version': instance.os_name,
                    'cpu_cores': instance.cpu,
                    'memory_gb': instance.memory / 1024,  # 转换为GB
                    'status': 'online' if instance.status == 'Running' else 'offline',
                    'created_at': timezone.now(),
                    'updated_at': timezone.now(),
                }
                
                # 获取网络信息
                if instance.network_interfaces and instance.network_interfaces.network_interface:
                    network_interface = instance.network_interfaces.network_interface[0]
                    host_data['internal_ip'] = network_interface.primary_ip_address
                    host_data['internal_mac'] = network_interface.mac_address
                
                if instance.public_ip_address and instance.public_ip_address.ip_address:
                    host_data['public_ip'] = instance.public_ip_address.ip_address[0]
                
                # 设置默认端口和用户名
                host_data['port'] = 22 if host_data['os_type'] == 'linux' else 3389
                host_data['username'] = 'root' if host_data['os_type'] == 'linux' else 'Administrator'
                host_data['auth_type'] = 'password'
                
                # 检查主机是否已存在
                existing_host = Host.objects.filter(
                    cloud_provider='aliyun',
                    instance_id=instance.instance_id
                ).first()
                
                if existing_host:
                    # 更新现有主机
                    for key, value in host_data.items():
                        if key not in ['created_at']:  # 不更新创建时间
                            setattr(existing_host, key, value)
                    existing_host.save()
                    updated_hosts.append(existing_host)
                else:
                    # 创建新主机
                    if user:
                        host_data['created_by'] = user
                    new_host = Host.objects.create(**host_data)
                    synced_hosts.append(new_host)
            
            # 记录操作日志
            if user:
                AuditLogService.log_action(
                    user=user,
                    action='sync_cloud_hosts',
                    description=f'同步阿里云主机: 新增 {len(synced_hosts)} 台，更新 {len(updated_hosts)} 台',
                    ip_address='127.0.0.1',
                    success=True,
                    extra_data={
                        'provider': 'aliyun',
                        'region': region or credentials['region'],
                        'synced_count': len(synced_hosts),
                        'updated_count': len(updated_hosts)
                    }
                )
            
            return {
                'success': True,
                'message': f'阿里云主机同步成功：新增 {len(synced_hosts)} 台，更新 {len(updated_hosts)} 台',
                'synced_hosts': len(synced_hosts),
                'updated_hosts': len(updated_hosts),
                'total_hosts': len(synced_hosts) + len(updated_hosts)
            }
            
        except Exception as e:
            logger.error(f"同步阿里云主机失败: {e}")
            return {
                'success': False,
                'message': f'同步阿里云主机失败: {str(e)}'
            }
    
    @staticmethod
    def sync_tencent_hosts(region: Optional[str] = None, user=None) -> Dict[str, Any]:
        """同步腾讯云主机"""
        try:
            credentials = CloudSyncService.get_cloud_credentials('tencent')
            if not credentials.get('secret_id') or not credentials.get('secret_key'):
                return {
                    'success': False,
                    'message': '腾讯云凭证未配置，请先在系统配置中设置SecretId和SecretKey'
                }
            
            # 这里需要安装腾讯云SDK: pip install tencentcloud-sdk-python
            try:
                from tencentcloud.common import credential
                from tencentcloud.common.profile.client_profile import ClientProfile
                from tencentcloud.common.profile.http_profile import HttpProfile
                from tencentcloud.cvm.v20170312 import cvm_client, models
            except ImportError:
                return {
                    'success': False,
                    'message': '腾讯云SDK未安装，请运行: pip install tencentcloud-sdk-python'
                }
            
            # 配置客户端
            cred = credential.Credential(
                credentials['secret_id'],
                credentials['secret_key']
            )
            
            httpProfile = HttpProfile()
            httpProfile.endpoint = "cvm.tencentcloudapi.com"
            
            clientProfile = ClientProfile()
            clientProfile.httpProfile = httpProfile
            
            client = cvm_client.CvmClient(cred, region or credentials['region'], clientProfile)
            
            # 查询实例
            req = models.DescribeInstancesRequest()
            resp = client.DescribeInstances(req)
            
            synced_hosts = []
            updated_hosts = []
            
            for instance in resp.InstanceSet:
                # 解析实例信息
                host_data = {
                    'name': instance.InstanceName or instance.InstanceId,
                    'cloud_provider': 'tencent',
                    'instance_id': instance.InstanceId,
                    'region': instance.Placement.Zone[:-1],  # 去掉最后的字母得到region
                    'zone': instance.Placement.Zone,
                    'instance_type': instance.InstanceType,
                    'os_type': 'linux' if 'linux' in instance.OsName.lower() else 'windows',
                    'os_version': instance.OsName,
                    'cpu_cores': instance.CPU,
                    'memory_gb': instance.Memory,
                    'status': 'online' if instance.InstanceState == 'RUNNING' else 'offline',
                    'created_at': timezone.now(),
                    'updated_at': timezone.now(),
                }
                
                # 获取网络信息
                if instance.PrivateIpAddresses:
                    host_data['internal_ip'] = instance.PrivateIpAddresses[0]
                
                if instance.PublicIpAddresses:
                    host_data['public_ip'] = instance.PublicIpAddresses[0]
                
                # 设置默认端口和用户名
                host_data['port'] = 22 if host_data['os_type'] == 'linux' else 3389
                host_data['username'] = 'root' if host_data['os_type'] == 'linux' else 'Administrator'
                host_data['auth_type'] = 'password'
                
                # 检查主机是否已存在
                existing_host = Host.objects.filter(
                    cloud_provider='tencent',
                    instance_id=instance.InstanceId
                ).first()
                
                if existing_host:
                    # 更新现有主机
                    for key, value in host_data.items():
                        if key not in ['created_at']:
                            setattr(existing_host, key, value)
                    existing_host.save()
                    updated_hosts.append(existing_host)
                else:
                    # 创建新主机
                    if user:
                        host_data['created_by'] = user
                    new_host = Host.objects.create(**host_data)
                    synced_hosts.append(new_host)
            
            # 记录操作日志
            if user:
                AuditLogService.log_action(
                    user=user,
                    action='sync_cloud_hosts',
                    description=f'同步腾讯云主机: 新增 {len(synced_hosts)} 台，更新 {len(updated_hosts)} 台',
                    ip_address='127.0.0.1',
                    success=True,
                    extra_data={
                        'provider': 'tencent',
                        'region': region or credentials['region'],
                        'synced_count': len(synced_hosts),
                        'updated_count': len(updated_hosts)
                    }
                )
            
            return {
                'success': True,
                'message': f'腾讯云主机同步成功：新增 {len(synced_hosts)} 台，更新 {len(updated_hosts)} 台',
                'synced_hosts': len(synced_hosts),
                'updated_hosts': len(updated_hosts),
                'total_hosts': len(synced_hosts) + len(updated_hosts)
            }
            
        except Exception as e:
            logger.error(f"同步腾讯云主机失败: {e}")
            return {
                'success': False,
                'message': f'同步腾讯云主机失败: {str(e)}'
            }
    
    @staticmethod
    def sync_cloud_hosts(provider: str, region: Optional[str] = None, user=None) -> Dict[str, Any]:
        """统一的云主机同步接口"""
        if provider == 'aliyun':
            return CloudSyncService.sync_aliyun_hosts(region, user)
        elif provider == 'tencent':
            return CloudSyncService.sync_tencent_hosts(region, user)
        elif provider == 'aws':
            # TODO: 实现AWS同步
            return {
                'success': False,
                'message': 'AWS主机同步功能正在开发中'
            }
        else:
            return {
                'success': False,
                'message': f'不支持的云厂商: {provider}'
            }
