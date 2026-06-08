"""
调度任务逻辑（原 Celery 任务，现由 APScheduler / 管理命令触发执行）
"""
import logging
from django.utils import timezone
from django.db.models import F
from .models import ScheduledJob
from apps.executor.services import ExecutionRecordService

logger = logging.getLogger(__name__)


def execute_scheduled_job(scheduled_job_id):
    """执行定时作业"""
    try:
        # 获取定时作业
        try:
            scheduled_job = ScheduledJob.objects.get(id=scheduled_job_id)
        except ScheduledJob.DoesNotExist:
            logger.error(f"定时作业不存在: {scheduled_job_id}")
            return {
                'success': False,
                'error': f'定时作业不存在: {scheduled_job_id}'
            }
        
        # 检查作业是否启用
        if not scheduled_job.is_active:
            logger.info(f"定时作业已禁用，跳过执行: {scheduled_job.name}")
            return {
                'success': False,
                'error': '定时作业已禁用'
            }

        # 直接执行ExecutionPlan，创建ExecutionRecord
        from apps.job_templates.services import ExecutionPlanService

        logger.info(f"开始执行定时作业: {scheduled_job.name}")

        # 使用ExecutionPlanService执行ExecutionPlan
        execution_parameters = scheduled_job.execution_parameters or {}
        result = ExecutionPlanService.execute_plan(
            execution_plan=scheduled_job.execution_plan,
            user=scheduled_job.created_by,
            trigger_type='scheduled',
            name=f"定时作业: {scheduled_job.name}",
            description=f"由定时作业 {scheduled_job.name} 自动创建",
            execution_parameters=execution_parameters,
            agent_server_id=execution_parameters.get('agent_server_id'),
            execution_type='scheduled_job',
            related_object=scheduled_job,
        )

        # 这里只统计调度触发次数；最终成功/失败由 ExecutionRecord 完成态回写。
        if not result.get('success'):
            ScheduledJob.objects.filter(id=scheduled_job.id).update(
                total_runs=F('total_runs') + 1,
                failed_runs=F('failed_runs') + 1,
                updated_at=timezone.now(),
            )
        else:
            ScheduledJob.objects.filter(id=scheduled_job.id).update(
                total_runs=F('total_runs') + 1,
                updated_at=timezone.now(),
            )

        return result

    except Exception as e:
        logger.error(f"执行定时作业失败: {scheduled_job.name} - {e}")

        # 启动阶段异常没有执行记录，直接按一次调度失败统计。
        ScheduledJob.objects.filter(id=scheduled_job.id).update(
            total_runs=F('total_runs') + 1,
            failed_runs=F('failed_runs') + 1,
            updated_at=timezone.now(),
        )

        return {
            'success': False,
            'error': str(e)
        }


def cleanup_old_executions(days=30):
    """清理旧的执行记录"""
    try:
        from datetime import timedelta
        from apps.executor.models import ExecutionRecord

        cutoff_date = timezone.now() - timedelta(days=days)

        # 清理定时作业的执行记录
        deleted_count = ExecutionRecord.objects.filter(
            execution_type='scheduled_job',
            created_at__lt=cutoff_date
        ).delete()[0]

        logger.info(f"清理了 {deleted_count} 条旧的定时作业执行记录")

        return {
            'success': True,
            'deleted_count': deleted_count
        }

    except Exception as e:
        logger.error(f"清理旧执行记录失败: {e}")
        return {
            'success': False,
            'error': str(e)
        }


def update_scheduled_job_stats():
    """更新定时作业统计信息"""
    try:
        updated_count = 0
        
        for scheduled_job in ScheduledJob.objects.filter(is_active=True):
            # 重新计算统计信息
            from apps.executor.models import ExecutionRecord
            from django.contrib.contenttypes.models import ContentType

            # 获取ScheduledJob的ContentType
            scheduled_job_content_type = ContentType.objects.get_for_model(ScheduledJob)

            # 查询执行记录
            executions = ExecutionRecord.objects.filter(
                execution_type='scheduled_job',
                content_type=scheduled_job_content_type,
                object_id=scheduled_job.id
            )

            execution_total_runs = executions.count()
            success_runs = executions.filter(status='success').count()
            failed_runs = executions.filter(status__in=['failed', 'cancelled', 'timeout']).count()
            launch_failures_without_records = max(scheduled_job.total_runs - execution_total_runs, 0)

            total_runs = max(scheduled_job.total_runs, execution_total_runs)
            failed_runs += launch_failures_without_records

            # 更新统计
            if (scheduled_job.total_runs != total_runs or
                scheduled_job.success_runs != success_runs or
                scheduled_job.failed_runs != failed_runs):

                scheduled_job.total_runs = total_runs
                scheduled_job.success_runs = success_runs
                scheduled_job.failed_runs = failed_runs
                scheduled_job.save()
                updated_count += 1
        
        logger.info(f"更新了 {updated_count} 个定时作业的统计信息")
        
        return {
            'success': True,
            'updated_count': updated_count
        }
        
    except Exception as e:
        logger.error(f"更新定时作业统计失败: {e}")
        return {
            'success': False,
            'error': str(e)
        }
