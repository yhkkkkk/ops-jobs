import uuid
from unittest.mock import patch

import pytest
from django.contrib.auth.models import User
from django.contrib.contenttypes.models import ContentType
from rest_framework.test import APIClient

from apps.flows.models import FlowEdge, FlowNode, FlowRun, FlowTemplate
from apps.hosts.models import Host
from apps.job_templates.models import ExecutionPlan, JobStep, JobTemplate, PlanStep
from apps.permissions.models import AuditLog


pytestmark = pytest.mark.django_db


def _client_for(user):
    client = APIClient()
    client.force_authenticate(user=user)
    return client


def _create_execution_plan(user, host):
    template = JobTemplate.objects.create(name=f"tpl-{uuid.uuid4().hex[:8]}", created_by=user)
    step = JobStep.objects.create(
        template=template,
        name="step",
        step_type="script",
        order=1,
        script_content="echo plan",
    )
    step.target_hosts.add(host)
    plan = ExecutionPlan.objects.create(template=template, name=f"plan-{uuid.uuid4().hex[:8]}", created_by=user)
    plan_step = PlanStep.objects.create(plan=plan, step=step, order=1)
    plan_step.copy_from_template_step()
    plan_step.save()
    return plan


def _flow_run_audit_logs(flow_run):
    return AuditLog.objects.filter(
        resource_type=ContentType.objects.get_for_model(FlowRun),
        resource_id=flow_run.id,
    )


def test_flow_api_creates_template_node_edge_and_starts_run():
    user = User.objects.create_user(f"user-{uuid.uuid4().hex[:6]}", password="pass")
    host = Host.objects.create(
        name=f"host-{uuid.uuid4().hex[:6]}",
        os_type="linux",
        device_type="physical",
        created_by=user,
    )
    client = _client_for(user)

    template_resp = client.post(
        "/api/flows/templates/",
        {
            "name": f"flow-{uuid.uuid4().hex[:8]}",
            "description": "api flow",
            "variables": {"env": {"default": "dev"}},
        },
        format="json",
    )
    assert template_resp.status_code == 200
    template_id = template_resp.data["content"]["id"]

    first_node_resp = client.post(
        "/api/flows/nodes/",
        {
            "template": template_id,
            "uuid": "script-1",
            "name": "first",
            "node_type": FlowNode.NodeType.SCRIPT,
            "config": {
                "script_content": "echo first",
                "target_host_ids": [host.id],
            },
        },
        format="json",
    )
    assert first_node_resp.status_code == 200
    first_node_id = first_node_resp.data["content"]["id"]

    second_node_resp = client.post(
        "/api/flows/nodes/",
        {
            "template": template_id,
            "uuid": "script-2",
            "name": "second",
            "node_type": FlowNode.NodeType.SCRIPT,
            "config": {
                "script_content": "echo second",
                "target_host_ids": [host.id],
            },
        },
        format="json",
    )
    assert second_node_resp.status_code == 200
    second_node_id = second_node_resp.data["content"]["id"]

    edge_resp = client.post(
        "/api/flows/edges/",
        {
            "template": template_id,
            "source": first_node_id,
            "target": second_node_id,
            "condition": {},
        },
        format="json",
    )
    assert edge_resp.status_code == 200

    with patch(
        "apps.agents.execution_service.AgentExecutionService.execute_script_via_agent",
        return_value={
            "success": True,
            "success_count": 1,
            "failed_count": 0,
            "results": [{"host_id": host.id, "host_name": host.name, "success": True}],
        },
    ):
        start_resp = client.post(
            f"/api/flows/templates/{template_id}/start/",
            {"inputs": {"env": "dev"}, "agent_server_id": 1},
            format="json",
        )

    assert start_resp.status_code == 200
    assert start_resp.data["content"]["status"] == FlowRun.Status.SUCCESS
    flow_run = FlowRun.objects.get(id=start_resp.data["content"]["id"])
    template = FlowTemplate.objects.get(id=template_id)
    assert flow_run.node_runs.count() == 2
    start_log = _flow_run_audit_logs(flow_run).get(action="start_flow")
    assert start_log.resource_name == f"{template.name} #{flow_run.id}"
    assert start_log.extra_data["template_id"] == template_id
    assert start_log.extra_data["agent_server_id"] == 1

    detail_resp = client.get(f"/api/flows/runs/{flow_run.id}/")
    assert detail_resp.status_code == 200
    assert len(detail_resp.data["content"]["node_runs"]) == 2

    logs_resp = client.get(f"/api/flows/runs/{flow_run.id}/operation_logs/")
    assert logs_resp.status_code == 200
    assert [item["action"] for item in logs_resp.data["content"]] == ["start_flow"]


def test_flow_node_plugins_api_returns_backend_supported_plugins():
    user = User.objects.create_user(f"user-{uuid.uuid4().hex[:6]}", password="pass")
    client = _client_for(user)

    resp = client.get("/api/flows/nodes/plugins/")

    assert resp.status_code == 200
    plugin_types = {item["type"] for item in resp.data["content"]}
    assert {
        "script",
        "file_transfer",
        "job_plan",
        "manual",
        "condition",
        "parallel",
        "join",
        "sub_process",
    }.issubset(plugin_types)
    sub_process = next(item for item in resp.data["content"] if item["type"] == "sub_process")
    assert sub_process["config_schema"]["required"] == ["template_id"]


def test_flow_node_api_accepts_owned_subprocess_template():
    user = User.objects.create_user(f"user-{uuid.uuid4().hex[:6]}", password="pass")
    parent = FlowTemplate.objects.create(name=f"parent-{uuid.uuid4().hex[:8]}", created_by=user)
    child = FlowTemplate.objects.create(name=f"child-{uuid.uuid4().hex[:8]}", created_by=user)
    client = _client_for(user)

    resp = client.post(
        "/api/flows/nodes/",
        {
            "template": parent.id,
            "uuid": "sub-1",
            "name": "child flow",
            "node_type": FlowNode.NodeType.SUB_PROCESS,
            "config": {
                "template_id": child.id,
                "inherit_inputs": True,
                "inputs": {"env": "prod"},
            },
        },
        format="json",
    )

    assert resp.status_code == 200
    node = FlowNode.objects.get(id=resp.data["content"]["id"])
    assert node.node_type == FlowNode.NodeType.SUB_PROCESS
    assert node.config["template_id"] == child.id


@pytest.mark.parametrize(
    ("config", "expected_error"),
    [
        ({}, "template_id"),
        ({"template_id": 999999}, "不存在"),
        ({"template_id": "__self__"}, "当前流程"),
        ({"template_id": "__child__", "inputs": ["not", "object"]}, "inputs"),
        ({"template_id": "__child__", "inherit_inputs": "yes"}, "inherit_inputs"),
    ],
)
def test_flow_node_api_rejects_invalid_subprocess_config(config, expected_error):
    user = User.objects.create_user(f"user-{uuid.uuid4().hex[:6]}", password="pass")
    parent = FlowTemplate.objects.create(name=f"parent-{uuid.uuid4().hex[:8]}", created_by=user)
    child = FlowTemplate.objects.create(name=f"child-{uuid.uuid4().hex[:8]}", created_by=user)
    resolved_config = dict(config)
    if resolved_config.get("template_id") == "__self__":
        resolved_config["template_id"] = parent.id
    if resolved_config.get("template_id") == "__child__":
        resolved_config["template_id"] = child.id
    client = _client_for(user)

    resp = client.post(
        "/api/flows/nodes/",
        {
            "template": parent.id,
            "uuid": "sub-1",
            "name": "child flow",
            "node_type": FlowNode.NodeType.SUB_PROCESS,
            "config": resolved_config,
        },
        format="json",
    )

    assert resp.status_code == 400
    assert expected_error in str(resp.data)
    assert FlowNode.objects.filter(template=parent).count() == 0


def test_flow_node_api_rejects_inactive_or_unauthorized_subprocess_template():
    user = User.objects.create_user(f"user-{uuid.uuid4().hex[:6]}", password="pass")
    other = User.objects.create_user(f"user-{uuid.uuid4().hex[:6]}", password="pass")
    parent = FlowTemplate.objects.create(name=f"parent-{uuid.uuid4().hex[:8]}", created_by=user)
    inactive = FlowTemplate.objects.create(name=f"inactive-{uuid.uuid4().hex[:8]}", created_by=user, is_active=False)
    other_child = FlowTemplate.objects.create(name=f"other-{uuid.uuid4().hex[:8]}", created_by=other)
    client = _client_for(user)

    inactive_resp = client.post(
        "/api/flows/nodes/",
        {
            "template": parent.id,
            "uuid": "sub-inactive",
            "name": "inactive child",
            "node_type": FlowNode.NodeType.SUB_PROCESS,
            "config": {"template_id": inactive.id},
        },
        format="json",
    )
    denied_resp = client.post(
        "/api/flows/nodes/",
        {
            "template": parent.id,
            "uuid": "sub-denied",
            "name": "denied child",
            "node_type": FlowNode.NodeType.SUB_PROCESS,
            "config": {"template_id": other_child.id},
        },
        format="json",
    )

    assert inactive_resp.status_code == 400
    assert "未启用" in str(inactive_resp.data)
    assert denied_resp.status_code == 400
    assert "无权引用" in str(denied_resp.data)


def test_flow_run_api_skips_paused_node_and_continues_flow():
    user = User.objects.create_user(f"user-{uuid.uuid4().hex[:6]}", password="pass")
    host = Host.objects.create(
        name=f"host-{uuid.uuid4().hex[:6]}",
        os_type="linux",
        device_type="physical",
        created_by=user,
    )
    template = FlowTemplate.objects.create(name=f"flow-{uuid.uuid4().hex[:8]}", created_by=user)
    first = FlowNode.objects.create(
        template=template,
        uuid="script-1",
        name="first",
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
        name="second",
        node_type=FlowNode.NodeType.SCRIPT,
        config={"script_content": "echo second", "target_host_ids": [host.id]},
    )
    FlowEdge.objects.create(template=template, source=first, target=second)
    client = _client_for(user)

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
        start_resp = client.post(
            f"/api/flows/templates/{template.id}/start/",
            {"inputs": {}, "agent_server_id": 1},
            format="json",
        )

    assert start_resp.status_code == 200
    flow_run = FlowRun.objects.get(id=start_resp.data["content"]["id"])
    first_run = flow_run.node_runs.get(node=first)
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
        skip_resp = client.post(
            f"/api/flows/runs/{flow_run.id}/skip_node/",
            {"node_run_id": first_run.id, "reason": "accepted risk"},
            format="json",
        )

    assert skip_resp.status_code == 200
    assert skip_resp.data["content"]["status"] == FlowRun.Status.SUCCESS
    flow_run.refresh_from_db()
    first_run.refresh_from_db()
    assert first_run.status == FlowRun.Status.SUCCESS
    assert first_run.outputs["skipped"] is True
    assert flow_run.node_runs.get(node=second).status == FlowRun.Status.SUCCESS
    execute_script.assert_called_once()
    assert execute_script.call_args.kwargs["agent_server_id"] == 1
    skip_log = _flow_run_audit_logs(flow_run).get(action="skip_flow_node")
    assert skip_log.extra_data["node_run_id"] == first_run.id
    assert skip_log.extra_data["node_uuid"] == first.uuid
    assert skip_log.extra_data["previous_status"] == FlowRun.Status.PAUSED
    assert skip_log.extra_data["new_status"] == FlowRun.Status.SUCCESS
    assert skip_log.extra_data["reason"] == "accepted risk"


def test_flow_run_api_retries_failed_node_and_continues_flow():
    user = User.objects.create_user(f"user-{uuid.uuid4().hex[:6]}", password="pass")
    host = Host.objects.create(
        name=f"host-{uuid.uuid4().hex[:6]}",
        os_type="linux",
        device_type="physical",
        created_by=user,
    )
    template = FlowTemplate.objects.create(name=f"flow-{uuid.uuid4().hex[:8]}", created_by=user)
    first = FlowNode.objects.create(
        template=template,
        uuid="script-1",
        name="first",
        node_type=FlowNode.NodeType.SCRIPT,
        config={"script_content": "echo first", "target_host_ids": [host.id]},
    )
    second = FlowNode.objects.create(
        template=template,
        uuid="script-2",
        name="second",
        node_type=FlowNode.NodeType.SCRIPT,
        config={"script_content": "echo second", "target_host_ids": [host.id]},
    )
    FlowEdge.objects.create(template=template, source=first, target=second)
    client = _client_for(user)

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
        start_resp = client.post(
            f"/api/flows/templates/{template.id}/start/",
            {"inputs": {}, "agent_server_id": 1},
            format="json",
        )

    flow_run = FlowRun.objects.get(id=start_resp.data["content"]["id"])
    first_run = flow_run.node_runs.get(node=first)
    assert flow_run.status == FlowRun.Status.FAILED

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
        retry_resp = client.post(
            f"/api/flows/runs/{flow_run.id}/retry_node/",
            {"node_run_id": first_run.id},
            format="json",
        )

    assert retry_resp.status_code == 200
    assert retry_resp.data["content"]["status"] == FlowRun.Status.SUCCESS
    flow_run.refresh_from_db()
    assert flow_run.node_runs.get(node=first).status == FlowRun.Status.SUCCESS
    assert flow_run.node_runs.get(node=second).status == FlowRun.Status.SUCCESS
    assert execute_script.call_args_list[0].kwargs["agent_server_id"] == 1
    retry_log = _flow_run_audit_logs(flow_run).get(action="retry_flow_node")
    assert retry_log.extra_data["node_run_id"] == first_run.id
    assert retry_log.extra_data["node_uuid"] == first.uuid
    assert retry_log.extra_data["previous_status"] == FlowRun.Status.FAILED
    assert retry_log.extra_data["new_status"] == FlowRun.Status.SUCCESS


def test_flow_run_api_confirms_manual_node_and_continues_flow():
    user = User.objects.create_user(f"user-{uuid.uuid4().hex[:6]}", password="pass")
    host = Host.objects.create(
        name=f"host-{uuid.uuid4().hex[:6]}",
        os_type="linux",
        device_type="physical",
        created_by=user,
    )
    template = FlowTemplate.objects.create(name=f"flow-{uuid.uuid4().hex[:8]}", created_by=user)
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
        name="second",
        node_type=FlowNode.NodeType.SCRIPT,
        config={"script_content": "echo second", "target_host_ids": [host.id]},
    )
    FlowEdge.objects.create(template=template, source=manual, target=script)
    client = _client_for(user)

    start_resp = client.post(
        f"/api/flows/templates/{template.id}/start/",
        {"inputs": {}, "agent_server_id": 1},
        format="json",
    )

    assert start_resp.status_code == 200
    flow_run = FlowRun.objects.get(id=start_resp.data["content"]["id"])
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
        confirm_resp = client.post(
            f"/api/flows/runs/{flow_run.id}/confirm_manual_node/",
            {"node_run_id": manual_run.id, "remark": "confirmed in window"},
            format="json",
        )

    assert confirm_resp.status_code == 200
    assert confirm_resp.data["content"]["status"] == FlowRun.Status.SUCCESS
    flow_run.refresh_from_db()
    manual_run.refresh_from_db()
    assert manual_run.status == FlowRun.Status.SUCCESS
    assert manual_run.outputs["confirmed"] is True
    assert manual_run.outputs["confirm_remark"] == "confirmed in window"
    assert flow_run.node_runs.get(node=script).status == FlowRun.Status.SUCCESS
    assert execute_script.call_args.kwargs["agent_server_id"] == 1
    confirm_log = _flow_run_audit_logs(flow_run).get(action="confirm_flow_node")
    assert confirm_log.extra_data["node_run_id"] == manual_run.id
    assert confirm_log.extra_data["node_uuid"] == manual.uuid
    assert confirm_log.extra_data["previous_status"] == FlowRun.Status.PAUSED
    assert confirm_log.extra_data["new_status"] == FlowRun.Status.SUCCESS
    assert confirm_log.extra_data["remark"] == "confirmed in window"


def test_flow_run_api_cancels_paused_run():
    user = User.objects.create_user(f"user-{uuid.uuid4().hex[:6]}", password="pass")
    template = FlowTemplate.objects.create(name=f"flow-{uuid.uuid4().hex[:8]}", created_by=user)
    FlowRun.objects.create(
        template=template,
        status=FlowRun.Status.PAUSED,
        started_by=user,
    )
    flow_run = template.runs.get()
    client = _client_for(user)

    resp = client.post(f"/api/flows/runs/{flow_run.id}/cancel/", format="json")

    assert resp.status_code == 200
    assert resp.data["content"]["status"] == FlowRun.Status.CANCELLED
    flow_run.refresh_from_db()
    assert flow_run.status == FlowRun.Status.CANCELLED
    cancel_log = _flow_run_audit_logs(flow_run).get(action="cancel_flow")
    assert cancel_log.extra_data["previous_status"] == FlowRun.Status.PAUSED
    assert cancel_log.extra_data["new_status"] == FlowRun.Status.CANCELLED


def test_flow_api_creates_template_with_full_graph_using_node_uuids():
    user = User.objects.create_user(f"user-{uuid.uuid4().hex[:6]}", password="pass")
    client = _client_for(user)

    resp = client.post(
        "/api/flows/templates/",
        {
            "name": f"flow-{uuid.uuid4().hex[:8]}",
            "nodes": [
                {
                    "uuid": "n1",
                    "name": "first",
                    "node_type": FlowNode.NodeType.SCRIPT,
                    "config": {"script_content": "echo 1"},
                    "position": {"x": 0, "y": 0},
                },
                {
                    "uuid": "n2",
                    "name": "second",
                    "node_type": FlowNode.NodeType.SCRIPT,
                    "config": {"script_content": "echo 2"},
                    "position": {"x": 100, "y": 0},
                },
            ],
            "edges": [
                {
                    "source_uuid": "n1",
                    "target_uuid": "n2",
                    "condition": {},
                }
            ],
        },
        format="json",
    )

    assert resp.status_code == 200
    template = FlowTemplate.objects.get(id=resp.data["content"]["id"])
    assert template.nodes.count() == 2
    edge = template.edges.get()
    assert edge.source.uuid == "n1"
    assert edge.target.uuid == "n2"


def test_flow_api_rejects_full_graph_file_transfer_source_without_remote_path():
    user = User.objects.create_user(f"user-{uuid.uuid4().hex[:6]}", password="pass")
    host = Host.objects.create(
        name=f"host-{uuid.uuid4().hex[:6]}",
        os_type="linux",
        device_type="physical",
        created_by=user,
    )
    client = _client_for(user)

    resp = client.post(
        "/api/flows/templates/",
        {
            "name": f"flow-{uuid.uuid4().hex[:8]}",
            "nodes": [
                {
                    "uuid": "file-1",
                    "name": "file",
                    "node_type": FlowNode.NodeType.FILE_TRANSFER,
                    "config": {
                        "target_host_ids": [host.id],
                        "file_sources": [{"type": "artifact", "download_url": "https://example.test/a.txt"}],
                    },
                }
            ],
        },
        format="json",
    )

    assert resp.status_code == 400
    assert FlowTemplate.objects.count() == 0


def test_flow_api_rejects_edge_with_nodes_from_another_template():
    user = User.objects.create_user(f"user-{uuid.uuid4().hex[:6]}", password="pass")
    first_template = FlowTemplate.objects.create(name=f"flow-{uuid.uuid4().hex[:8]}", created_by=user)
    second_template = FlowTemplate.objects.create(name=f"flow-{uuid.uuid4().hex[:8]}", created_by=user)
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
    client = _client_for(user)

    resp = client.post(
        "/api/flows/edges/",
        {
            "template": first_template.id,
            "source": first_node.id,
            "target": second_node.id,
        },
        format="json",
    )

    assert resp.status_code == 400
    assert FlowEdge.objects.count() == 0


def test_flow_api_scopes_templates_nodes_edges_and_runs_to_owner():
    owner = User.objects.create_user(f"owner-{uuid.uuid4().hex[:6]}", password="pass")
    other = User.objects.create_user(f"other-{uuid.uuid4().hex[:6]}", password="pass")
    template = FlowTemplate.objects.create(name=f"flow-{uuid.uuid4().hex[:8]}", created_by=owner)
    node = FlowNode.objects.create(
        template=template,
        uuid="a",
        name="a",
        node_type=FlowNode.NodeType.SCRIPT,
        config={"script_content": "echo a"},
    )
    run = FlowRun.objects.create(template=template, started_by=owner, status=FlowRun.Status.SUCCESS)
    client = _client_for(other)

    list_resp = client.get("/api/flows/templates/")
    assert list_resp.status_code == 200
    assert list_resp.data["content"] == []

    detail_resp = client.get(f"/api/flows/templates/{template.id}/")
    assert detail_resp.status_code == 404

    create_node_resp = client.post(
        "/api/flows/nodes/",
        {
            "template": template.id,
            "uuid": "b",
            "name": "b",
            "node_type": FlowNode.NodeType.SCRIPT,
            "config": {"script_content": "echo b"},
        },
        format="json",
    )
    assert create_node_resp.status_code == 400
    assert FlowNode.objects.filter(template=template).count() == 1

    node_detail_resp = client.get(f"/api/flows/nodes/{node.id}/")
    assert node_detail_resp.status_code == 404

    run_detail_resp = client.get(f"/api/flows/runs/{run.id}/")
    assert run_detail_resp.status_code == 404

    run_logs_resp = client.get(f"/api/flows/runs/{run.id}/operation_logs/")
    assert run_logs_resp.status_code == 404


def test_flow_api_rejects_node_config_referencing_unauthorized_resources():
    owner = User.objects.create_user(f"owner-{uuid.uuid4().hex[:6]}", password="pass")
    other = User.objects.create_user(f"other-{uuid.uuid4().hex[:6]}", password="pass")
    host = Host.objects.create(
        name=f"host-{uuid.uuid4().hex[:6]}",
        os_type="linux",
        device_type="physical",
        created_by=owner,
    )
    owner_plan = _create_execution_plan(owner, host)
    client_template = FlowTemplate.objects.create(name=f"flow-{uuid.uuid4().hex[:8]}", created_by=other)
    client = _client_for(other)

    host_resp = client.post(
        "/api/flows/nodes/",
        {
            "template": client_template.id,
            "uuid": "script-1",
            "name": "script",
            "node_type": FlowNode.NodeType.SCRIPT,
            "config": {"script_content": "echo no", "target_host_ids": [host.id]},
        },
        format="json",
    )
    assert host_resp.status_code == 400
    assert FlowNode.objects.filter(template=client_template).count() == 0

    plan_resp = client.post(
        "/api/flows/nodes/",
        {
            "template": client_template.id,
            "uuid": "job-plan-1",
            "name": "plan",
            "node_type": FlowNode.NodeType.JOB_PLAN,
            "config": {"execution_plan_id": owner_plan.id},
        },
        format="json",
    )
    assert plan_resp.status_code == 400


def test_flow_api_rejects_job_plan_config_with_unauthorized_internal_host():
    owner = User.objects.create_user(f"owner-{uuid.uuid4().hex[:6]}", password="pass")
    other = User.objects.create_user(f"other-{uuid.uuid4().hex[:6]}", password="pass")
    owner_host = Host.objects.create(
        name=f"host-{uuid.uuid4().hex[:6]}",
        os_type="linux",
        device_type="physical",
        created_by=owner,
    )
    plan = _create_execution_plan(other, owner_host)
    client_template = FlowTemplate.objects.create(name=f"flow-{uuid.uuid4().hex[:8]}", created_by=other)
    client = _client_for(other)

    resp = client.post(
        "/api/flows/nodes/",
        {
            "template": client_template.id,
            "uuid": "job-plan-1",
            "name": "plan",
            "node_type": FlowNode.NodeType.JOB_PLAN,
            "config": {"execution_plan_id": plan.id},
        },
        format="json",
    )

    assert resp.status_code == 400
    assert FlowNode.objects.filter(template=client_template).count() == 0


def test_flow_node_and_edge_api_use_syc_response_for_list_retrieve_and_delete():
    user = User.objects.create_user(f"user-{uuid.uuid4().hex[:6]}", password="pass")
    template = FlowTemplate.objects.create(name=f"flow-{uuid.uuid4().hex[:8]}", created_by=user)
    first_node = FlowNode.objects.create(
        template=template,
        uuid="a",
        name="a",
        node_type=FlowNode.NodeType.SCRIPT,
        config={"script_content": "echo a"},
    )
    second_node = FlowNode.objects.create(
        template=template,
        uuid="b",
        name="b",
        node_type=FlowNode.NodeType.SCRIPT,
        config={"script_content": "echo b"},
    )
    edge = FlowEdge.objects.create(template=template, source=first_node, target=second_node)
    client = _client_for(user)

    node_list = client.get("/api/flows/nodes/")
    assert node_list.status_code == 200
    assert node_list.data["success"] is True
    assert "content" in node_list.data

    node_detail = client.get(f"/api/flows/nodes/{first_node.id}/")
    assert node_detail.status_code == 200
    assert node_detail.data["content"]["id"] == first_node.id

    edge_list = client.get("/api/flows/edges/")
    assert edge_list.status_code == 200
    assert edge_list.data["success"] is True

    edge_delete = client.delete(f"/api/flows/edges/{edge.id}/")
    assert edge_delete.status_code == 200
    assert edge_delete.data["success"] is True
    assert not FlowEdge.objects.filter(id=edge.id).exists()


def test_flow_edge_api_rejects_unknown_source_uuid_with_validation_response():
    user = User.objects.create_user(f"user-{uuid.uuid4().hex[:6]}", password="pass")
    template = FlowTemplate.objects.create(name=f"flow-{uuid.uuid4().hex[:8]}", created_by=user)
    FlowNode.objects.create(
        template=template,
        uuid="b",
        name="b",
        node_type=FlowNode.NodeType.SCRIPT,
        config={"script_content": "echo b"},
    )
    client = _client_for(user)

    resp = client.post(
        "/api/flows/edges/",
        {
            "template": template.id,
            "source_uuid": "missing",
            "target_uuid": "b",
        },
        format="json",
    )

    assert resp.status_code == 400
    assert resp.data["success"] is False
    assert FlowEdge.objects.count() == 0


def test_flow_edge_api_updates_nodes_by_uuid_without_template_payload():
    user = User.objects.create_user(f"user-{uuid.uuid4().hex[:6]}", password="pass")
    template = FlowTemplate.objects.create(name=f"flow-{uuid.uuid4().hex[:8]}", created_by=user)
    first = FlowNode.objects.create(
        template=template,
        uuid="a",
        name="a",
        node_type=FlowNode.NodeType.SCRIPT,
        config={"script_content": "echo a"},
    )
    second = FlowNode.objects.create(
        template=template,
        uuid="b",
        name="b",
        node_type=FlowNode.NodeType.SCRIPT,
        config={"script_content": "echo b"},
    )
    third = FlowNode.objects.create(
        template=template,
        uuid="c",
        name="c",
        node_type=FlowNode.NodeType.SCRIPT,
        config={"script_content": "echo c"},
    )
    edge = FlowEdge.objects.create(template=template, source=first, target=second)
    client = _client_for(user)

    resp = client.patch(
        f"/api/flows/edges/{edge.id}/",
        {"source_uuid": "b", "target_uuid": "c"},
        format="json",
    )

    assert resp.status_code == 200
    edge.refresh_from_db()
    assert edge.source == second
    assert edge.target == third
