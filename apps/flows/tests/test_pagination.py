import uuid

import pytest
from django.contrib.auth.models import User
from rest_framework.test import APIClient

from apps.flows.models import FlowRun, FlowTemplate


pytestmark = pytest.mark.django_db


def _client_for(user):
    client = APIClient()
    client.force_authenticate(user)
    return client


def test_flow_template_list_accepts_page_and_page_size():
    user = User.objects.create_user(f"flow-page-{uuid.uuid4().hex[:8]}", password="pass")
    FlowTemplate.objects.create(name=f"flow-a-{uuid.uuid4().hex[:8]}", created_by=user)
    FlowTemplate.objects.create(name=f"flow-b-{uuid.uuid4().hex[:8]}", created_by=user)

    response = _client_for(user).get("/api/flows/templates/?page=2&page_size=1")

    assert response.status_code == 200
    content = response.data["content"]
    assert content["page"] == 2
    assert content["page_size"] == 1
    assert content["total"] == 2
    assert len(content["results"]) == 1


def test_flow_run_latest_per_template_is_paginated():
    user = User.objects.create_user(f"flow-run-page-{uuid.uuid4().hex[:8]}", password="pass")
    template = FlowTemplate.objects.create(name=f"flow-{uuid.uuid4().hex[:8]}", created_by=user)
    FlowRun.objects.create(template=template, started_by=user, name="old")
    latest = FlowRun.objects.create(template=template, started_by=user, name="latest")

    response = _client_for(user).get(
        f"/api/flows/runs/?template_ids={template.id}&latest_per_template=1&page=1&page_size=1"
    )

    assert response.status_code == 200
    content = response.data["content"]
    assert content["total"] == 1
    assert [item["id"] for item in content["results"]] == [latest.id]


def test_flow_template_run_status_filter_uses_latest_run():
    user = User.objects.create_user(f"flow-status-page-{uuid.uuid4().hex[:8]}", password="pass")
    template = FlowTemplate.objects.create(name=f"flow-{uuid.uuid4().hex[:8]}", created_by=user)
    FlowRun.objects.create(template=template, started_by=user, status=FlowRun.Status.FAILED)
    FlowRun.objects.create(template=template, started_by=user, status=FlowRun.Status.SUCCESS)

    response = _client_for(user).get(
        "/api/flows/templates/?run_status=success&page=1&page_size=10"
    )

    assert response.status_code == 200
    assert [item["id"] for item in response.data["content"]["results"]] == [template.id]
