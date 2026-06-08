import uuid
from unittest.mock import patch

import pytest
from django.contrib.auth.models import User

from apps.executor.models import ExecutionRecord
from apps.hosts.models import Host
from apps.job_templates.models import ExecutionPlan, JobStep, JobTemplate, PlanStep
from apps.job_templates.services import ExecutionPlanService


pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def run_workflow_inline(settings):
    settings.TESTING = True


def _create_two_step_plan():
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
    steps = []
    for order in (1, 2):
        step = JobStep.objects.create(
            template=template,
            name=f"step-{order}",
            step_type="script",
            order=order,
            script_type="shell",
            script_content=f"echo {order}",
            timeout=30,
        )
        step.target_hosts.add(host)
        steps.append(step)

    plan = ExecutionPlan.objects.create(
        template=template,
        name=f"plan-{uuid.uuid4().hex[:8]}",
        created_by=user,
    )
    for order, step in enumerate(steps, start=1):
        plan_step = PlanStep.objects.create(plan=plan, step=step, order=order)
        plan_step.copy_from_template_step()
        plan_step.save()

    return user, plan


def test_execute_plan_passes_all_plan_steps_to_workflow():
    user, plan = _create_two_step_plan()
    captured = {}

    def _capture_workflow(**kwargs):
        captured["plan_steps"] = kwargs["plan_steps"]
        return {"success": True, "message": "ok"}

    with patch(
        "apps.agents.execution_service.AgentExecutionService.execute_workflow_via_agent",
        side_effect=_capture_workflow,
    ):
        result = ExecutionPlanService.execute_plan(
            execution_plan=plan,
            user=user,
            agent_server_id=1,
            execution_mode="serial",
        )

    assert result["success"] is True
    assert [step["step_name"] for step in captured["plan_steps"]] == ["step-1", "step-2"]


def test_execute_plan_without_agent_server_does_not_create_pending_record():
    user, plan = _create_two_step_plan()

    result = ExecutionPlanService.execute_plan(
        execution_plan=plan,
        user=user,
        execution_mode="serial",
    )

    assert result["success"] is False
    assert result["error"] == "请先选择Agent-Server"
    assert ExecutionRecord.objects.count() == 0
