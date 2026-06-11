import uuid
from unittest.mock import patch

import pytest
from django.contrib.auth.models import Permission, User
from django.contrib.contenttypes.models import ContentType
from guardian.shortcuts import assign_perm
from rest_framework.test import APIClient

from apps.executor.models import ExecutionRecord, ExecutionStep
from apps.hosts.models import Host
from apps.job_templates.models import ExecutionPlan, JobTemplate
from apps.permissions.models import AuditLog


pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def disable_debug_toolbar(settings):
    settings.DEBUG = False
    settings.MIDDLEWARE = [mw for mw in settings.MIDDLEWARE if "debug_toolbar" not in mw]


def _client_for(user: User) -> APIClient:
    client = APIClient()
    assert client.login(username=user.username, password="pass")
    return client


def _grant_global_permission(user: User, codename: str, app_model=AuditLog) -> None:
    content_type = ContentType.objects.get_for_model(app_model)
    perm, _ = Permission.objects.get_or_create(
        content_type=content_type,
        codename=codename,
        defaults={"name": codename},
    )
    user.user_permissions.add(perm)


def _create_quick_record(owner: User, status: str = "failed") -> ExecutionRecord:
    return ExecutionRecord.objects.create(
        execution_type="quick_script",
        name=f"quick-{uuid.uuid4().hex[:6]}",
        status=status,
        executed_by=owner,
        execution_parameters={"execution_mode": "ssh"},
    )


def _create_plan(owner: User) -> ExecutionPlan:
    template = JobTemplate.objects.create(
        name=f"tpl-{uuid.uuid4().hex[:8]}",
        description="",
        created_by=owner,
    )
    return ExecutionPlan.objects.create(
        template=template,
        name=f"plan-{uuid.uuid4().hex[:8]}",
        description="",
        created_by=owner,
    )


def _create_workflow_record(owner: User, plan: ExecutionPlan, status: str = "failed") -> ExecutionRecord:
    return ExecutionRecord.objects.create(
        execution_type="job_workflow",
        name=f"workflow-{uuid.uuid4().hex[:6]}",
        status=status,
        executed_by=owner,
        content_type=ContentType.objects.get_for_model(ExecutionPlan),
        object_id=plan.id,
        execution_parameters={"execution_mode": "agent"},
    )


def test_retrieve_forbidden_without_object_view_permission():
    owner = User.objects.create_user(f"owner-{uuid.uuid4().hex[:6]}", password="pass")
    viewer = User.objects.create_user(f"viewer-{uuid.uuid4().hex[:6]}", password="pass")
    record = _create_quick_record(owner)

    client = _client_for(viewer)
    resp = client.get(f"/api/executor/execution-records/{record.id}/")

    assert resp.status_code == 403


def test_retrieve_and_host_logs_allowed_with_object_view_permission(monkeypatch):
    owner = User.objects.create_user(f"owner-{uuid.uuid4().hex[:6]}", password="pass")
    viewer = User.objects.create_user(f"viewer-{uuid.uuid4().hex[:6]}", password="pass")
    record = _create_quick_record(owner, status="success")

    host = Host.objects.create(
        name=f"host-{uuid.uuid4().hex[:6]}",
        os_type="linux",
        device_type="physical",
        created_by=owner,
    )
    step = ExecutionStep.objects.create(
        execution_record=record,
        step_name="step-1",
        step_type="script",
        step_order=1,
        status="success",
    )
    record.execution_results = {
        "step_logs": {
            "step-1": {
                "step_name": "step-1",
                "step_order": 1,
                "hosts": {
                    str(host.id): {"stdout": "hello", "stderr": ""}
                },
            }
        }
    }
    record.save(update_fields=["execution_results"])

    assign_perm("executor.view_executionrecord", viewer, record)

    client = _client_for(viewer)
    detail_resp = client.get(f"/api/executor/execution-records/{record.id}/")
    assert detail_resp.status_code == 200

    logs_resp = client.get(
        f"/api/executor/execution-records/{record.id}/steps/{step.id}/hosts/{host.id}/logs/"
    )
    assert logs_resp.status_code == 200
    assert "log_context" in logs_resp.data.get("content", {})


def test_retry_quick_script_forbidden_without_execute_scripts_permission():
    owner = User.objects.create_user(f"owner-{uuid.uuid4().hex[:6]}", password="pass")
    operator = User.objects.create_user(f"op-{uuid.uuid4().hex[:6]}", password="pass")
    record = _create_quick_record(owner, status="failed")

    client = _client_for(operator)
    resp = client.post(
        f"/api/executor/execution-records/{record.id}/retry/",
        data={"retry_type": "full"},
        format="json",
    )

    assert resp.status_code == 403


def test_retry_quick_script_allowed_with_execute_scripts_permission():
    owner = User.objects.create_user(f"owner-{uuid.uuid4().hex[:6]}", password="pass")
    operator = User.objects.create_user(f"op-{uuid.uuid4().hex[:6]}", password="pass")
    record = _create_quick_record(owner, status="failed")
    _grant_global_permission(operator, "execute_scripts")

    client = _client_for(operator)
    with patch("apps.agents.execution_service.AgentExecutionService.retry_execution_record") as mock_retry:
        mock_retry.return_value = {
            "success": True,
            "execution_record_id": record.id,
            "execution_id": str(record.execution_id),
            "message": "ok",
        }
        resp = client.post(
            f"/api/executor/execution-records/{record.id}/retry/",
            data={"retry_type": "full"},
            format="json",
        )

    assert resp.status_code == 200
    mock_retry.assert_called_once()


def test_retry_job_workflow_requires_execute_plan_object_permission():
    owner = User.objects.create_user(f"owner-{uuid.uuid4().hex[:6]}", password="pass")
    operator = User.objects.create_user(f"op-{uuid.uuid4().hex[:6]}", password="pass")
    plan = _create_plan(owner)
    record = _create_workflow_record(owner, plan, status="failed")

    client = _client_for(operator)

    # 未赋予 execute_executionplan 对象权限时应拒绝
    deny_resp = client.post(
        f"/api/executor/execution-records/{record.id}/retry/",
        data={"retry_type": "full"},
        format="json",
    )
    assert deny_resp.status_code == 403

    assign_perm("job_templates.execute_executionplan", operator, plan)

    with patch("apps.agents.execution_service.AgentExecutionService.retry_execution_record") as mock_retry:
        mock_retry.return_value = {
            "success": True,
            "execution_record_id": record.id,
            "execution_id": str(record.execution_id),
            "message": "ok",
        }
        allow_resp = client.post(
            f"/api/executor/execution-records/{record.id}/retry/",
            data={"retry_type": "full"},
            format="json",
        )

    assert allow_resp.status_code == 200
    mock_retry.assert_called_once()


def test_cancel_quick_script_requires_execute_scripts_permission():
    owner = User.objects.create_user(f"owner-{uuid.uuid4().hex[:6]}", password="pass")
    operator = User.objects.create_user(f"op-{uuid.uuid4().hex[:6]}", password="pass")
    record = _create_quick_record(owner, status="running")

    client = _client_for(operator)
    deny_resp = client.post(f"/api/executor/execution-records/{record.id}/cancel/", format="json")
    assert deny_resp.status_code == 403

    _grant_global_permission(operator, "execute_scripts")
    allow_resp = client.post(f"/api/executor/execution-records/{record.id}/cancel/", format="json")
    assert allow_resp.status_code == 200

    record.refresh_from_db()
    assert record.status == "cancelled"
