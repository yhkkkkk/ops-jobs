import uuid
from unittest.mock import patch

import pytest
from django.contrib.auth.models import User
from django.contrib.contenttypes.models import ContentType
from django.db.models import F

from apps.executor.models import ExecutionRecord
from apps.executor.services import ExecutionRecordService
from apps.hosts.models import Host
from apps.job_templates.models import ExecutionPlan, JobStep, JobTemplate, PlanStep
from apps.scheduler.models import ScheduledJob
from apps.scheduler.services import SchedulerService

from apps.scheduler.tasks import execute_scheduled_job, update_scheduled_job_stats


pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def run_workflow_inline(settings):
    settings.TESTING = True


def _create_scheduled_job():
    user = User.objects.create_user(f"user-{uuid.uuid4().hex[:6]}", password="pass")
    host = Host.objects.create(
        name=f"host-{uuid.uuid4().hex[:6]}",
        os_type="linux",
        device_type="physical",
        created_by=user,
    )
    template = JobTemplate.objects.create(
        name=f"tpl-{uuid.uuid4().hex[:8]}",
        created_by=user,
    )
    step = JobStep.objects.create(
        template=template,
        name="scheduled-step",
        step_type="script",
        order=1,
        script_type="shell",
        script_content="echo scheduled",
        timeout=30,
    )
    step.target_hosts.add(host)

    plan = ExecutionPlan.objects.create(
        template=template,
        name=f"plan-{uuid.uuid4().hex[:8]}",
        created_by=user,
    )
    plan_step = PlanStep.objects.create(plan=plan, step=step, order=1)
    plan_step.copy_from_template_step()
    plan_step.save()

    job = ScheduledJob.objects.create(
        name=f"scheduled-{uuid.uuid4().hex[:8]}",
        execution_plan=plan,
        cron_expression="* * * * *",
        created_by=user,
        execution_parameters={"agent_server_id": 1},
        is_active=True,
    )
    return job


def test_scheduled_job_execution_creates_scheduled_execution_record():
    job = _create_scheduled_job()

    with patch(
        "apps.agents.execution_service.AgentExecutionService.execute_workflow_via_agent",
        return_value={"success": True, "message": "ok"},
    ):
        result = execute_scheduled_job(job.id)

    assert result["success"] is True
    record = ExecutionRecord.objects.get()
    assert record.execution_type == "scheduled_job"
    assert record.trigger_type == "scheduled"
    assert record.content_type == ContentType.objects.get_for_model(ScheduledJob)
    assert record.object_id == job.id

    job.refresh_from_db()
    assert job.total_runs == 1
    assert job.success_runs == 0
    assert job.failed_runs == 0


def test_scheduled_job_completion_updates_job_and_plan_statistics():
    job = _create_scheduled_job()
    record = ExecutionRecord.objects.create(
        execution_type="scheduled_job",
        name="scheduled run",
        executed_by=job.created_by,
        related_object=job,
        trigger_type="scheduled",
        status="running",
    )
    job.total_runs = 1
    job.save(update_fields=["total_runs", "updated_at"])

    with patch("utils.realtime_logs.realtime_log_service.push_status"), patch(
        "utils.log_archive_service.log_archive_service.archive_execution_logs",
        return_value=True,
    ):
        ExecutionRecordService.update_execution_status(record, "success")

    job.refresh_from_db()
    job.execution_plan.refresh_from_db()
    assert job.success_runs == 1
    assert job.failed_runs == 0
    assert job.execution_plan.success_executions == 1


def test_scheduled_job_start_counter_does_not_overwrite_completion_counter():
    job = _create_scheduled_job()

    def _complete_during_launch(**kwargs):
        ScheduledJob.objects.filter(id=job.id).update(success_runs=F("success_runs") + 1)
        return {"success": True, "message": "ok"}

    with patch(
        "apps.job_templates.services.ExecutionPlanService.execute_plan",
        side_effect=_complete_during_launch,
    ):
        result = execute_scheduled_job(job.id)

    assert result["success"] is True
    job.refresh_from_db()
    assert job.total_runs == 1
    assert job.success_runs == 1
    assert job.failed_runs == 0


def test_scheduled_job_completion_statistics_are_idempotent_for_stale_records():
    job = _create_scheduled_job()
    record = ExecutionRecord.objects.create(
        execution_type="scheduled_job",
        name="scheduled run",
        executed_by=job.created_by,
        related_object=job,
        trigger_type="scheduled",
        status="running",
    )
    first_worker_record = ExecutionRecord.objects.get(id=record.id)
    second_worker_record = ExecutionRecord.objects.get(id=record.id)

    with patch("utils.realtime_logs.realtime_log_service.push_status"), patch(
        "utils.log_archive_service.log_archive_service.archive_execution_logs",
        return_value=True,
    ):
        ExecutionRecordService.update_execution_status(first_worker_record, "success")
        ExecutionRecordService.update_execution_status(second_worker_record, "success")

    job.refresh_from_db()
    job.execution_plan.refresh_from_db()
    assert job.success_runs == 1
    assert job.execution_plan.success_executions == 1


def test_scheduled_job_timeout_counts_as_plan_and_job_failure():
    job = _create_scheduled_job()
    record = ExecutionRecord.objects.create(
        execution_type="scheduled_job",
        name="scheduled run",
        executed_by=job.created_by,
        related_object=job,
        trigger_type="scheduled",
        status="running",
    )

    with patch("utils.realtime_logs.realtime_log_service.push_status"), patch(
        "utils.log_archive_service.log_archive_service.archive_execution_logs",
        return_value=True,
    ):
        ExecutionRecordService.update_execution_status(record, "timeout")

    job.refresh_from_db()
    job.execution_plan.refresh_from_db()
    assert job.failed_runs == 1
    assert job.execution_plan.failed_executions == 1


def test_scheduled_job_stats_reconciliation_keeps_launch_failures_without_records():
    job = _create_scheduled_job()
    job.total_runs = 1
    job.failed_runs = 1
    job.save(update_fields=["total_runs", "failed_runs", "updated_at"])

    result = update_scheduled_job_stats()

    assert result["success"] is True
    job.refresh_from_db()
    assert job.total_runs == 1
    assert job.success_runs == 0
    assert job.failed_runs == 1


def test_scheduler_update_persists_execution_plan_and_parameters():
    job = _create_scheduled_job()
    replacement = _create_scheduled_job().execution_plan

    SchedulerService.update_scheduled_job(
        job,
        execution_plan=replacement,
        execution_parameters={"ReleaseVersion": "v2"},
    )

    job.refresh_from_db()
    assert job.execution_plan == replacement
    assert job.execution_parameters == {"ReleaseVersion": "v2"}


def test_scheduler_enable_disable_no_longer_uses_removed_periodic_task():
    job = _create_scheduled_job()

    SchedulerService.disable_scheduled_job(job)
    job.refresh_from_db()
    assert job.is_active is False

    SchedulerService.enable_scheduled_job(job)
    job.refresh_from_db()
    assert job.is_active is True


def test_scheduler_reconciles_database_jobs_without_restart():
    from apscheduler.schedulers.blocking import BlockingScheduler
    from apps.scheduler.management.commands.run_scheduler import _sync_jobs

    job = _create_scheduled_job()
    scheduler = BlockingScheduler(timezone="Asia/Shanghai")

    _sync_jobs(scheduler)
    assert scheduler.get_job(f"scheduled_job_{job.id}") is not None

    job.is_active = False
    job.save(update_fields=["is_active", "updated_at"])
    _sync_jobs(scheduler)
    assert scheduler.get_job(f"scheduled_job_{job.id}") is None

    assert job.success_runs == 0
    assert job.failed_runs == 0
