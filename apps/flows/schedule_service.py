from django.db import transaction
from django.utils import timezone

from .models import FlowRun, FlowSchedule, FlowScheduleRun
from .secret_service import decrypt_flow_secret_values
from .services import FlowRunner


ACTIVE_FLOW_RUN_STATUSES = (
    FlowRun.Status.PENDING,
    FlowRun.Status.RUNNING,
    FlowRun.Status.PAUSED,
)


def _scheduled_minute(scheduled_for=None):
    scheduled_for = scheduled_for or timezone.now()
    if timezone.is_naive(scheduled_for):
        scheduled_for = timezone.make_aware(scheduled_for, timezone.get_current_timezone())
    return scheduled_for.replace(second=0, microsecond=0)


def execute_flow_schedule(schedule_id, scheduled_for=None):
    """Start one FlowRun at most once for each FlowSchedule Cron minute."""
    scheduled_for = _scheduled_minute(scheduled_for)
    try:
        with transaction.atomic():
            schedule = (
                FlowSchedule.objects.select_for_update()
                .select_related('template', 'created_by')
                .get(pk=schedule_id)
            )
            if not schedule.is_active or not schedule.template.is_active:
                return {'success': False, 'error': '流程调度或流程模板已禁用'}

            schedule_run, created = FlowScheduleRun.objects.get_or_create(
                schedule=schedule,
                scheduled_for=scheduled_for,
            )
            if not created:
                return {'success': True, 'skipped': True, 'reason': 'duplicate_schedule'}

            has_active_run = FlowScheduleRun.objects.filter(
                schedule=schedule,
                flow_run__status__in=ACTIVE_FLOW_RUN_STATUSES,
            ).exists()
            if schedule.overlap_policy == FlowSchedule.OverlapPolicy.SKIP and has_active_run:
                schedule_run.status = 'skipped'
                schedule_run.error_message = 'previous scheduled flow run is still active'
                schedule_run.save(update_fields=['status', 'error_message', 'updated_at'])
                return {'success': True, 'skipped': True, 'reason': 'overlap'}

            try:
                flow_run = FlowRunner.start(
                    schedule.template,
                    schedule.created_by,
                    inputs={
                        **(schedule.inputs or {}),
                        **decrypt_flow_secret_values(schedule.encrypted_secret_inputs or {}),
                    },
                    trigger_type='scheduled',
                    run_name=schedule.name,
                )
            except Exception as exc:
                schedule_run.status = 'failed'
                schedule_run.error_message = str(exc)
                schedule_run.save(update_fields=['status', 'error_message', 'updated_at'])
                return {'success': False, 'error': str(exc)}

            schedule_run.flow_run = flow_run
            schedule_run.status = 'launched'
            schedule_run.error_message = ''
            schedule_run.save(update_fields=['flow_run', 'status', 'error_message', 'updated_at'])
            return {'success': True, 'flow_run_id': flow_run.id}
    except FlowSchedule.DoesNotExist:
        return {'success': False, 'error': f'流程调度不存在: {schedule_id}'}