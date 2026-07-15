import pytest

from apps.flows.secret_service import decrypt_flow_secret_values, encrypt_flow_secret_values, mask_flow_secret_values


def test_flow_secret_values_encrypt_decrypt_and_mask_without_plaintext_leakage():
    values = {"ApiToken": "token-value", "Password": "p@ss"}

    encrypted = encrypt_flow_secret_values(values)

    assert encrypted != values
    assert all(value not in encrypted.values() for value in values.values())
    assert decrypt_flow_secret_values(encrypted) == values
    assert mask_flow_secret_values({"Region": "sh", **values}, values.keys()) == {
        "Region": "sh",
        "ApiToken": "****",
        "Password": "****",
    }


def test_flow_secret_values_fail_closed_for_invalid_ciphertext():
    with pytest.raises(RuntimeError, match="密文变量"):
        decrypt_flow_secret_values({"ApiToken": "not-a-ciphertext"})
from django.contrib.auth.models import User
from rest_framework.test import APIClient

from apps.flows.models import FlowNode, FlowTemplate
from apps.flows.services import FlowRunner
from apps.hosts.models import Host


@pytest.mark.django_db
def test_flow_template_secret_default_is_encrypted_and_never_returned_by_api():
    user = User.objects.create_user("flow-secret-template", password="pass")
    client = APIClient()
    client.force_authenticate(user)

    response = client.post(
        "/api/flows/templates/",
        {
            "name": "flow-secret-template",
            "variables": {
                "ApiToken": {
                    "name": "API Token",
                    "type": "password",
                    "widget": "password",
                    "default": "token-value",
                }
            },
        },
        format="json",
    )

    assert response.status_code == 200
    template = FlowTemplate.objects.get(pk=response.data["content"]["id"])
    assert template.variables["ApiToken"].get("default") is None
    assert template.variables["ApiToken"]["has_default"] is True
    assert decrypt_flow_secret_values(template.encrypted_secret_defaults) == {"ApiToken": "token-value"}
    assert "token-value" not in str(response.data)
    assert response.data["content"]["variables"]["ApiToken"]["has_default"] is True


@pytest.mark.django_db
def test_flow_run_masks_secret_inputs_but_dispatches_the_actual_secret_value():
    user = User.objects.create_user("flow-secret-run", password="pass")
    host = Host.objects.create(name="flow-secret-host", os_type="linux", device_type="physical", created_by=user)
    template = FlowTemplate.objects.create(
        name="flow-secret-run",
        created_by=user,
        variables={
            "CheckHost": {"type": "host_list", "required": True},
            "ApiToken": {"type": "password", "widget": "password", "required": True},
        },
    )
    node = FlowNode.objects.create(
        template=template,
        uuid="script",
        name="script",
        node_type=FlowNode.NodeType.SCRIPT,
        config={
            "target_host_ids": "${CheckHost}",
            "script_content": "deploy --token=${ApiToken}",
        },
    )

    from unittest.mock import patch

    with patch(
        "apps.agents.execution_service.AgentExecutionService.execute_script_via_agent",
        return_value={"success": True, "success_count": 1, "failed_count": 0, "results": []},
    ) as execute_script:
        flow_run = FlowRunner.start(
            template=template,
            user=user,
            inputs={"CheckHost": [host.id], "ApiToken": "runtime-token"},
        )

    flow_run.refresh_from_db()
    node_run = flow_run.node_runs.get(node=node)
    assert flow_run.inputs["ApiToken"] == "****"
    assert decrypt_flow_secret_values(flow_run.encrypted_secret_inputs) == {"ApiToken": "runtime-token"}
    assert "runtime-token" not in str(node_run.inputs)
    assert execute_script.call_args.kwargs["script_content"] == "deploy --token=runtime-token"
    assert execute_script.call_args.kwargs["global_variables"]["ApiToken"] == "runtime-token"
@pytest.mark.django_db
def test_flow_schedule_masks_secret_input_and_restores_it_only_when_starting():
    from unittest.mock import patch

    from apps.flows.models import FlowSchedule
    from apps.flows.schedule_service import execute_flow_schedule

    user = User.objects.create_user("flow-secret-schedule", password="pass")
    template = FlowTemplate.objects.create(
        name="flow-secret-schedule",
        created_by=user,
        variables={"ApiToken": {"type": "password", "widget": "password", "required": True}},
    )
    schedule = FlowSchedule.objects.create(
        name="flow-secret-schedule",
        template=template,
        cron_expression="0 1 * * *",
        inputs={"ApiToken": "schedule-token"},
        created_by=user,
    )

    assert schedule.inputs == {"ApiToken": "****"}
    assert decrypt_flow_secret_values(schedule.encrypted_secret_inputs) == {"ApiToken": "schedule-token"}
    with patch("apps.flows.schedule_service.FlowRunner.start") as start:
        execute_flow_schedule(schedule.id)

    assert start.call_args.kwargs["inputs"] == {"ApiToken": "schedule-token"}
@pytest.mark.django_db
def test_flow_job_plan_masks_secret_in_execution_record_but_executes_with_it():
    from unittest.mock import patch

    from apps.job_templates.models import ExecutionPlan, JobStep, JobTemplate, PlanStep

    user = User.objects.create_user("flow-secret-plan", password="pass")
    host = Host.objects.create(name="flow-secret-plan-host", os_type="linux", device_type="physical", created_by=user)
    job_template = JobTemplate.objects.create(name="flow-secret-job-template", created_by=user)
    job_step = JobStep.objects.create(
        template=job_template,
        name="job-script",
        step_type="script",
        order=1,
        script_content="echo ${ApiToken}",
    )
    job_step.target_hosts.add(host)
    execution_plan = ExecutionPlan.objects.create(
        template=job_template,
        name="flow-secret-execution-plan",
        created_by=user,
    )
    plan_step = PlanStep.objects.create(plan=execution_plan, step=job_step, order=1)
    plan_step.copy_from_template_step()
    plan_step.save()
    template = FlowTemplate.objects.create(
        name="flow-secret-plan",
        created_by=user,
        variables={"ApiToken": {"type": "password", "widget": "password", "required": True}},
    )
    node = FlowNode.objects.create(
        template=template,
        uuid="job-plan",
        name="job plan",
        node_type=FlowNode.NodeType.JOB_PLAN,
        config={
            "execution_plan_id": execution_plan.id,
            "execution_parameter_bindings": {"ApiToken": "${ApiToken}"},
        },
    )

    with patch(
        "apps.agents.execution_service.AgentExecutionService.execute_workflow_via_agent",
        return_value={"success": True},
    ):
        flow_run = FlowRunner.start(template=template, user=user, inputs={"ApiToken": "plan-token"})

    node_run = flow_run.node_runs.get(node=node)
    node_run.execution_record.refresh_from_db()
    assert node_run.execution_record.execution_parameters["ApiToken"] == "****"
    assert "plan-token" not in str(node_run.inputs)
@pytest.mark.django_db
def test_copying_flow_template_preserves_encrypted_secret_defaults_without_exposing_them():
    user = User.objects.create_user("flow-secret-copy", password="pass")
    template = FlowTemplate.objects.create(
        name="flow-secret-copy",
        created_by=user,
        variables={"ApiToken": {"type": "password", "default": "copy-token"}},
    )
    client = APIClient()
    client.force_authenticate(user)

    response = client.post(
        f"/api/flows/templates/{template.id}/copy/",
        {"name": "flow-secret-copy-target"},
        format="json",
    )

    copied = FlowTemplate.objects.get(pk=response.data["content"]["id"])
    assert decrypt_flow_secret_values(copied.encrypted_secret_defaults) == {"ApiToken": "copy-token"}
    assert "copy-token" not in str(response.data)
@pytest.mark.django_db
def test_retry_reconstructs_secret_config_without_persisting_plaintext():
    from unittest.mock import patch

    user = User.objects.create_user("flow-secret-retry", password="pass")
    host = Host.objects.create(name="flow-secret-retry-host", os_type="linux", device_type="physical", created_by=user)
    template = FlowTemplate.objects.create(
        name="flow-secret-retry",
        created_by=user,
        variables={
            "CheckHost": {"type": "host_list", "required": True},
            "ApiToken": {"type": "password", "required": True},
        },
    )
    node = FlowNode.objects.create(
        template=template,
        uuid="retry-script",
        name="retry script",
        node_type=FlowNode.NodeType.SCRIPT,
        config={"target_host_ids": "${CheckHost}", "script_content": "deploy ${ApiToken}"},
    )

    with patch(
        "apps.agents.execution_service.AgentExecutionService.execute_script_via_agent",
        return_value={"success": False, "success_count": 0, "failed_count": 1, "results": []},
    ):
        flow_run = FlowRunner.start(
            template=template,
            user=user,
            inputs={"CheckHost": [host.id], "ApiToken": "retry-token"},
        )

    node_run = flow_run.node_runs.get(node=node)
    with patch(
        "apps.agents.execution_service.AgentExecutionService.execute_script_via_agent",
        return_value={"success": True, "success_count": 1, "failed_count": 0, "results": []},
    ) as execute_script:
        FlowRunner.retry_node(flow_run, node_run, user=user)

    node_run.refresh_from_db()
    assert node_run.status == "success"
    assert "retry-token" not in str(node_run.inputs)
    assert execute_script.call_args.kwargs["script_content"] == "deploy retry-token"


@pytest.mark.django_db
def test_sub_process_inherits_secret_at_runtime_without_exposing_it_in_child_run():
    from unittest.mock import patch

    user = User.objects.create_user("flow-secret-sub-process", password="pass")
    host = Host.objects.create(name="flow-secret-sub-host", os_type="linux", device_type="physical", created_by=user)
    child = FlowTemplate.objects.create(
        name="flow-secret-child",
        created_by=user,
        variables={
            "CheckHost": {"type": "host_list", "required": True},
            "ApiToken": {"type": "password", "required": True},
        },
    )
    FlowNode.objects.create(
        template=child,
        uuid="child-script",
        name="child script",
        node_type=FlowNode.NodeType.SCRIPT,
        config={"target_host_ids": "${CheckHost}", "script_content": "child ${ApiToken}"},
    )
    parent = FlowTemplate.objects.create(
        name="flow-secret-parent",
        created_by=user,
        variables={
            "CheckHost": {"type": "host_list", "required": True},
            "ApiToken": {"type": "password", "required": True},
        },
    )
    parent_node = FlowNode.objects.create(
        template=parent,
        uuid="sub-process",
        name="sub process",
        node_type=FlowNode.NodeType.SUB_PROCESS,
        config={"template_id": child.id, "inherit_inputs": True},
    )

    with patch(
        "apps.agents.execution_service.AgentExecutionService.execute_script_via_agent",
        return_value={"success": True, "success_count": 1, "failed_count": 0, "results": []},
    ) as execute_script:
        parent_run = FlowRunner.start(
            template=parent,
            user=user,
            inputs={"CheckHost": [host.id], "ApiToken": "child-token"},
        )

    parent_node_run = parent_run.node_runs.get(node=parent_node)
    child_run = FlowTemplate.objects.get(pk=child.id).runs.get()
    assert parent_run.inputs["ApiToken"] == "****"
    assert child_run.inputs["ApiToken"] == "****"
    assert "child-token" not in str(parent_node_run.inputs)
    assert execute_script.call_args.kwargs["script_content"] == "child child-token"
@pytest.mark.django_db
def test_file_node_execution_record_masks_secret_file_source_values():
    from unittest.mock import patch

    user = User.objects.create_user("flow-secret-file", password="pass")
    host = Host.objects.create(name="flow-secret-file-host", os_type="linux", device_type="physical", created_by=user)
    template = FlowTemplate.objects.create(
        name="flow-secret-file",
        created_by=user,
        variables={
            "CheckHost": {"type": "host_list", "required": True},
            "ApiToken": {"type": "password", "required": True},
        },
    )
    node = FlowNode.objects.create(
        template=template,
        uuid="file-node",
        name="file node",
        node_type=FlowNode.NodeType.FILE_TRANSFER,
        config={
            "target_host_ids": "${CheckHost}",
            "file_sources": [
                {
                    "type": "artifact",
                    "download_url": "https://example.test/package?token=${ApiToken}",
                    "remote_path": "/tmp/package",
                    "auth_headers": {"Authorization": "Bearer ${ApiToken}"},
                }
            ],
        },
    )

    with patch(
        "apps.agents.execution_service.AgentExecutionService.execute_file_transfer_via_agent",
        return_value={"success": True, "success_count": 1, "failed_count": 0, "results": []},
    ) as transfer:
        flow_run = FlowRunner.start(
            template=template,
            user=user,
            inputs={"CheckHost": [host.id], "ApiToken": "file-token"},
        )

    node_run = flow_run.node_runs.get(node=node)
    node_run.execution_record.refresh_from_db()
    assert "file-token" not in str(node_run.execution_record.execution_parameters)
    assert transfer.call_args.kwargs["download_url"] == "https://example.test/package?token=file-token"
    assert transfer.call_args.kwargs["auth_headers"] == {"Authorization": "Bearer file-token"}