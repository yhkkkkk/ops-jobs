import logging
import time
import uuid
import pytz

from django.conf import settings
from django.core.management.base import BaseCommand
from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger
from apscheduler.jobstores.memory import MemoryJobStore
from django_apscheduler.jobstores import DjangoJobStore, register_events

from apps.scheduler.lease import SchedulerLeaseService
from apps.flows.models import FlowSchedule
from apps.scheduler.models import ScheduledJob

logger = logging.getLogger(__name__)


def _run_job(job_id: int):
    """Delegate every Cron trigger to the shared durable launch guard."""
    from apps.scheduler.tasks import execute_scheduled_job

    return execute_scheduled_job(job_id)


def _sync_jobs(scheduler: BlockingScheduler):
    """将数据库中的启用状态和 Cron 配置同步到运行中的调度器。"""
    active_job_ids = set()
    for job in ScheduledJob.objects.filter(is_active=True):
        scheduler_job_id = f"scheduled_job_{job.id}"
        active_job_ids.add(scheduler_job_id)
        try:
            tz = pytz.timezone(job.timezone or "Asia/Shanghai")
        except Exception:
            tz = pytz.timezone("Asia/Shanghai")
        trigger = CronTrigger.from_crontab(job.cron_expression, timezone=tz)
        existing = scheduler.get_job(scheduler_job_id)
        if existing is None:
            scheduler.add_job(
                _run_job,
                trigger=trigger,
                args=[job.id],
                id=scheduler_job_id,
                replace_existing=True,
            )
            logger.info("ScheduledJob loaded", extra={"job_id": job.id, "cron": job.cron_expression, "tz": str(tz)})
        elif str(existing.trigger) != str(trigger):
            scheduler.reschedule_job(scheduler_job_id, trigger=trigger)
            logger.info("ScheduledJob rescheduled", extra={"job_id": job.id, "cron": job.cron_expression, "tz": str(tz)})

    for scheduled_job in scheduler.get_jobs():
        if scheduled_job.id.startswith("scheduled_job_") and scheduled_job.id not in active_job_ids:
            scheduler.remove_job(scheduled_job.id)
            logger.info("ScheduledJob removed", extra={"scheduler_job_id": scheduled_job.id})


def _run_flow_schedule(schedule_id: int):
    from apps.flows.schedule_service import execute_flow_schedule

    return execute_flow_schedule(schedule_id)


def _sync_flow_schedules(scheduler: BlockingScheduler):
    active_schedule_ids = set()
    for schedule in FlowSchedule.objects.filter(is_active=True, template__is_active=True):
        scheduler_job_id = f"flow_schedule_{schedule.id}"
        active_schedule_ids.add(scheduler_job_id)
        try:
            tz = pytz.timezone(schedule.timezone or "Asia/Shanghai")
        except Exception:
            tz = pytz.timezone("Asia/Shanghai")
        trigger = CronTrigger.from_crontab(schedule.cron_expression, timezone=tz)
        job_options = {
            "max_instances": 1,
            "coalesce": schedule.misfire_policy == FlowSchedule.MisfirePolicy.COALESCE,
            "misfire_grace_time": schedule.misfire_grace_seconds,
        }
        existing = scheduler.get_job(scheduler_job_id)
        if existing is None:
            scheduler.add_job(
                _run_flow_schedule,
                trigger=trigger,
                args=[schedule.id],
                id=scheduler_job_id,
                replace_existing=True,
                **job_options,
            )
        else:
            scheduler.modify_job(scheduler_job_id, **job_options)
            if str(existing.trigger) != str(trigger):
                scheduler.reschedule_job(scheduler_job_id, trigger=trigger)

    for scheduled_job in scheduler.get_jobs():
        if scheduled_job.id.startswith("flow_schedule_") and scheduled_job.id not in active_schedule_ids:
            scheduler.remove_job(scheduled_job.id)


def _sync_automation_jobs(scheduler: BlockingScheduler):
    _sync_jobs(scheduler)
    _sync_flow_schedules(scheduler)

def _load_jobs(scheduler: BlockingScheduler):
    """兼容管理命令内部旧名称。"""
    _sync_jobs(scheduler)


class Command(BaseCommand):
    help = "Run APScheduler to execute ScheduledJob without Celery Beat"

    def handle(self, *args, **options):
        lease_name = 'scheduler:leader'
        lease_holder = uuid.uuid4().hex
        lease_ttl = max(15, int(getattr(settings, 'SCHEDULER_LEASE_TTL_SECONDS', 30)))
        retry_seconds = max(1, min(5, lease_ttl // 3))

        while not SchedulerLeaseService.acquire(lease_name, lease_holder, lease_ttl):
            logger.info('Scheduler standby waiting for leader lease')
            time.sleep(retry_seconds)

        scheduler = BlockingScheduler(timezone=pytz.timezone("Asia/Shanghai"))
        scheduler.add_jobstore(DjangoJobStore(), "default")
        scheduler.add_jobstore(MemoryJobStore(), "runtime")
        _sync_automation_jobs(scheduler)

        def renew_lease():
            if SchedulerLeaseService.renew(lease_name, lease_holder, lease_ttl):
                return
            logger.error('Scheduler leader lease lost; shutting down')
            scheduler.shutdown(wait=False)

        scheduler.add_job(
            _sync_automation_jobs,
            trigger=IntervalTrigger(seconds=int(getattr(settings, "SCHEDULER_SYNC_INTERVAL", 5))),
            args=[scheduler],
            id="sync_scheduled_jobs",
            jobstore="runtime",
            replace_existing=True,
            max_instances=1,
            coalesce=True,
        )
        scheduler.add_job(
            renew_lease,
            trigger=IntervalTrigger(seconds=max(1, lease_ttl // 3)),
            id='renew_scheduler_lease',
            jobstore='runtime',
            replace_existing=True,
            max_instances=1,
            coalesce=True,
        )
        register_events(scheduler)
        logger.info("APS scheduler started (run_scheduler)")
        try:
            scheduler.start()
        except KeyboardInterrupt:
            scheduler.shutdown()
            logger.info("Scheduler stopped")
        finally:
            SchedulerLeaseService.release(lease_name, lease_holder)
