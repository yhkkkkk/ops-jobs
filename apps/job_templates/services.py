"""
执行方案服务 - 直接执行ExecutionPlan
"""
import logging
import os
from django.utils import timezone
from django.db import transaction
from django.conf import settings
from apps.executor.services import ExecutionRecordService
from apps.agents.execution_service import AgentExecutionService

logger = logging.getLogger(__name__)


class ExecutionPlanService:
    """执行方案服务"""
    @staticmethod
    def execute_template_debug(template, user, trigger_type='debug', execution_parameters=None,
                              client_ip=None, user_agent=None, **kwargs):
        """直接执行模板调试 - 不创建临时执行方案"""
        try:
            if not template:
                return {
                    'success': False,
                    'error': '作业模板不存在'
                }

            # 获取模板的所有步骤
            template_steps = template.steps.all().order_by('order')
            
            if not template_steps.exists():
                return {
                    'success': False,
                    'error': '作业模板没有包含任何步骤'
                }

            # 收集所有目标主机
            all_target_hosts = set()
            for step in template_steps:
                # 添加步骤的直接主机
                all_target_hosts.update(step.target_hosts.all())
                # 添加步骤分组中的主机
                for group in step.target_groups.all():
                    all_target_hosts.update(group.host_set.all())

            all_target_hosts = list(all_target_hosts)
            
            if not all_target_hosts:
                return {
                    'success': False,
                    'error': '作业模板的步骤没有配置目标主机'
                }

            # 合并全局变量和执行参数
            global_parameters = execution_parameters or {}

            # 创建执行记录（关联到模板而不是执行方案）
            execution_record = ExecutionRecordService.create_execution_record(
                execution_type='job_workflow',
                name=kwargs.get('name', f'[调试] {template.name}'),
                description=kwargs.get('description', f'调试作业模板 {template.name}'),
                executed_by=user,
                related_object=template,  # 关联到模板
                trigger_type=trigger_type,
                execution_parameters=global_parameters,
                target_hosts=[{
                    'id': host.id,
                    'name': host.name,
                    'ip_address': host.ip_address
                } for host in all_target_hosts],
                client_ip=client_ip,
                user_agent=user_agent
            )

            # 准备可序列化的步骤数据（直接从模板步骤创建）
            serializable_template_steps = []
            for step in template_steps:
                step_data = {
                    'id': f'template_step_{step.id}',  # 使用特殊ID标识模板步骤
                    'order': step.order,
                    'step_id': step.id,
                    'step_name': step.name,
                    'step_type': step.step_type,
                    'step_parameters': step.step_parameters,
                    'script_content': step.script_content,
                    'timeout': step.timeout,
                    'ignore_error': step.ignore_error,
                    'execution_parameters': {},  # 模板步骤没有覆盖参数
                    'target_hosts': [{
                        'id': host.id,
                        'name': host.name,
                        'ip_address': host.ip_address
                    } for host in step.target_hosts.all()],
                    'target_groups': [{
                        'id': group.id,
                        'name': group.name,
                        'hosts': [{
                            'id': host.id,
                            'name': host.name,
                            'ip_address': host.ip_address
                        } for host in group.host_set.all()]
                    } for group in step.target_groups.all()],
                    'is_template_step': True  # 标识这是模板步骤
                }
                # 文件源（仅 artifact）
                if step.step_type == 'file_transfer':
                    step_data['file_sources'] = getattr(step, 'file_sources', []) or []
                # 添加account_id
                if step.step_type == 'script' and step.account_id:
                    step_data['account_id'] = step.account_id
                elif step.step_type == 'file_transfer' and step.account_id:
                    step_data['account_id'] = step.account_id

                # 添加文件传输相关参数
                if step.step_type == 'file_transfer':
                    step_data['bandwidth_limit'] = step.bandwidth_limit
                serializable_template_steps.append(step_data)

            # 使用 Agent-Server 异步执行调试工作流（与 execute_plan 路径对齐）
            agent_server_id = kwargs.get('agent_server_id')
            if not agent_server_id:
                return {
                    'success': False,
                    'error': '请先选择Agent-Server'
                }
            execution_mode = kwargs.get('execution_mode', 'parallel')

            # 更新执行参数，添加执行方式标识
            execution_record.execution_parameters.update({
                'execution_mode': execution_mode,
                'agent_server_id': agent_server_id,
            })
            execution_record.save()

            from utils.thread_pool import get_global_thread_pool

            def execute_workflow_debug():
                try:
                    result = AgentExecutionService.execute_workflow_via_agent(
                        execution_record=execution_record,
                        plan_steps=serializable_template_steps,
                        target_hosts=all_target_hosts,
                        global_parameters=global_parameters,
                        execution_mode=execution_mode,
                        rolling_batch_size=kwargs.get('rolling_batch_size', 1),
                        rolling_batch_delay=kwargs.get('rolling_batch_delay', 0),
                        start_step_order=1,
                        agent_server_id=agent_server_id,
                    )
                    return result
                except Exception as e:
                    logger.error(f"模板调试执行异常: {str(e)}", exc_info=True)
                    ExecutionRecordService.update_execution_status(
                        execution_record=execution_record,
                        status='failed',
                        error_message=f'模板调试执行异常: {str(e)}'
                    )
                    return {'success': False, 'error': str(e)}

            run_inline = os.getenv("E2E_CONTROL_PLANE") == "1" or getattr(settings, "TESTING", False)
            if run_inline:
                execute_workflow_debug()
            else:
                pool = get_global_thread_pool()
                pool.submit(execute_workflow_debug)
                # 异步模式下标记运行中
                ExecutionRecordService.update_execution_status(
                    execution_record=execution_record,
                    status='running',
                )

            logger.info(f"模板调试执行已启动: {template.name} (执行ID: {execution_record.execution_id})")

            return {
                'success': True,
                'execution_id': execution_record.execution_id,
                'execution_record_id': execution_record.id,
                'task_id': str(execution_record.execution_id),  # 使用execution_id作为task_id
                'message': '模板调试执行已启动（Agent方式）',
                'target_host_count': len(all_target_hosts),
                'step_count': len(template_steps)
            }

        except Exception as e:
            logger.error(f"模板调试执行失败: {template.name} - {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    @staticmethod
    def execute_plan(execution_plan, user, trigger_type='manual', execution_parameters=None,
                    client_ip=None, user_agent=None, **kwargs):
        """执行执行方案 - 创建ExecutionRecord并执行"""
        try:
            # 并发控制已在系统配置中处理，无需额外检查
            if not execution_plan:
                return {
                    'success': False,
                    'error': '执行方案不存在'
                }

            with transaction.atomic():
                # 获取执行方案的步骤，每个步骤有自己的目标主机
                plan_steps = execution_plan.planstep_set.all().order_by('order')
                
                if not plan_steps.exists():
                    return {
                        'success': False,
                        'error': '执行方案没有包含任何步骤'
                    }

                # 收集所有目标主机
                all_target_hosts = set()
                for plan_step in plan_steps:
                    step = plan_step.step
                    # 添加步骤的直接主机
                    all_target_hosts.update(step.target_hosts.all())
                    # 添加步骤分组中的主机
                    for group in step.target_groups.all():
                        all_target_hosts.update(group.host_set.all())

                all_target_hosts = list(all_target_hosts)
                
                if not all_target_hosts:
                    return {
                        'success': False,
                        'error': '执行方案的步骤没有配置目标主机'
                    }

                # 合并全局变量和执行参数
                # 先使用执行方案的全局变量快照作为默认值
                default_global_parameters = execution_plan.global_parameters_snapshot or {}
                # 然后用传入的执行参数覆盖（定时任务的execution_parameters会覆盖默认值）
                global_parameters = {**default_global_parameters, **(execution_parameters or {})}

                # 创建统一的执行记录
                execution_record = ExecutionRecordService.create_execution_record(
                    execution_type='job_workflow',
                    name=kwargs.get('name', f'执行方案: {execution_plan.name}'),
                    description=kwargs.get('description', f'执行方案 {execution_plan.name}'),
                    executed_by=user,
                    related_object=execution_plan,
                    trigger_type=trigger_type,
                    execution_parameters=global_parameters,
                    target_hosts=[{
                        'id': host.id,
                        'name': host.name,
                        'ip_address': host.ip_address
                    } for host in all_target_hosts],
                    client_ip=client_ip,
                    user_agent=user_agent
                )

                # 准备可序列化的步骤数据
                serializable_plan_steps = []
                for plan_step in plan_steps:
                    step = plan_step.step
                step_data = {
                    'id': plan_step.id,
                    'order': plan_step.order,
                    'step_id': step.id,
                    'step_name': step.name,
                    'step_type': step.step_type,
                    'step_parameters': step.step_parameters,
                    'script_content': step.script_content,
                    'timeout': plan_step.get_effective_timeout(),
                    'ignore_error': step.ignore_error,
                    'execution_parameters': plan_step.get_effective_parameters(),
                    # 支持 file_sources（从模板步骤迁移过来）
                    'file_sources': getattr(step, 'file_sources', []) or [],
                    'target_hosts': [{
                        'id': host.id,
                        'name': host.name,
                        'ip_address': host.ip_address
                    } for host in step.target_hosts.all()],
                    'target_groups': [{
                        'id': group.id,
                        'name': group.name,
                        'hosts': [{
                            'id': host.id,
                            'name': host.name,
                            'ip_address': host.ip_address
                        } for host in group.host_set.all()]
                    } for group in step.target_groups.all()]
                }
                # 添加account_id
                if step.step_type == 'script' and step.account_id:
                    step_data['account_id'] = step.account_id
                elif step.step_type == 'file_transfer' and step.account_id:
                    step_data['account_id'] = step.account_id
                # 如果使用快照数据，也检查step_account_id
                if hasattr(plan_step, 'step_account_id') and plan_step.step_account_id:
                    step_data['account_id'] = plan_step.step_account_id
                serializable_plan_steps.append(step_data)

                # 只支持Agent方式执行
                agent_server_id = kwargs.get('agent_server_id')
                if not agent_server_id:
                    return {
                        'success': False,
                        'error': '请先选择Agent-Server'
                    }
                execution_mode = kwargs.get('execution_mode', 'agent')

                # 更新执行参数，添加执行方式标识
                execution_record.execution_parameters.update({
                    'execution_mode': execution_mode,
                    'agent_server_id': agent_server_id,
                })
                execution_record.save()

                # 启动异步工作流执行 - 使用Agent方式
                from apps.agents.execution_service import AgentExecutionService
                from utils.thread_pool import get_global_thread_pool

                # 在后台线程中执行工作流
                def execute_workflow():
                    try:
                        result = AgentExecutionService.execute_workflow_via_agent(
                            execution_record=execution_record,
                            plan_steps=serializable_plan_steps,
                            target_hosts=all_target_hosts,
                            global_parameters=global_parameters,
                            execution_mode=kwargs.get('execution_mode', 'parallel'),
                            rolling_batch_size=kwargs.get('rolling_batch_size', 1),
                            rolling_batch_delay=kwargs.get('rolling_batch_delay', 0),
                            start_step_order=kwargs.get('start_step_order', 1),
                            agent_server_id=agent_server_id,
                        )
                        return result
                    except Exception as e:
                        logger.error(f"工作流执行异常: {str(e)}", exc_info=True)
                        ExecutionRecordService.update_execution_status(
                            execution_record=execution_record,
                            status='failed',
                            error_message=f'工作流执行异常: {str(e)}'
                        )
                        return {'success': False, 'error': str(e)}

                run_inline = os.getenv("E2E_CONTROL_PLANE") == "1" or getattr(settings, "TESTING", False)
                if run_inline:
                    execute_workflow()
                else:
                    pool = get_global_thread_pool()
                    pool.submit(execute_workflow)
                    # 异步模式下标记运行中
                    ExecutionRecordService.update_execution_status(
                        execution_record=execution_record,
                        status='running',
                    )

                # 更新执行方案统计
                execution_plan.total_executions += 1
                execution_plan.last_executed_at = timezone.now()
                execution_plan.save()

                logger.info(f"执行方案执行已启动: {execution_plan.name} (执行ID: {execution_record.execution_id})")

                return {
                    'success': True,
                    'execution_id': execution_record.execution_id,
                    'execution_record_id': execution_record.id,
                    'task_id': str(execution_record.execution_id),  # 使用execution_id作为task_id
                    'message': '执行方案执行已启动（Agent方式）',
                    'target_host_count': len(all_target_hosts),
                    'step_count': len(plan_steps)
                }

        except Exception as e:
            logger.error(f"执行方案执行失败: {execution_plan.name} - {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    @staticmethod
    def update_plan_statistics(execution_plan, status):
        """更新执行方案统计信息"""
        try:
            # 更新执行方案统计
            if status == 'success':
                execution_plan.success_executions += 1
            elif status == 'failed':
                execution_plan.failed_executions += 1
            execution_plan.save()
            
            logger.info(f"执行方案统计更新完成: {execution_plan.name} -> {status}")
            
        except Exception as e:
            logger.error(f"更新执行方案统计失败: {execution_plan.name} - {e}")
            raise
