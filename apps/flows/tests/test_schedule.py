import uuid
from unittest.mock import patch

import pytest
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.utils import timezone

from apps.flows.models import FlowRun, FlowSchedule, FlowScheduleRun, FlowTemplate
from apps.flows.schedule_service import execute_flow_schedule
from apps.flows.services import FlowRunner


pytestmark = pytest.mark.django_db


def _schedule():
    user = User.objects.create_user(f"schedule-{uuid.uuid4().hex[:6]}", password="pass")
    template = FlowTemplate.objects.create(name=f"flow-{uuid.uuid4().hex[:8]}", created_by=user)
    return FlowSchedule.objects.create(
        name=f"schedule-{uuid.uuid4().hex[:8]}",
        template=template,
        cron_expression="* * * * *",
        inputs={"ReleaseVersion": "v1.2.3"},
        created_by=user,
    )


def test_flow_schedule_launches_once_per_scheduled_minute_with_defined_inputs():
    schedule = _schedule()
    scheduled_for = timezone.now().replace(second=0, microsecond=0)
    flow_run = FlowRun.objects.create(
        template=schedule.template,
        started_by=schedule.created_by,
        status=FlowRun.Status.RUNNING,
    )

    with patch("apps.flows.schedule_service.FlowRunner.start", return_value=flow_run) as start:
        first = execute_flow_schedule(schedule.id, scheduled_for=scheduled_for)
        second = execute_flow_schedule(schedule.id, scheduled_for=scheduled_for)

    assert first["success"] is True
    assert second == {"success": True, "skipped": True, "reason": "duplicate_schedule"}
    start.assert_called_once_with(schedule.template, schedule.created_by, inputs={"ReleaseVersion": "v1.2.3"}, trigger_type="scheduled")
    schedule_run = FlowScheduleRun.objects.get(schedule=schedule, scheduled_for=scheduled_for)
    assert schedule_run.flow_run == flow_run
    assert schedule_run.status == "launched"


def test_flow_runner_persists_scheduled_trigger_type():
    schedule = _schedule()

    flow_run = FlowRunner.start(
        template=schedule.template,
        user=schedule.created_by,
        inputs=schedule.inputs,
        trigger_type="scheduled",
    )

    assert flow_run.trigger_type == "scheduled"

def test_scheduler_loads_active_flow_schedules():
    from apscheduler.schedulers.blocking import BlockingScheduler
    from apps.scheduler.management.commands.run_scheduler import _sync_flow_schedules

    schedule = _schedule()
    scheduler = BlockingScheduler(timezone="Asia/Shanghai")

    _sync_flow_schedules(scheduler)

    assert scheduler.get_job(f"flow_schedule_{schedule.id}") is not None

    schedule.is_active = False
    schedule.save(update_fields=["is_active", "updated_at"])
    _sync_flow_schedules(scheduler)
    assert scheduler.get_job(f"flow_schedule_{schedule.id}") is None

def test_flow_schedule_rejects_six_field_cron_expression():
    user = User.objects.create_user(f"cron-{uuid.uuid4().hex[:6]}", password="pass")
    template = FlowTemplate.objects.create(name=f"flow-{uuid.uuid4().hex[:8]}", created_by=user)

    with pytest.raises(ValidationError, match="5个字段"):
        FlowSchedule.objects.create(
            name=f"schedule-{uuid.uuid4().hex[:8]}",
            template=template,
            cron_expression="* * * * * *",
            created_by=user,
        )

def test_flow_schedule_api_rejects_six_field_cron_expression():
    from rest_framework.test import APIClient

    owner = User.objects.create_user(f"api-cron-{uuid.uuid4().hex[:6]}", password="pass")
    template = FlowTemplate.objects.create(name=f"flow-{uuid.uuid4().hex[:8]}", created_by=owner)
    client = APIClient()
    client.force_authenticate(owner)

    response = client.post(
        "/api/flows/schedules/",
        {
            "name": f"schedule-{uuid.uuid4().hex[:8]}",
            "template": template.id,
            "cron_expression": "* * * * * *",
            "inputs": {},
        },
        format="json",
    )

    assert response.status_code == 400

def test_flow_schedule_api_creates_schedule_only_for_owned_template():
    from rest_framework.test import APIClient

    owner = User.objects.create_user(f"owner-{uuid.uuid4().hex[:6]}", password="pass")
    other = User.objects.create_user(f"other-{uuid.uuid4().hex[:6]}", password="pass")
    template = FlowTemplate.objects.create(name=f"flow-{uuid.uuid4().hex[:8]}", created_by=owner)
    foreign_template = FlowTemplate.objects.create(name=f"flow-{uuid.uuid4().hex[:8]}", created_by=other)
    client = APIClient()
    client.force_authenticate(owner)

    response = client.post(
        "/api/flows/schedules/",
        {
            "name": f"schedule-{uuid.uuid4().hex[:8]}",
            "template": template.id,
            "cron_expression": "0 2 * * *",
            "timezone": "Asia/Shanghai",
            "inputs": {"ReleaseVersion": "v1.2.3"},
        },
        format="json",
    )

    assert response.status_code == 200
    assert response.data["content"]["template"] == template.id
    assert response.data["content"]["inputs"] == {"ReleaseVersion": "v1.2.3"}

    denied = client.post(
        "/api/flows/schedules/",
        {
            "name": f"schedule-{uuid.uuid4().hex[:8]}",
            "template": foreign_template.id,
            "cron_expression": "0 2 * * *",
            "inputs": {},
        },
        format="json",
    )
    assert denied.status_code == 400