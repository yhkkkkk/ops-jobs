import logging
import pytz
from datetime import datetime

from django.conf import settings
from django.core.management import call_command
from django.core.management.base import BaseCommand
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

    result = ExecutionPlanService.execute_plan(
        execution_plan=job.execution_plan,
        user=job.created_by,
        trigger_type="scheduled",
        execution_parameters={},
        name=f"[定时]{job.name}",
        description=f"定时执行方案 {job.execution_plan}",
        agent_server_url=None,
    )

    # 更新统计
    job.total_runs += 1
    if result.get("success"):
        job.success_runs += 1
    else:
        job.failed_runs += 1
    job.last_run_time = datetime.now(tz=pytz.timezone(job.timezone))
    job.save(update_fields=["total_runs", "success_runs", "failed_runs", "last_run_time", "updated_at"])


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

    # 内置系统任务：Agent 离线扫描（可通过配置关闭）
    offline_enabled = getattr(settings, "AGENT_OFFLINE_SCHED_ENABLED", True)
    interval_minutes = int(getattr(settings, "AGENT_OFFLINE_SCHED_INTERVAL_MINUTES", 5))

    if offline_enabled and interval_minutes > 0:
        try:
            scheduler.add_job(
                _run_mark_agents_offline,
                trigger=IntervalTrigger(minutes=interval_minutes),
                id="agent_mark_offline_job",
                replace_existing=True,
            )
            logger.info(
                "Builtin job loaded: mark_agents_offline",
                extra={"interval_minutes": interval_minutes},
            )
        except Exception:  # noqa: BLE001
            logger.exception("Failed to schedule mark_agents_offline job")


def _run_mark_agents_offline():
    """
    周期性执行 Agent 离线扫描：
      - 调用管理命令 mark_agents_offline
      - 阈值逻辑由命令自身和 SystemConfig 决定
    """
    logger.info("Running builtin job: mark_agents_offline")
    try:
        call_command("mark_agents_offline")
    except Exception:  # noqa: BLE001
        logger.exception("mark_agents_offline job failed")


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

