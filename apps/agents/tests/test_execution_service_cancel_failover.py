import uuid
from unittest.mock import patch

import pytest
from django.contrib.auth.models import User

from apps.agents.execution_service import AgentExecutionService
from apps.agents.models import Agent, AgentServer
from apps.hosts.models import Host


pytestmark = pytest.mark.django_db


class _FakeResponse:
    def __init__(self, status_code: int, text: str = ""):
        self.status_code = status_code
        self.text = text


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


def _build_task_map(agent: Agent, task_id: str = "task-1"):
    return {
        agent.host_id: {
            "agent": agent,
            "tasks": [{"task_id": task_id, "host_id": agent.host_id}],
        }
    }


def test_cancel_tasks_failover_to_secondary_server():
    agent = _create_agent()
    primary = _create_server("cancel-primary")
    secondary = _create_server("cancel-secondary")

    with patch(
        "utils.agent_server_client.AgentServerClient.post",
        side_effect=[_FakeResponse(502, "bad gateway"), _FakeResponse(200, "ok")],
    ) as mock_post:
        result = AgentExecutionService._cancel_tasks_via_agent_server(
            agent_task_map=_build_task_map(agent),
            agent_server_id=primary.id,
        )

    assert result["success"] is True
    assert result["cancelled_count"] == 1
    assert result["failed_count"] == 0
    assert mock_post.call_count == 2
    assert mock_post.call_args_list[0].args[0].startswith(primary.base_url)
    assert mock_post.call_args_list[1].args[0].startswith(secondary.base_url)


def test_cancel_tasks_uses_bound_server_when_selected_without_secret():
    agent = _create_agent()
    selected_without_secret = _create_server("cancel-no-secret", shared_secret="")
    bound = _create_server("cancel-bound")

    agent.agent_server = bound
    agent.save(update_fields=["agent_server"])

    with patch("utils.agent_server_client.AgentServerClient.post", return_value=_FakeResponse(200, "ok")) as mock_post:
        result = AgentExecutionService._cancel_tasks_via_agent_server(
            agent_task_map=_build_task_map(agent),
            agent_server_id=selected_without_secret.id,
        )

    assert result["success"] is True
    assert result["cancelled_count"] == 1
    assert mock_post.call_count == 1
    assert mock_post.call_args_list[0].args[0].startswith(bound.base_url)


def test_cancel_tasks_all_candidates_fail():
    agent = _create_agent()
    primary = _create_server("cancel-fail-primary")
    secondary = _create_server("cancel-fail-secondary")

    with patch(
        "utils.agent_server_client.AgentServerClient.post",
        side_effect=[_FakeResponse(503, "service unavailable"), RuntimeError("connection reset")],
    ) as mock_post:
        result = AgentExecutionService._cancel_tasks_via_agent_server(
            agent_task_map=_build_task_map(agent),
            agent_server_id=primary.id,
        )

    assert result["success"] is False
    assert result["cancelled_count"] == 0
    assert result["failed_count"] == 1
    assert result["errors"]
    assert primary.base_url in result["errors"][0]
    assert secondary.base_url in result["errors"][0]
    assert mock_post.call_count == 2


def test_cancel_tasks_returns_error_when_no_active_server():
    agent = _create_agent()
    _create_server("cancel-inactive-only", is_active=False)

    result = AgentExecutionService._cancel_tasks_via_agent_server(
        agent_task_map=_build_task_map(agent),
        agent_server_id=None,
    )

    assert result["success"] is False
    assert result["error"] == "Agent-Server 未注册或已禁用"
