import uuid
from unittest.mock import patch

import pytest
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError

from apps.flows.models import FlowEdge, FlowNode, FlowRun, FlowTemplate
from apps.flows.services import FlowRunner
from apps.hosts.models import Host


pytestmark = pytest.mark.django_db


def test_flow_runner_executes_script_node_with_agent_service():
    user = User.objects.create_user(f"user-{uuid.uuid4().hex[:6]}", password="pass")
    host = Host.objects.create(
        name=f"host-{uuid.uuid4().hex[:6]}",
        os_type="linux",
        device_type="physical",
        created_by=user,
    )
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
    user = User.objects.create_user(f"user-{uuid.uuid4().hex[:6]}", password="pass")
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
    user = User.objects.create_user(f"user-{uuid.uuid4().hex[:6]}", password="pass")
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
    user = User.objects.create_user(f"user-{uuid.uuid4().hex[:6]}", password="pass")
    host = Host.objects.create(
        name=f"host-{uuid.uuid4().hex[:6]}",
        os_type="linux",
        device_type="physical",
        created_by=user,
    )
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
    user = User.objects.create_user(f"user-{uuid.uuid4().hex[:6]}", password="pass")
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
