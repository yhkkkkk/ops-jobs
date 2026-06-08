import uuid
from unittest.mock import patch

import pytest
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.utils import timezone

from apps.executor.models import ExecutionRecord
from apps.executor.services import ExecutionRecordService
from apps.flows.models import FlowEdge, FlowNode, FlowNodeRun, FlowRun, FlowTemplate
from apps.flows.services import FlowRunner
from apps.hosts.models import Host
from apps.job_templates.models import ExecutionPlan, JobStep, JobTemplate, PlanStep


pytestmark = pytest.mark.django_db


def _create_user():
    return User.objects.create_user(f"user-{uuid.uuid4().hex[:6]}", password="pass")


def _create_host(user):
    return Host.objects.create(
        name=f"host-{uuid.uuid4().hex[:6]}",
        os_type="linux",
        device_type="physical",
        created_by=user,
    )


def _create_execution_plan(user, host):
    template = JobTemplate.objects.create(
        name=f"tpl-{uuid.uuid4().hex[:8]}",
        created_by=user,
    )
    step = JobStep.objects.create(
        template=template,
        name="plan-step",
        step_type="script",
        order=1,
        script_type="shell",
        script_content="echo plan",
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
    return plan


def test_flow_runner_executes_script_node_with_agent_service():
    user = _create_user()
    host = _create_host(user)
    template = FlowTemplate.objects.create(
        name=f"flow-{uuid.uuid4().hex[:8]}",
        created_by=user,
    )
    node = FlowNode.objects.create(
        template=template,
        uuid="script-1",
        name="run script",
        node_type=FlowNode.NodeType.SCRIPT,
        config={
            "script_content": "echo hello",
            "script_type": "shell",
            "target_host_ids": [host.id],
            "timeout": 30,
        },
    )

    with patch(
        "apps.agents.execution_service.AgentExecutionService.execute_script_via_agent",
        return_value={
            "success": True,
            "success_count": 1,
            "failed_count": 0,
            "results": [{"host_id": host.id, "host_name": host.name, "success": True}],
        },
    ) as execute_script:
        flow_run = FlowRunner.start(template=template, user=user, inputs={}, agent_server_id=1)

    flow_run.refresh_from_db()
    assert flow_run.status == FlowRun.Status.SUCCESS
    node_run = flow_run.node_runs.get(node=node)
    assert node_run.status == FlowRun.Status.SUCCESS
    assert node_run.execution_record is not None
    assert node_run.execution_record.execution_type == "flow_node"
    assert node_run.execution_record.related_object == node_run
    assert node_run.outputs["success_count"] == 1
    execute_script.assert_called_once()
    assert execute_script.call_args.kwargs["script_content"] == "echo hello"


def test_flow_runner_rejects_cycles():
    user = _create_user()
    template = FlowTemplate.objects.create(
        name=f"flow-{uuid.uuid4().hex[:8]}",
        created_by=user,
    )
    first = FlowNode.objects.create(
        template=template,
        uuid="a",
        name="a",
        node_type=FlowNode.NodeType.SCRIPT,
        config={"script_content": "echo a", "target_host_ids": []},
    )
    second = FlowNode.objects.create(
        template=template,
        uuid="b",
        name="b",
        node_type=FlowNode.NodeType.SCRIPT,
        config={"script_content": "echo b", "target_host_ids": []},
    )
    FlowEdge.objects.create(template=template, source=first, target=second)
    FlowEdge.objects.create(template=template, source=second, target=first)

    with pytest.raises(ValueError, match="cycle"):
        FlowRunner.start(template=template, user=user, inputs={}, agent_server_id=1)


def test_flow_runner_rejects_script_node_without_valid_target_hosts():
    user = _create_user()
    template = FlowTemplate.objects.create(
        name=f"flow-{uuid.uuid4().hex[:8]}",
        created_by=user,
    )
    node = FlowNode.objects.create(
        template=template,
        uuid="script-1",
        name="run script",
        node_type=FlowNode.NodeType.SCRIPT,
        config={"script_content": "echo hello", "target_host_ids": [999999]},
    )

    with patch("apps.agents.execution_service.AgentExecutionService.execute_script_via_agent") as execute_script:
        flow_run = FlowRunner.start(template=template, user=user, inputs={}, agent_server_id=1)

    execute_script.assert_not_called()
    flow_run.refresh_from_db()
    assert flow_run.status == FlowRun.Status.FAILED
    node_run = flow_run.node_runs.get(node=node)
    assert node_run.status == FlowRun.Status.FAILED
    assert "valid target host" in node_run.error_message


def test_flow_runner_marks_node_failed_when_script_execution_raises():
    user = _create_user()
    host = _create_host(user)
    template = FlowTemplate.objects.create(
        name=f"flow-{uuid.uuid4().hex[:8]}",
        created_by=user,
    )
    node = FlowNode.objects.create(
        template=template,
        uuid="script-1",
        name="run script",
        node_type=FlowNode.NodeType.SCRIPT,
        config={"script_content": "echo hello", "target_host_ids": [host.id]},
    )

    with patch(
        "apps.agents.execution_service.AgentExecutionService.execute_script_via_agent",
        side_effect=RuntimeError("agent unavailable"),
    ):
        with pytest.raises(RuntimeError, match="agent unavailable"):
            FlowRunner.start(template=template, user=user, inputs={}, agent_server_id=1)

    flow_run = FlowRun.objects.get(template=template)
    assert flow_run.status == FlowRun.Status.FAILED
    node_run = flow_run.node_runs.get(node=node)
    assert node_run.status == FlowRun.Status.FAILED
    assert node_run.finished_at is not None
    assert "agent unavailable" in node_run.error_message


def test_flow_edge_requires_template_to_match_source_and_target():
    user = _create_user()
    first_template = FlowTemplate.objects.create(
        name=f"flow-{uuid.uuid4().hex[:8]}",
        created_by=user,
    )
    second_template = FlowTemplate.objects.create(
        name=f"flow-{uuid.uuid4().hex[:8]}",
        created_by=user,
    )
    first_node = FlowNode.objects.create(
        template=first_template,
        uuid="a",
        name="a",
        node_type=FlowNode.NodeType.SCRIPT,
        config={"script_content": "echo a"},
    )
    second_node = FlowNode.objects.create(
        template=second_template,
        uuid="b",
        name="b",
        node_type=FlowNode.NodeType.SCRIPT,
        config={"script_content": "echo b"},
    )

    edge = FlowEdge(template=first_template, source=first_node, target=second_node)

    with pytest.raises(ValidationError, match="same template"):
        edge.full_clean()


def test_flow_runner_executes_job_plan_node_with_execution_plan_service():
    user = _create_user()
    host = _create_host(user)
    plan = _create_execution_plan(user, host)
    template = FlowTemplate.objects.create(
        name=f"flow-{uuid.uuid4().hex[:8]}",
        created_by=user,
    )
    node = FlowNode.objects.create(
        template=template,
        uuid="job-plan-1",
        name="run plan",
        node_type=FlowNode.NodeType.JOB_PLAN,
        config={
            "execution_plan_id": plan.id,
            "execution_parameters": {"foo": "bar"},
        },
    )
    node_run_holder = {}

    def execute_plan(**kwargs):
        node_run_holder["node_run"] = kwargs["related_object"]
        execution_record = ExecutionRecordService.create_execution_record(
            execution_type="flow_node",
            name="flow job plan",
            executed_by=user,
            related_object=kwargs["related_object"],
        )
        execution_record.status = "success"
        execution_record.save(update_fields=["status"])
        return {
            "success": True,
            "execution_record_id": execution_record.id,
        }

    with patch(
        "apps.job_templates.services.ExecutionPlanService.execute_plan",
        side_effect=execute_plan,
    ) as execute_plan_mock:
        flow_run = FlowRunner.start(template=template, user=user, inputs={}, agent_server_id=7)

    flow_run.refresh_from_db()
    assert flow_run.status == FlowRun.Status.SUCCESS
    node_run = flow_run.node_runs.get(node=node)
    assert node_run.status == FlowRun.Status.SUCCESS
    assert node_run.execution_record.related_object == node_run
    execute_plan_mock.assert_called_once()
    assert execute_plan_mock.call_args.kwargs["execution_plan"] == plan
    assert execute_plan_mock.call_args.kwargs["execution_type"] == "flow_node"
    assert execute_plan_mock.call_args.kwargs["related_object"] == node_run
    assert execute_plan_mock.call_args.kwargs["agent_server_id"] == 7
    assert node_run_holder["node_run"] == node_run


def test_flow_runner_pauses_job_plan_node_when_execution_record_is_still_running():
    user = _create_user()
    host = _create_host(user)
    plan = _create_execution_plan(user, host)
    template = FlowTemplate.objects.create(
        name=f"flow-{uuid.uuid4().hex[:8]}",
        created_by=user,
    )
    node = FlowNode.objects.create(
        template=template,
        uuid="job-plan-1",
        name="run plan",
        node_type=FlowNode.NodeType.JOB_PLAN,
        config={"execution_plan_id": plan.id},
    )

    execution_record_holder = {}

    def execute_plan(**kwargs):
        execution_record = ExecutionRecordService.create_execution_record(
            execution_type="flow_node",
            name="flow job plan",
            executed_by=user,
            related_object=kwargs["related_object"],
        )
        execution_record.status = "running"
        execution_record.save(update_fields=["status"])
        execution_record_holder["record"] = execution_record
        return {"success": True, "execution_record_id": execution_record.id}

    with patch(
        "apps.job_templates.services.ExecutionPlanService.execute_plan",
        side_effect=execute_plan,
    ):
        flow_run = FlowRunner.start(template=template, user=user, inputs={}, agent_server_id=7)

    flow_run.refresh_from_db()
    assert flow_run.status == FlowRun.Status.PAUSED
    node_run = flow_run.node_runs.get(node=node)
    assert node_run.status == FlowRun.Status.PAUSED
    assert node_run.execution_record == execution_record_holder["record"]
    assert node_run.finished_at is None


def test_flow_runner_rejects_job_plan_node_without_plan_permission():
    owner = _create_user()
    other = _create_user()
    host = _create_host(owner)
    plan = _create_execution_plan(owner, host)
    template = FlowTemplate.objects.create(
        name=f"flow-{uuid.uuid4().hex[:8]}",
        created_by=other,
    )
    FlowNode.objects.create(
        template=template,
        uuid="job-plan-1",
        name="run plan",
        node_type=FlowNode.NodeType.JOB_PLAN,
        config={"execution_plan_id": plan.id},
    )

    with patch("apps.job_templates.services.ExecutionPlanService.execute_plan") as execute_plan:
        flow_run = FlowRunner.start(template=template, user=other, inputs={}, agent_server_id=7)

    execute_plan.assert_not_called()
    assert flow_run.status == FlowRun.Status.FAILED
    assert "permission" in flow_run.error_message


def test_flow_runner_rejects_job_plan_with_unauthorized_internal_host():
    owner = _create_user()
    other = _create_user()
    owner_host = _create_host(owner)
    plan = _create_execution_plan(other, owner_host)
    template = FlowTemplate.objects.create(
        name=f"flow-{uuid.uuid4().hex[:8]}",
        created_by=other,
    )
    FlowNode.objects.create(
        template=template,
        uuid="job-plan-1",
        name="run plan",
        node_type=FlowNode.NodeType.JOB_PLAN,
        config={"execution_plan_id": plan.id},
    )

    with patch("apps.job_templates.services.ExecutionPlanService.execute_plan") as execute_plan:
        flow_run = FlowRunner.start(template=template, user=other, inputs={}, agent_server_id=7)

    execute_plan.assert_not_called()
    assert flow_run.status == FlowRun.Status.FAILED
    assert "permission" in flow_run.error_message


def test_flow_runner_rejects_script_node_without_host_permission():
    owner = _create_user()
    other = _create_user()
    host = _create_host(owner)
    template = FlowTemplate.objects.create(
        name=f"flow-{uuid.uuid4().hex[:8]}",
        created_by=other,
    )
    FlowNode.objects.create(
        template=template,
        uuid="script-1",
        name="script",
        node_type=FlowNode.NodeType.SCRIPT,
        config={"script_content": "echo no", "target_host_ids": [host.id]},
    )

    with patch("apps.agents.execution_service.AgentExecutionService.execute_script_via_agent") as execute_script:
        flow_run = FlowRunner.start(template=template, user=other, inputs={}, agent_server_id=7)

    execute_script.assert_not_called()
    assert flow_run.status == FlowRun.Status.FAILED
    assert "permission" in flow_run.error_message


def test_flow_runner_continues_after_paused_job_plan_execution_succeeds():
    user = _create_user()
    host = _create_host(user)
    plan = _create_execution_plan(user, host)
    template = FlowTemplate.objects.create(
        name=f"flow-{uuid.uuid4().hex[:8]}",
        created_by=user,
    )
    job_node = FlowNode.objects.create(
        template=template,
        uuid="job-plan-1",
        name="run plan",
        node_type=FlowNode.NodeType.JOB_PLAN,
        config={"execution_plan_id": plan.id},
    )
    script_node = FlowNode.objects.create(
        template=template,
        uuid="script-1",
        name="script",
        node_type=FlowNode.NodeType.SCRIPT,
        config={"script_content": "echo next", "target_host_ids": [host.id]},
    )
    FlowEdge.objects.create(template=template, source=job_node, target=script_node)

    execution_record_holder = {}

    def execute_plan(**kwargs):
        execution_record = ExecutionRecordService.create_execution_record(
            execution_type="flow_node",
            name="flow job plan",
            executed_by=user,
            related_object=kwargs["related_object"],
        )
        execution_record.status = "running"
        execution_record.save(update_fields=["status"])
        execution_record_holder["record"] = execution_record
        return {"success": True, "execution_record_id": execution_record.id}

    with patch(
        "apps.job_templates.services.ExecutionPlanService.execute_plan",
        side_effect=execute_plan,
    ):
        flow_run = FlowRunner.start(template=template, user=user, inputs={}, agent_server_id=7)

    assert flow_run.status == FlowRun.Status.PAUSED
    execution_record = execution_record_holder["record"]
    execution_record.status = "success"
    execution_record.execution_results = {"summary": {"ok": True}}
    execution_record.save(update_fields=["status", "execution_results"])

    with patch(
        "apps.agents.execution_service.AgentExecutionService.execute_script_via_agent",
        return_value={
            "success": True,
            "success_count": 1,
            "failed_count": 0,
            "results": [{"host_id": host.id, "host_name": host.name, "success": True}],
        },
    ) as execute_script:
        FlowRunner.handle_execution_record_finished(execution_record)

    flow_run.refresh_from_db()
    assert flow_run.status == FlowRun.Status.SUCCESS
    assert flow_run.node_runs.get(node=job_node).status == FlowRun.Status.SUCCESS
    assert flow_run.node_runs.get(node=script_node).status == FlowRun.Status.SUCCESS
    execute_script.assert_called_once()


def test_execution_record_status_update_advances_paused_flow_node():
    user = _create_user()
    host = _create_host(user)
    plan = _create_execution_plan(user, host)
    template = FlowTemplate.objects.create(
        name=f"flow-{uuid.uuid4().hex[:8]}",
        created_by=user,
    )
    job_node = FlowNode.objects.create(
        template=template,
        uuid="job-plan-1",
        name="run plan",
        node_type=FlowNode.NodeType.JOB_PLAN,
        config={"execution_plan_id": plan.id},
    )
    script_node = FlowNode.objects.create(
        template=template,
        uuid="script-1",
        name="script",
        node_type=FlowNode.NodeType.SCRIPT,
        config={"script_content": "echo next", "target_host_ids": [host.id]},
    )
    FlowEdge.objects.create(template=template, source=job_node, target=script_node)

    execution_record_holder = {}

    def execute_plan(**kwargs):
        execution_record = ExecutionRecordService.create_execution_record(
            execution_type="flow_node",
            name="flow job plan",
            executed_by=user,
            related_object=kwargs["related_object"],
        )
        execution_record.status = "running"
        execution_record.save(update_fields=["status"])
        execution_record_holder["record"] = execution_record
        return {"success": True, "execution_record_id": execution_record.id}

    with patch(
        "apps.job_templates.services.ExecutionPlanService.execute_plan",
        side_effect=execute_plan,
    ):
        flow_run = FlowRunner.start(template=template, user=user, inputs={}, agent_server_id=7)

    assert flow_run.status == FlowRun.Status.PAUSED

    with patch(
        "apps.agents.execution_service.AgentExecutionService.execute_script_via_agent",
        return_value={
            "success": True,
            "success_count": 1,
            "failed_count": 0,
            "results": [{"host_id": host.id, "host_name": host.name, "success": True}],
        },
    ) as execute_script, patch(
        "apps.executor.services.realtime_log_service.push_status"
    ), patch(
        "utils.log_archive_service.log_archive_service.archive_execution_logs",
        return_value=True,
    ):
        ExecutionRecordService.update_execution_status(
            execution_record_holder["record"],
            "success",
            execution_results={"summary": {"ok": True}},
        )

    flow_run.refresh_from_db()
    assert flow_run.status == FlowRun.Status.SUCCESS
    assert flow_run.node_runs.get(node=job_node).status == FlowRun.Status.SUCCESS
    assert flow_run.node_runs.get(node=script_node).status == FlowRun.Status.SUCCESS
    execute_script.assert_called_once()


def test_flow_runner_rejects_mismatched_job_plan_execution_record_without_rebinding():
    user = _create_user()
    host = _create_host(user)
    plan = _create_execution_plan(user, host)
    template = FlowTemplate.objects.create(name=f"flow-{uuid.uuid4().hex[:8]}", created_by=user)
    node = FlowNode.objects.create(
        template=template,
        uuid="job-plan-1",
        name="run plan",
        node_type=FlowNode.NodeType.JOB_PLAN,
        config={"execution_plan_id": plan.id},
    )
    other_flow_run = FlowRun.objects.create(template=template, started_by=user, status=FlowRun.Status.PAUSED)
    other_node_run = FlowNodeRun.objects.create(
        flow_run=other_flow_run,
        node=node,
        status=FlowRun.Status.PAUSED,
        started_at=timezone.now(),
    )
    mismatched_record = ExecutionRecordService.create_execution_record(
        execution_type="flow_node",
        name="mismatched",
        executed_by=user,
        related_object=other_node_run,
    )
    original_content_type_id = mismatched_record.content_type_id
    original_object_id = mismatched_record.object_id

    with patch(
        "apps.job_templates.services.ExecutionPlanService.execute_plan",
        return_value={"success": True, "execution_record_id": mismatched_record.id},
    ):
        flow_run = FlowRunner.start(template=template, user=user, inputs={}, agent_server_id=7)

    mismatched_record.refresh_from_db()
    assert flow_run.status == FlowRun.Status.FAILED
    assert mismatched_record.content_type_id == original_content_type_id
    assert mismatched_record.object_id == original_object_id
    assert mismatched_record.related_object == other_node_run


def test_flow_runner_ignores_late_job_plan_success_for_cancelled_flow():
    user = _create_user()
    host = _create_host(user)
    plan = _create_execution_plan(user, host)
    template = FlowTemplate.objects.create(name=f"flow-{uuid.uuid4().hex[:8]}", created_by=user)
    job_node = FlowNode.objects.create(
        template=template,
        uuid="job-plan-1",
        name="run plan",
        node_type=FlowNode.NodeType.JOB_PLAN,
        config={"execution_plan_id": plan.id},
    )
    script_node = FlowNode.objects.create(
        template=template,
        uuid="script-1",
        name="script",
        node_type=FlowNode.NodeType.SCRIPT,
        config={"script_content": "echo next", "target_host_ids": [host.id]},
    )
    FlowEdge.objects.create(template=template, source=job_node, target=script_node)
    flow_run = FlowRun.objects.create(
        template=template,
        status=FlowRun.Status.CANCELLED,
        started_by=user,
        started_at=timezone.now(),
        finished_at=timezone.now(),
    )
    node_run = FlowNodeRun.objects.create(
        flow_run=flow_run,
        node=job_node,
        status=FlowRun.Status.PAUSED,
        started_at=timezone.now(),
    )
    execution_record = ExecutionRecordService.create_execution_record(
        execution_type="flow_node",
        name="late success",
        executed_by=user,
        related_object=node_run,
    )
    execution_record.status = "success"
    execution_record.execution_results = {"summary": {"ok": True}}
    execution_record.save(update_fields=["status", "execution_results"])

    with patch("apps.agents.execution_service.AgentExecutionService.execute_script_via_agent") as execute_script:
        FlowRunner.handle_execution_record_finished(execution_record)

    flow_run.refresh_from_db()
    node_run.refresh_from_db()
    assert flow_run.status == FlowRun.Status.CANCELLED
    assert node_run.status == FlowRun.Status.PAUSED
    assert not FlowNodeRun.objects.filter(flow_run=flow_run, node=script_node).exists()
    execute_script.assert_not_called()


def test_flow_runner_does_not_continue_past_existing_running_node():
    user = _create_user()
    host = _create_host(user)
    template = FlowTemplate.objects.create(
        name=f"flow-{uuid.uuid4().hex[:8]}",
        created_by=user,
    )
    running_node = FlowNode.objects.create(
        template=template,
        uuid="running-1",
        name="running",
        node_type=FlowNode.NodeType.JOB_PLAN,
        config={"execution_plan_id": 1},
    )
    script_node = FlowNode.objects.create(
        template=template,
        uuid="script-1",
        name="script",
        node_type=FlowNode.NodeType.SCRIPT,
        config={"script_content": "echo next", "target_host_ids": [host.id]},
    )
    FlowEdge.objects.create(template=template, source=running_node, target=script_node)
    flow_run = FlowRun.objects.create(
        template=template,
        status=FlowRun.Status.PAUSED,
        started_by=user,
        started_at=timezone.now(),
    )
    FlowNodeRun.objects.create(
        flow_run=flow_run,
        node=running_node,
        status=FlowRun.Status.RUNNING,
        started_at=timezone.now(),
    )

    with patch("apps.agents.execution_service.AgentExecutionService.execute_script_via_agent") as execute_script:
        FlowRunner._continue_flow(flow_run, user, agent_server_id=7)

    flow_run.refresh_from_db()
    assert flow_run.status == FlowRun.Status.PAUSED
    assert not FlowNodeRun.objects.filter(flow_run=flow_run, node=script_node).exists()
    execute_script.assert_not_called()


def test_flow_runner_executes_file_transfer_node_with_agent_service():
    user = _create_user()
    host = _create_host(user)
    template = FlowTemplate.objects.create(
        name=f"flow-{uuid.uuid4().hex[:8]}",
        created_by=user,
    )
    node = FlowNode.objects.create(
        template=template,
        uuid="file-1",
        name="send file",
        node_type=FlowNode.NodeType.FILE_TRANSFER,
        config={
            "target_host_ids": [host.id],
            "timeout": 60,
            "bandwidth_limit": 5,
            "file_sources": [
                {
                    "type": "artifact",
                    "remote_path": "/tmp/a.txt",
                    "download_url": "https://example.test/a.txt",
                    "sha256": "abc",
                    "size": 12,
                    "auth_headers": {"X-Test": "1"},
                }
            ],
        },
    )

    with patch(
        "apps.agents.execution_service.AgentExecutionService.execute_file_transfer_via_agent",
        return_value={
            "success": True,
            "success_count": 1,
            "failed_count": 0,
            "results": [{"host_id": host.id, "host_name": host.name, "success": True}],
        },
    ) as execute_transfer:
        flow_run = FlowRunner.start(template=template, user=user, inputs={}, agent_server_id=3)

    flow_run.refresh_from_db()
    assert flow_run.status == FlowRun.Status.SUCCESS
    node_run = flow_run.node_runs.get(node=node)
    assert node_run.status == FlowRun.Status.SUCCESS
    assert node_run.execution_record.execution_type == "flow_node"
    assert node_run.outputs["success_count"] == 1
    execute_transfer.assert_called_once()
    assert execute_transfer.call_args.kwargs["remote_path"] == "/tmp/a.txt"
    assert execute_transfer.call_args.kwargs["download_url"] == "https://example.test/a.txt"
    assert execute_transfer.call_args.kwargs["agent_server_id"] == 3


def test_flow_runner_rejects_invalid_file_transfer_source_before_dispatch():
    user = _create_user()
    host = _create_host(user)
    template = FlowTemplate.objects.create(
        name=f"flow-{uuid.uuid4().hex[:8]}",
        created_by=user,
    )
    FlowNode.objects.create(
        template=template,
        uuid="file-1",
        name="send file",
        node_type=FlowNode.NodeType.FILE_TRANSFER,
        config={
            "target_host_ids": [host.id],
            "file_sources": [
                {
                    "type": "artifact",
                    "remote_path": "/tmp/a.txt",
                    "download_url": "https://example.test/a.txt",
                },
                {"type": "artifact", "remote_path": "/tmp/b.txt"},
            ],
        },
    )

    with patch("apps.agents.execution_service.AgentExecutionService.execute_file_transfer_via_agent") as transfer:
        flow_run = FlowRunner.start(template=template, user=user, inputs={}, agent_server_id=3)

    transfer.assert_not_called()
    assert flow_run.status == FlowRun.Status.FAILED
    node_run = flow_run.node_runs.get()
    assert node_run.status == FlowRun.Status.FAILED
    assert "download_url" in node_run.error_message
    assert ExecutionRecord.objects.filter(execution_type="flow_node").count() == 0


def test_flow_runner_rejects_file_transfer_source_without_remote_path():
    user = _create_user()
    host = _create_host(user)
    template = FlowTemplate.objects.create(
        name=f"flow-{uuid.uuid4().hex[:8]}",
        created_by=user,
    )
    FlowNode.objects.create(
        template=template,
        uuid="file-1",
        name="send file",
        node_type=FlowNode.NodeType.FILE_TRANSFER,
        config={
            "target_host_ids": [host.id],
            "file_sources": [{"type": "artifact", "download_url": "https://example.test/a.txt"}],
        },
    )

    with patch("apps.agents.execution_service.AgentExecutionService.execute_file_transfer_via_agent") as transfer:
        flow_run = FlowRunner.start(template=template, user=user, inputs={}, agent_server_id=3)

    transfer.assert_not_called()
    assert flow_run.status == FlowRun.Status.FAILED
    assert "remote_path" in flow_run.error_message


def test_flow_runner_marks_file_transfer_execution_record_failed_when_dispatch_raises():
    user = _create_user()
    host = _create_host(user)
    template = FlowTemplate.objects.create(
        name=f"flow-{uuid.uuid4().hex[:8]}",
        created_by=user,
    )
    FlowNode.objects.create(
        template=template,
        uuid="file-1",
        name="send file",
        node_type=FlowNode.NodeType.FILE_TRANSFER,
        config={
            "target_host_ids": [host.id],
            "file_sources": [
                {
                    "type": "artifact",
                    "remote_path": "/tmp/a.txt",
                    "download_url": "https://example.test/a.txt",
                }
            ],
        },
    )

    with patch(
        "apps.agents.execution_service.AgentExecutionService.execute_file_transfer_via_agent",
        side_effect=RuntimeError("agent dispatch failed"),
    ):
        with pytest.raises(RuntimeError, match="agent dispatch failed"):
            FlowRunner.start(template=template, user=user, inputs={}, agent_server_id=3)

    node_run = FlowNodeRun.objects.get()
    assert node_run.status == FlowRun.Status.FAILED
    assert node_run.execution_record.status == "failed"
    assert "agent dispatch failed" in node_run.execution_record.error_message
