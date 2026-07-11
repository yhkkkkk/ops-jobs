"""
云厂商主机同步服务
支持从阿里云、腾讯云、AWS等云厂商同步主机信息
"""
import logging
from typing import Any, Dict, Optional

from apps.system_config.models import ConfigManager
from .models import Host
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
                }
                
                # 获取网络信息
                if instance.network_interfaces and instance.network_interfaces.network_interface:
                    network_interface = instance.network_interfaces.network_interface[0]
                    host_data['internal_ip'] = network_interface.primary_ip_address
                    host_data['internal_mac'] = network_interface.mac_address
                
                if instance.public_ip_address and instance.public_ip_address.ip_address:
                    host_data['public_ip'] = instance.public_ip_address.ip_address[0]
                # Set the platform-appropriate management port; credentials remain in ServerAccount.
                host_data['port'] = 22 if host_data['os_type'] == 'linux' else 3389
                if CloudSyncService._upsert_cloud_host(host_data, user):
                    synced_hosts.append(host_data['instance_id'])
                else:
                    updated_hosts.append(host_data['instance_id'])
            
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
                }
                
                # 获取网络信息
                if instance.PrivateIpAddresses:
                    host_data['internal_ip'] = instance.PrivateIpAddresses[0]
                
                if instance.PublicIpAddresses:
                    host_data['public_ip'] = instance.PublicIpAddresses[0]
                # Set the platform-appropriate management port; credentials remain in ServerAccount.
                host_data['port'] = 22 if host_data['os_type'] == 'linux' else 3389
                if CloudSyncService._upsert_cloud_host(host_data, user):
                    synced_hosts.append(host_data['instance_id'])
                else:
                    updated_hosts.append(host_data['instance_id'])
            
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
    def _upsert_cloud_host(host_data: Dict[str, Any], user) -> bool:
        """Persist a cloud instance using the provider and instance ID as its identity.

        Returns True when a Host was created and False when an existing Host was updated.
        """
        provider = host_data["cloud_provider"]
        instance_id = host_data["instance_id"]
        existing_host = Host.objects.filter(
            cloud_provider=provider,
            instance_id=instance_id,
        ).first()
        if existing_host:
            for field, value in host_data.items():
                setattr(existing_host, field, value)
            existing_host.save()
            return False

        if user is None:
            raise ValueError("A user is required when synchronizing a new cloud host")
        Host.objects.create(created_by=user, **host_data)
        return True

    @staticmethod
    def sync_aws_hosts(region: Optional[str] = None, user=None) -> Dict[str, Any]:
        """Synchronize AWS EC2 instances through the paginated DescribeInstances API."""
        try:
            credentials = CloudSyncService.get_cloud_credentials('aws')
            if not credentials.get('access_key') or not credentials.get('secret_key'):
                return {
                    'success': False,
                    'message': 'AWS credentials are not configured. Set the access key and secret key first.',
                }

            try:
                import boto3
            except ImportError:
                return {
                    'success': False,
                    'message': 'boto3 is not installed. Install boto3 before synchronizing AWS hosts.',
                }

            target_region = region or credentials['region']
            client = boto3.client(
                'ec2',
                region_name=target_region,
                aws_access_key_id=credentials['access_key'],
                aws_secret_access_key=credentials['secret_key'],
            )
            paginator = client.get_paginator('describe_instances')
            synced_hosts = 0
            updated_hosts = 0

            for page in paginator.paginate():
                for reservation in page.get('Reservations', []):
                    for instance in reservation.get('Instances', []):
                        instance_id = instance.get('InstanceId')
                        if not instance_id:
                            continue

                        tags = {
                            tag.get('Key'): tag.get('Value')
                            for tag in instance.get('Tags', [])
                            if tag.get('Key')
                        }
                        platform = str(instance.get('Platform') or instance.get('PlatformDetails') or '').lower()
                        os_type = 'windows' if 'windows' in platform else 'linux'
                        availability_zone = instance.get('Placement', {}).get('AvailabilityZone') or ''
                        interfaces = instance.get('NetworkInterfaces') or []
                        primary_interface = next(
                            (
                                interface
                                for interface in interfaces
                                if interface.get('Attachment', {}).get('DeviceIndex') == 0
                            ),
                            interfaces[0] if interfaces else {},
                        )
                        cpu_options = instance.get('CpuOptions') or {}
                        core_count = cpu_options.get('CoreCount')
                        threads_per_core = cpu_options.get('ThreadsPerCore')
                        host_data = {
                            'name': tags.get('Name') or instance_id,
                            'cloud_provider': 'aws',
                            'instance_id': instance_id,
                            'region': target_region,
                            'zone': availability_zone,
                            'instance_type': instance.get('InstanceType') or '',
                            'os_type': os_type,
                            'port': 3389 if os_type == 'windows' else 22,
                            'status': 'online' if instance.get('State', {}).get('Name') == 'running' else 'offline',
                            'internal_ip': instance.get('PrivateIpAddress') or None,
                            'public_ip': instance.get('PublicIpAddress') or None,
                            'internal_mac': primary_interface.get('MacAddress') or '',
                        }
                        if core_count and threads_per_core:
                            host_data['cpu_cores'] = int(core_count) * int(threads_per_core)

                        if CloudSyncService._upsert_cloud_host(host_data, user):
                            synced_hosts += 1
                        else:
                            updated_hosts += 1

            if user:
                AuditLogService.log_action(
                    user=user,
                    action='sync_cloud_hosts',
                    description=f'同步 AWS 主机: 新增 {synced_hosts} 台，更新 {updated_hosts} 台',
                    ip_address='127.0.0.1',
                    success=True,
                    extra_data={
                        'provider': 'aws',
                        'region': target_region,
                        'synced_count': synced_hosts,
                        'updated_count': updated_hosts,
                    },
                )

            return {
                'success': True,
                'message': f'AWS 主机同步成功：新增 {synced_hosts} 台，更新 {updated_hosts} 台',
                'synced_hosts': synced_hosts,
                'updated_hosts': updated_hosts,
                'total_hosts': synced_hosts + updated_hosts,
            }
        except Exception as exc:
            logger.exception('同步 AWS 主机失败')
            return {
                'success': False,
                'message': f'AWS 主机同步失败: {exc}',
            }

    @staticmethod
    def sync_cloud_hosts(provider: str, region: Optional[str] = None, user=None) -> Dict[str, Any]:
        """统一的云主机同步接口"""
        if provider == 'aliyun':
            return CloudSyncService.sync_aliyun_hosts(region, user)
        elif provider == 'tencent':
            return CloudSyncService.sync_tencent_hosts(region, user)
        elif provider == 'aws':
            return CloudSyncService.sync_aws_hosts(region, user)
        else:
            return {
                'success': False,
                'message': f'不支持的云厂商: {provider}'
            }
