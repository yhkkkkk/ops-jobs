"""
基于Fabric的执行协调逻辑
提供更稳定的脚本执行功能
支持任务取消功能
"""
import logging
import uuid
from celery import shared_task
from celery.result import allow_join_result
from celery.exceptions import SoftTimeLimitExceeded

# 导入异常类用于重试机制
try:
    from paramiko.ssh_exception import SSHException, AuthenticationException, NoValidConnectionsError
    from invoke.exceptions import CommandTimedOut, UnexpectedExit
    from socket import timeout as SocketTimeout
    SSH_EXCEPTIONS = (SSHException, AuthenticationException, NoValidConnectionsError, CommandTimedOut, SocketTimeout, ConnectionError)
except ImportError:
    # 如果导入失败，使用基础异常类
    SSH_EXCEPTIONS = (ConnectionError, TimeoutError)

from apps.hosts.fabric_ssh_manager import fabric_ssh_manager, FABRIC_AVAILABLE, FabricSSHError
from utils.realtime_logs import realtime_log_service
from .abortable_tasks import AbortableTask, raise_if_cancelled

logger = logging.getLogger(__name__)


def execute_script_on_hosts_fabric(script_content, script_type, target_hosts, timeout=None,
                                   execution_mode='parallel', global_variables=None, positional_args=None, **kwargs):
    """
    使用Fabric在指定主机上执行脚本
    """
    try:
        # 使用execution_id作为Redis Stream的键名，这样前端可以直接通过execution_id访问
        execution_id = kwargs.get('execution_id')
        celery_task_id = kwargs.get('celery_task_id', str(uuid.uuid4()))
        task_id = str(execution_id) if execution_id else celery_task_id  # 优先使用execution_id
        
        # 任务开始时检查取消状态
        raise_if_cancelled(execution_id)
        
        # 如果没有指定超时时间，使用系统配置的默认值
        if timeout is None:
            from apps.system_config.models import ConfigManager
            timeout = ConfigManager.get('task.job_timeout', 300)
        
        logger.info(f"[Fabric] 开始执行脚本，目标主机数: {len(target_hosts)}, 任务ID: {celery_task_id}, 执行ID: {execution_id}, 日志ID: {task_id}, 超时时间: {timeout}秒")

        # 根据调用来源确定步骤名称
        step_name = kwargs.get('step_name', '脚本执行')
        
        # 推送任务开始状态
        realtime_log_service.push_status(task_id, {
            'status': 'running',
            'progress': 0,
            'current_step': step_name,
            'total_hosts': len(target_hosts),
            'success_hosts': 0,
            'failed_hosts': 0,
            'running_hosts': len(target_hosts),
            'message': f'开始执行{step_name}'
        })

        results = []

        # 获取ignore_error参数
        ignore_error = kwargs.get('ignore_error', False)

        if execution_mode == 'parallel':
            from celery import group

            logger.info(f"[Fabric] 开始并行执行，目标主机数: {len(target_hosts)}")
            
            # 使用celery并行执行
            job = group(
                execute_script_on_single_host_fabric.s(
                    script_content, script_type, host_info, timeout, task_id,
                    global_variables, positional_args, ignore_error
                ) for host_info in target_hosts
            )

            try:
                completed_count = 0
                with allow_join_result():
                    group_result = job.apply_async()
                    for result in group_result.iterate():
                        if completed_count % 3 == 0:
                            raise_if_cancelled(execution_id)
                        results.append(result)
                        completed_count += 1
                        logger.info(
                            f"[Fabric] 主机 {result.get('host_name')} 并行执行完成: {result.get('success')}"
                        )
            except SoftTimeLimitExceeded:
                logger.info(f"任务被取消，已处理 {len(results)}/{len(target_hosts)} 个主机")
                return {
                    'success': False,
                    'message': '任务已被用户取消',
                    'cancelled': True,
                    'partial_results': results
                }
            except Exception as e:
                logger.error(f"[Fabric] 并行执行异常: {e}")
                return {
                    'success': False,
                    'message': f'并行执行异常: {e}',
                    'results': results,
                    'engine': 'fabric'
                }

        elif execution_mode == 'serial':
            # 串行执行
            for i, host_info in enumerate(target_hosts):
                # 每处理几个主机检查一次取消状态
                if i % 3 == 0:  # 每3个主机检查一次
                    raise_if_cancelled(execution_id)
                
                try:
                    with allow_join_result():
                        async_result = execute_script_on_single_host_fabric.apply_async(args=(
                            script_content, script_type, host_info, timeout, task_id,
                            global_variables, positional_args, ignore_error
                        ))
                        result = async_result.get()
                    results.append(result)

                    # 如果实际执行失败且不忽略错误，停止后续主机的执行
                    actual_success = result.get('actual_success', result['success'])
                    if not actual_success and not ignore_error:
                        logger.warning(f"主机 {host_info['name']} 执行失败，停止后续主机执行")
                        break
                except SoftTimeLimitExceeded:
                    logger.info(f"任务被取消，已处理 {i}/{len(target_hosts)} 个主机")
                    return {
                        'success': False,
                        'message': '任务已被用户取消',
                        'cancelled': True,
                        'partial_results': results
                    }

        elif execution_mode == 'rolling':
            # 滚动执行
            import time
            batch_size_percent = kwargs.get('rolling_batch_size', 20)  # 百分比
            batch_delay = kwargs.get('rolling_batch_delay', 0)
            rolling_strategy = kwargs.get('rolling_strategy', 'fail_pause')

            # 计算实际批次大小（按百分比）
            total_hosts = len(target_hosts)
            actual_batch_size = max(1, int(total_hosts * batch_size_percent / 100))

            logger.info(f"[Fabric] 滚动执行: 总主机数={total_hosts}, 批次百分比={batch_size_percent}%, 实际批次大小={actual_batch_size}, 策略={rolling_strategy}")

            for i in range(0, len(target_hosts), actual_batch_size):
                # 每批次开始前检查取消状态
                raise_if_cancelled(execution_id)
                
                batch = target_hosts[i:i + actual_batch_size]
                batch_num = i // actual_batch_size + 1
                total_batches = (len(target_hosts) + actual_batch_size - 1) // actual_batch_size

                logger.info(f"[Fabric] 执行批次 {batch_num}/{total_batches}, 主机数: {len(batch)}")

                try:
                    # 并行执行当前批次
                    from celery import group
                    job = group(
                        execute_script_on_single_host_fabric.s(
                            script_content, script_type, host_info, timeout, task_id, global_variables, positional_args, ignore_error
                        ) for host_info in batch
                    )

                    # 使用allow_join_result上下文管理器来安全地获取结果
                    with allow_join_result():
                        batch_result = job.apply_async()
                        batch_results = batch_result.get()
                        results.extend(batch_results)
                except SoftTimeLimitExceeded:
                    logger.info(f"任务被取消，已处理 {len(results)}/{len(target_hosts)} 个主机")
                    return {
                        'success': False,
                        'message': '任务已被用户取消',
                        'cancelled': True,
                        'partial_results': results
                    }

                # 检查滚动策略
                if rolling_strategy == 'ignore_error':
                    # 忽略错误继续执行，不做特殊处理
                    pass
                else:
                    # fail_pause 策略：检查当前批次是否有失败
                    batch_failed = any(not result.get('success', False) for result in batch_results)
                    if batch_failed:
                        logger.warning(f"[Fabric] 批次 {batch_num} 有失败主机，根据策略({rolling_strategy})暂停执行")
                        break

                # 批次间延迟
                if i + actual_batch_size < len(target_hosts) and batch_delay > 0:
                    logger.info(f"[Fabric] 批次间延迟 {batch_delay} 秒")
                    time.sleep(batch_delay)

        # 统计结果
        success_count = sum(1 for r in results if r['success'])
        total_count = len(results)
        failed_count = total_count - success_count

        # 推送任务完成状态
        overall_success = success_count == total_count
        realtime_log_service.push_status(task_id, {
            'status': 'completed' if overall_success else 'failed',
            'progress': 100,
            'current_step': '脚本执行完成 (Fabric)',
            'total_hosts': total_count,
            'success_hosts': success_count,
            'failed_hosts': failed_count,
            'running_hosts': 0,
            'message': f'脚本执行完成 (Fabric)，成功: {success_count}/{total_count}'
        })

        # 更新执行记录状态
        try:
            from apps.executor.services import ExecutionRecordService
            from apps.executor.models import ExecutionRecord
            
            # 查找对应的执行记录
            execution_record = ExecutionRecord.objects.filter(celery_task_id=celery_task_id).first()
            if execution_record:
                # 创建执行步骤
                execution_step = ExecutionRecordService.create_execution_step(
                    execution_record=execution_record,
                    step_name='脚本执行 (Fabric)',
                    step_type='script',
                    step_order=1,
                    step_parameters={
                        'script_content': script_content,
                        'script_type': script_type,
                        'timeout': timeout,
                        'execution_mode': execution_mode,
                        'engine': 'fabric'
                    }
                )
                
                # 更新步骤状态
                ExecutionRecordService.update_step_status(
                    step=execution_step,
                    status='success' if overall_success else 'failed',
                    step_results={
                        'success_count': success_count,
                        'total_count': total_count,
                        'failed_count': failed_count
                    },
                    host_results=results
                )
                
                # 构建step_results结构
                step_results = {
                    '脚本执行': {
                        'step_order': 1,
                        'step_type': 'script',
                        'step_status': 'success' if overall_success else 'failed',
                        'hosts': {}
                    }
                }

                # 将results转换为step_results格式，并收集时间信息
                step_start_times = []
                step_end_times = []

                for result in results:
                    host_id = str(result['host_id'])

                    # 计算主机开始和结束时间
                    host_start_time = result.get('start_time')
                    host_end_time = result.get('end_time')

                    # 如果没有明确的开始/结束时间，使用执行记录的时间
                    if not host_start_time and execution_record.started_at:
                        host_start_time = execution_record.started_at.isoformat()
                    if not host_end_time and execution_record.finished_at:
                        host_end_time = execution_record.finished_at.isoformat()

                    step_results['脚本执行']['hosts'][host_id] = {
                        'host_id': result['host_id'],
                        'host_name': result['host_name'],
                        'host_ip': result['host_ip'],
                        'success': result['success'],
                        'stdout': result.get('stdout', ''),
                        'stderr': result.get('stderr', ''),
                        'exit_code': result.get('exit_code', 0),
                        'execution_time': result.get('execution_time', 0),
                        'message': result.get('message', ''),
                        'log_lines': len(result.get('stdout', '').split('\n')) + len(result.get('stderr', '').split('\n')),
                        'start_time': host_start_time,
                        'end_time': host_end_time
                    }

                    # 收集步骤时间信息
                    if host_start_time:
                        step_start_times.append(host_start_time)
                    if host_end_time:
                        step_end_times.append(host_end_time)

                # 计算步骤级别的时间信息
                step_started_at = min(step_start_times) if step_start_times else None
                step_finished_at = max(step_end_times) if step_end_times else None
                step_duration = None

                # 计算步骤持续时间
                if step_started_at and step_finished_at:
                    try:
                        from datetime import datetime
                        start_dt = datetime.fromisoformat(step_started_at.replace('Z', '+00:00'))
                        end_dt = datetime.fromisoformat(step_finished_at.replace('Z', '+00:00'))
                        step_duration = (end_dt - start_dt).total_seconds()
                    except Exception as e:
                        logger.warning(f"计算步骤持续时间失败: {e}")

                # 添加步骤级别的时间信息
                step_results['脚本执行'].update({
                    'started_at': step_started_at,
                    'finished_at': step_finished_at,
                    'duration': step_duration
                })

                # 更新执行记录状态
                ExecutionRecordService.update_execution_status(
                    execution_record=execution_record,
                    status='success' if overall_success else 'failed',
                    execution_results={
                        'success_count': success_count,
                        'total_count': total_count,
                        'failed_count': failed_count,
                        'step_results': step_results,  # 新的按步骤组织的结构
                        'engine': 'fabric'
                    }
                )
                
                # 更新主机结果统计
                ExecutionRecordService.update_host_results(
                    execution_record=execution_record,
                    success_hosts=success_count,
                    failed_hosts=failed_count
                )
                
                logger.info(f"已更新执行记录状态 (Fabric): {execution_record.execution_id} -> {'success' if overall_success else 'failed'}")
            else:
                logger.warning(f"未找到对应的执行记录: {task_id}")
        except Exception as e:
            logger.error(f"更新执行记录状态失败: {e}")

        return {
            'success': overall_success,
            'results': results,
            'success_count': success_count,
            'total_count': total_count,
            'failed_count': failed_count,
            'engine': 'fabric'
        }



    except SoftTimeLimitExceeded as e:
        # 任务被取消或超时
        logger.info(f"任务被取消或超时: {execution_id}")
        return {
            'success': False,
            'message': '任务已被用户取消' if '取消' in str(e) else '任务执行超时',
            'cancelled': '取消' in str(e),
            'timeout': '超时' in str(e),
            'results': [],
            'engine': 'fabric'
        }
    except Exception as e:
        # 其他异常，不重试
        logger.error(f"[Fabric] 脚本执行异常: {e}")

        # 推送错误日志到Redis Stream，确保前端能看到错误信息
        try:
            realtime_log_service.push_log(task_id, 0, {
                'host_name': '系统',
                'host_ip': '',
                'log_type': 'error',
                'content': f'任务执行异常 (Fabric): {str(e)}',
                'step_name': '脚本执行',
                'step_order': 1
            })

            # 推送失败状态
            realtime_log_service.push_status(task_id, {
                'status': 'failed',
                'progress': 100,
                'current_step': '执行失败 (Fabric)',
                'total_hosts': len(target_hosts),
                'success_hosts': 0,
                'failed_hosts': len(target_hosts),
                'running_hosts': 0,
                'message': f'任务执行异常 (Fabric): {str(e)}'
            })
        except Exception as log_error:
            logger.error(f"推送错误日志失败: {log_error}")

        # 更新执行记录状态为失败
        try:
            from apps.executor.services import ExecutionRecordService
            from apps.executor.models import ExecutionRecord

            # 查找对应的执行记录
            execution_record = ExecutionRecord.objects.filter(celery_task_id=celery_task_id).first()
            if execution_record:
                ExecutionRecordService.update_execution_status(
                    execution_record=execution_record,
                    status='failed',
                    error_message=f'Fabric执行异常: {str(e)}'
                )
                logger.info(f"已更新执行记录状态为失败 (Fabric): {execution_record.execution_id}")
            else:
                logger.warning(f"未找到对应的执行记录: {celery_task_id}")
        except Exception as update_error:
            logger.error(f"更新执行记录状态失败: {update_error}")

        return {
            'success': False,
            'message': f'Fabric执行异常: {str(e)}',
            'results': [],
            'engine': 'fabric'
        }


@shared_task(bind=True)
def execute_script_on_single_host_fabric(self, script_content, script_type, host_info, timeout, task_id=None,
                                        global_variables=None, positional_args=None, ignore_error=False):
    """
    使用Fabric在单个主机上执行脚本
    """
    try:
        from apps.hosts.models import Host

        host = Host.objects.get(id=host_info['id'])

        # 推送开始执行日志
        if task_id:
            realtime_log_service.push_log(task_id, host.id, {
                'host_name': host.name,
                'host_ip': host.ip_address,
                'log_type': 'info',
                'content': f'[Fabric] 开始在主机 {host.name} ({host.ip_address}) 上执行脚本',
                'step_name': '脚本执行',
                'step_order': 1
            })

        # 处理脚本内容中的变量替换
        processed_script_content = script_content

        # 替换全局变量
        if global_variables:
            for var_name, var_value in global_variables.items():
                if var_name != '_positional_args':  # 跳过位置参数
                    # 支持 ${VAR_NAME} 和 $VAR_NAME 两种格式
                    processed_script_content = processed_script_content.replace(f'${{{var_name}}}', str(var_value))
                    processed_script_content = processed_script_content.replace(f'${var_name}', str(var_value))

        # 从global_variables中提取account_id（如果存在）
        account_id = None
        if global_variables and 'account_id' in global_variables:
            account_id = global_variables.get('account_id')
            if account_id:
                try:
                    account_id = int(account_id)
                except (ValueError, TypeError):
                    account_id = None
                    logger.warning(f"无效的account_id: {global_variables.get('account_id')}")

        # 使用Fabric执行脚本
        result = fabric_ssh_manager.execute_script(
            host=host,
            script_content=processed_script_content,
            script_type=script_type,
            timeout=timeout,
            task_id=task_id,
            account_id=account_id
        )

        # 如果ignore_error为True，即使执行失败也标记为成功
        if ignore_error and not result['success']:
            result['actual_success'] = False  # 保存实际执行结果
            result['success'] = True  # 标记为成功以继续执行
            result['message'] = f"执行失败但已忽略错误: {result['message']}"
            
            # 推送警告日志
            if task_id:
                realtime_log_service.push_log(task_id, host.id, {
                    'host_name': host.name,
                    'host_ip': host.ip_address,
                    'log_type': 'warning',
                    'content': f'[Fabric] 主机 {host.name} 执行失败但已忽略错误',
                    'step_name': '脚本执行',
                    'step_order': 1
                })

        return result



    except Exception as e:
        # 其他异常，不重试
        logger.error(f"[Fabric] 单主机脚本执行异常: {host_info['name']} - {e}")

        # 推送错误日志
        if task_id:
            realtime_log_service.push_log(task_id, host_info['id'], {
                'host_name': host_info['name'],
                'host_ip': host_info['ip_address'],
                'log_type': 'error',
                'content': f'[Fabric] 执行异常: {str(e)}',
                'step_name': '脚本执行',
                'step_order': 1
            })

        result = {
            'success': False,
            'host_id': host_info['id'],
            'host_name': host_info['name'],
            'host_ip': host_info['ip_address'],
            'stdout': '',
            'stderr': str(e),
            'exit_code': -1,
            'message': f'Fabric执行异常: {str(e)}'
        }

        # 如果ignore_error为True，标记为成功
        if ignore_error:
            result['actual_success'] = False
            result['success'] = True
            result['message'] = f"执行异常但已忽略错误: {str(e)}"

        return result


def execute_workflow_on_hosts(plan_steps, target_hosts, global_parameters=None,
                              execution_mode='parallel', rolling_batch_size=1, rolling_batch_delay=0,
                              execution_id=None, is_debug=False, start_step_order=1, celery_task_id=None, **kwargs):
    """
    使用Fabric执行工作流
    """
    try:
        task_id = execution_id or celery_task_id or str(uuid.uuid4())
        celery_task_id = celery_task_id or str(uuid.uuid4())

        logger.info(f"[Fabric] 开始执行工作流，步骤数: {len(plan_steps)}, 目标主机数: {len(target_hosts)}, 任务ID: {celery_task_id}, 执行ID: {execution_id}")

        # 推送工作流开始状态
        realtime_log_service.push_status(task_id, {
            'status': 'running',
            'progress': 0,
            'current_step': '工作流执行 (Fabric)',
            'total_hosts': len(target_hosts),
            'success_hosts': 0,
            'failed_hosts': 0,
            'running_hosts': len(target_hosts),
            'message': '开始执行工作流 (使用Fabric)'
        })

        # 按步骤顺序执行
        overall_success = True
        all_results = []

        for step_index, step in enumerate(plan_steps):
            if step.get('step_order', step_index + 1) < start_step_order:
                continue  # 跳过指定步骤之前的步骤

            step_name = step.get('name', f'步骤{step_index + 1}')
            step_type = step.get('step_type', 'script')

            logger.info(f"[Fabric] 执行工作流步骤: {step_name} (类型: {step_type})")

            # 推送步骤开始状态
            realtime_log_service.push_status(task_id, {
                'status': 'running',
                'progress': int((step_index / len(plan_steps)) * 100),
                'current_step': f'执行步骤: {step_name}',
                'total_hosts': len(target_hosts),
                'message': f'正在执行步骤: {step_name}'
            })

            if step_type == 'script':
                # 脚本执行步骤
                # 从step中提取account_id并添加到global_variables中
                step_global_variables = (global_parameters or {}).copy()
                if step.get('account_id'):
                    step_global_variables['account_id'] = step.get('account_id')
                
                result = execute_script_on_hosts_fabric(
                    script_content=step.get('script_content', ''),
                    script_type=step.get('script_type', 'shell'),
                    target_hosts=target_hosts,
                    timeout=step.get('timeout', 300),
                    execution_mode=execution_mode,
                    global_variables=step_global_variables,
                    positional_args=[],
                    rolling_batch_size=rolling_batch_size,
                    rolling_batch_delay=rolling_batch_delay,
                    ignore_error=step.get('ignore_error', False),
                    execution_id=task_id,
                    celery_task_id=celery_task_id,
                    step_name=step_name  # 传递步骤名称
                )

                all_results.append({
                    'step_name': step_name,
                    'step_type': step_type,
                    'result': result
                })

                if not result.get('success') and not step.get('ignore_error', False):
                    overall_success = False
                    logger.error(f"[Fabric] 工作流步骤失败: {step_name}")
                    break

            else:
                # 其他步骤类型暂未实现
                logger.warning(f"[Fabric] 步骤类型暂未实现: {step_type}")
                all_results.append({
                    'step_name': step_name,
                    'step_type': step_type,
                    'result': {
                        'success': False,
                        'message': f'步骤类型 {step_type} 暂未在Fabric中实现'
                    }
                })
                if not step.get('ignore_error', False):
                    overall_success = False
                    break

        # 推送最终状态
        realtime_log_service.push_status(task_id, {
            'status': 'completed' if overall_success else 'failed',
            'progress': 100,
            'current_step': '工作流完成' if overall_success else '工作流失败',
            'total_hosts': len(target_hosts),
            'message': '工作流执行完成' if overall_success else '工作流执行失败'
        })

        return {
            'success': overall_success,
            'results': all_results,
            'engine': 'fabric',
            'message': '工作流执行完成' if overall_success else '工作流执行失败'
        }

    except Exception as e:
        logger.error(f"[Fabric] 工作流执行异常: {e}")

        # 推送错误状态
        try:
            realtime_log_service.push_status(task_id, {
                'status': 'failed',
                'progress': 100,
                'current_step': '工作流异常',
                'total_hosts': len(target_hosts),
                'message': f'工作流执行异常: {str(e)}'
            })
        except Exception as log_error:
            logger.error(f"推送错误状态失败: {log_error}")

        return {
            'success': False,
            'message': f'工作流执行异常: {str(e)}',
            'results': [],
            'engine': 'fabric'
        }


def execute_file_transfer_on_hosts(transfer_type, local_path, remote_path, target_hosts, timeout=None,
                                   execution_mode='parallel', source_server_host=None, source_server_user=None,
                                   source_server_path=None, celery_task_id=None, **kwargs):
    """
    使用Fabric在指定主机上执行文件传输
    """
    try:
        if timeout is None:
            from apps.system_config.models import ConfigManager
            timeout = ConfigManager.get('task.job_timeout', 360)

        # 使用execution_id作为Redis Stream的键名
        execution_id = kwargs.get('execution_id')
        celery_task_id = celery_task_id or str(uuid.uuid4())
        task_id = str(execution_id) if execution_id else celery_task_id

        logger.info(f"[Fabric] 开始文件传输，目标主机数: {len(target_hosts)}, 任务ID: {celery_task_id}, 执行ID: {execution_id}")

        # 根据调用来源确定步骤名称
        step_name = kwargs.get('step_name', f'文件传输 ({transfer_type})')
        
        # 推送任务开始状态
        realtime_log_service.push_status(task_id, {
            'status': 'running',
            'progress': 0,
            'current_step': step_name,
            'total_hosts': len(target_hosts),
            'success_hosts': 0,
            'failed_hosts': 0,
            'running_hosts': len(target_hosts),
            'message': f'开始{step_name}'
        })

        results = []
        rolling_strategy = kwargs.get('rolling_strategy', 'fail_pause')

        if execution_mode == 'parallel':
            from celery import group

            logger.info(f"[Fabric] 开始并行文件传输，目标主机数: {len(target_hosts)}")
            
            # 从kwargs中提取account_id
            account_id = kwargs.pop('account_id', None)
            
            job = group(
                execute_file_transfer_on_single_host.s(
                    transfer_type, local_path, remote_path, host_info, timeout, task_id,
                    source_server_host, source_server_user, source_server_path, account_id, **kwargs
                ) for host_info in target_hosts
            )

            with allow_join_result():
                group_result = job.apply_async()
                for result in group_result.iterate():
                    results.append(result)
                    logger.info(f"[Fabric] 主机 {result.get('host_name')} 并行传输完成: {result.get('success')}")

        elif execution_mode == 'serial':
            # 串行执行
            for host_info in target_hosts:
                # 从kwargs中提取account_id
                account_id = kwargs.pop('account_id', None)
                
                with allow_join_result():
                    async_result = execute_file_transfer_on_single_host.apply_async(args=(
                        transfer_type, local_path, remote_path, host_info, timeout, task_id,
                        source_server_host, source_server_user, source_server_path, account_id
                    ), kwargs=kwargs)
                    result = async_result.get()
                results.append(result)

                # 如果传输失败且策略不是忽略错误，停止后续主机的执行
                if not result['success'] and rolling_strategy != 'ignore_error':
                    logger.warning(f"主机 {host_info['name']} 传输失败，停止后续主机执行")
                    break

        elif execution_mode == 'rolling':
            # 滚动执行
            import time
            batch_size_percent = kwargs.get('rolling_batch_size', 20)  # 百分比
            batch_delay = kwargs.get('rolling_batch_delay', 0)

            # 计算实际批次大小（按百分比）
            total_hosts = len(target_hosts)
            actual_batch_size = max(1, int(total_hosts * batch_size_percent / 100))

            logger.info(f"[Fabric] 滚动传输: 总主机数={total_hosts}, 批次百分比={batch_size_percent}%, 实际批次大小={actual_batch_size}, 策略={rolling_strategy}")

            for i in range(0, len(target_hosts), actual_batch_size):
                batch = target_hosts[i:i + actual_batch_size]
                batch_num = i // actual_batch_size + 1
                total_batches = (len(target_hosts) + actual_batch_size - 1) // actual_batch_size

                logger.info(f"[Fabric] 传输批次 {batch_num}/{total_batches}, 主机数: {len(batch)}")

                # 从kwargs中提取account_id
                account_id = kwargs.get('account_id')
                
                # 并行执行当前批次
                from celery import group
                job = group(
                    execute_file_transfer_on_single_host.s(
                        transfer_type, local_path, remote_path, host_info, timeout, task_id,
                        source_server_host, source_server_user, source_server_path, account_id, **kwargs
                    ) for host_info in batch
                )

                # 使用allow_join_result上下文管理器来安全地获取结果
                with allow_join_result():
                    batch_result = job.apply_async()
                    batch_results = batch_result.get()
                    results.extend(batch_results)

                # 检查滚动策略
                if rolling_strategy == 'ignore_error':
                    # 忽略错误继续执行，不做特殊处理
                    pass
                else:
                    # fail_pause 策略：检查当前批次是否有失败
                    batch_failed = any(not result.get('success', False) for result in batch_results)
                    if batch_failed:
                        logger.warning(f"[Fabric] 批次 {batch_num} 有失败主机，根据策略({rolling_strategy})暂停传输")
                        break

                # 批次间延迟
                if i + actual_batch_size < len(target_hosts) and batch_delay > 0:
                    logger.info(f"[Fabric] 批次间延迟 {batch_delay} 秒")
                    time.sleep(batch_delay)

        # 统计结果
        success_count = sum(1 for r in results if r['success'])
        failed_count = len(results) - success_count
        overall_success = failed_count == 0

        # 推送最终状态
        realtime_log_service.push_status(task_id, {
            'status': 'completed' if overall_success else 'failed',
            'progress': 100,
            'current_step': '文件传输完成',
            'total_hosts': len(target_hosts),
            'success_hosts': success_count,
            'failed_hosts': failed_count,
            'running_hosts': 0,
            'message': f'文件传输完成，成功: {success_count}, 失败: {failed_count}'
        })

        logger.info(f"[Fabric] 文件传输完成，成功: {success_count}, 失败: {failed_count}")

        return {
            'success': overall_success,
            'message': f'文件传输完成，成功: {success_count}, 失败: {failed_count}',
            'results': results,
            'summary': {
                'total': len(target_hosts),
                'success': success_count,
                'failed': failed_count
            }
        }

    except Exception as e:
        logger.error(f"[Fabric] 文件传输任务失败: {e}")

        # 推送错误状态
        realtime_log_service.push_status(task_id, {
            'status': 'failed',
            'progress': 0,
            'current_step': '文件传输失败',
            'total_hosts': len(target_hosts),
            'success_hosts': 0,
            'failed_hosts': len(target_hosts),
            'running_hosts': 0,
            'message': f'文件传输失败: {str(e)}'
        })

        return {
            'success': False,
            'message': f'文件传输失败: {str(e)}',
            'results': []
        }


@shared_task(bind=True)
def execute_file_transfer_on_single_host(self, transfer_type, local_path, remote_path, host_info, timeout, task_id=None,
                                        source_server_host=None, source_server_user=None, source_server_path=None, account_id=None, **kwargs):
    """
    在单个主机上执行文件传输
    """
    try:
        from apps.hosts.models import Host

        host = Host.objects.get(id=host_info['id'])

        # 推送开始传输日志
        if task_id:
            realtime_log_service.push_log(task_id, host.id, {
                'host_name': host.name,
                'host_ip': host.ip_address,
                'log_type': 'info',
                'content': f'[Fabric] 开始在主机 {host.name} ({host.ip_address}) 上{transfer_type}文件',
                'step_name': '文件传输',
                'step_order': 1
            })

        # 处理account_id（如果存在）
        if account_id:
            try:
                account_id = int(account_id)
            except (ValueError, TypeError):
                account_id = None
                logger.warning(f"无效的account_id: {account_id}")
                logger.warning(f"无效的account_id: {kwargs.get('account_id')}")

        # 使用Fabric执行文件传输
        result = fabric_ssh_manager.transfer_file(
            host=host,
            transfer_type=transfer_type,
            local_path=local_path,
            remote_path=remote_path,
            timeout=timeout,
            task_id=task_id,
            source_server_host=source_server_host,
            source_server_user=source_server_user,
            source_server_path=source_server_path,
            account_id=account_id,
            **kwargs
        )

        return result

    except Exception as e:
        logger.error(f"[Fabric] 单主机文件传输失败: {e}")
        return {
            'success': False,
            'host_id': host_info['id'],
            'host_name': host_info['name'],
            'host_ip': host_info['ip_address'],
            'message': f'传输失败: {str(e)}',
        }


@shared_task(bind=True, base=AbortableTask, name='executor.fabric.script_execution')
def execute_script_on_hosts_fabric_task(self, *args, **kwargs):
    """Celery入口：封装脚本执行"""
    timeout = kwargs.get('timeout')
    if timeout:
        self.soft_time_limit = timeout
    kwargs['celery_task_id'] = self.request.id
    return execute_script_on_hosts_fabric(*args, **kwargs)


@shared_task(bind=True, base=AbortableTask, name='executor.fabric.workflow_execution')
def execute_workflow_on_hosts_task(self, *args, **kwargs):
    """Celery入口：封装工作流执行"""
    kwargs['celery_task_id'] = self.request.id
    return execute_workflow_on_hosts(*args, **kwargs)


@shared_task(bind=True, base=AbortableTask, name='executor.fabric.file_transfer')
def execute_file_transfer_on_hosts_task(self, *args, **kwargs):
    """Celery入口：封装文件传输"""
    timeout = kwargs.get('timeout')
    if timeout:
        self.soft_time_limit = timeout
    kwargs['celery_task_id'] = self.request.id
    return execute_file_transfer_on_hosts(*args, **kwargs)


def start_script_execution(**kwargs):
    """
    对外统一入口：服务层调用此函数以异步方式调度脚本执行
    """
    return execute_script_on_hosts_fabric_task.apply_async(kwargs=kwargs)


def start_workflow_execution(**kwargs):
    """
    对外统一入口：服务层调用此函数以异步方式调度工作流执行
    """
    return execute_workflow_on_hosts_task.apply_async(kwargs=kwargs)


def start_file_transfer(**kwargs):
    """
    对外统一入口：服务层调用此函数以异步方式调度文件传输
    """
    return execute_file_transfer_on_hosts_task.apply_async(kwargs=kwargs)