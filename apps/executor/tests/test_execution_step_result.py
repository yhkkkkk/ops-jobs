import pytest
from django.contrib.auth.models import User
from rest_framework.test import APIClient

from apps.executor.models import ExecutionRecord, ExecutionStep
from apps.hosts.models import Host
from apps.agents.models import AgentServer


@pytest.fixture()
def disable_debug_toolbar(settings):
    settings.DEBUG = False
    settings.MIDDLEWARE = [
        mw for mw in settings.MIDDLEWARE if "debug_toolbar" not in mw
    ]


@pytest.mark.django_db
def test_step_result_returns_hosts(disable_debug_toolbar):
    user = User.objects.create_superuser(
        username="step-result-admin",
        email="admin2@example.com",
        password="pass",
    )
    client = APIClient()
    assert client.login(username="step-result-admin", password="pass")

    host = Host.objects.create(
        name="host-1",
        os_type="linux",
        device_type="physical",
        created_by=user,
    )

    record = ExecutionRecord.objects.create(
        execution_type="quick_script",
        name="test-step-result-record",
        status="success",
        executed_by=user,
    )
    step = ExecutionStep.objects.create(
        execution_record=record,
        step_name="step-1",
        step_type="script",
        step_order=1,
        status="success",
        host_results=[
            {
                "host_id": host.id,
                "status": "success",
                "exit_code": 0,
                "agent_server_id": 101,
                "agent_server_base_url": "http://127.0.0.1:18080",
            }
        ],
    )

    resp = client.get(
        f"/api/executor/execution-records/{record.id}/steps/{step.id}/result/"
    )
    assert resp.status_code == 200
    data = resp.data["content"]
    assert data["id"] == step.id
    assert "hosts" in data
    assert data["hosts"][0]["id"] == host.id
    assert data["hosts"][0]["agent_server_id"] == 101
    assert data["hosts"][0]["agent_server_base_url"] == "http://127.0.0.1:18080"


@pytest.mark.django_db
def test_step_result_fallbacks_to_execution_params_agent_server(disable_debug_toolbar):
    user = User.objects.create_superuser(
        username="step-result-fallback-admin",
        email="admin3@example.com",
        password="pass",
    )
    client = APIClient()
    assert client.login(username="step-result-fallback-admin", password="pass")

    host = Host.objects.create(
        name="host-2",
        os_type="linux",
        device_type="physical",
        created_by=user,
    )

    server = AgentServer.objects.create(
        name="fallback-server",
        base_url="http://127.0.0.1:28080",
        shared_secret="fallback-secret",
        is_active=True,
    )

    record = ExecutionRecord.objects.create(
        execution_type="quick_script",
        name="test-step-result-fallback-record",
        status="success",
        executed_by=user,
        execution_parameters={
            "execution_mode": "agent",
            "agent_server_id": server.id,
        },
    )
    step = ExecutionStep.objects.create(
        execution_record=record,
        step_name="step-1",
        step_type="script",
        step_order=1,
        status="success",
        host_results=[
            {
                "host_id": host.id,
                "status": "success",
                "exit_code": 0,
            }
        ],
    )

    resp = client.get(
        f"/api/executor/execution-records/{record.id}/steps/{step.id}/result/"
    )
    assert resp.status_code == 200
    data = resp.data["content"]
    assert data["hosts"][0]["id"] == host.id
    assert data["hosts"][0]["agent_server_id"] == server.id
    assert data["hosts"][0]["agent_server_base_url"] == server.base_url
