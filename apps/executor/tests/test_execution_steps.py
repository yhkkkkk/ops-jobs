import pytest
from django.contrib.auth.models import User
from rest_framework.test import APIClient

from apps.executor.models import ExecutionRecord, ExecutionStep


@pytest.fixture()
def disable_debug_toolbar(settings):
    settings.DEBUG = False
    settings.MIDDLEWARE = [
        mw for mw in settings.MIDDLEWARE if "debug_toolbar" not in mw
    ]


@pytest.mark.django_db
def test_execution_detail_includes_steps(disable_debug_toolbar):
    user = User.objects.create_superuser(
        username="step-admin",
        email="admin@example.com",
        password="pass",
    )
    client = APIClient()
    assert client.login(username="step-admin", password="pass")

    record = ExecutionRecord.objects.create(
        execution_type="quick_script",
        name="test-step-record",
        status="success",
        executed_by=user,
    )
    step = ExecutionStep.objects.create(
        execution_record=record,
        step_name="step-1",
        step_type="script",
        step_order=1,
        status="success",
    )

    resp = client.get(f"/api/executor/execution-records/{record.id}/")
    assert resp.status_code == 200
    data = resp.data["content"]
    assert "steps" in data
    assert data["steps"][0]["id"] == step.id
