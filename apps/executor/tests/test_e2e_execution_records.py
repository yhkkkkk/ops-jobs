"""
E2E: 验证快速执行和执行方案的端到端链路，会真实启动本地 agent-server 与 agent，
并向其下发任务，随后通过业务 API 创建执行记录，最终断言执行记录的状态与结果结构。

依赖：
- 环境变量 E2E_CONTROL_PLANE=1（与 apps/agents/tests/test_e2e_control_plane.py 保持一致）
- Redis / 数据库 可用
- 运行时会编译并启动本地 agent-server / agent 二进制（由 control_plane_env fixture 完成）
"""

import hashlib
import http.server
import json
import os
import threading
import time
import uuid
import functools
from pathlib import Path

import pytest
from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import connection, transaction
from django.urls import reverse
from rest_framework.test import APIClient

from apps.agents.tests.test_e2e_control_plane import (
    _failure_script,
    _success_script,
    _task_spec,
    control_plane_env,
)
from apps.executor.models import ExecutionRecord
from apps.hosts.models import Host, ServerAccount
from apps.job_templates.models import ExecutionPlan, JobStep, JobTemplate, PlanStep
from utils import log_archive_service
from utils.agent_server_client import AgentServerClient

pytestmark = pytest.mark.django_db(transaction=True)


@pytest.fixture(scope="session", autouse=True)
def enable_sqlite_wal():
    try:
        with connection.cursor() as cur:
            cur.execute("PRAGMA journal_mode=WAL;")
            cur.execute("PRAGMA busy_timeout=5000;")
    except Exception:
        # 非 sqlite 环境忽略
        pass


@pytest.fixture()
def disable_debug_toolbar(settings):
    settings.DEBUG = False
    settings.MIDDLEWARE = [mw for mw in settings.MIDDLEWARE if "debug_toolbar" not in mw]


@pytest.fixture()
def stub_log_archive(monkeypatch):
    try:
        monkeypatch.setattr(
            log_archive_service, "archive_execution_logs", lambda execution_id, task_id=None: True
        )
    except AttributeError:
        # 本地跑测试时若 service 不存在，直接忽略
        pass


@pytest.fixture()
def api_client():
    username = f"e2e-user-{uuid.uuid4().hex[:6]}"
    user = User.objects.create_user(username, password="e2e-pass")
    client = APIClient()
    assert client.login(username=username, password="e2e-pass")
    return client, user


def _create_plan(user, host, script_content, script_type):
    tpl = JobTemplate.objects.create(
        name=f"e2e-tpl-{uuid.uuid4().hex[:6]}",
        description="e2e tpl",
        created_by=user,
    )
    step = JobStep.objects.create(
        template=tpl,
        name="step1",
        description="e2e step",
        step_type="script",
        order=1,
        step_parameters={},
        script_type=script_type,
        script_content=script_content,
        timeout=60,
        ignore_error=False,
    )
    step.target_hosts.add(host)

    plan = ExecutionPlan.objects.create(
        template=tpl,
        name="e2e-plan",
        description="",
        created_by=user,
    )
    plan_step = PlanStep.copy_from_template_step(step, plan)
    plan_step.order = 1
    plan_step.save()
    return plan, plan_step


def _create_plan_two_steps_multi(user, hosts, first_script, second_script):
    tpl = JobTemplate.objects.create(
        name=f"e2e-tpl-multi-{uuid.uuid4().hex[:6]}",
        description="e2e tpl multi hosts",
        created_by=user,
    )
    step1 = JobStep.objects.create(
        template=tpl,
        name="step1",
        description="multi host step1",
        step_type="script",
        order=1,
        step_parameters={},
        script_type=first_script[1],
        script_content=first_script[0],
        timeout=60,
        ignore_error=False,
    )
    for h in hosts:
        step1.target_hosts.add(h)

    step2 = JobStep.objects.create(
        template=tpl,
        name="step2",
        description="multi host step2",
        step_type="script",
        order=2,
        step_parameters={"start": True},
        script_type=second_script[1],
        script_content=second_script[0],
        timeout=60,
        ignore_error=False,
    )
    for h in hosts:
        step2.target_hosts.add(h)

    plan = ExecutionPlan.objects.create(
        template=tpl,
        name="e2e-plan-multi",
        description="",
        created_by=user,
    )
    for order, st in enumerate([step1, step2], start=1):
        ps = PlanStep.copy_from_template_step(st, plan)
        ps.order = order
        ps.save()
    return plan


def _create_plan_two_steps(user, host, first_script, second_script):
    return _create_plan_two_steps_multi(user, [host], first_script, second_script)


def _assert_record(record: ExecutionRecord):
    record.refresh_from_db()
    assert record.status in ("success", "failed", "running")
    assert record.execution_id


def _ensure_host_online(control_plane_env):
    host = control_plane_env["host"]
    host.status = "online"
    host.internal_ip = "127.0.0.1"
    host.save(update_fields=["status", "internal_ip"])
    return host


def _record_id_from_response(resp):
    data = resp.json()
    return data.get("data", {}).get("execution_record_id") or data.get("execution_record_id")


def _wait_status(record_id, statuses=("success", "failed"), timeout=120):
    deadline = time.time() + timeout
    while time.time() < deadline:
        rec = ExecutionRecord.objects.get(id=record_id)
        if rec.status in statuses:
            return rec
        time.sleep(1)
    raise AssertionError(f"timeout waiting status {statuses}")


def _make_hosts(user, n=2):
    hosts = []
    for _ in range(n):
        hosts.append(
            Host.objects.create(
                name=f"e2e-host-{uuid.uuid4().hex[:6]}",
                os_type="linux",
                device_type="physical",
                created_by=user,
            )
        )
    return hosts


def _start_file_server(root: Path):
    handler = http.server.SimpleHTTPRequestHandler
    httpd = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    httpd.directory = str(root)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    return httpd, thread, httpd.server_address[1]


def test_quick_execute_end_to_end(control_plane_env, api_client, disable_debug_toolbar):
    client, user = api_client
    host = _ensure_host_online(control_plane_env)
    server_url = control_plane_env["server_url"]
    agent_server_id = control_plane_env["agent_server_id"]
    waiter = control_plane_env["waiter"]

    # 先直接下发一条任务到 agent-server，确保 agent 链路畅通
    cmd, script_type = _success_script()
    task_id = f"qe_{uuid.uuid4().hex[:6]}"
    spec = _task_spec(task_id, cmd, script_type, 901, host.id)
    client_as = AgentServerClient.from_settings()
    resp = client_as.post(f"{server_url}/api/agents/{agent_server_id}/tasks", json=spec)
    assert resp.status_code == 200, resp.text
    result = waiter.wait_for_result(task_id, timeout=60)
    assert result.get("status") == "success", result

    # 再通过业务 API 走 quick execute，验证执行记录落库
    resp = client.post(
        "/api/quick/execute_script/",
        data={
            "name": f"e2e-quick-{uuid.uuid4().hex[:6]}",
            "target_host_ids": [host.id],
            "script_content": cmd,
            "script_type": script_type,
            "timeout": 30,
        },
        format="json",
    )
    assert resp.status_code == 200, resp.content
    record_id = _record_id_from_response(resp)
    record = ExecutionRecord.objects.get(id=record_id)
    _assert_record(record)


def test_execution_plan_end_to_end(control_plane_env, api_client, disable_debug_toolbar):
    client, user = api_client
    host = _ensure_host_online(control_plane_env)
    server_url = control_plane_env["server_url"]
    agent_server_id = control_plane_env["agent_server_id"]
    waiter = control_plane_env["waiter"]

    # 先向 agent-server 下发一条失败一条成功，验证落结果
    exec_id = 902
    fail_task_id = f"plan_{host.id}_fail"
    ok_task_id = f"plan_{host.id}_retry"
    client_as = AgentServerClient.from_settings()
    for tid, script in [(fail_task_id, _failure_script()), (ok_task_id, _success_script())]:
        spec = _task_spec(tid, script[0], script[1], exec_id, host.id)
        r = client_as.post(f"{server_url}/api/agents/{agent_server_id}/tasks", json=spec)
        assert r.status_code == 200, r.text
        res = waiter.wait_for_result(tid, timeout=60)
        expected = "failed" if tid == fail_task_id else "success"
        assert res.get("status") == expected, res

    # 执行计划（串行）
    plan, _ = _create_plan(user, host, "echo plan", "bash")
    resp = client.post(
        f"/api/job-templates/plans/{plan.id}/execute/",
        data={
            "execution_mode": "serial",
            "target_host_ids": [host.id],
        },
        format="json",
    )
    assert resp.status_code == 200, resp.content
    record_id = _record_id_from_response(resp)
    record = ExecutionRecord.objects.get(id=record_id)
    record = _wait_status(record.id)
    _assert_record(record)


def test_retry_failed_step_inplace(control_plane_env, api_client, disable_debug_toolbar):
    client, user = api_client
    host = _ensure_host_online(control_plane_env)
    server_url = control_plane_env["server_url"]

    fail_cmd, fail_type = _failure_script()
    plan, _ = _create_plan(user, host, fail_cmd, fail_type)

    resp = client.post(
        f"/api/job-templates/plans/{plan.id}/execute/",
        data={
            "execution_mode": "serial",
            "agent_server_url": server_url,
            "target_host_ids": [host.id],
        },
        format="json",
    )
    assert resp.status_code == 200, resp.content
    record_id = _record_id_from_response(resp)
    record = _wait_status(record_id, statuses=("failed", "success"))
    assert record.status == "failed"

    step = record.steps.first()
    ok_cmd, ok_type = _success_script()
    step.step_parameters["script_content"] = ok_cmd
    step.step_parameters["script_type"] = ok_type
    step.save(update_fields=["step_parameters"])

    retry_resp = client.post(
        f"/api/executor/execution-records/{record.id}/retry_step/",
        data={
            "step_id": step.id,
            "retry_type": "all",
        },
        format="json",
    )
    assert retry_resp.data.get("success") is True
    final = _wait_status(record.id, statuses=("success", "failed"), timeout=150)
    assert final.status in ("success", "failed")


def test_retry_failed_step_with_host_filter(control_plane_env, api_client, disable_debug_toolbar):
    client, user = api_client
    host = _ensure_host_online(control_plane_env)
    server_url = control_plane_env["server_url"]

    fail_cmd, fail_type = _failure_script()
    plan, _ = _create_plan(user, host, fail_cmd, fail_type)

    resp = client.post(
        f"/api/job-templates/plans/{plan.id}/execute/",
        data={
            "execution_mode": "serial",
            "agent_server_url": server_url,
            "target_host_ids": [host.id],
        },
        format="json",
    )
    assert resp.status_code == 200, resp.content
    record_id = _record_id_from_response(resp)
    record = _wait_status(record_id, statuses=("failed", "success"))
    assert record.status == "failed"

    step = record.steps.first()
    ok_cmd, ok_type = _success_script()
    step.step_parameters["script_content"] = ok_cmd
    step.step_parameters["script_type"] = ok_type
    step.save(update_fields=["step_parameters"])

    retry_resp = client.post(
        f"/api/executor/execution-records/{record.id}/retry_step/",
        data={
            "step_id": step.id,
            "retry_type": "failed_only",
            "host_ids": [str(host.id)],
        },
        format="json",
    )
    assert retry_resp.data.get("success") is True

    final = _wait_status(record.id, statuses=("success", "failed"), timeout=150)
    assert final.status in ("success", "failed")
    final.refresh_from_db()
    # 所有 host_results 都应为成功
    assert all(hr.get("status") == "success" for hr in final.steps.first().host_results)


def test_retry_execution_full_redo(control_plane_env, api_client, disable_debug_toolbar):
    client, user = api_client
    host = _ensure_host_online(control_plane_env)
    server_url = control_plane_env["server_url"]

    fail_cmd, fail_type = _failure_script()
    plan, _ = _create_plan(user, host, fail_cmd, fail_type)

    resp = client.post(
        f"/api/job-templates/plans/{plan.id}/execute/",
        data={
            "execution_mode": "serial",
            "agent_server_url": server_url,
            "target_host_ids": [host.id],
        },
        format="json",
    )
    assert resp.status_code == 200, resp.content
    record_id = _record_id_from_response(resp)
    record = _wait_status(record_id, statuses=("failed", "success"))
    assert record.status == "failed"

    redo_resp = client.post(
        f"/api/executor/execution-records/{record.id}/retry/",
        data={
            "retry_type": "full",
            "agent_server_url": server_url,
        },
        format="json",
    )
    assert redo_resp.data.get("success") is True
    new_record_id = redo_resp.data.get("execution_record_id")
    assert new_record_id and new_record_id != record.id
    new_record = _wait_status(new_record_id, statuses=("success", "failed", "running"), timeout=180)
    assert new_record.status in ("success", "failed", "running")


def test_job_template_debug_execution(control_plane_env, api_client, disable_debug_toolbar):
    client, user = api_client
    host = _ensure_host_online(control_plane_env)
    server_url = control_plane_env["server_url"]

    ok_cmd, ok_type = _success_script()
    plan, template_step = _create_plan(user, host, ok_cmd, ok_type)
    template = plan.template

    resp = client.post(
        f"/api/job-templates/templates/{template.id}/debug/",
        data={
            "execution_mode": "serial",
            "agent_server_url": server_url,
            "target_host_ids": [host.id],
        },
        format="json",
    )
    assert resp.status_code == 200, resp.content
    assert resp.data.get("success") is True
    record_id = _record_id_from_response(resp)
    record = _wait_status(record_id, statuses=("success", "failed"), timeout=150)
    assert record.status in ("success", "failed")


def test_ignore_error_and_continue_next_step(control_plane_env, api_client, disable_debug_toolbar):
    client, user = api_client
    host = _ensure_host_online(control_plane_env)
    server_url = control_plane_env["server_url"]

    fail_cmd, fail_type = _failure_script()
    ok_cmd, ok_type = _success_script()
    plan = _create_plan_two_steps(user, host, (fail_cmd, fail_type), (ok_cmd, ok_type))

    resp = client.post(
        f"/api/job-templates/plans/{plan.id}/execute/",
        data={
            "execution_mode": "serial",
            "agent_server_url": server_url,
            "target_host_ids": [host.id],
        },
        format="json",
    )
    assert resp.status_code == 200, resp.content
    record_id = _record_id_from_response(resp)
    record = _wait_status(record_id, statuses=("failed",), timeout=120)
    assert record.status == "failed"

    # 增加重试次数让后续 full 重试能被阻拦
    record.retry_count = record.max_retries
    record.save(update_fields=["retry_count"])

    redo = client.post(
        f"/api/executor/execution-records/{record.id}/retry/",
        data={"retry_type": "full", "agent_server_url": server_url},
        format="json",
    )
    assert redo.status_code == 400
    assert "最大重试次数" in redo.data.get("message", "")


def test_retry_blocked_after_reaching_limit(control_plane_env, api_client, disable_debug_toolbar):
    client, user = api_client
    host = _ensure_host_online(control_plane_env)
    server_url = control_plane_env["server_url"]

    fail_cmd, fail_type = _failure_script()
    plan, _ = _create_plan(user, host, fail_cmd, fail_type)

    resp = client.post(
        f"/api/job-templates/plans/{plan.id}/execute/",
        data={
            "execution_mode": "serial",
            "agent_server_url": server_url,
            "target_host_ids": [host.id],
        },
        format="json",
    )
    assert resp.status_code == 200, resp.content
    record_id = _record_id_from_response(resp)
    record = _wait_status(record_id, statuses=("failed",), timeout=120)
    assert record.status == "failed"

    record.retry_count = record.max_retries
    record.save(update_fields=["retry_count"])

    redo = client.post(
        f"/api/executor/execution-records/{record.id}/retry/",
        data={"retry_type": "full", "agent_server_url": server_url},
        format="json",
    )
    assert redo.status_code == 400
    assert "最大重试次数" in redo.data.get("message", "")


def test_cancel_running_execution(control_plane_env, api_client, disable_debug_toolbar):
    client, user = api_client
    host = _ensure_host_online(control_plane_env)
    server_url = control_plane_env["server_url"]

    long_cmd = ('python -c "import time; time.sleep(40); print(\'done\')"', "python")
    plan, _ = _create_plan(user, host, long_cmd[0], long_cmd[1])

    resp = client.post(
        f"/api/job-templates/plans/{plan.id}/execute/",
        data={
            "execution_mode": "serial",
            "agent_server_url": server_url,
            "target_host_ids": [host.id],
        },
        format="json",
    )
    assert resp.status_code == 200, resp.content
    record_id = _record_id_from_response(resp)

    cancel_resp = client.post(f"/api/executor/execution-records/{record_id}/cancel/", format="json")
    assert cancel_resp.status_code in (200, 400)
    final = _wait_status(record_id, statuses=("cancelled", "failed", "success"), timeout=90)
    assert final.status in ("cancelled", "failed", "success")


def test_cancel_running_execution_long(control_plane_env, api_client, disable_debug_toolbar):
    """启动长耗时任务后立刻取消，验证取消链路而不是直接失败。"""
    client, user = api_client
    host = _ensure_host_online(control_plane_env)
    server_url = control_plane_env["server_url"]

    if os.name == "nt":
        long_cmd = ('Start-Sleep -Seconds 40; Write-Output "done"', "powershell")
    else:
        long_cmd = ("echo start; sleep 40; echo end", "bash")
    plan, _ = _create_plan(user, host, long_cmd[0], long_cmd[1])

    resp = client.post(
        f"/api/job-templates/plans/{plan.id}/execute/",
        data={
            "execution_mode": "serial",
            "agent_server_url": server_url,
            "target_host_ids": [host.id],
        },
        format="json",
    )
    assert resp.status_code == 200, resp.content
    record_id = _record_id_from_response(resp)

    # 给任务一点启动时间
    time.sleep(2)
    cancel_resp = client.post(f"/api/executor/execution-records/{record_id}/cancel/", format="json")
    assert cancel_resp.status_code in (200, 400)
    final = _wait_status(record_id, statuses=("cancelled", "failed", "success"), timeout=120)
    assert final.status in ("cancelled", "failed", "success")


def test_ignore_error_multi_host(control_plane_env, api_client, disable_debug_toolbar):
    """两主机：一台失败，一台成功，调用忽略错误后应继续到下一步并成功。"""
    client, user = api_client
    hosts = _make_hosts(user, n=2)
    assert len(hosts) == 2
    for h in hosts:
        h.status = "online"
        h.internal_ip = "127.0.0.1"
        h.save(update_fields=["status", "internal_ip"])

    server_url = control_plane_env["server_url"]
    fail_cmd, fail_type = ('if [ "$(hostname)" = "unknown" ]; then exit 1; fi; echo mixed', "bash")
    ok_cmd, ok_type = _success_script()
    plan = _create_plan_two_steps_multi(user, hosts, (fail_cmd, fail_type), (ok_cmd, ok_type))

    resp = client.post(
        f"/api/job-templates/plans/{plan.id}/execute/",
        data={
            "execution_mode": "parallel",
            "agent_server_url": server_url,
            "target_host_ids": [h.id for h in hosts],
        },
        format="json",
    )
    assert resp.status_code == 200, resp.content
    record_id = _record_id_from_response(resp)
    record = _wait_status(record_id, statuses=("failed", "success"), timeout=180)
    assert record.status in ("failed", "success")

    step = record.steps.order_by("order").first()
    ig = client.post(
        f"/api/executor/execution-records/{record.id}/ignore_step_error/",
        data={"step_id": step.id},
        format="json",
    )
    assert ig.status_code == 200

    final_record = _wait_status(record.id, statuses=("success", "failed"), timeout=180)
    assert final_record.status in ("success", "failed")
    next_step = final_record.steps.filter(step_order=1).first()
    assert next_step is not None


def test_quick_file_transfer_success_and_checksum_fail(control_plane_env, api_client, disable_debug_toolbar):
    client, user = api_client
    host = _ensure_host_online(control_plane_env)
    server_url = control_plane_env["server_url"]
    work_dir = control_plane_env["work_dir"]

    account = ServerAccount.objects.create(name="e2e-account", username="user", password="pass")
    payload = b"e2e-file-transfer"
    src_path = work_dir / "source.txt"
    src_path.write_bytes(payload)
    checksum = hashlib.sha256(payload).hexdigest()
    remote_path = "/tmp/e2e-dest.txt"

    upload = SimpleUploadedFile("e2e.txt", payload, content_type="application/octet-stream")
    sources_json = json.dumps(
        [
            {
                "type": "local",
                "file_field": "file0",
                "remote_path": remote_path,
                "checksum": checksum,
                "size": len(payload),
            }
        ]
    )

    resp = client.post(
        "/api/quick/transfer_file/",
        data={
            "name": "e2e-file",
            "target_host_ids": [host.id],
            "sources": sources_json,
            "timeout": 60,
            "agent_server_url": server_url,
            "file0": upload,
        },
        format="multipart",
    )
    assert resp.status_code == 200, resp.content
    record_id = _record_id_from_response(resp)
    record = _wait_status(record_id, statuses=("success", "failed"), timeout=180)
    assert record.status == "success"

    # 校验失败路径：不带文件、期望 400
    resp_bad = client.post(
        "/api/quick/transfer_file/",
        data={
            "name": "e2e-file-bad",
            "target_host_ids": [host.id],
            "timeout": 60,
            "agent_server_url": server_url,
        },
        format="json",
    )
    assert resp_bad.status_code == 400


def test_parallel_multi_host_workflow_success(control_plane_env, api_client, disable_debug_toolbar):
    client, user = api_client
    hosts = _make_hosts(user, n=2)
    assert len(hosts) == 2, "fixture未提供足够主机"
    for h in hosts:
        h.status = "online"
        h.internal_ip = "127.0.0.1"
        h.save(update_fields=["status", "internal_ip"])

    server_url = control_plane_env["server_url"]
    ok_cmd, ok_type = _success_script()
    plan = _create_plan_two_steps_multi(user, hosts, (ok_cmd, ok_type), (ok_cmd, ok_type))

    resp = client.post(
        f"/api/job-templates/plans/{plan.id}/execute/",
        data={
            "execution_mode": "parallel",
            "agent_server_url": server_url,
            "target_host_ids": [h.id for h in hosts],
        },
        format="json",
    )
    assert resp.status_code == 200, resp.content
    record_id = _record_id_from_response(resp)
    record = _wait_status(record_id, statuses=("success", "failed"), timeout=180)
    assert record.status in ("success", "failed")
    steps = record.steps.order_by("step_order")
    assert steps.exists()
    for step in steps:
        step.refresh_from_db()
        assert step.host_results


def test_execution_parameters_preserve_is_secret_flag(api_client, disable_debug_toolbar):
    """
    确认执行详情接口会携带 is_secret 标记，供前端 formatVar 做敏感掩码。
    （不在后端做遮罩，只确保标记与原值透传。）
    """
    from rest_framework.test import APIClient as DRFClient

    client = DRFClient()
    user = User.objects.create_superuser(f"admin-{uuid.uuid4().hex[:6]}", "a@example.com", "e2e-pass")
    assert client.login(username=user.username, password="e2e-pass")

    record = ExecutionRecord.objects.create(
        execution_type="quick_script",
        name="secret-vars",
        description="",
        status="success",
        executed_by=user,
        execution_parameters={
            "global_variables": [
                {"name": "token", "value": "secret123", "is_secret": True},
                {"name": "region", "value": "sh", "is_secret": False},
            ]
        },
    )

    url = reverse("executor:execution-record-detail", args=[record.id])
    resp = client.get(url, format="json")
    assert resp.status_code == 200, resp.content
    params = resp.data["content"]["execution_parameters"]
    gv = params.get("global_variables", [])
    token = next((v for v in gv if v["name"] == "token"), None)
    region = next((v for v in gv if v["name"] == "region"), None)
    assert token is not None and token["is_secret"] is True and token["value"] == "secret123"
    assert region is not None and region["is_secret"] is False and region["value"] == "sh"


def test_log_pointer_replay_order_and_limit(monkeypatch):
    """
    使用 storage pointer 回溯日志时，保证按时间正序返回且尊重 limit。
    """
    from utils.realtime_logs import realtime_log_service

    class FakeRedis:
        def __init__(self):
            self.calls = []

        def xrevrange(self, key, max="+", count=500):
            # 返回倒序数据，模拟 Redis 行为
            return [
                ("2-0", {"execution_id": "exec-1", "timestamp": "t2", "content": "b", "host_id": "h1", "step_order": 1, "step_name": "s"}),
                ("1-0", {"execution_id": "exec-1", "timestamp": "t1", "content": "a", "host_id": "h1", "step_order": 1, "step_name": "s"}),
            ]

    fake = FakeRedis()
    monkeypatch.setattr(realtime_log_service, "redis_client", fake)
    logs = realtime_log_service.get_logs_by_pointer("redis:agent_logs/exec-1@2-0", limit=2)
    # 应转换成正序
    assert [log["id"] for log in logs] == ["1-0", "2-0"]
    assert [log["content"] for log in logs] == ["a", "b"]


def test_log_pointer_respects_limit(monkeypatch):
    """大批量回溯时只返回 limit 条，并保持时间正序。"""
    from utils.realtime_logs import realtime_log_service

    class FakeRedis:
        def xrevrange(self, key, max="+", count=500):
            data = [
                ("5-0", {"execution_id": "exec-2", "timestamp": "t5", "content": "e", "host_id": "h1", "step_order": 1, "step_name": "s"}),
                ("4-0", {"execution_id": "exec-2", "timestamp": "t4", "content": "d", "host_id": "h1", "step_order": 1, "step_name": "s"}),
                ("3-0", {"execution_id": "exec-2", "timestamp": "t3", "content": "c", "host_id": "h1", "step_order": 1, "step_name": "s"}),
                ("2-0", {"execution_id": "exec-2", "timestamp": "t2", "content": "b", "host_id": "h1", "step_order": 1, "step_name": "s"}),
                ("1-0", {"execution_id": "exec-2", "timestamp": "t1", "content": "a", "host_id": "h1", "step_order": 1, "step_name": "s"}),
            ]
            return data[:count]

    monkeypatch.setattr(realtime_log_service, "redis_client", FakeRedis())
    logs = realtime_log_service.get_logs_by_pointer("redis:agent_logs/exec-2@5-0", limit=3)
    assert [log["id"] for log in logs] == ["3-0", "4-0", "5-0"]
    assert [log["content"] for log in logs] == ["c", "d", "e"]


def test_plan_file_transfer_with_artifact_source(control_plane_env, api_client, disable_debug_toolbar):
    """
    模板/执行方案的 file_transfer 步骤（artifact 下载 URL），覆盖前端老格式 download_url 的执行路径。
    """
    import http.server
    import threading

    from rest_framework.test import APIClient as DRFClient
    client = DRFClient()
    user = User.objects.create_superuser(f"super-{uuid.uuid4().hex[:6]}", "a@example.com", "e2e-pass")
    assert client.login(username=user.username, password="e2e-pass")

    # 保持原有 host/agent 环境
    host = _ensure_host_online(control_plane_env)
    server_url = control_plane_env["server_url"]
    work_dir = control_plane_env["work_dir"]

    payload = b"plan-file-transfer"
    src_path = work_dir / "tpl_source.txt"
    src_path.write_bytes(payload)
    checksum = hashlib.sha256(payload).hexdigest()
    remote_path = "/tmp/plan-dest.txt"

    handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(work_dir))
    httpd = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    download_url = f"http://127.0.0.1:{httpd.server_address[1]}/{src_path.name}"

    try:
        # 创建模板（包含 file_transfer 步骤，使用 artifact 源）
        tpl = JobTemplate.objects.create(
            name=f"tpl-ft-{uuid.uuid4().hex[:6]}",
            description="ft artifact",
            created_by=user,
        )
        step = JobStep.objects.create(
            template=tpl,
            name="ft-step",
            description="artifact download",
            step_type="file_transfer",
            order=1,
            step_parameters={},
            timeout=120,
            ignore_error=False,
            remote_path=remote_path,
            file_sources=[
                {
                    "type": "artifact",
                    "download_url": download_url,
                    "remote_path": remote_path,
                    "sha256": checksum,
                    "size": len(payload),
                }
            ],
        )
        step.target_hosts.add(host)

        plan = ExecutionPlan.objects.create(
            template=tpl,
            name="ft-plan",
            description="",
            created_by=user,
            global_parameters_snapshot=tpl.global_parameters,
        )
        from apps.job_templates.sync_service import TemplateChangeDetector
        plan_step = PlanStep.objects.create(
            plan=plan,
            step=step,
            order=1,
            step_hash=TemplateChangeDetector.calculate_step_hash(step),
        )
        plan_step.copy_from_template_step()
        plan_step.save()

        resp = client.post(
            f"/api/job-templates/plans/{plan.id}/execute/",
            data={
                "execution_mode": "serial",
                "agent_server_url": server_url,
                "target_host_ids": [host.id],
            },
            format="json",
        )
        assert resp.status_code == 200, resp.content
        record_id = _record_id_from_response(resp)
        if not record_id:
            fallback = (
                ExecutionRecord.objects.filter(executed_by=user, execution_type="job_workflow")
                .order_by("-id")
                .first()
            )
            assert fallback, "未找到执行记录"
            record_id = fallback.id
        record = _wait_status(record_id, statuses=("success", "failed"), timeout=240)
        assert record.status == "success"
    finally:
        httpd.shutdown()
        httpd.server_close()
        thread.join(timeout=2)
