from django.db import transaction
from django.utils import timezone

from .models import FlowSchedule, FlowScheduleRun
from .services import FlowRunner


def _scheduled_minute(scheduled_for=None):
    scheduled_for = scheduled_for or timezone.now()
    if timezone.is_naive(scheduled_for):
        scheduled_for = timezone.make_aware(scheduled_for, timezone.get_current_timezone())
    return scheduled_for.replace(second=0, microsecond=0)


def execute_flow_schedule(schedule_id, scheduled_for=None):
    """Start one FlowRun at most once for each FlowSchedule Cron minute."""
    scheduled_for = _scheduled_minute(scheduled_for)
    try:
        schedule = FlowSchedule.objects.select_related('template', 'created_by').get(pk=schedule_id)
    except FlowSchedule.DoesNotExist:
        return {'success': False, 'error': f'流程调度不存在: {schedule_id}'}

    if not schedule.is_active or not schedule.template.is_active:
        return {'success': False, 'error': '流程调度或流程模板已禁用'}

    schedule_run = None
    try:
        with transaction.atomic():
            schedule_run, created = FlowScheduleRun.objects.get_or_create(
                schedule=schedule,
                scheduled_for=scheduled_for,
            )
        if not created:
            return {'success': True, 'skipped': True, 'reason': 'duplicate_schedule'}

        flow_run = FlowRunner.start(
            schedule.template,
            schedule.created_by,
            inputs=schedule.inputs or {},
            trigger_type='scheduled',
        )
        schedule_run.flow_run = flow_run
        schedule_run.status = 'launched'
        schedule_run.error_message = ''
        schedule_run.save(update_fields=['flow_run', 'status', 'error_message', 'updated_at'])
        return {'success': True, 'flow_run_id': flow_run.id}
    except Exception as exc:
        if schedule_run is not None:
            schedule_run.status = 'failed'
            schedule_run.error_message = str(exc)
            schedule_run.save(update_fields=['status', 'error_message', 'updated_at'])
        return {'success': False, 'error': str(exc)}