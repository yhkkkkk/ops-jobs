"""
快速执行服务层
"""
import logging
from django.utils import timezone
from apps.hosts.models import Host, HostGroup
from apps.agents.execution_service import AgentExecutionService
from apps.executor.services import ExecutionRecordService

logger = logging.getLogger(__name__)


class QuickExecuteService:
    """快速执行服务"""
    
    @staticmethod
    def execute_script(user, script_data, client_ip=None, user_agent=None):
        """快速执行脚本"""
        try:
            # 获取目标主机
            target_hosts = QuickExecuteService._get_target_hosts_from_data(script_data)

            if not target_hosts:
                return {
                    'success': False,
                    'message': '没有找到目标主机'
                }

            # 构建主机信息列表
            host_info_list = [
                {
                    'id': host.id,
                    'name': host.name,
                    'ip_address': host.ip_address
                }
                for host in target_hosts
            ]

            # 获取全局变量和位置参数
            global_variables = script_data.get('global_variables', {})
            positional_args = script_data.get('positional_args', [])
            
            # 从global_variables中提取account_id（前端传递的）
            account_id = global_variables.get('account_id') if global_variables else None

            # 创建统一的执行记录
            execution_record = ExecutionRecordService.create_execution_record(
                executed_by=user,
                execution_type='quick_script',
                name=f"快速脚本执行 - {script_data.get('script_name', '未命名')}",
                execution_parameters={
                    'script_content': script_data.get('script_content'),
                    'script_type': script_data.get('script_type', 'shell'),
                    'timeout': script_data.get('timeout'),
                    'execution_mode': script_data.get('execution_mode', 'parallel'),
                    'rolling_strategy': script_data.get('rolling_strategy', 'fail_pause'),
                    'rolling_batch_size': script_data.get('rolling_batch_size', 20),
                    'rolling_batch_delay': script_data.get('rolling_batch_delay', 0),
                    'global_variables': global_variables,
                    'positional_args': positional_args,
                    'account_id': account_id,  # 保存account_id到执行参数中
                    'target_host_ids': [host.id for host in target_hosts],
                },
                trigger_type='manual',
                client_ip=client_ip,
                user_agent=user_agent
            )

            # 如果没有指定超时时间，使用系统配置的默认值
            if not script_data.get('timeout'):
                from apps.system_config.models import ConfigManager
                script_data['timeout'] = ConfigManager.get('task.job_timeout', 300)

            # 只支持Agent方式执行
            agent_server_url = script_data.get('agent_server_url')

            # 更新执行参数，添加执行方式标识
            execution_record.execution_parameters.update({
                'execution_mode': 'agent',
                'agent_server_url': agent_server_url,
            })
            execution_record.save()

            # 通过Agent执行脚本
            result = AgentExecutionService.execute_script_via_agent(
                execution_record=execution_record,
                    script_content=script_data.get('script_content'),
                script_type=script_data.get('script_type', 'shell'),
                target_hosts=target_hosts,
                    timeout=script_data['timeout'],
                    global_variables=global_variables,
                step_id=None,  # 快速执行没有步骤ID
                agent_server_url=agent_server_url,
            )

            if result['success']:
                # 更新执行记录状态
                ExecutionRecordService.update_execution_status(
                    execution_record=execution_record,
                    status='running',
                )

                logger.info(f"快速脚本执行已启动: {execution_record.execution_id}")

                return {
                    'success': True,
                    'execution_id': execution_record.execution_id,
                    'execution_record_id': execution_record.id,
                        'task_id': str(execution_record.execution_id),  # 用于实时日志的task_id
                        'message': '脚本执行已启动（Agent方式）',
                        'target_host_count': len(target_hosts),
                        'success_count': result.get('success_count', 0),
                        'failed_count': result.get('failed_count', 0)
                    }
            else:
                # 执行失败
                ExecutionRecordService.update_execution_status(
                    execution_record=execution_record,
                    status='failed',
                    error_message=result.get('error', '脚本执行启动失败')
                )

                return {
                    'success': False,
                    'error': result.get('error', '脚本执行启动失败')
            }

        except Exception as e:
            logger.error(f"快速脚本执行启动失败: {e}")
            return {
                'success': False,
                'message': f'启动失败: {str(e)}'
            }
    
    @staticmethod
    def transfer_file(user, transfer_data, client_ip=None, user_agent=None):
        """快速文件传输"""
        try:
            # 获取目标主机 - 使用统一的target_host_ids格式
            target_host_ids = transfer_data.get('target_host_ids', [])
            if not target_host_ids:
                return {
                    'success': False,
                    'message': '没有指定目标主机'
                }
            
            try:
                target_hosts = Host.objects.filter(id__in=target_host_ids)
                if not target_hosts.exists():
                    return {
                        'success': False,
                        'message': '没有找到目标主机'
                    }
            except Exception as e:
                logger.error(f"获取主机列表失败: {e}")
                return {
                    'success': False,
                    'message': f'获取主机列表失败: {str(e)}'
                }

            # 构建主机信息列表
            host_info_list = [
                {
                    'id': host.id,
                    'name': host.name,
                    'ip_address': host.ip_address
                }
                for host in target_hosts
            ]

            # 创建统一的执行记录
            execution_record = ExecutionRecordService.create_execution_record(
                executed_by=user,
                execution_type='file_transfer',
                name=f"文件传输 - {transfer_data.get('transfer_name', '未命名')}",
                execution_parameters={
                    'transfer_type': transfer_data.get('transfer_type'),
                    'local_path': transfer_data.get('local_path'),
                    'remote_path': transfer_data.get('remote_path'),
                    'source_server_host': transfer_data.get('source_server_host'),
                    'source_server_user': transfer_data.get('source_server_user'),
                    'source_server_path': transfer_data.get('source_server_path'),
                    'timeout': transfer_data.get('timeout'),
                    'execution_mode': transfer_data.get('execution_mode', 'parallel'),
                    'rolling_batch_size': transfer_data.get('rolling_batch_size', 20),
                    'rolling_batch_delay': transfer_data.get('rolling_batch_delay', 0),
                    'overwrite_policy': transfer_data.get('overwrite_policy', 'overwrite'),
                    'target_host_ids': [host.id for host in target_hosts],
                },
                trigger_type='manual',
                client_ip=client_ip,
                user_agent=user_agent
            )

            # 如果没有指定超时时间，使用系统配置的默认值
            if not transfer_data.get('timeout'):
                from apps.system_config.models import ConfigManager
                transfer_data['timeout'] = ConfigManager.get('task.job_timeout', 300)

            # 只支持Agent方式执行
            agent_server_url = transfer_data.get('agent_server_url')

            # 更新执行参数，添加执行方式标识
            execution_record.execution_parameters.update({
                'execution_mode': 'agent',
                'agent_server_url': agent_server_url,
            })
            execution_record.save()

            # 读取文件内容（如果是上传）
            file_content = None
            if transfer_data.get('transfer_type') == 'upload':
                local_path = transfer_data.get('local_path', '')
                if local_path:
                    try:
                        with open(local_path, 'rb') as f:
                            file_content = f.read()
                    except Exception as e:
                        logger.error(f"读取文件失败: {str(e)}")
                        ExecutionRecordService.update_execution_status(
                            execution_record=execution_record,
                            status='failed',
                            error_message=f'读取文件失败: {str(e)}'
                        )
                        return {
                            'success': False,
                            'message': f'读取文件失败: {str(e)}'
                        }

            # 通过Agent执行文件传输
            result = AgentExecutionService.execute_file_transfer_via_agent(
                execution_record=execution_record,
                transfer_type=transfer_data.get('transfer_type', 'upload'),
                local_path=transfer_data.get('local_path', ''),
                remote_path=transfer_data.get('remote_path', ''),
                target_hosts=list(target_hosts),
                file_content=file_content,
                timeout=transfer_data.get('timeout', 300),
                bandwidth_limit=transfer_data.get('bandwidth_limit', 0),
                step_id=None,  # 快速执行没有步骤ID
                agent_server_url=agent_server_url,
            )

            if result['success']:
                # 更新执行记录状态
                ExecutionRecordService.update_execution_status(
                    execution_record=execution_record,
                    status='running',
                )

                logger.info(f"快速文件传输已启动: {execution_record.execution_id}")

                return {
                    'success': True,
                    'execution_id': execution_record.execution_id,
                    'execution_record_id': execution_record.id,
                    'task_id': str(execution_record.execution_id),  # 用于实时日志的task_id
                    'message': '文件传输已启动（Agent方式）',
                    'target_host_count': len(target_hosts),
                    'success_count': result.get('success_count', 0),
                    'failed_count': result.get('failed_count', 0)
                }
            else:
                # 执行失败
                ExecutionRecordService.update_execution_status(
                    execution_record=execution_record,
                    status='failed',
                    error_message=result.get('error', '文件传输启动失败')
                )

                return {
                    'success': False,
                    'error': result.get('error', '文件传输启动失败')
                }

            # 从transfer_data中提取account_id（如果前端传递了）
            account_id = transfer_data.get('account_id')
            
        except Exception as e:
            logger.error(f"快速文件传输启动失败: {e}")
            return {
                'success': False,
                'message': f'启动失败: {str(e)}'
            }
    
    @staticmethod
    def _get_target_hosts_from_data(script_data):
        """从脚本数据中获取目标主机列表，支持两种格式"""
        target_hosts = []
        
        # 优先使用target_host_ids格式（新格式）
        target_host_ids = script_data.get('target_host_ids', [])
        if target_host_ids:
            try:
                target_hosts = Host.objects.filter(id__in=target_host_ids)
                return list(target_hosts)
            except Exception as e:
                logger.error(f"获取主机列表失败: {e}")
                return []
        
        return []
