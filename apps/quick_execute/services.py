"""
快速执行服务层
"""
import logging
from django.utils import timezone
from apps.hosts.models import Host, HostGroup
from apps.executor.fabric_tasks import start_script_execution, start_file_transfer, FABRIC_AVAILABLE
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
                },
                target_hosts=host_info_list,
                total_hosts=len(host_info_list),
                trigger_type='manual',
                client_ip=client_ip,
                user_agent=user_agent
            )

            # 如果没有指定超时时间，使用系统配置的默认值
            if not script_data.get('timeout'):
                from apps.system_config.models import ConfigManager
                script_data['timeout'] = ConfigManager.get('task.job_timeout', 300)

            # 默认使用Fabric执行引擎
            use_fabric = script_data.get('use_fabric', True) and FABRIC_AVAILABLE

            if use_fabric:
                # 使用Fabric执行引擎
                celery_task = start_script_execution(
                    script_content=script_data.get('script_content'),
                    script_type=script_data.get('script_type'),
                    target_hosts=host_info_list,
                    timeout=script_data['timeout'],
                    execution_mode=script_data.get('execution_mode', 'serial'),
                    global_variables=global_variables,
                    positional_args=positional_args,
                    rolling_strategy=script_data.get('rolling_strategy', 'fail_pause'),
                    rolling_batch_size=script_data.get('rolling_batch_size', 20),
                    rolling_batch_delay=script_data.get('rolling_batch_delay', 0),
                    execution_id=execution_record.execution_id,  # 传递执行ID用于实时日志
                    step_name='脚本执行'  # 快速执行固定为脚本执行
                )
            else:
                raise Exception("Fabric引擎不可用，请安装fabric库: uv add fabric")

            # 更新执行记录
            ExecutionRecordService.update_execution_status(
                execution_record=execution_record,
                status='running',
                celery_task_id=celery_task.id
            )

            logger.info(f"快速脚本执行已启动: {execution_record.execution_id} (Celery任务ID: {celery_task.id})")

            return {
                'success': True,
                'execution_id': execution_record.execution_id,
                'execution_record_id': execution_record.id,
                'task_id': celery_task.id,  # 用于实时日志的task_id
                'celery_task_id': celery_task.id,
                'message': '脚本执行已启动',
                'target_host_count': len(target_hosts)
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
                    'overwrite_policy': transfer_data.get('overwrite_policy', 'overwrite')
                },
                target_hosts=host_info_list,
                total_hosts=len(host_info_list),
                trigger_type='manual',
                client_ip=client_ip,
                user_agent=user_agent
            )

            # 如果没有指定超时时间，使用系统配置的默认值
            if not transfer_data.get('timeout'):
                from apps.system_config.models import ConfigManager
                transfer_data['timeout'] = ConfigManager.get('task.job_timeout', 300)

            # 从transfer_data中提取account_id（如果前端传递了）
            account_id = transfer_data.get('account_id')
            
            # 启动异步文件传输
            celery_task = start_file_transfer(
                transfer_type=transfer_data.get('transfer_type'),
                local_path=transfer_data.get('local_path'),
                remote_path=transfer_data.get('remote_path'),
                source_server_host=transfer_data.get('source_server_host'),
                source_server_user=transfer_data.get('source_server_user'),
                source_server_path=transfer_data.get('source_server_path'),
                target_hosts=host_info_list,
                timeout=transfer_data['timeout'],
                execution_mode=transfer_data.get('execution_mode', 'parallel'),
                rolling_strategy=transfer_data.get('rolling_strategy', 'fail_pause'),
                rolling_batch_size=transfer_data.get('rolling_batch_size', 20),
                rolling_batch_delay=transfer_data.get('rolling_batch_delay', 0),
                overwrite_policy=transfer_data.get('overwrite_policy', 'overwrite'),
                account_id=account_id,  # 传递account_id
                execution_id=execution_record.execution_id,  # 传递执行ID用于实时日志
                step_name='文件上传'  # 快速执行固定为文件上传
            )

            # 更新执行记录
            ExecutionRecordService.update_execution_status(
                execution_record=execution_record,
                status='running',
                celery_task_id=celery_task.id
            )

            logger.info(f"快速文件传输已启动: {execution_record.execution_id} (Celery任务ID: {celery_task.id})")

            return {
                'success': True,
                'execution_id': execution_record.execution_id,
                'execution_record_id': execution_record.id,
                'task_id': celery_task.id,  # 用于实时日志的task_id
                'celery_task_id': celery_task.id,
                'message': '文件传输已启动',
                'target_host_count': len(target_hosts)
            }

        except Exception as e:
            logger.error(f"快速文件传输启动失败: {e}")
            return {
                'success': False,
                'message': f'启动失败: {str(e)}'
            }
    
    @staticmethod
    def get_task_status(celery_task_id):
        """获取Celery任务执行状态"""
        try:
            from celery import current_app

            # 获取Celery任务状态
            task_result = current_app.AsyncResult(celery_task_id)

            if task_result.state == 'PENDING':
                status = 'pending'
                status_display = '等待中'
            elif task_result.state == 'STARTED':
                status = 'running'
                status_display = '执行中'
            elif task_result.state == 'SUCCESS':
                status = 'success'
                status_display = '成功'
            elif task_result.state == 'FAILURE':
                status = 'failed'
                status_display = '失败'
            elif task_result.state == 'REVOKED':
                status = 'cancelled'
                status_display = '已取消'
            else:
                status = 'unknown'
                status_display = '未知状态'

            # 如果任务完成，获取结果
            result_data = {}
            if task_result.state == 'SUCCESS' and task_result.result:
                result_data = task_result.result

            return {
                'success': True,
                'celery_task_id': celery_task_id,
                'status': status,
                'status_display': status_display,
                'result': result_data
            }

        except Exception as e:
            logger.error(f"获取任务状态失败: {celery_task_id} - {e}")
            return {
                'success': False,
                'message': f'获取状态失败: {str(e)}'
            }
    
    @staticmethod
    def get_task_executions(celery_task_id):
        """获取任务的执行记录"""
        try:
            from celery import current_app

            # 获取Celery任务结果
            task_result = current_app.AsyncResult(celery_task_id)

            if task_result.state == 'SUCCESS' and task_result.result:
                result_data = task_result.result
                executions = result_data.get('results', [])

                return {
                    'success': True,
                    'celery_task_id': celery_task_id,
                    'executions': executions
                }
            else:
                return {
                    'success': False,
                    'message': '任务尚未完成或执行失败'
                }

        except Exception as e:
            logger.error(f"获取任务执行记录失败: {celery_task_id} - {e}")
            return {
                'success': False,
                'message': f'获取执行记录失败: {str(e)}'
            }

    @staticmethod
    def cancel_task(celery_task_id, user):
        """取消任务执行 - 使用混合取消方案"""
        try:
            from celery import current_app
            from django.core.cache import cache
            import signal
            
            # 获取执行记录以获取execution_id
            from apps.executor.models import ExecutionRecord
            try:
                execution_record = ExecutionRecord.objects.get(celery_task_id=celery_task_id)
                execution_id = execution_record.execution_id
            except ExecutionRecord.DoesNotExist:
                # 如果没有找到执行记录，使用celery_task_id作为execution_id
                execution_id = celery_task_id
            
            # 第一层：设置Redis取消标志（优雅取消）
            cache.set(f"cancel:{execution_id}", "1", timeout=3600)
            logger.info(f"设置取消标志: {execution_id}")
            
            # 第二层：发送SIGUSR1信号（强制取消）
            try:
                current_app.control.revoke(
                    celery_task_id, 
                    terminate=True, 
                    signal=signal.SIGUSR1
                )
                logger.info(f"发送取消信号: {celery_task_id}")
            except Exception as e:
                logger.warning(f"发送取消信号失败: {e}")
                # 如果信号发送失败，至少设置Redis标志
                pass

            logger.info(f"快速任务已取消: (celery任务ID: {celery_task_id}, 执行ID: {execution_id})")

            return {
                'success': True,
                'message': '任务已取消'
            }

        except Exception as e:
            logger.error(f"取消任务失败: {celery_task_id} - {e}")
            return {
                'success': False,
                'message': f'取消失败: {str(e)}'
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
