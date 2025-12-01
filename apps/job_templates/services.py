"""
执行方案服务 - 直接执行ExecutionPlan
"""
import logging
from django.utils import timezone
from django.db import transaction
from apps.executor.services import ExecutionRecordService
# 工作流执行现在通过Fabric任务处理

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
                # 添加account_id（如果存在）
                if step.step_type == 'script' and step.account_id:
                    step_data['account_id'] = step.account_id
                elif step.step_type == 'file_transfer' and step.account_id:
                    step_data['account_id'] = step.account_id
                serializable_template_steps.append(step_data)

            # 启动异步工作流执行
            from apps.executor.fabric_tasks import start_workflow_execution
            celery_task = start_workflow_execution(
                plan_steps=serializable_template_steps,
                target_hosts=[{
                    'id': host.id,
                    'name': host.name,
                    'ip_address': host.ip_address
                } for host in all_target_hosts],
                global_parameters=global_parameters,
                execution_mode=kwargs.get('execution_mode', 'parallel'),
                rolling_batch_size=kwargs.get('rolling_batch_size', 1),
                rolling_batch_delay=kwargs.get('rolling_batch_delay', 0),
                execution_id=execution_record.execution_id,  # 传递执行ID用于SSE日志
                is_debug=True  # 标识这是调试执行
            )

            # 更新执行记录
            ExecutionRecordService.update_execution_status(
                execution_record=execution_record,
                status='running',
                celery_task_id=celery_task.id
            )

            logger.info(f"模板调试执行已启动: {template.name} (执行ID: {execution_record.execution_id})")

            return {
                'success': True,
                'execution_id': execution_record.execution_id,
                'execution_record_id': execution_record.id,
                'task_id': celery_task.id,
                'celery_task_id': celery_task.id,
                'message': '模板调试执行已启动',
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
                global_parameters = execution_parameters or {}

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
                    # 添加account_id（如果存在）
                    if step.step_type == 'script' and step.account_id:
                        step_data['account_id'] = step.account_id
                    elif step.step_type == 'file_transfer' and step.account_id:
                        step_data['account_id'] = step.account_id
                    # 如果使用快照数据，也检查step_account_id
                    if hasattr(plan_step, 'step_account_id') and plan_step.step_account_id:
                        step_data['account_id'] = plan_step.step_account_id
                    serializable_plan_steps.append(step_data)

                # 启动异步工作流执行 - 使用Fabric版本
                from apps.executor.fabric_tasks import start_workflow_execution
                celery_task = start_workflow_execution(
                    plan_steps=serializable_plan_steps,
                    target_hosts=[{
                        'id': host.id,
                        'name': host.name,
                        'ip_address': host.ip_address
                    } for host in all_target_hosts],
                    global_parameters=global_parameters,
                    execution_mode=kwargs.get('execution_mode', 'parallel'),
                    rolling_batch_size=kwargs.get('rolling_batch_size', 1),
                    rolling_batch_delay=kwargs.get('rolling_batch_delay', 0),
                    execution_id=execution_record.execution_id  # 传递执行ID用于SSE日志
                )

                # 更新执行记录
                ExecutionRecordService.update_execution_status(
                    execution_record=execution_record,
                    status='running',
                    celery_task_id=celery_task.id
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
                    'task_id': celery_task.id,
                    'celery_task_id': celery_task.id,
                    'message': '执行方案执行已启动',
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
