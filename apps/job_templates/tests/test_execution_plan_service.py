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


def test_execute_plan_without_agent_server_lets_agent_layer_route_by_host_binding():
    user, plan = _create_two_step_plan()
    captured = {}

    def _capture_workflow(**kwargs):
        captured["has_agent_server_id"] = "agent_server_id" in kwargs
        captured["target_hosts"] = kwargs["target_hosts"]
        return {"success": True, "message": "ok"}

    with patch(
        "apps.agents.execution_service.AgentExecutionService.execute_workflow_via_agent",
        side_effect=_capture_workflow,
    ):
        result = ExecutionPlanService.execute_plan(
            execution_plan=plan,
            user=user,
            execution_mode="serial",
        )

    assert result["success"] is True
    assert captured["has_agent_server_id"] is False
    assert len(captured["target_hosts"]) == 1
    assert ExecutionRecord.objects.count() == 1
    record = ExecutionRecord.objects.get()
    assert "agent_server_id" not in record.execution_parameters
    assert record.execution_parameters["execution_backend"] == "agent"


def test_execute_plan_does_not_read_agent_server_from_business_parameters():
    user, plan = _create_two_step_plan()
    captured = {}

    def _capture_workflow(**kwargs):
        captured["has_agent_server_id"] = "agent_server_id" in kwargs
        return {"success": True, "message": "ok"}

    with patch(
        "apps.agents.execution_service.AgentExecutionService.execute_workflow_via_agent",
        side_effect=_capture_workflow,
    ):
        result = ExecutionPlanService.execute_plan(
            execution_plan=plan,
            user=user,
            execution_parameters={"agent_server_id": 99, "ReleaseVersion": "v1"},
            execution_mode="serial",
        )

    assert result["success"] is True
    assert captured["has_agent_server_id"] is False
    record = ExecutionRecord.objects.get()
    assert record.execution_parameters["ReleaseVersion"] == "v1"
    assert "agent_server_id" not in record.execution_parameters


def test_execution_plan_execute_serializer_does_not_require_agent_server():
    from apps.job_templates.serializers import ExecutionPlanExecuteSerializer

    serializer = ExecutionPlanExecuteSerializer(data={"execution_parameters": {}})

    assert serializer.is_valid(), serializer.errors
    assert "agent_server_id" not in serializer.validated_data
