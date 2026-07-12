import json
import uuid

import pytest
from django.contrib.auth.models import User
from guardian.shortcuts import assign_perm
from rest_framework.test import APIClient

from apps.executor.models import ExecutionRecord
from apps.hosts.models import Host


pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def clear_dashboard_cache():
    from django.core.cache import cache

    cache.clear()
    yield
    cache.clear()


def _response_content(response):
    if hasattr(response, "data"):
        return response.data["content"]
    return json.loads(response.content)["content"]


def _client_for(user):
    client = APIClient()
    assert client.login(username=user.username, password="pass")
    return client


def test_dashboard_overview_and_recent_activity_only_include_permitted_objects():
    owner = User.objects.create_user(f"owner-{uuid.uuid4().hex[:6]}", password="pass")
    viewer = User.objects.create_user(f"viewer-{uuid.uuid4().hex[:6]}", password="pass")
    visible_record = ExecutionRecord.objects.create(
        execution_type="quick_script",
        name="visible-execution",
        status="success",
        executed_by=owner,
    )
    ExecutionRecord.objects.create(
        execution_type="quick_script",
        name="hidden-execution",
        status="failed",
        executed_by=owner,
    )
    visible_host = Host.objects.create(
        name=f"visible-host-{uuid.uuid4().hex[:6]}",
        os_type="linux",
        device_type="physical",
        created_by=owner,
    )
    Host.objects.create(
        name=f"hidden-host-{uuid.uuid4().hex[:6]}",
        os_type="linux",
        device_type="physical",
        created_by=owner,
    )
    assign_perm("executor.view_executionrecord", viewer, visible_record)
    assign_perm("hosts.view_host", viewer, visible_host)

    client = _client_for(viewer)
    overview = client.get("/api/dashboard/overview/")
    recent = client.get("/api/dashboard/recent_activities/")

    assert overview.status_code == 200
    assert _response_content(overview)["resources"]["hosts"]["total"] == 1
    assert overview.data["content"]["job_overview"]["today_total"] == 1
    assert recent.status_code == 200
    descriptions = [item["description"] for item in recent.data["content"]["activities"]]
    assert "执行任务: visible-execution" in descriptions
    assert "执行任务: hidden-execution" not in descriptions

def test_dashboard_overview_only_counts_permitted_resources():
    owner = User.objects.create_user(f"owner-{uuid.uuid4().hex[:6]}", password="pass")
    viewer = User.objects.create_user(f"viewer-{uuid.uuid4().hex[:6]}", password="pass")

    from apps.hosts.models import HostGroup
    from apps.job_templates.models import ExecutionPlan, JobTemplate
    from apps.scheduler.models import ScheduledJob

    visible_template = JobTemplate.objects.create(
        name=f"visible-template-{uuid.uuid4().hex[:6]}", created_by=owner
    )
    hidden_template = JobTemplate.objects.create(
        name=f"hidden-template-{uuid.uuid4().hex[:6]}", created_by=owner
    )
    visible_plan = ExecutionPlan.objects.create(
        template=visible_template, name=f"visible-plan-{uuid.uuid4().hex[:6]}", created_by=owner
    )
    hidden_plan = ExecutionPlan.objects.create(
        template=hidden_template, name=f"hidden-plan-{uuid.uuid4().hex[:6]}", created_by=owner
    )
    visible_group = HostGroup.objects.create(name=f"visible-group-{uuid.uuid4().hex[:6]}", created_by=owner)
    HostGroup.objects.create(name=f"hidden-group-{uuid.uuid4().hex[:6]}", created_by=owner)
    visible_schedule = ScheduledJob.objects.create(
        name=f"visible-schedule-{uuid.uuid4().hex[:6]}",
        execution_plan=visible_plan,
        cron_expression="0 0 * * *",
        created_by=owner,
    )
    ScheduledJob.objects.create(
        name=f"hidden-schedule-{uuid.uuid4().hex[:6]}",
        execution_plan=hidden_plan,
        cron_expression="0 0 * * *",
        created_by=owner,
    )
    assign_perm("job_templates.view_jobtemplate", viewer, visible_template)
    assign_perm("job_templates.view_executionplan", viewer, visible_plan)
    assign_perm("hosts.view_hostgroup", viewer, visible_group)
    assign_perm("scheduler.view_scheduledjob", viewer, visible_schedule)

    overview = _client_for(viewer).get("/api/dashboard/overview/")

    assert overview.status_code == 200
    resources = _response_content(overview)["resources"]
    assert resources["job_templates"]["total"] == 1
    assert resources["execution_plans"]["total"] == 1
    assert resources["host_groups"]["total"] == 1
    assert _response_content(overview)["scheduled_overview"]["total"] == 1


def test_dashboard_response_cache_is_not_shared_between_users():
    from django.core.cache import cache

    cache.clear()
    owner = User.objects.create_user(f"owner-{uuid.uuid4().hex[:6]}", password="pass")
    first_viewer = User.objects.create_user(f"first-{uuid.uuid4().hex[:6]}", password="pass")
    second_viewer = User.objects.create_user(f"second-{uuid.uuid4().hex[:6]}", password="pass")
    first_record = ExecutionRecord.objects.create(
        execution_type="quick_script", name="first-only-execution", status="success", executed_by=owner
    )
    second_record = ExecutionRecord.objects.create(
        execution_type="quick_script", name="second-only-execution", status="success", executed_by=owner
    )
    assign_perm("executor.view_executionrecord", first_viewer, first_record)
    assign_perm("executor.view_executionrecord", second_viewer, second_record)

    first_response = _client_for(first_viewer).get("/api/dashboard/recent_activities/")
    second_response = _client_for(second_viewer).get("/api/dashboard/recent_activities/")

    assert first_response.status_code == 200
    assert second_response.status_code == 200
    first_descriptions = [item["description"] for item in _response_content(first_response)["activities"]]
    second_descriptions = [item["description"] for item in _response_content(second_response)["activities"]]
    assert "执行任务: first-only-execution" in first_descriptions
    assert "执行任务: second-only-execution" in second_descriptions
    assert "执行任务: first-only-execution" not in second_descriptions


def test_dashboard_ops_endpoints_require_operations_permission():
    user = User.objects.create_user(f"viewer-{uuid.uuid4().hex[:6]}", password="pass")
    client = _client_for(user)

    assert client.get("/api/dashboard/ops_overview/").status_code == 403
    assert client.get("/api/dashboard/ops_latency_trend/").status_code == 403

def test_dashboard_system_status_and_audit_activity_are_limited_to_visible_hosts_and_self():
    owner = User.objects.create_user(f"owner-{uuid.uuid4().hex[:6]}", password="pass")
    viewer = User.objects.create_user(f"viewer-{uuid.uuid4().hex[:6]}", password="pass")

    from apps.agents.models import Agent
    from apps.permissions.models import AuditLog

    visible_host = Host.objects.create(
        name=f"visible-host-{uuid.uuid4().hex[:6]}",
        os_type="linux",
        device_type="physical",
        created_by=owner,
    )
    hidden_host = Host.objects.create(
        name=f"hidden-host-{uuid.uuid4().hex[:6]}",
        os_type="linux",
        device_type="physical",
        created_by=owner,
    )
    Agent.objects.create(host=visible_host, status="online")
    Agent.objects.create(host=hidden_host, status="offline")
    assign_perm("hosts.view_host", viewer, visible_host)
    AuditLog.objects.create(
        user=viewer,
        action="login",
        description="viewer-private-audit",
        ip_address="127.0.0.1",
    )
    AuditLog.objects.create(
        user=owner,
        action="logout",
        description="owner-private-audit",
        ip_address="127.0.0.1",
    )

    client = _client_for(viewer)
    system_status = client.get("/api/dashboard/system_status/")
    recent = client.get("/api/dashboard/recent_activities/")
    statistics = client.get("/api/dashboard/statistics/")

    assert system_status.status_code == 200
    system_content = _response_content(system_status)
    assert system_content["agent_status"]["total"] == 1
    assert system_content["system_info"] == {}
    assert system_content["service_status"] == {}
    descriptions = [item["description"] for item in _response_content(recent)["activities"]]
    assert "viewer-private-audit" in descriptions
    assert "owner-private-audit" not in descriptions
    actions = {item["action"] for item in _response_content(statistics)["user_activity"]}
    assert actions == {"login"}