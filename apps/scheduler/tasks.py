"""
调度任务逻辑（原 Celery 任务，现由 APScheduler / 管理命令触发执行）
"""
import logging
from django.utils import timezone
from django.db import transaction
from django.db.models import F
from .models import ScheduledJob, ScheduledJobRun

logger = logging.getLogger(__name__)


def _scheduled_minute(scheduled_for=None):
    scheduled_for = scheduled_for or timezone.now()
    if timezone.is_naive(scheduled_for):
        scheduled_for = timezone.make_aware(scheduled_for, timezone.get_current_timezone())
    return scheduled_for.replace(second=0, microsecond=0)


def execute_scheduled_job(scheduled_job_id, scheduled_for=None):
    """Launch one scheduled job at most once for each scheduled minute."""
    scheduled_job = None
    scheduled_run = None
    scheduled_for = _scheduled_minute(scheduled_for)

    try:
        scheduled_job = ScheduledJob.objects.select_related('execution_plan', 'created_by').get(id=scheduled_job_id)
    except ScheduledJob.DoesNotExist:
        logger.error(f"定时作业不存在: {scheduled_job_id}")
        return {
            'success': False,
            'error': f'定时作业不存在: {scheduled_job_id}',
        }

    if not scheduled_job.is_active:
        logger.info(f"定时作业已禁用，跳过执行: {scheduled_job.name}")
        return {
            'success': False,
            'error': '定时作业已禁用',
        }

    try:
        # The unique database constraint is the cross-process launch claim.
        with transaction.atomic():
            scheduled_run, created = ScheduledJobRun.objects.get_or_create(
                scheduled_job=scheduled_job,
                scheduled_for=scheduled_for,
            )

        if not created:
            logger.info(
                "ScheduledJob duplicate trigger skipped",
                extra={'job_id': scheduled_job.id, 'scheduled_for': scheduled_for.isoformat()},
            )
            return {'success': True, 'skipped': True, 'reason': 'duplicate_schedule'}

        from apps.job_templates.services import ExecutionPlanService

        logger.info(
            "开始执行定时作业",
            extra={'job_id': scheduled_job.id, 'scheduled_for': scheduled_for.isoformat()},
        )
        result = ExecutionPlanService.execute_plan(
            execution_plan=scheduled_job.execution_plan,
            user=scheduled_job.created_by,
            trigger_type='scheduled',
            name=f"定时作业: {scheduled_job.name}",
            description=f"由定时作业 {scheduled_job.name} 自动创建",
            execution_parameters=scheduled_job.execution_parameters or {},
            execution_type='scheduled_job',
            related_object=scheduled_job,
        )

        if result.get('success'):
            scheduled_run.status = 'launched'
            scheduled_run.error_message = ''
            ScheduledJob.objects.filter(id=scheduled_job.id).update(
                total_runs=F('total_runs') + 1,
                updated_at=timezone.now(),
            )
        else:
            scheduled_run.status = 'failed'
            scheduled_run.error_message = result.get('error', '')
            ScheduledJob.objects.filter(id=scheduled_job.id).update(
                total_runs=F('total_runs') + 1,
                failed_runs=F('failed_runs') + 1,
                updated_at=timezone.now(),
            )
        scheduled_run.save(update_fields=['status', 'error_message', 'updated_at'])
        return result

    except Exception as exc:
        logger.exception("执行定时作业失败", extra={'job_id': scheduled_job.id})
        if scheduled_run is not None:
            scheduled_run.status = 'failed'
            scheduled_run.error_message = str(exc)
            scheduled_run.save(update_fields=['status', 'error_message', 'updated_at'])
        ScheduledJob.objects.filter(id=scheduled_job.id).update(
            total_runs=F('total_runs') + 1,
            failed_runs=F('failed_runs') + 1,
            updated_at=timezone.now(),
        )
        return {
            'success': False,
            'error': str(exc),
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
