import uuid

import pytest
from django.contrib.auth.models import User

from apps.agents.management.commands.consume_streams import Command
from apps.agents.models import Agent, AgentTaskStats
from apps.agents.tools.render_config import render_config_yaml
from apps.hosts.models import Host


pytestmark = pytest.mark.django_db


def _create_agent(status="pending"):
    user = User.objects.create_user(f"user-{uuid.uuid4().hex[:8]}", password="pass")
    host = Host.objects.create(
        name=f"host-{uuid.uuid4().hex[:8]}",
        os_type="linux",
        device_type="physical",
        created_by=user,
    )
    return Agent.objects.create(host=host, agent_type="agent", status=status)


def test_agent_gets_immutable_uuid_identity():
    agent = _create_agent()
    original_uid = agent.agent_uid

    assert isinstance(original_uid, uuid.UUID)
    assert original_uid.version == 4

    agent.agent_uid = uuid.uuid4()
    with pytest.raises(ValueError, match="agent_uid is immutable"):
        agent.save()


def test_agent_config_renders_stable_agent_uid():
    agent_uid = uuid.uuid4()

    rendered = render_config_yaml(
        install_type="agent",
        agent_token="token",
        agent_uid=str(agent_uid),
        host_id=42,
        agent_name="host-a",
        agent_server_url="ws://agent-server:8080",
    )

    assert f"agent_uid: {agent_uid}" in rendered
    assert "host_id: 42" in rendered


def test_status_stream_requires_agent_uid_and_updates_matching_agent():
    agent = _create_agent(status="pending")

    assert Command.handle_agent_status("1-0", {"agent_id": str(agent.id), "status": "online"}) is False
    agent.refresh_from_db()
    assert agent.status == "pending"

    assert Command.handle_agent_status(
        "2-0",
        {"agent_uid": str(agent.agent_uid), "status": "online", "timestamp": 1_700_000_000},
    ) is True
    agent.refresh_from_db()
    assert agent.status == "online"


def test_task_stats_stream_requires_agent_uid_and_updates_matching_agent():
    agent = _create_agent()

    assert Command.handle_agent_task_stats("1-0", {"agent_id": str(agent.id), "total": 8}) is False
    assert not AgentTaskStats.objects.filter(agent=agent).exists()

    assert Command.handle_agent_task_stats(
        "2-0",
        {
            "agent_uid": str(agent.agent_uid),
            "total": 8,
            "success": 6,
            "failed": 1,
            "cancelled": 1,
            "avg_duration_ms": 25,
        },
    ) is True
    stats = AgentTaskStats.objects.get(agent=agent)
    assert stats.total_tasks == 8
