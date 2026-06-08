import logging
import pytz

from django.conf import settings
from django.core.management import call_command
from django.core.management.base import BaseCommand
from django.db.models import F
from django.utils import timezone
from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger
from django_apscheduler.jobstores import DjangoJobStore, register_events

from apps.scheduler.models import ScheduledJob
from apps.job_templates.services import ExecutionPlanService

logger = logging.getLogger(__name__)


def _run_job(job_id: int):
    """执行单个 ScheduledJob 对应的执行方案"""
    try:
        job = ScheduledJob.objects.select_related("execution_plan", "created_by").get(id=job_id)
    except ScheduledJob.DoesNotExist:
        logger.warning("ScheduledJob not found", extra={"job_id": job_id})
        return

    if not job.is_active:
        logger.info("ScheduledJob inactive, skip", extra={"job_id": job_id})
        return

    logger.info("ScheduledJob triggering execution", extra={"job_id": job_id, "plan_id": job.execution_plan_id})

    try:
        result = ExecutionPlanService.execute_plan(
            execution_plan=job.execution_plan,
            user=job.created_by,
            trigger_type="scheduled",
            execution_parameters=job.execution_parameters or {},
            name=f"[定时]{job.name}",
            description=f"定时执行方案 {job.execution_plan}",
            agent_server_id=(job.execution_parameters or {}).get("agent_server_id"),
            execution_type="scheduled_job",
            related_object=job,
        )
    except Exception:
        logger.exception("ScheduledJob launch failed", extra={"job_id": job.id})
        result = {"success": False}

    # 这里只统计调度触发次数；最终成功/失败由 ExecutionRecord 完成态回写。
    if not result.get("success"):
        ScheduledJob.objects.filter(id=job.id).update(
            total_runs=F("total_runs") + 1,
            failed_runs=F("failed_runs") + 1,
            updated_at=timezone.now(),
        )
    else:
        ScheduledJob.objects.filter(id=job.id).update(
            total_runs=F("total_runs") + 1,
            updated_at=timezone.now(),
        )


def _load_jobs(scheduler: BlockingScheduler):
    jobs = ScheduledJob.objects.filter(is_active=True)
    for job in jobs:
        try:
            tz = pytz.timezone(job.timezone or "Asia/Shanghai")
        except Exception:
            tz = pytz.timezone("Asia/Shanghai")
        trigger = CronTrigger.from_crontab(job.cron_expression, timezone=tz)
        scheduler.add_job(
            _run_job,
            trigger=trigger,
            args=[job.id],
            id=f"scheduled_job_{job.id}",
            replace_existing=True,
        )
        logger.info("ScheduledJob loaded", extra={"job_id": job.id, "cron": job.cron_expression, "tz": str(tz)})


class Command(BaseCommand):
    help = "Run APScheduler to execute ScheduledJob without Celery Beat"

    def handle(self, *args, **options):
        scheduler = BlockingScheduler(timezone=pytz.timezone("Asia/Shanghai"))
        scheduler.add_jobstore(DjangoJobStore(), "default")
        _load_jobs(scheduler)
        register_events(scheduler)
        logger.info("APS cheduler started (run_scheduler)")
        try:
            scheduler.start()
        except KeyboardInterrupt:
            scheduler.shutdown()
            logger.info("Scheduler stopped")
