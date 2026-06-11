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


def test_flow_runner_selected_scope_executes_only_selected_nodes():
    user = _create_user()
    host = _create_host(user)
    template = FlowTemplate.objects.create(
        name=f"flow-{uuid.uuid4().hex[:8]}",
        created_by=user,
    )
    first = FlowNode.objects.create(
        template=template,
        uuid="script-1",
        name="first script",
        node_type=FlowNode.NodeType.SCRIPT,
        config={"script_content": "echo first", "target_host_ids": [host.id]},
    )
    second = FlowNode.objects.create(
        template=template,
        uuid="script-2",
        name="second script",
        node_type=FlowNode.NodeType.SCRIPT,
        config={"script_content": "echo second", "target_host_ids": [host.id]},
    )
    FlowEdge.objects.create(template=template, source=first, target=second)

    with patch(
        "apps.agents.execution_service.AgentExecutionService.execute_script_via_agent",
        return_value={
            "success": True,
            "success_count": 1,
            "failed_count": 0,
            "results": [{"host_id": host.id, "host_name": host.name, "success": True}],
        },
    ) as execute_script:
        flow_run = FlowRunner.start(
            template=template,
            user=user,
            inputs={
                "__execution_scope": "selected",
                "__selected_node_uuids": ["script-2"],
            },
            agent_server_id=3,
        )

    flow_run.refresh_from_db()
    assert flow_run.status == FlowRun.Status.SUCCESS
    assert list(flow_run.node_runs.values_list("node__uuid", flat=True)) == ["script-2"]
    execute_script.assert_called_once()
    assert execute_script.call_args.kwargs["script_content"] == "echo second"


def test_flow_runner_node_overrides_apply_to_run_without_mutating_template():
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
            "script_content": "echo original",
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
        flow_run = FlowRunner.start(
            template=template,
            user=user,
            inputs={
                "__node_overrides": {
                    "script-1": {
                        "script_content": "echo override",
                        "timeout": 99,
                    }
                }
            },
            agent_server_id=3,
        )

    flow_run.refresh_from_db()
    node_run = flow_run.node_runs.get(node=node)
    assert node_run.status == FlowRun.Status.SUCCESS
    assert node_run.inputs["script_content"] == "echo override"
    assert node_run.inputs["timeout"] == 99
    assert execute_script.call_args.kwargs["script_content"] == "echo override"
    assert execute_script.call_args.kwargs["timeout"] == 99
    node.refresh_from_db()
    assert node.config["script_content"] == "echo original"
    assert node.config["timeout"] == 30


def test_flow_runner_strips_control_inputs_from_job_plan_parameters():
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
            "execution_parameters": {"node_param": "node-value"},
        },
    )

    def execute_plan(**kwargs):
        execution_record = ExecutionRecordService.create_execution_record(
            execution_type="flow_node",
            name="flow job plan",
            executed_by=user,
            related_object=kwargs["related_object"],
        )
        execution_record.status = "success"
        execution_record.save(update_fields=["status"])
        return {"success": True, "execution_record_id": execution_record.id}

    with patch(
        "apps.job_templates.services.ExecutionPlanService.execute_plan",
        side_effect=execute_plan,
    ) as execute_plan_mock:
        flow_run = FlowRunner.start(
            template=template,
            user=user,
            inputs={
                "business_param": "business-value",
                "__execution_scope": "selected",
                "__selected_node_uuids": ["job-plan-1"],
                "__node_overrides": {},
            },
            agent_server_id=3,
        )

    assert flow_run.status == FlowRun.Status.SUCCESS
    execution_parameters = execute_plan_mock.call_args.kwargs["execution_parameters"]
    assert execution_parameters == {
        "business_param": "business-value",
        "node_param": "node-value",
    }
    assert flow_run.node_runs.get(node=node).status == FlowRun.Status.SUCCESS


def test_flow_runner_ignore_failure_policy_continues_after_failed_node():
    user = _create_user()
    host = _create_host(user)
    template = FlowTemplate.objects.create(
        name=f"flow-{uuid.uuid4().hex[:8]}",
        created_by=user,
    )
    first = FlowNode.objects.create(
        template=template,
        uuid="script-1",
        name="first script",
        node_type=FlowNode.NodeType.SCRIPT,
        config={
            "script_content": "echo first",
            "target_host_ids": [host.id],
            "failure_policy": "ignore",
        },
    )
    second = FlowNode.objects.create(
        template=template,
        uuid="script-2",
        name="second script",
        node_type=FlowNode.NodeType.SCRIPT,
        config={"script_content": "echo second", "target_host_ids": [host.id]},
    )
    FlowEdge.objects.create(template=template, source=first, target=second)

    with patch(
        "apps.agents.execution_service.AgentExecutionService.execute_script_via_agent",
        side_effect=[
            {
                "success": False,
                "success_count": 0,
                "failed_count": 1,
                "error": "script failed",
                "results": [{"host_id": host.id, "host_name": host.name, "success": False}],
            },
            {
                "success": True,
                "success_count": 1,
                "failed_count": 0,
                "results": [{"host_id": host.id, "host_name": host.name, "success": True}],
            },
        ],
    ) as execute_script:
        flow_run = FlowRunner.start(template=template, user=user, inputs={}, agent_server_id=3)

    flow_run.refresh_from_db()
    assert flow_run.status == FlowRun.Status.SUCCESS
    assert flow_run.node_runs.get(node=first).status == FlowRun.Status.FAILED
    assert flow_run.node_runs.get(node=second).status == FlowRun.Status.SUCCESS
    assert execute_script.call_count == 2


def test_flow_runner_pause_failure_policy_pauses_before_downstream_nodes():
    user = _create_user()
    host = _create_host(user)
    template = FlowTemplate.objects.create(
        name=f"flow-{uuid.uuid4().hex[:8]}",
        created_by=user,
    )
    first = FlowNode.objects.create(
        template=template,
        uuid="script-1",
        name="first script",
        node_type=FlowNode.NodeType.SCRIPT,
        config={
            "script_content": "echo first",
            "target_host_ids": [host.id],
            "failure_policy": "pause",
        },
    )
    second = FlowNode.objects.create(
        template=template,
        uuid="script-2",
        name="second script",
        node_type=FlowNode.NodeType.SCRIPT,
        config={"script_content": "echo second", "target_host_ids": [host.id]},
    )
    FlowEdge.objects.create(template=template, source=first, target=second)

    with patch(
        "apps.agents.execution_service.AgentExecutionService.execute_script_via_agent",
        return_value={
            "success": False,
            "success_count": 0,
            "failed_count": 1,
            "error": "script failed",
            "results": [{"host_id": host.id, "host_name": host.name, "success": False}],
        },
    ) as execute_script:
        flow_run = FlowRunner.start(template=template, user=user, inputs={}, agent_server_id=3)

    flow_run.refresh_from_db()
    assert flow_run.status == FlowRun.Status.PAUSED
    assert flow_run.error_message == "script failed"
    assert flow_run.node_runs.get(node=first).status == FlowRun.Status.PAUSED
    assert not flow_run.node_runs.filter(node=second).exists()
    execute_script.assert_called_once()


def test_flow_runner_skip_paused_node_continues_downstream_nodes():
    user = _create_user()
    host = _create_host(user)
    template = FlowTemplate.objects.create(
        name=f"flow-{uuid.uuid4().hex[:8]}",
        created_by=user,
    )
    first = FlowNode.objects.create(
        template=template,
        uuid="script-1",
        name="first script",
        node_type=FlowNode.NodeType.SCRIPT,
        config={
            "script_content": "echo first",
            "target_host_ids": [host.id],
            "failure_policy": "pause",
        },
    )
    second = FlowNode.objects.create(
        template=template,
        uuid="script-2",
        name="second script",
        node_type=FlowNode.NodeType.SCRIPT,
        config={"script_content": "echo second", "target_host_ids": [host.id]},
    )
    FlowEdge.objects.create(template=template, source=first, target=second)

    with patch(
        "apps.agents.execution_service.AgentExecutionService.execute_script_via_agent",
        return_value={
            "success": False,
            "success_count": 0,
            "failed_count": 1,
            "error": "script failed",
            "results": [{"host_id": host.id, "host_name": host.name, "success": False}],
        },
    ):
        flow_run = FlowRunner.start(template=template, user=user, inputs={}, agent_server_id=3)

    first_run = flow_run.node_runs.get(node=first)
    assert first_run.status == FlowRun.Status.PAUSED

    with patch(
        "apps.agents.execution_service.AgentExecutionService.execute_script_via_agent",
        return_value={
            "success": True,
            "success_count": 1,
            "failed_count": 0,
            "results": [{"host_id": host.id, "host_name": host.name, "success": True}],
        },
    ) as execute_script:
        flow_run = FlowRunner.skip_node(
            flow_run=flow_run,
            node_run=first_run,
            user=user,
            reason="manual skip",
            agent_server_id=3,
        )

    flow_run.refresh_from_db()
    first_run.refresh_from_db()
    assert flow_run.status == FlowRun.Status.SUCCESS
    assert first_run.status == FlowRun.Status.SUCCESS
    assert first_run.outputs["skipped"] is True
    assert first_run.outputs["skip_reason"] == "manual skip"
    assert flow_run.node_runs.get(node=second).status == FlowRun.Status.SUCCESS
    execute_script.assert_called_once()


def test_flow_runner_pauses_at_manual_node_before_downstream_nodes():
    user = _create_user()
    host = _create_host(user)
    template = FlowTemplate.objects.create(
        name=f"flow-{uuid.uuid4().hex[:8]}",
        created_by=user,
    )
    manual = FlowNode.objects.create(
        template=template,
        uuid="manual-1",
        name="人工确认",
        node_type=FlowNode.NodeType.MANUAL,
        config={"instructions": "确认变更窗口后继续"},
    )
    script = FlowNode.objects.create(
        template=template,
        uuid="script-1",
        name="second script",
        node_type=FlowNode.NodeType.SCRIPT,
        config={"script_content": "echo second", "target_host_ids": [host.id]},
    )
    FlowEdge.objects.create(template=template, source=manual, target=script)

    with patch("apps.agents.execution_service.AgentExecutionService.execute_script_via_agent") as execute_script:
        flow_run = FlowRunner.start(template=template, user=user, inputs={}, agent_server_id=3)

    flow_run.refresh_from_db()
    manual_run = flow_run.node_runs.get(node=manual)
    assert flow_run.status == FlowRun.Status.PAUSED
    assert manual_run.status == FlowRun.Status.PAUSED
    assert manual_run.inputs["instructions"] == "确认变更窗口后继续"
    assert manual_run.outputs["manual"] is True
    assert manual_run.finished_at is None
    assert not flow_run.node_runs.filter(node=script).exists()
    execute_script.assert_not_called()


def test_flow_runner_confirms_manual_node_and_continues_downstream_nodes():
    user = _create_user()
    host = _create_host(user)
    template = FlowTemplate.objects.create(
        name=f"flow-{uuid.uuid4().hex[:8]}",
        created_by=user,
    )
    manual = FlowNode.objects.create(
        template=template,
        uuid="manual-1",
        name="人工确认",
        node_type=FlowNode.NodeType.MANUAL,
        config={"instructions": "确认后继续"},
    )
    script = FlowNode.objects.create(
        template=template,
        uuid="script-1",
        name="second script",
        node_type=FlowNode.NodeType.SCRIPT,
        config={"script_content": "echo second", "target_host_ids": [host.id]},
    )
    FlowEdge.objects.create(template=template, source=manual, target=script)

    flow_run = FlowRunner.start(template=template, user=user, inputs={}, agent_server_id=3)
    manual_run = flow_run.node_runs.get(node=manual)
    assert flow_run.status == FlowRun.Status.PAUSED

    with patch(
        "apps.agents.execution_service.AgentExecutionService.execute_script_via_agent",
        return_value={
            "success": True,
            "success_count": 1,
            "failed_count": 0,
            "results": [{"host_id": host.id, "host_name": host.name, "success": True}],
        },
    ) as execute_script:
        flow_run = FlowRunner.confirm_manual_node(
            flow_run=flow_run,
            node_run=manual_run,
            user=user,
            remark="window verified",
            agent_server_id=3,
        )

    flow_run.refresh_from_db()
    manual_run.refresh_from_db()
    assert flow_run.status == FlowRun.Status.SUCCESS
    assert manual_run.status == FlowRun.Status.SUCCESS
    assert manual_run.outputs["confirmed"] is True
    assert manual_run.outputs["confirmed_by"] == user.username
    assert manual_run.outputs["confirm_remark"] == "window verified"
    assert manual_run.finished_at is not None
    assert flow_run.node_runs.get(node=script).status == FlowRun.Status.SUCCESS
    execute_script.assert_called_once()


def test_flow_runner_subprocess_success_continues_parent_downstream_nodes():
    user = _create_user()
    child_template = FlowTemplate.objects.create(name=f"child-{uuid.uuid4().hex[:8]}", created_by=user)
    child_gateway = FlowNode.objects.create(
        template=child_template,
        uuid="child-gateway",
        name="child gateway",
        node_type=FlowNode.NodeType.PARALLEL,
        config={},
    )
    parent_template = FlowTemplate.objects.create(name=f"parent-{uuid.uuid4().hex[:8]}", created_by=user)
    sub_process = FlowNode.objects.create(
        template=parent_template,
        uuid="sub-process",
        name="child flow",
        node_type=FlowNode.NodeType.SUB_PROCESS,
        config={"template_id": child_template.id, "inputs": {"child_only": "yes"}},
    )
    downstream = FlowNode.objects.create(
        template=parent_template,
        uuid="after-child",
        name="after child",
        node_type=FlowNode.NodeType.JOIN,
        config={},
    )
    FlowEdge.objects.create(template=parent_template, source=sub_process, target=downstream)

    flow_run = FlowRunner.start(
        template=parent_template,
        user=user,
        inputs={"env": "prod", "__parent_flow_run_id": 999},
        agent_server_id=3,
    )

    flow_run.refresh_from_db()
    assert flow_run.status == FlowRun.Status.SUCCESS
    parent_node_run = flow_run.node_runs.get(node=sub_process)
    child_flow_run = FlowRun.objects.get(id=parent_node_run.outputs["child_flow_run_id"])
    assert parent_node_run.status == FlowRun.Status.SUCCESS
    assert child_flow_run.template == child_template
    assert child_flow_run.status == FlowRun.Status.SUCCESS
    assert child_flow_run.inputs["env"] == "prod"
    assert child_flow_run.inputs["child_only"] == "yes"
    assert "__parent_flow_run_id" not in FlowRunner._business_inputs(child_flow_run.inputs)
    assert child_flow_run.node_runs.get(node=child_gateway).status == FlowRun.Status.SUCCESS
    assert flow_run.node_runs.get(node=downstream).status == FlowRun.Status.SUCCESS


def test_flow_runner_subprocess_pauses_parent_and_resumes_when_child_succeeds():
    user = _create_user()
    child_template = FlowTemplate.objects.create(name=f"child-{uuid.uuid4().hex[:8]}", created_by=user)
    manual = FlowNode.objects.create(
        template=child_template,
        uuid="manual-1",
        name="approve",
        node_type=FlowNode.NodeType.MANUAL,
        config={"instructions": "approve child"},
    )
    child_done = FlowNode.objects.create(
        template=child_template,
        uuid="child-done",
        name="child done",
        node_type=FlowNode.NodeType.JOIN,
        config={},
    )
    FlowEdge.objects.create(template=child_template, source=manual, target=child_done)
    parent_template = FlowTemplate.objects.create(name=f"parent-{uuid.uuid4().hex[:8]}", created_by=user)
    sub_process = FlowNode.objects.create(
        template=parent_template,
        uuid="sub-process",
        name="child flow",
        node_type=FlowNode.NodeType.SUB_PROCESS,
        config={"template_id": child_template.id},
    )
    downstream = FlowNode.objects.create(
        template=parent_template,
        uuid="after-child",
        name="after child",
        node_type=FlowNode.NodeType.JOIN,
        config={},
    )
    FlowEdge.objects.create(template=parent_template, source=sub_process, target=downstream)

    parent_run = FlowRunner.start(template=parent_template, user=user, inputs={}, agent_server_id=3)

    parent_run.refresh_from_db()
    parent_node_run = parent_run.node_runs.get(node=sub_process)
    child_run = FlowRun.objects.get(id=parent_node_run.outputs["child_flow_run_id"])
    assert parent_run.status == FlowRun.Status.PAUSED
    assert parent_node_run.status == FlowRun.Status.PAUSED
    assert child_run.status == FlowRun.Status.PAUSED
    assert not parent_run.node_runs.filter(node=downstream).exists()

    child_manual_run = child_run.node_runs.get(node=manual)
    FlowRunner.confirm_manual_node(
        flow_run=child_run,
        node_run=child_manual_run,
        user=user,
        remark="ok",
        agent_server_id=3,
    )

    parent_run.refresh_from_db()
    parent_node_run.refresh_from_db()
    child_run.refresh_from_db()
    assert child_run.status == FlowRun.Status.SUCCESS
    assert parent_run.status == FlowRun.Status.SUCCESS
    assert parent_node_run.status == FlowRun.Status.SUCCESS
    assert parent_run.node_runs.get(node=downstream).status == FlowRun.Status.SUCCESS


def test_flow_runner_subprocess_child_failure_fails_parent_node():
    user = _create_user()
    child_template = FlowTemplate.objects.create(name=f"child-{uuid.uuid4().hex[:8]}", created_by=user)
    FlowNode.objects.create(
        template=child_template,
        uuid="bad-script",
        name="bad script",
        node_type=FlowNode.NodeType.SCRIPT,
        config={"script_content": "exit 1", "target_host_ids": []},
    )
    parent_template = FlowTemplate.objects.create(name=f"parent-{uuid.uuid4().hex[:8]}", created_by=user)
    sub_process = FlowNode.objects.create(
        template=parent_template,
        uuid="sub-process",
        name="child flow",
        node_type=FlowNode.NodeType.SUB_PROCESS,
        config={"template_id": child_template.id},
    )

    with patch("apps.agents.execution_service.AgentExecutionService.execute_script_via_agent") as execute_script:
        parent_run = FlowRunner.start(template=parent_template, user=user, inputs={}, agent_server_id=3)

    execute_script.assert_not_called()
    parent_run.refresh_from_db()
    parent_node_run = parent_run.node_runs.get(node=sub_process)
    child_run = FlowRun.objects.get(id=parent_node_run.outputs["child_flow_run_id"])
    assert child_run.status == FlowRun.Status.FAILED
    assert parent_run.status == FlowRun.Status.FAILED
    assert parent_node_run.status == FlowRun.Status.FAILED
    assert "valid target host" in parent_node_run.error_message


def test_flow_runner_subprocess_async_child_failure_updates_parent():
    user = _create_user()
    host = _create_host(user)
    plan = _create_execution_plan(user, host)
    child_template = FlowTemplate.objects.create(name=f"child-{uuid.uuid4().hex[:8]}", created_by=user)
    child_job = FlowNode.objects.create(
        template=child_template,
        uuid="child-job",
        name="child job",
        node_type=FlowNode.NodeType.JOB_PLAN,
        config={"execution_plan_id": plan.id},
    )
    parent_template = FlowTemplate.objects.create(name=f"parent-{uuid.uuid4().hex[:8]}", created_by=user)
    sub_process = FlowNode.objects.create(
        template=parent_template,
        uuid="sub-process",
        name="child flow",
        node_type=FlowNode.NodeType.SUB_PROCESS,
        config={"template_id": child_template.id},
    )
    execution_record_holder = {}

    def execute_plan(**kwargs):
        execution_record = ExecutionRecordService.create_execution_record(
            execution_type="flow_node",
            name="child job plan",
            executed_by=user,
            related_object=kwargs["related_object"],
            execution_parameters={"agent_server_id": 3},
        )
        execution_record.status = "running"
        execution_record.save(update_fields=["status"])
        execution_record_holder["record"] = execution_record
        return {"success": True, "execution_record_id": execution_record.id}

    with patch("apps.job_templates.services.ExecutionPlanService.execute_plan", side_effect=execute_plan):
        parent_run = FlowRunner.start(template=parent_template, user=user, inputs={}, agent_server_id=3)

    parent_node_run = parent_run.node_runs.get(node=sub_process)
    child_run = FlowRun.objects.get(id=parent_node_run.outputs["child_flow_run_id"])
    assert parent_run.status == FlowRun.Status.PAUSED
    assert child_run.node_runs.get(node=child_job).status == FlowRun.Status.PAUSED

    execution_record = execution_record_holder["record"]
    execution_record.status = "failed"
    execution_record.error_message = "child async failed"
    execution_record.save(update_fields=["status", "error_message"])
    FlowRunner.handle_execution_record_finished(execution_record)

    parent_run.refresh_from_db()
    parent_node_run.refresh_from_db()
    child_run.refresh_from_db()
    assert child_run.status == FlowRun.Status.FAILED
    assert parent_run.status == FlowRun.Status.FAILED
    assert parent_node_run.status == FlowRun.Status.FAILED
    assert "child async failed" in parent_node_run.error_message


def test_flow_runner_subprocess_rejects_recursive_template_stack():
    user = _create_user()
    parent_template = FlowTemplate.objects.create(name=f"parent-{uuid.uuid4().hex[:8]}", created_by=user)
    child_template = FlowTemplate.objects.create(name=f"child-{uuid.uuid4().hex[:8]}", created_by=user)
    parent_sub = FlowNode.objects.create(
        template=parent_template,
        uuid="parent-sub",
        name="parent sub",
        node_type=FlowNode.NodeType.SUB_PROCESS,
        config={"template_id": child_template.id},
    )
    FlowNode.objects.create(
        template=child_template,
        uuid="child-sub",
        name="child sub",
        node_type=FlowNode.NodeType.SUB_PROCESS,
        config={"template_id": parent_template.id},
    )

    parent_run = FlowRunner.start(template=parent_template, user=user, inputs={}, agent_server_id=3)

    parent_run.refresh_from_db()
    parent_node_run = parent_run.node_runs.get(node=parent_sub)
    child_run = FlowRun.objects.get(id=parent_node_run.outputs["child_flow_run_id"])
    assert FlowRun.objects.count() == 2
    assert child_run.status == FlowRun.Status.FAILED
    assert parent_run.status == FlowRun.Status.FAILED
    assert "recursion" in child_run.error_message
    assert "recursion" in parent_node_run.error_message


def test_flow_runner_cancel_parent_subprocess_cancels_active_child_flow():
    user = _create_user()
    child_template = FlowTemplate.objects.create(name=f"child-{uuid.uuid4().hex[:8]}", created_by=user)
    child_manual = FlowNode.objects.create(
        template=child_template,
        uuid="manual-1",
        name="approve",
        node_type=FlowNode.NodeType.MANUAL,
        config={},
    )
    parent_template = FlowTemplate.objects.create(name=f"parent-{uuid.uuid4().hex[:8]}", created_by=user)
    sub_process = FlowNode.objects.create(
        template=parent_template,
        uuid="sub-process",
        name="child flow",
        node_type=FlowNode.NodeType.SUB_PROCESS,
        config={"template_id": child_template.id},
    )

    parent_run = FlowRunner.start(template=parent_template, user=user, inputs={}, agent_server_id=3)
    parent_node_run = parent_run.node_runs.get(node=sub_process)
    child_run = FlowRun.objects.get(id=parent_node_run.outputs["child_flow_run_id"])

    FlowRunner.cancel_flow(parent_run, user=user)

    parent_run.refresh_from_db()
    parent_node_run.refresh_from_db()
    child_run.refresh_from_db()
    assert parent_run.status == FlowRun.Status.CANCELLED
    assert parent_node_run.status == FlowRun.Status.CANCELLED
    assert child_run.status == FlowRun.Status.CANCELLED
    assert child_run.node_runs.get(node=child_manual).status == FlowRun.Status.CANCELLED


def test_flow_runner_condition_node_executes_only_matching_branch():
    user = _create_user()
    host = _create_host(user)
    template = FlowTemplate.objects.create(
        name=f"flow-{uuid.uuid4().hex[:8]}",
        created_by=user,
    )
    condition = FlowNode.objects.create(
        template=template,
        uuid="condition-1",
        name="环境判断",
        node_type=FlowNode.NodeType.CONDITION,
        config={"description": "route by env"},
    )
    prod = FlowNode.objects.create(
        template=template,
        uuid="prod-script",
        name="prod script",
        node_type=FlowNode.NodeType.SCRIPT,
        config={"script_content": "echo prod", "target_host_ids": [host.id]},
    )
    fallback = FlowNode.objects.create(
        template=template,
        uuid="fallback-script",
        name="fallback script",
        node_type=FlowNode.NodeType.SCRIPT,
        config={"script_content": "echo fallback", "target_host_ids": [host.id]},
    )
    FlowEdge.objects.create(
        template=template,
        source=condition,
        target=prod,
        condition={"variable": "inputs.env", "operator": "eq", "value": "prod"},
    )
    FlowEdge.objects.create(
        template=template,
        source=condition,
        target=fallback,
        condition={"default": True},
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
        flow_run = FlowRunner.start(template=template, user=user, inputs={"env": "prod"}, agent_server_id=3)

    flow_run.refresh_from_db()
    condition_run = flow_run.node_runs.get(node=condition)
    assert flow_run.status == FlowRun.Status.SUCCESS
    assert condition_run.status == FlowRun.Status.SUCCESS
    assert condition_run.outputs["selected_node_uuids"] == ["prod-script"]
    assert flow_run.node_runs.get(node=prod).status == FlowRun.Status.SUCCESS
    assert not flow_run.node_runs.filter(node=fallback).exists()
    execute_script.assert_called_once()
    assert execute_script.call_args.kwargs["script_content"] == "echo prod"


def test_flow_runner_condition_node_uses_default_branch_when_no_condition_matches():
    user = _create_user()
    host = _create_host(user)
    template = FlowTemplate.objects.create(
        name=f"flow-{uuid.uuid4().hex[:8]}",
        created_by=user,
    )
    condition = FlowNode.objects.create(
        template=template,
        uuid="condition-1",
        name="环境判断",
        node_type=FlowNode.NodeType.CONDITION,
        config={},
    )
    prod = FlowNode.objects.create(
        template=template,
        uuid="prod-script",
        name="prod script",
        node_type=FlowNode.NodeType.SCRIPT,
        config={"script_content": "echo prod", "target_host_ids": [host.id]},
    )
    fallback = FlowNode.objects.create(
        template=template,
        uuid="fallback-script",
        name="fallback script",
        node_type=FlowNode.NodeType.SCRIPT,
        config={"script_content": "echo fallback", "target_host_ids": [host.id]},
    )
    FlowEdge.objects.create(
        template=template,
        source=condition,
        target=prod,
        condition={"variable": "env", "operator": "eq", "value": "prod"},
    )
    FlowEdge.objects.create(
        template=template,
        source=condition,
        target=fallback,
        condition={"default": True},
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
        flow_run = FlowRunner.start(template=template, user=user, inputs={"env": "stage"}, agent_server_id=3)

    flow_run.refresh_from_db()
    condition_run = flow_run.node_runs.get(node=condition)
    assert flow_run.status == FlowRun.Status.SUCCESS
    assert condition_run.outputs["selected_node_uuids"] == ["fallback-script"]
    assert not flow_run.node_runs.filter(node=prod).exists()
    assert flow_run.node_runs.get(node=fallback).status == FlowRun.Status.SUCCESS
    execute_script.assert_called_once()
    assert execute_script.call_args.kwargs["script_content"] == "echo fallback"


def test_flow_runner_parallel_gateway_starts_all_ready_async_branches_before_pausing():
    user = _create_user()
    host = _create_host(user)
    first_plan = _create_execution_plan(user, host)
    second_plan = _create_execution_plan(user, host)
    template = FlowTemplate.objects.create(
        name=f"flow-{uuid.uuid4().hex[:8]}",
        created_by=user,
    )
    gateway = FlowNode.objects.create(
        template=template,
        uuid="parallel-1",
        name="并行网关",
        node_type=FlowNode.NodeType.PARALLEL,
        config={},
    )
    first = FlowNode.objects.create(
        template=template,
        uuid="job-plan-1",
        name="first plan",
        node_type=FlowNode.NodeType.JOB_PLAN,
        config={"execution_plan_id": first_plan.id},
    )
    second = FlowNode.objects.create(
        template=template,
        uuid="job-plan-2",
        name="second plan",
        node_type=FlowNode.NodeType.JOB_PLAN,
        config={"execution_plan_id": second_plan.id},
    )
    FlowEdge.objects.create(template=template, source=gateway, target=first)
    FlowEdge.objects.create(template=template, source=gateway, target=second)

    def execute_plan(**kwargs):
        execution_record = ExecutionRecordService.create_execution_record(
            execution_type="flow_node",
            name="flow job plan",
            executed_by=user,
            related_object=kwargs["related_object"],
        )
        execution_record.status = "running"
        execution_record.save(update_fields=["status"])
        return {"success": True, "execution_record_id": execution_record.id}

    with patch("apps.job_templates.services.ExecutionPlanService.execute_plan", side_effect=execute_plan) as execute_plan_mock:
        flow_run = FlowRunner.start(template=template, user=user, inputs={}, agent_server_id=3)

    flow_run.refresh_from_db()
    assert flow_run.status == FlowRun.Status.PAUSED
    assert flow_run.node_runs.get(node=gateway).status == FlowRun.Status.SUCCESS
    assert flow_run.node_runs.get(node=first).status == FlowRun.Status.PAUSED
    assert flow_run.node_runs.get(node=second).status == FlowRun.Status.PAUSED
    assert execute_plan_mock.call_count == 2


def test_flow_runner_join_waits_for_all_active_parallel_branches_before_downstream_runs():
    user = _create_user()
    host = _create_host(user)
    first_plan = _create_execution_plan(user, host)
    second_plan = _create_execution_plan(user, host)
    template = FlowTemplate.objects.create(
        name=f"flow-{uuid.uuid4().hex[:8]}",
        created_by=user,
    )
    gateway = FlowNode.objects.create(
        template=template,
        uuid="parallel-1",
        name="并行网关",
        node_type=FlowNode.NodeType.PARALLEL,
        config={},
    )
    first = FlowNode.objects.create(
        template=template,
        uuid="job-plan-1",
        name="first plan",
        node_type=FlowNode.NodeType.JOB_PLAN,
        config={"execution_plan_id": first_plan.id},
    )
    second = FlowNode.objects.create(
        template=template,
        uuid="job-plan-2",
        name="second plan",
        node_type=FlowNode.NodeType.JOB_PLAN,
        config={"execution_plan_id": second_plan.id},
    )
    join = FlowNode.objects.create(
        template=template,
        uuid="join-1",
        name="汇聚网关",
        node_type=FlowNode.NodeType.JOIN,
        config={},
    )
    downstream = FlowNode.objects.create(
        template=template,
        uuid="script-after-join",
        name="join downstream",
        node_type=FlowNode.NodeType.SCRIPT,
        config={"script_content": "echo joined", "target_host_ids": [host.id]},
    )
    FlowEdge.objects.create(template=template, source=gateway, target=first)
    FlowEdge.objects.create(template=template, source=gateway, target=second)
    FlowEdge.objects.create(template=template, source=first, target=join)
    FlowEdge.objects.create(template=template, source=second, target=join)
    FlowEdge.objects.create(template=template, source=join, target=downstream)
    execution_records = []

    def execute_plan(**kwargs):
        execution_record = ExecutionRecordService.create_execution_record(
            execution_type="flow_node",
            name="flow job plan",
            executed_by=user,
            related_object=kwargs["related_object"],
        )
        execution_record.status = "running"
        execution_record.save(update_fields=["status"])
        execution_records.append(execution_record)
        return {"success": True, "execution_record_id": execution_record.id}

    with patch("apps.job_templates.services.ExecutionPlanService.execute_plan", side_effect=execute_plan):
        flow_run = FlowRunner.start(template=template, user=user, inputs={}, agent_server_id=3)

    assert flow_run.status == FlowRun.Status.PAUSED
    assert len(execution_records) == 2
    assert not flow_run.node_runs.filter(node=join).exists()
    assert not flow_run.node_runs.filter(node=downstream).exists()

    execution_records[0].status = "success"
    execution_records[0].save(update_fields=["status"])
    flow_run = FlowRunner.handle_execution_record_finished(execution_records[0])
    flow_run.refresh_from_db()
    assert flow_run.status == FlowRun.Status.PAUSED
    assert not flow_run.node_runs.filter(node=join).exists()
    assert not flow_run.node_runs.filter(node=downstream).exists()

    execution_records[1].status = "success"
    execution_records[1].save(update_fields=["status"])
    with patch(
        "apps.agents.execution_service.AgentExecutionService.execute_script_via_agent",
        return_value={
            "success": True,
            "success_count": 1,
            "failed_count": 0,
            "results": [{"host_id": host.id, "host_name": host.name, "success": True}],
        },
    ) as execute_script:
        flow_run = FlowRunner.handle_execution_record_finished(execution_records[1])

    flow_run.refresh_from_db()
    assert flow_run.status == FlowRun.Status.SUCCESS
    assert flow_run.node_runs.get(node=join).status == FlowRun.Status.SUCCESS
    assert flow_run.node_runs.get(node=downstream).status == FlowRun.Status.SUCCESS
    execute_script.assert_called_once()


def test_flow_runner_join_ignores_unselected_condition_branch():
    user = _create_user()
    host = _create_host(user)
    template = FlowTemplate.objects.create(
        name=f"flow-{uuid.uuid4().hex[:8]}",
        created_by=user,
    )
    condition = FlowNode.objects.create(
        template=template,
        uuid="condition-1",
        name="环境判断",
        node_type=FlowNode.NodeType.CONDITION,
        config={},
    )
    prod = FlowNode.objects.create(
        template=template,
        uuid="prod-script",
        name="prod script",
        node_type=FlowNode.NodeType.SCRIPT,
        config={"script_content": "echo prod", "target_host_ids": [host.id]},
    )
    fallback = FlowNode.objects.create(
        template=template,
        uuid="fallback-script",
        name="fallback script",
        node_type=FlowNode.NodeType.SCRIPT,
        config={"script_content": "echo fallback", "target_host_ids": [host.id]},
    )
    join = FlowNode.objects.create(
        template=template,
        uuid="join-1",
        name="汇聚网关",
        node_type=FlowNode.NodeType.JOIN,
        config={},
    )
    downstream = FlowNode.objects.create(
        template=template,
        uuid="after-join",
        name="join downstream",
        node_type=FlowNode.NodeType.SCRIPT,
        config={"script_content": "echo after", "target_host_ids": [host.id]},
    )
    FlowEdge.objects.create(template=template, source=condition, target=prod, condition={"variable": "env", "operator": "eq", "value": "prod"})
    FlowEdge.objects.create(template=template, source=condition, target=fallback, condition={"default": True})
    FlowEdge.objects.create(template=template, source=prod, target=join)
    FlowEdge.objects.create(template=template, source=fallback, target=join)
    FlowEdge.objects.create(template=template, source=join, target=downstream)

    with patch(
        "apps.agents.execution_service.AgentExecutionService.execute_script_via_agent",
        return_value={
            "success": True,
            "success_count": 1,
            "failed_count": 0,
            "results": [{"host_id": host.id, "host_name": host.name, "success": True}],
        },
    ) as execute_script:
        flow_run = FlowRunner.start(template=template, user=user, inputs={"env": "prod"}, agent_server_id=3)

    flow_run.refresh_from_db()
    assert flow_run.status == FlowRun.Status.SUCCESS
    assert flow_run.node_runs.get(node=prod).status == FlowRun.Status.SUCCESS
    assert not flow_run.node_runs.filter(node=fallback).exists()
    assert flow_run.node_runs.get(node=join).status == FlowRun.Status.SUCCESS
    assert flow_run.node_runs.get(node=downstream).status == FlowRun.Status.SUCCESS
    assert execute_script.call_count == 2


def test_flow_runner_join_waits_for_selected_async_condition_branch():
    user = _create_user()
    host = _create_host(user)
    plan = _create_execution_plan(user, host)
    template = FlowTemplate.objects.create(
        name=f"flow-{uuid.uuid4().hex[:8]}",
        created_by=user,
    )
    condition = FlowNode.objects.create(
        template=template,
        uuid="condition-1",
        name="环境判断",
        node_type=FlowNode.NodeType.CONDITION,
        config={},
    )
    prod = FlowNode.objects.create(
        template=template,
        uuid="prod-plan",
        name="prod plan",
        node_type=FlowNode.NodeType.JOB_PLAN,
        config={"execution_plan_id": plan.id},
    )
    fallback = FlowNode.objects.create(
        template=template,
        uuid="fallback-script",
        name="fallback script",
        node_type=FlowNode.NodeType.SCRIPT,
        config={"script_content": "echo fallback", "target_host_ids": [host.id]},
    )
    join = FlowNode.objects.create(
        template=template,
        uuid="join-1",
        name="汇聚网关",
        node_type=FlowNode.NodeType.JOIN,
        config={},
    )
    downstream = FlowNode.objects.create(
        template=template,
        uuid="after-join",
        name="join downstream",
        node_type=FlowNode.NodeType.SCRIPT,
        config={"script_content": "echo after", "target_host_ids": [host.id]},
    )
    FlowEdge.objects.create(template=template, source=condition, target=prod, condition={"variable": "env", "operator": "eq", "value": "prod"})
    FlowEdge.objects.create(template=template, source=condition, target=fallback, condition={"default": True})
    FlowEdge.objects.create(template=template, source=prod, target=join)
    FlowEdge.objects.create(template=template, source=fallback, target=join)
    FlowEdge.objects.create(template=template, source=join, target=downstream)
    execution_records = []

    def execute_plan(**kwargs):
        execution_record = ExecutionRecordService.create_execution_record(
            execution_type="flow_node",
            name="flow job plan",
            executed_by=user,
            related_object=kwargs["related_object"],
        )
        execution_record.status = "running"
        execution_record.save(update_fields=["status"])
        execution_records.append(execution_record)
        return {"success": True, "execution_record_id": execution_record.id}

    with patch("apps.job_templates.services.ExecutionPlanService.execute_plan", side_effect=execute_plan):
        flow_run = FlowRunner.start(template=template, user=user, inputs={"env": "prod"}, agent_server_id=3)

    flow_run.refresh_from_db()
    assert flow_run.status == FlowRun.Status.PAUSED
    assert flow_run.node_runs.get(node=prod).status == FlowRun.Status.PAUSED
    assert not flow_run.node_runs.filter(node=fallback).exists()
    assert not flow_run.node_runs.filter(node=join).exists()
    assert not flow_run.node_runs.filter(node=downstream).exists()

    execution_records[0].status = "success"
    execution_records[0].save(update_fields=["status"])
    with patch(
        "apps.agents.execution_service.AgentExecutionService.execute_script_via_agent",
        return_value={
            "success": True,
            "success_count": 1,
            "failed_count": 0,
            "results": [{"host_id": host.id, "host_name": host.name, "success": True}],
        },
    ):
        flow_run = FlowRunner.handle_execution_record_finished(execution_records[0])

    flow_run.refresh_from_db()
    assert flow_run.status == FlowRun.Status.SUCCESS
    assert flow_run.node_runs.get(node=join).status == FlowRun.Status.SUCCESS
    assert flow_run.node_runs.get(node=downstream).status == FlowRun.Status.SUCCESS


def test_flow_runner_async_failed_branch_with_ignore_policy_can_pass_join():
    user = _create_user()
    host = _create_host(user)
    first_plan = _create_execution_plan(user, host)
    second_plan = _create_execution_plan(user, host)
    template = FlowTemplate.objects.create(
        name=f"flow-{uuid.uuid4().hex[:8]}",
        created_by=user,
    )
    gateway = FlowNode.objects.create(
        template=template,
        uuid="parallel-1",
        name="并行网关",
        node_type=FlowNode.NodeType.PARALLEL,
        config={},
    )
    ignored_failure = FlowNode.objects.create(
        template=template,
        uuid="ignored-failure",
        name="ignored failure",
        node_type=FlowNode.NodeType.JOB_PLAN,
        config={"execution_plan_id": first_plan.id, "failure_policy": "ignore"},
    )
    successful = FlowNode.objects.create(
        template=template,
        uuid="successful-branch",
        name="successful branch",
        node_type=FlowNode.NodeType.JOB_PLAN,
        config={"execution_plan_id": second_plan.id},
    )
    join = FlowNode.objects.create(
        template=template,
        uuid="join-1",
        name="汇聚网关",
        node_type=FlowNode.NodeType.JOIN,
        config={},
    )
    downstream = FlowNode.objects.create(
        template=template,
        uuid="after-join",
        name="join downstream",
        node_type=FlowNode.NodeType.SCRIPT,
        config={"script_content": "echo after", "target_host_ids": [host.id]},
    )
    FlowEdge.objects.create(template=template, source=gateway, target=ignored_failure)
    FlowEdge.objects.create(template=template, source=gateway, target=successful)
    FlowEdge.objects.create(template=template, source=ignored_failure, target=join)
    FlowEdge.objects.create(template=template, source=successful, target=join)
    FlowEdge.objects.create(template=template, source=join, target=downstream)
    execution_records = []

    def execute_plan(**kwargs):
        execution_record = ExecutionRecordService.create_execution_record(
            execution_type="flow_node",
            name="flow job plan",
            executed_by=user,
            related_object=kwargs["related_object"],
        )
        execution_record.status = "running"
        execution_record.save(update_fields=["status"])
        execution_records.append(execution_record)
        return {"success": True, "execution_record_id": execution_record.id}

    with patch("apps.job_templates.services.ExecutionPlanService.execute_plan", side_effect=execute_plan):
        flow_run = FlowRunner.start(template=template, user=user, inputs={}, agent_server_id=3)

    execution_records[0].status = "failed"
    execution_records[0].error_message = "ignored branch failed"
    execution_records[0].save(update_fields=["status", "error_message"])
    flow_run = FlowRunner.handle_execution_record_finished(execution_records[0])
    flow_run.refresh_from_db()
    assert flow_run.status == FlowRun.Status.PAUSED
    assert flow_run.node_runs.get(node=ignored_failure).status == FlowRun.Status.FAILED
    assert not flow_run.node_runs.filter(node=join).exists()

    execution_records[1].status = "success"
    execution_records[1].save(update_fields=["status"])
    with patch(
        "apps.agents.execution_service.AgentExecutionService.execute_script_via_agent",
        return_value={
            "success": True,
            "success_count": 1,
            "failed_count": 0,
            "results": [{"host_id": host.id, "host_name": host.name, "success": True}],
        },
    ):
        flow_run = FlowRunner.handle_execution_record_finished(execution_records[1])

    flow_run.refresh_from_db()
    assert flow_run.status == FlowRun.Status.SUCCESS
    assert flow_run.node_runs.get(node=join).status == FlowRun.Status.SUCCESS
    assert flow_run.node_runs.get(node=downstream).status == FlowRun.Status.SUCCESS


def test_flow_runner_parallel_stop_failure_does_not_pass_join():
    user = _create_user()
    host = _create_host(user)
    first_plan = _create_execution_plan(user, host)
    second_plan = _create_execution_plan(user, host)
    template = FlowTemplate.objects.create(
        name=f"flow-{uuid.uuid4().hex[:8]}",
        created_by=user,
    )
    gateway = FlowNode.objects.create(
        template=template,
        uuid="parallel-1",
        name="并行网关",
        node_type=FlowNode.NodeType.PARALLEL,
        config={},
    )
    failed_branch = FlowNode.objects.create(
        template=template,
        uuid="failed-branch",
        name="failed branch",
        node_type=FlowNode.NodeType.JOB_PLAN,
        config={"execution_plan_id": first_plan.id},
    )
    running_branch = FlowNode.objects.create(
        template=template,
        uuid="running-branch",
        name="running branch",
        node_type=FlowNode.NodeType.JOB_PLAN,
        config={"execution_plan_id": second_plan.id},
    )
    join = FlowNode.objects.create(
        template=template,
        uuid="join-1",
        name="汇聚网关",
        node_type=FlowNode.NodeType.JOIN,
        config={},
    )
    downstream = FlowNode.objects.create(
        template=template,
        uuid="after-join",
        name="join downstream",
        node_type=FlowNode.NodeType.SCRIPT,
        config={"script_content": "echo after", "target_host_ids": [host.id]},
    )
    FlowEdge.objects.create(template=template, source=gateway, target=failed_branch)
    FlowEdge.objects.create(template=template, source=gateway, target=running_branch)
    FlowEdge.objects.create(template=template, source=failed_branch, target=join)
    FlowEdge.objects.create(template=template, source=running_branch, target=join)
    FlowEdge.objects.create(template=template, source=join, target=downstream)
    execution_records = []

    def execute_plan(**kwargs):
        execution_record = ExecutionRecordService.create_execution_record(
            execution_type="flow_node",
            name="flow job plan",
            executed_by=user,
            related_object=kwargs["related_object"],
        )
        execution_record.status = "running"
        execution_record.save(update_fields=["status"])
        execution_records.append(execution_record)
        return {"success": True, "execution_record_id": execution_record.id}

    with patch("apps.job_templates.services.ExecutionPlanService.execute_plan", side_effect=execute_plan):
        flow_run = FlowRunner.start(template=template, user=user, inputs={}, agent_server_id=3)

    execution_records[0].status = "failed"
    execution_records[0].error_message = "branch failed"
    execution_records[0].save(update_fields=["status", "error_message"])
    flow_run = FlowRunner.handle_execution_record_finished(execution_records[0])

    flow_run.refresh_from_db()
    assert flow_run.status == FlowRun.Status.FAILED
    assert flow_run.node_runs.get(node=failed_branch).status == FlowRun.Status.FAILED
    assert flow_run.node_runs.get(node=running_branch).status == FlowRun.Status.PAUSED
    assert not flow_run.node_runs.filter(node=join).exists()
    assert not flow_run.node_runs.filter(node=downstream).exists()


def test_flow_runner_retries_failed_node_and_continues_downstream_nodes():
    user = _create_user()
    host = _create_host(user)
    template = FlowTemplate.objects.create(
        name=f"flow-{uuid.uuid4().hex[:8]}",
        created_by=user,
    )
    first = FlowNode.objects.create(
        template=template,
        uuid="script-1",
        name="first script",
        node_type=FlowNode.NodeType.SCRIPT,
        config={"script_content": "echo first", "target_host_ids": [host.id]},
    )
    second = FlowNode.objects.create(
        template=template,
        uuid="script-2",
        name="second script",
        node_type=FlowNode.NodeType.SCRIPT,
        config={"script_content": "echo second", "target_host_ids": [host.id]},
    )
    FlowEdge.objects.create(template=template, source=first, target=second)

    with patch(
        "apps.agents.execution_service.AgentExecutionService.execute_script_via_agent",
        return_value={
            "success": False,
            "success_count": 0,
            "failed_count": 1,
            "error": "script failed",
            "results": [{"host_id": host.id, "host_name": host.name, "success": False}],
        },
    ):
        flow_run = FlowRunner.start(template=template, user=user, inputs={}, agent_server_id=3)

    first_run = flow_run.node_runs.get(node=first)
    assert flow_run.status == FlowRun.Status.FAILED
    assert first_run.status == FlowRun.Status.FAILED

    with patch(
        "apps.agents.execution_service.AgentExecutionService.execute_script_via_agent",
        side_effect=[
            {
                "success": True,
                "success_count": 1,
                "failed_count": 0,
                "results": [{"host_id": host.id, "host_name": host.name, "success": True}],
            },
            {
                "success": True,
                "success_count": 1,
                "failed_count": 0,
                "results": [{"host_id": host.id, "host_name": host.name, "success": True}],
            },
        ],
    ) as execute_script:
        flow_run = FlowRunner.retry_node(
            flow_run=flow_run,
            node_run=first_run,
            user=user,
            agent_server_id=3,
        )

    flow_run.refresh_from_db()
    first_run.refresh_from_db()
    assert flow_run.status == FlowRun.Status.SUCCESS
    assert first_run.status == FlowRun.Status.SUCCESS
    assert first_run.outputs["success_count"] == 1
    assert flow_run.node_runs.get(node=second).status == FlowRun.Status.SUCCESS
    assert execute_script.call_count == 2


def test_flow_runner_cancels_paused_flow_and_running_node_record():
    user = _create_user()
    template = FlowTemplate.objects.create(
        name=f"flow-{uuid.uuid4().hex[:8]}",
        created_by=user,
    )
    node = FlowNode.objects.create(
        template=template,
        uuid="job-plan-1",
        name="run plan",
        node_type=FlowNode.NodeType.JOB_PLAN,
        config={"execution_plan_id": 1},
    )
    flow_run = FlowRun.objects.create(
        template=template,
        status=FlowRun.Status.PAUSED,
        started_by=user,
        started_at=timezone.now(),
    )
    node_run = FlowNodeRun.objects.create(
        flow_run=flow_run,
        node=node,
        status=FlowRun.Status.PAUSED,
        started_at=timezone.now(),
    )
    execution_record = ExecutionRecordService.create_execution_record(
        execution_type="flow_node",
        name="running flow node",
        executed_by=user,
        related_object=node_run,
        execution_parameters={"agent_server_id": 3},
    )
    execution_record.status = "running"
    execution_record.save(update_fields=["status"])
    node_run.execution_record = execution_record
    node_run.save(update_fields=["execution_record"])

    with patch(
        "apps.agents.execution_service.AgentExecutionService.cancel_task_via_agent",
        return_value={"success": True, "cancelled_count": 1, "failed_count": 0, "total_count": 1},
    ) as cancel_task:
        flow_run = FlowRunner.cancel_flow(flow_run=flow_run, user=user)

    flow_run.refresh_from_db()
    node_run.refresh_from_db()
    execution_record.refresh_from_db()
    assert flow_run.status == FlowRun.Status.CANCELLED
    assert node_run.status == FlowRun.Status.CANCELLED
    assert execution_record.status == "cancelled"
    cancel_task.assert_called_once()


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
