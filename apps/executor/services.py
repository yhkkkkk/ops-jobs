"""
统一的执行记录服务
"""
import logging
from django.utils import timezone
from django.contrib.contenttypes.models import ContentType
from .models import ExecutionRecord, ExecutionStep
from utils.realtime_logs import realtime_log_service

logger = logging.getLogger(__name__)


class ExecutionRecordService:
    """统一的执行记录服务"""
    
    @staticmethod
    def create_execution_record(execution_type, name, executed_by, 
                              related_object=None, trigger_type='manual',
                              execution_parameters=None,
                              client_ip=None, user_agent=None, **kwargs):
        """创建执行记录"""
        try:
            # 准备关联对象信息
            content_type = None
            object_id = None
            if related_object:
                content_type = ContentType.objects.get_for_model(related_object)
                object_id = related_object.pk
            
            # 创建执行记录
            execution_record = ExecutionRecord.objects.create(
                execution_type=execution_type,
                name=name,
                description=kwargs.get('description', ''),
                content_type=content_type,
                object_id=object_id,
                status='pending',
                trigger_type=trigger_type,
                executed_by=executed_by,
                execution_parameters=execution_parameters or {},
                client_ip=client_ip,
                user_agent=user_agent or ''  # 确保不为 None
            )
            
            logger.info(f"创建执行记录: {execution_record.execution_id}")
            return execution_record
            
        except Exception as e:
            logger.error(f"创建执行记录失败: {e}")
            raise
    
    @staticmethod
    def update_execution_status(execution_record, status,
                                error_message=None, execution_results=None):
        """更新执行状态"""
        try:
            execution_record.status = status
            
            if status == 'running' and not execution_record.started_at:
                execution_record.started_at = timezone.now()
            
            if status in ['success', 'failed', 'cancelled', 'timeout']:
                if not execution_record.finished_at:
                    execution_record.finished_at = timezone.now()

                if error_message:
                    execution_record.error_message = error_message

                if execution_results:
                    execution_record.execution_results = execution_results
            
            execution_record.save()
            
            # 推送状态更新到实时日志（统一使用 execution_id 作为 task_id）
            summary = (execution_record.execution_results or {}).get('summary', {})
            total_hosts = summary.get('total_hosts', 0)
            success_hosts = summary.get('success_hosts', 0)
            failed_hosts = summary.get('failed_hosts', 0)
            realtime_log_service.push_status(str(execution_record.execution_id), {
                'status': status,
                'progress': 100 if status in ['success', 'failed'] else 0,
                'current_step': execution_record.name,
                'total_hosts': total_hosts,
                'success_hosts': success_hosts,
                'failed_hosts': failed_hosts,
                'running_hosts': max(total_hosts - success_hosts - failed_hosts, 0),
                'message': f'执行状态: {execution_record.get_status_display()}'
            })

            # 如果执行完成，立即归档日志（同步执行，确保日志不丢失）
            if status in ['success', 'failed', 'cancelled', 'timeout']:
                try:
                    from utils.log_archive_service import log_archive_service
                    archive_success = log_archive_service.archive_execution_logs(
                        execution_record.execution_id,
                        str(execution_record.execution_id)
                    )
                    if not archive_success:
                        logger.warning(f"日志归档失败: {execution_record.execution_id}")
                except Exception as e:
                    logger.error(f"日志归档异常: {execution_record.execution_id} - {e}")

            # 更新ExecutionPlan统计
            if hasattr(execution_record.related_object, 'success_executions'):
                from apps.job_templates.services import ExecutionPlanService
                ExecutionPlanService.update_plan_statistics(execution_record.related_object, status)

            logger.info(f"更新执行状态: {execution_record.execution_id} -> {status}")

        except Exception as e:
            logger.error(f"更新执行状态失败: {execution_record.execution_id} - {e}")
            raise
    
    @staticmethod
    def update_host_results(execution_record, total_hosts=None, success_hosts=None, failed_hosts=None):
        """更新主机执行结果统计"""
        try:
            # 推送统计更新到实时日志（统一使用 execution_id 作为 task_id）
            summary = (execution_record.execution_results or {}).get('summary', {})
            total = total_hosts if total_hosts is not None else summary.get('total_hosts', 0)
            success = success_hosts if success_hosts is not None else summary.get('success_hosts', 0)
            failed = failed_hosts if failed_hosts is not None else summary.get('failed_hosts', 0)
            running = max(total - success - failed, 0)
            progress = (success + failed) / total * 100 if total > 0 else 0
            realtime_log_service.push_status(str(execution_record.execution_id), {
                'status': execution_record.status,
                'progress': progress,
                'current_step': execution_record.name,
                'total_hosts': total,
                'success_hosts': success,
                'failed_hosts': failed,
                'running_hosts': running,
                'message': '主机执行统计更新'
            })
            
        except Exception as e:
            logger.error(f"更新主机结果失败: {execution_record.execution_id} - {e}")
            raise
    
    @staticmethod
    def create_execution_step(execution_record, step_name, step_type, step_order,
                            step_parameters=None):
        """创建执行步骤"""
        try:
            step = ExecutionStep.objects.create(
                execution_record=execution_record,
                step_name=step_name,
                step_type=step_type,
                step_order=step_order,
                step_parameters=step_parameters or {}
            )
            
            logger.debug(f"创建执行步骤: {execution_record.execution_id} - {step_name}")
            return step
            
        except Exception as e:
            logger.error(f"创建执行步骤失败: {execution_record.execution_id} - {step_name} - {e}")
            raise
    
    @staticmethod
    def update_step_status(step, status, step_results=None, host_results=None, 
                            error_message=None):
        """更新步骤状态"""
        try:
            step.status = status
            
            if status == 'running' and not step.started_at:
                step.started_at = timezone.now()
            
            if status in ['success', 'failed', 'skipped']:
                if not step.finished_at:
                    step.finished_at = timezone.now()
                
                if step_results:
                    step.step_results = step_results
                
                if host_results:
                    step.host_results = host_results
                
                if error_message:
                    step.error_message = error_message
            
            step.save()
            
            logger.debug(f"更新步骤状态: {step.execution_record.execution_id} - {step.step_name} -> {status}")
            
        except Exception as e:
            logger.error(f"更新步骤状态失败: {step.execution_record.execution_id} - {step.step_name} - {e}")
            raise
    
    @staticmethod
    def get_execution_statistics(execution_type=None, executed_by=None, days=30):
        """获取执行统计"""
        try:
            from datetime import timedelta
            from django.db.models import Count, Q
            
            cutoff_date = timezone.now() - timedelta(days=days)
            queryset = ExecutionRecord.objects.filter(created_at__gte=cutoff_date)
            
            if execution_type:
                queryset = queryset.filter(execution_type=execution_type)
            
            if executed_by:
                queryset = queryset.filter(executed_by=executed_by)
            
            stats = queryset.aggregate(
                total=Count('id'),
                success=Count('id', filter=Q(status='success')),
                failed=Count('id', filter=Q(status='failed')),
                running=Count('id', filter=Q(status__in=['pending', 'running']))
            )
            
            stats['success_rate'] = (stats['success'] / stats['total'] * 100) if stats['total'] > 0 else 0
            
            return stats
            
        except Exception as e:
            logger.error(f"获取执行统计失败: {e}")
            return {
                'total': 0,
                'success': 0,
                'failed': 0,
                'running': 0,
                'success_rate': 0
            }

    @staticmethod
    def retry_step_inplace(execution_record, step_id, retry_type='failed_only', user=None, host_ids=None):
        """步骤原地重试服务 - 不创建新的执行记录，在原记录上重试（只支持Agent方式）
        
        Args:
            execution_record: 执行记录
            step_id: 步骤ID
            retry_type: 重试类型，'failed_only' 或 'all'
            user: 执行用户
            host_ids: 可选，指定要重试的主机ID列表（如果提供，则只重试这些主机）
        """
        try:
            # 获取要重试的步骤
            try:
                step = ExecutionStep.objects.get(
                    id=step_id,
                    execution_record=execution_record
                )
            except ExecutionStep.DoesNotExist:
                return {'success': False, 'error': '步骤不存在'}

            # 检查执行记录状态
            if execution_record.status not in ['failed', 'running']:
                return {'success': False, 'error': '只有失败或运行中的执行记录才能进行原地重试'}

            # 检查步骤状态
            if step.status not in ['failed', 'skipped', 'timeout']:
                return {'success': False, 'error': '只有失败、跳过或超时的步骤才能重试'}

            # 根据重试类型或主机ID列表确定要重试的主机
            if host_ids:
                # 如果指定了主机ID列表，只重试这些主机
                target_hosts = [
                    host for host in step.host_results 
                    if host.get('host_id') in host_ids
                ]
            elif retry_type == 'failed_only':
                # 只重试失败的主机
                target_hosts = [
                    host for host in step.host_results 
                    if host.get('status') in ['failed', 'timeout']
                ]
            else:
                # 重试所有主机
                target_hosts = step.host_results

            if not target_hosts:
                return {'success': False, 'error': '没有需要重试的主机'}

            # 重置步骤状态为待执行
            step.status = 'pending'
            step.started_at = None
            step.finished_at = None
            step.error_message = ""  # TextField 不允许 NULL，使用空串清理
            step.host_results = []  # 清空之前的结果
            step.save()

            # 更新执行记录状态
            execution_record.status = 'running'
            execution_record.retry_count += 1
            execution_record.last_retry_at = timezone.now()
            execution_record.save()

            # 记录重试日志
            logger.info(f"开始原地重试步骤: {step.step_name}, 执行记录: {execution_record.execution_id}")

            # 只支持Agent方式执行
            agent_server_url = execution_record.execution_parameters.get('agent_server_url')

            # 根据执行类型启动原地重试（只支持Agent方式）
            if execution_record.execution_type == 'job_workflow':
                # 工作流执行 - 从指定步骤开始
                result = ExecutionRecordService._retry_job_workflow_from_step_inplace_agent(
                    execution_record, step, target_hosts, user, agent_server_url
                )
            elif execution_record.execution_type == 'quick_script':
                # 快速脚本执行
                result = ExecutionRecordService._retry_quick_script_step_inplace_agent(
                    execution_record, step, target_hosts, user, agent_server_url
                )
            elif execution_record.execution_type == 'quick_file_transfer':
                # 快速文件传输
                result = ExecutionRecordService._retry_file_transfer_step_inplace_agent(
                    execution_record, step, target_hosts, user, agent_server_url
                )
            else:
                result = {'success': False, 'error': '不支持的执行类型'}

            if result['success']:
                # 补充步骤执行结果并标记成功
                step.host_results = target_hosts
                step.status = 'success'
                step.finished_at = timezone.now()
                step.save(update_fields=['host_results', 'status', 'finished_at'])

                ExecutionRecordService.update_execution_status(
                    execution_record=execution_record,
                    status='success',
                    execution_results=result.get('execution_results')
                )
                return {
                    'success': True,
                    'execution_record_id': execution_record.id,
                    'message': f'步骤原地重试已启动，执行记录ID: {execution_record.execution_id}'
                }
            else:
                # 重试失败，恢复步骤状态
                step.status = 'failed'
                step.error_message = f"原地重试失败: {result.get('error', '未知错误')}"
                step.finished_at = timezone.now()
                step.save()
                
                # 恢复执行记录状态
                execution_record.status = 'failed'
                execution_record.save()
                
                return result

        except Exception as e:
            logger.error(f"步骤原地重试失败: {e}")
            return {'success': False, 'error': f'步骤原地重试失败: {str(e)}'}

    @staticmethod
    def ignore_step_error(execution_record, step_id, user=None):
        """忽略步骤错误继续执行服务"""
        try:
            # 获取要忽略错误的步骤
            try:
                step = ExecutionStep.objects.get(
                    id=step_id,
                    execution_record=execution_record
                )
            except ExecutionStep.DoesNotExist:
                return {'success': False, 'error': '步骤不存在'}

            # 检查执行记录状态
            if execution_record.status != 'failed':
                return {'success': False, 'error': '只有失败的执行记录才能忽略错误'}

            # 检查步骤状态
            if step.status != 'failed':
                return {'success': False, 'error': '只有失败的步骤才能忽略错误'}

            # 标记步骤为已跳过
            step.status = 'skipped'
            step.error_message = f"错误已忽略，由用户 {user.username if user else 'system'} 跳过"
            step.finished_at = timezone.now()
            step.save()

            # 获取下一个步骤
            next_step = ExecutionStep.objects.filter(
                execution_record=execution_record,
                step_order__gt=step.step_order,
                status='pending'
            ).order_by('step_order').first()

            if next_step:
                # 从下一个步骤继续执行
                result = ExecutionRecordService._continue_execution_from_step(
                    execution_record, next_step, user
                )
                
                if result['success']:
                    return {
                        'success': True,
                        'message': f'已忽略步骤 {step.step_name} 的错误，从步骤 {next_step.step_name} 继续执行'
                    }
                else:
                    return result
            else:
                # 没有下一个步骤，标记执行记录为成功
                execution_record.status = 'success'
                execution_record.finished_at = timezone.now()
                execution_record.save()

                return {
                    'success': True,
                    'message': f'已忽略步骤 {step.step_name} 的错误，执行完成'
                }

        except Exception as e:
            logger.error(f"忽略步骤错误失败: {str(e)}", exc_info=True)
            return {'success': False, 'error': f'忽略步骤错误失败: {str(e)}'}

    @staticmethod
    def _continue_execution_from_step(execution_record, step, user):
        """从指定步骤继续执行（只支持Agent方式）"""
        try:
            # 根据执行类型继续执行
            if execution_record.execution_type == 'job_workflow':
                return ExecutionRecordService._continue_job_workflow_from_step(
                    execution_record, step, user
                )
            elif execution_record.execution_type == 'quick_script':
                return ExecutionRecordService._continue_quick_script_from_step(
                    execution_record, step, user
                )
            elif execution_record.execution_type == 'quick_file_transfer':
                return ExecutionRecordService._continue_file_transfer_from_step(
                    execution_record, step, user
                )
            else:
                return {'success': False, 'error': '不支持的执行类型'}

        except Exception as e:
            logger.error(f"继续执行失败: {str(e)}", exc_info=True)
            return {'success': False, 'error': f'继续执行失败: {str(e)}'}

    @staticmethod
    def _continue_job_workflow_from_step(execution_record, step, user):
        """从指定步骤继续工作流执行（只支持Agent方式）"""
        try:
            from apps.job_templates.services import ExecutionPlanService

            # 获取Agent-Server地址
            agent_server_url = execution_record.execution_parameters.get('agent_server_url')

            # 启动异步工作流执行 - 使用ExecutionPlanService（Agent方式）
            result = ExecutionPlanService.execute_plan(
                execution_plan=execution_record.related_object,
                user=user,
                trigger_type='retry',
                name=f"重试: {execution_record.name}",
                description=f"从步骤 {step.step_order} 重试执行",
                execution_mode='agent',  # 只支持Agent方式
                agent_server_url=agent_server_url,
                start_step_order=step.step_order,  # 从指定步骤开始
            )

            if not result.get('success'):
                return {'success': False, 'error': result.get('error', '工作流重试失败')}

            return result

        except Exception as e:
            logger.error(f"继续工作流执行失败: {str(e)}", exc_info=True)
            return {'success': False, 'error': f'继续工作流执行失败: {str(e)}'}

    @staticmethod
    def _continue_quick_script_from_step(execution_record, step, user):
        """从指定步骤继续脚本执行（只支持Agent方式）"""
        try:
            from apps.agents.execution_service import AgentExecutionService
            from apps.hosts.models import Host

            # 从execution_parameters获取目标主机ID列表
            target_host_ids = execution_record.execution_parameters.get('target_host_ids', [])
            if not target_host_ids:
                return {'success': False, 'error': '没有目标主机'}

            # 获取主机对象
            target_hosts = Host.objects.filter(id__in=target_host_ids)

            # 获取Agent-Server地址
            agent_server_url = execution_record.execution_parameters.get('agent_server_url')

            # 通过Agent执行脚本
            result = AgentExecutionService.execute_script_via_agent(
                execution_record=execution_record,
                script_content=step.step_parameters.get('script_content', ''),
                script_type=step.step_parameters.get('script_type', 'shell'),
                target_hosts=list(target_hosts),
                timeout=step.step_parameters.get('timeout', 300),
                global_variables=execution_record.execution_parameters.get('global_variables', {}),
                step_id=str(step.id),
                agent_server_url=agent_server_url,
            )

            if result['success']:
                # 更新执行记录状态
                execution_record.status = 'running'
                execution_record.started_at = timezone.now()
                execution_record.save()

            return result

        except Exception as e:
            logger.error(f"继续脚本执行失败: {str(e)}", exc_info=True)
            return {'success': False, 'error': f'继续脚本执行失败: {str(e)}'}

    @staticmethod
    def _continue_file_transfer_from_step(execution_record, step, user):
        """从指定步骤继续文件传输（只支持Agent方式）"""
        try:
            from apps.agents.execution_service import AgentExecutionService
            from apps.hosts.models import Host

            # 从execution_parameters获取目标主机ID列表
            target_host_ids = execution_record.execution_parameters.get('target_host_ids', [])
            if not target_host_ids:
                return {'success': False, 'error': '没有目标主机'}

            # 获取主机对象
            target_hosts = Host.objects.filter(id__in=target_host_ids)

            # 获取Agent-Server地址
            agent_server_url = execution_record.execution_parameters.get('agent_server_url')

            # 获取步骤参数（仅 artifact 模式）
            step_params = step.step_parameters or {}
            file_sources = step_params.get('file_sources') or []
            if not file_sources:
                return {'success': False, 'error': 'file_sources required for file_transfer step'}

            timeout = step_params.get('timeout', 300)
            bandwidth_limit = step_params.get('bandwidth_limit', 0)

            # 仅处理首个源（历史接口仅支持单文件），如需多文件应在上层拆分
            src = file_sources[0]
            remote_path = src.get('remote_path') or step_params.get('remote_path', '')
            download_url = src.get('download_url')
            storage_path = src.get('storage_path')
            if storage_path and not download_url:
                storage_type = ConfigManager.get('storage.type', 'local')
                from apps.agents.storage_service import StorageService
                backend = StorageService.get_backend(storage_type)
                download_url = backend.generate_url(storage_path, expires_in=3600) if backend else None

            if not download_url:
                return {'success': False, 'error': 'download_url/storage_path missing for file transfer'}

            # 通过Agent执行文件传输
            result = AgentExecutionService.execute_file_transfer_via_agent(
                execution_record=execution_record,
                remote_path=remote_path,
                target_hosts=list(target_hosts),
                timeout=timeout,
                bandwidth_limit=bandwidth_limit,
                download_url=download_url,
                checksum=src.get('sha256'),
                size=src.get('size'),
                auth_headers=src.get('auth_headers') or {},
                step_id=str(step.id),
                agent_server_url=agent_server_url,
            )

            if result['success']:
                # 更新执行记录状态
                execution_record.status = 'running'
                execution_record.started_at = timezone.now()
                execution_record.save()

            return result

        except Exception as e:
            logger.error(f"继续文件传输失败: {str(e)}", exc_info=True)
            return {'success': False, 'error': f'继续文件传输失败: {str(e)}'}

    @staticmethod
    def _retry_job_workflow_from_step_inplace_agent(execution_record, step, target_hosts, user, agent_server_url):
        """工作流步骤原地重试（Agent方式）"""
        try:
            from apps.agents.execution_service import AgentExecutionService
            from apps.hosts.models import Host

            # target_hosts是字典列表，需要转换为Host对象
            host_ids = []
            if target_hosts:
                for h in target_hosts:
                    if isinstance(h, dict):
                        hid = h.get('id') or h.get('host_id')
                        if hid:
                            host_ids.append(hid)
                    elif hasattr(h, 'id'):
                        host_ids.append(h.id)
                    else:
                        host_ids.append(h)
            if not host_ids:
                return {'success': False, 'error': '没有有效的主机ID'}

            target_host_objs = Host.objects.filter(id__in=host_ids)

            # 获取步骤参数
            script_content = step.step_parameters.get('script_content', '')
            script_type = step.step_parameters.get('script_type', 'shell')
            timeout = step.step_parameters.get('timeout', 300)
            global_variables = execution_record.execution_parameters.get('global_variables', {})

            # 通过Agent执行脚本
            result = AgentExecutionService.execute_script_via_agent(
                execution_record=execution_record,
                script_content=script_content,
                script_type=script_type,
                target_hosts=list(target_host_objs),
                timeout=timeout,
                global_variables=global_variables,
                step_id=str(step.id),
                agent_server_url=agent_server_url,
            )

            return result

        except Exception as e:
            logger.error(f"工作流步骤原地重试失败: {str(e)}", exc_info=True)
            return {'success': False, 'error': f'工作流步骤重试失败: {str(e)}'}

    @staticmethod
    def _retry_quick_script_step_inplace_agent(execution_record, step, target_hosts, user, agent_server_url):
        """快速脚本步骤原地重试（Agent方式）"""
        try:
            from apps.agents.execution_service import AgentExecutionService
            from apps.hosts.models import Host

            # target_hosts是字典列表，需要转换为Host对象
            host_ids = [h.get('id') for h in target_hosts if isinstance(h, dict) and h.get('id')]
            if not host_ids:
                # 如果target_hosts是Host对象列表
                host_ids = [h.id if hasattr(h, 'id') else h for h in target_hosts]

            target_host_objs = Host.objects.filter(id__in=host_ids)

            # 获取步骤参数
            script_content = step.step_parameters.get('script_content', '')
            script_type = step.step_parameters.get('script_type', 'shell')
            timeout = step.step_parameters.get('timeout', 300)
            global_variables = execution_record.execution_parameters.get('global_variables', {})

            # 通过Agent执行脚本
            result = AgentExecutionService.execute_script_via_agent(
                execution_record=execution_record,
                script_content=script_content,
                script_type=script_type,
                target_hosts=list(target_host_objs),
                timeout=timeout,
                global_variables=global_variables,
                step_id=str(step.id),
                agent_server_url=agent_server_url,
            )

            return result

        except Exception as e:
            logger.error(f"快速脚本步骤原地重试失败: {str(e)}", exc_info=True)
            return {'success': False, 'error': f'快速脚本步骤重试失败: {str(e)}'}

    @staticmethod
    def _retry_file_transfer_step_inplace_agent(execution_record, step, target_hosts, user, agent_server_url):
        """文件传输步骤原地重试（Agent方式）"""
        try:
            from apps.agents.execution_service import AgentExecutionService
            from apps.hosts.models import Host

            # target_hosts是字典列表，需要转换为Host对象
            host_ids = [h.get('host_id') for h in target_hosts if isinstance(h, dict) and h.get('host_id')]
            if not host_ids:
                # 如果target_hosts是Host对象列表
                host_ids = [h.id if hasattr(h, 'id') else h for h in target_hosts]

            target_host_objs = Host.objects.filter(id__in=host_ids)

            # 获取步骤参数（仅 artifact 模式）
            step_params = step.step_parameters or {}
            file_sources = step_params.get('file_sources') or []
            if not file_sources:
                return {'success': False, 'error': 'file_sources required for file_transfer step'}

            timeout = step_params.get('timeout', 300)
            bandwidth_limit = step_params.get('bandwidth_limit', 0)

            src = file_sources[0]
            remote_path = src.get('remote_path') or step_params.get('remote_path', '')
            download_url = src.get('download_url')
            storage_path = src.get('storage_path')
            if storage_path and not download_url:
                storage_type = ConfigManager.get('storage.type', 'local')
                from apps.agents.storage_service import StorageService
                backend = StorageService.get_backend(storage_type)
                download_url = backend.generate_url(storage_path, expires_in=3600) if backend else None

            if not download_url:
                return {'success': False, 'error': 'download_url/storage_path missing for file transfer'}

            # 通过Agent执行文件传输
            result = AgentExecutionService.execute_file_transfer_via_agent(
                execution_record=execution_record,
                remote_path=remote_path,
                target_hosts=list(target_host_objs),
                timeout=timeout,
                bandwidth_limit=bandwidth_limit,
                download_url=download_url,
                checksum=src.get('sha256'),
                size=src.get('size'),
                auth_headers=src.get('auth_headers') or {},
                step_id=str(step.id),
                agent_server_url=agent_server_url,
            )

            return result

        except Exception as e:
            logger.error(f"文件传输步骤原地重试失败: {str(e)}", exc_info=True)
            return {'success': False, 'error': f'文件传输步骤重试失败: {str(e)}'}
