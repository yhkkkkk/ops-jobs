import uuid
from unittest.mock import patch

import pytest
from django.contrib.auth.models import User

from apps.agents.execution_service import AgentExecutionService
from apps.agents.models import Agent, AgentServer
from apps.hosts.models import Host


pytestmark = pytest.mark.django_db


class _FakeResponse:
    def __init__(self, status_code: int, payload=None, text: str = ""):
        self.status_code = status_code
        self._payload = payload or {}
        self.text = text

    def json(self):
        return self._payload


def _create_agent() -> Agent:
    user = User.objects.create_user(f"user-{uuid.uuid4().hex[:6]}", password="pass")
    host = Host.objects.create(
        name=f"host-{uuid.uuid4().hex[:6]}",
        os_type="linux",
        device_type="physical",
        created_by=user,
    )
    return Agent.objects.create(host=host, agent_type="agent", status="online")


def _create_server(name: str, shared_secret: str = "secret", is_active: bool = True) -> AgentServer:
    return AgentServer.objects.create(
        name=name,
        base_url=f"http://127.0.0.1/{name}-{uuid.uuid4().hex[:8]}",
        shared_secret=shared_secret,
        require_signature=True,
        is_active=is_active,
    )


def test_push_task_to_agent_failover_to_secondary_server():
    agent = _create_agent()
    primary = _create_server("primary")
    secondary = _create_server("secondary")

    fail_resp = _FakeResponse(status_code=502, text="bad gateway")
    ok_resp = _FakeResponse(status_code=200, payload={"status": "queued"})

    with patch("utils.agent_server_client.AgentServerClient.post", side_effect=[fail_resp, ok_resp]) as mock_post:
        result = AgentExecutionService.push_task_to_agent(
            agent=agent,
            task_spec={"id": "task-failover-1"},
            agent_server_id=primary.id,
        )

    assert result["success"] is True
    assert result["status"] == "queued"
    assert result["agent_server_id"] == secondary.id
    assert mock_post.call_count == 2
    assert mock_post.call_args_list[0].args[0].startswith(primary.base_url)
    assert mock_post.call_args_list[1].args[0].startswith(secondary.base_url)


def test_push_task_to_agent_routes_by_stable_agent_uid():
    agent = _create_agent()
    server = _create_server("stable-identity")

    with patch(
        "utils.agent_server_client.AgentServerClient.post",
        return_value=_FakeResponse(status_code=200, payload={"status": "queued"}),
    ) as mock_post:
        result = AgentExecutionService.push_task_to_agent(
            agent=agent,
            task_spec={"id": "task-stable-identity"},
            agent_server_id=server.id,
        )

    assert result["success"] is True
    assert result["agent_uid"] == str(agent.agent_uid)
    assert mock_post.call_args.args[0] == f"{server.base_url}/api/agents/{agent.agent_uid}/tasks"

def test_push_task_to_agent_uses_other_active_server_when_selected_server_inactive():
    agent = _create_agent()
    primary = _create_server("inactive-primary", is_active=False)
    secondary = _create_server("active-secondary")

    ok_resp = _FakeResponse(status_code=200, payload={"status": "dispatched"})

    with patch("utils.agent_server_client.AgentServerClient.post", return_value=ok_resp) as mock_post:
        result = AgentExecutionService.push_task_to_agent(
            agent=agent,
            task_spec={"id": "task-failover-2"},
            agent_server_id=primary.id,
        )

    assert result["success"] is True
    assert result["agent_server_id"] == secondary.id
    assert mock_post.call_count == 1
    assert mock_post.call_args_list[0].args[0].startswith(secondary.base_url)


def test_push_task_to_agent_skips_server_without_secret_and_uses_bound_server():
    agent = _create_agent()
    no_secret = _create_server("no-secret", shared_secret="")
    bound = _create_server("bound-server")

    agent.agent_server = bound
    agent.save(update_fields=["agent_server"])

    ok_resp = _FakeResponse(status_code=200, payload={"status": "dispatched"})

    with patch("utils.agent_server_client.AgentServerClient.post", return_value=ok_resp) as mock_post:
        result = AgentExecutionService.push_task_to_agent(
            agent=agent,
            task_spec={"id": "task-failover-3"},
            agent_server_id=no_secret.id,
        )

    assert result["success"] is True
    assert result["agent_server_id"] == bound.id
    assert mock_post.call_count == 1
    assert mock_post.call_args_list[0].args[0].startswith(bound.base_url)


def test_push_task_to_agent_all_candidates_fail_returns_aggregated_error():
    agent = _create_agent()
    primary = _create_server("primary-fail")
    secondary = _create_server("secondary-fail")

    fail_resp = _FakeResponse(status_code=503, text="service unavailable")

    with patch(
        "utils.agent_server_client.AgentServerClient.post",
        side_effect=[fail_resp, RuntimeError("connection reset")],
    ) as mock_post:
        result = AgentExecutionService.push_task_to_agent(
            agent=agent,
            task_spec={"id": "task-failover-4"},
            agent_server_id=primary.id,
        )

    assert result["success"] is False
    assert result["error"].startswith("推送任务失败: ")
    assert primary.base_url in result["error"]
    assert secondary.base_url in result["error"]
    assert mock_post.call_count == 2


def test_push_task_to_agent_without_server_selection_returns_original_error():
    agent = _create_agent()

    result = AgentExecutionService.push_task_to_agent(
        agent=agent,
        task_spec={"id": "task-failover-5"},
        agent_server_id=None,
    )

    assert result["success"] is False
    assert result["error"] == "目标主机 Agent 未绑定 Agent-Server"
