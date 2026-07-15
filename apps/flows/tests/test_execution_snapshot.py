import uuid

import pytest
from django.contrib.auth.models import User

from apps.flows.models import FlowNode, FlowRun, FlowTemplate
from apps.flows.services import FlowRunner


pytestmark = pytest.mark.django_db


def test_flow_run_keeps_immutable_definition_snapshot_after_template_changes():
    user = User.objects.create_user(f"snapshot-{uuid.uuid4().hex[:8]}", password="pass")
    template = FlowTemplate.objects.create(
        name=f"snapshot-flow-{uuid.uuid4().hex[:8]}",
        created_by=user,
        description="original definition",
        variables={"ReleaseVersion": {"type": "text", "default": "v1"}},
    )
    node = FlowNode.objects.create(
        template=template,
        uuid="manual-approval",
        name="original approval",
        node_type=FlowNode.NodeType.MANUAL,
        config={"instructions": "approve v1"},
    )

    flow_run = FlowRunner.start(template=template, user=user)

    snapshot = flow_run.definition_snapshot
    assert snapshot["template"]["name"] == template.name
    assert snapshot["template"]["description"] == "original definition"
    assert snapshot["nodes"] == [
        {
            "id": node.id,
            "uuid": "manual-approval",
            "name": "original approval",
            "node_type": "manual",
            "config": {"instructions": "approve v1"},
            "position": {},
        }
    ]
    assert snapshot["edges"] == []

    node.name = "changed approval"
    node.config = {"instructions": "approve v2"}
    node.save(update_fields=["name", "config"])
    template.description = "changed definition"
    template.save(update_fields=["description"])
    flow_run.refresh_from_db()

    assert flow_run.definition_snapshot == snapshot

def test_flow_run_list_omits_definition_snapshot_but_detail_keeps_it():
    from rest_framework.test import APIClient

    user = User.objects.create_user(f"snapshot-api-{uuid.uuid4().hex[:8]}", password="pass")
    template = FlowTemplate.objects.create(name=f"snapshot-api-flow-{uuid.uuid4().hex[:8]}", created_by=user)
    flow_run = FlowRun.objects.create(
        template=template,
        started_by=user,
        definition_snapshot={"template": {"name": template.name}, "nodes": [], "edges": []},
    )
    client = APIClient()
    client.force_authenticate(user)

    list_response = client.get("/api/flows/runs/")
    detail_response = client.get(f"/api/flows/runs/{flow_run.id}/")

    assert list_response.status_code == 200
    assert "definition_snapshot" not in list_response.data["content"][0]
    assert detail_response.status_code == 200
    assert detail_response.data["content"]["definition_snapshot"] == flow_run.definition_snapshot