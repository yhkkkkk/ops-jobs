import pytest
from django.contrib.auth.models import User
from rest_framework.test import APIClient

from apps.executor.models import ExecutionRecord, ExecutionStep
from apps.hosts.models import Host
from utils.realtime_logs import realtime_log_service


@pytest.fixture()
def disable_debug_toolbar(settings):
    settings.DEBUG = False
    settings.MIDDLEWARE = [
        mw for mw in settings.MIDDLEWARE if "debug_toolbar" not in mw
    ]


@pytest.fixture()
def admin_client(disable_debug_toolbar):
    user = User.objects.create_superuser(
        username="log-admin",
        email="admin3@example.com",
        password="pass",
    )
    client = APIClient()
    assert client.login(username="log-admin", password="pass")
    return client, user


@pytest.mark.django_db
def test_host_logs_pointer_returns_next(monkeypatch, admin_client):
    client, user = admin_client

    host = Host.objects.create(
        name="host-log",
        os_type="linux",
        device_type="physical",
        created_by=user,
    )

    record = ExecutionRecord.objects.create(
        execution_type="quick_script",
        name="test-host-log-record",
        status="success",
        executed_by=user,
        execution_results={
            "logs_meta": {"log_pointer": "redis:agent_logs/999@3-0"}
        },
    )
    step = ExecutionStep.objects.create(
        execution_record=record,
        step_name="step-1",
        step_type="script",
        step_order=1,
        status="success",
    )

    class FakeRedis:
        def xrevrange(self, key, max=",", count=500):
            return [
                ("3-0", {"execution_id": "999", "host_id": str(host.id), "step_order": 1, "step_name": "step-1", "content": "c", "timestamp": "t3", "log_type": "stdout"}),
                ("2-0", {"execution_id": "999", "host_id": str(host.id), "step_order": 1, "step_name": "step-1", "content": "b", "timestamp": "t2", "log_type": "stdout"}),
                ("1-0", {"execution_id": "999", "host_id": str(host.id), "step_order": 1, "step_name": "step-1", "content": "a", "timestamp": "t1", "log_type": "stdout"}),
            ]

    monkeypatch.setattr(realtime_log_service, "redis_client", FakeRedis())

    resp = client.get(
        f"/api/executor/execution-records/{record.id}/steps/{step.id}/hosts/{host.id}/logs/?limit=2"
    )
    assert resp.status_code == 200
    data = resp.data["content"]
    assert "logContent" in data
    assert "next_pointer" in data
    assert "b" in data["logContent"]
    assert data["next_pointer"].startswith("redis:agent_logs/999@")
