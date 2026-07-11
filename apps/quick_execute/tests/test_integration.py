"""
集成测试 - 验证架构一致性和执行逻辑
"""
import pytest
from unittest.mock import MagicMock, patch

from apps.agents.execution_service import AgentExecutionService
from apps.quick_execute.services import QuickExecuteService


pytestmark = pytest.mark.django_db


@pytest.fixture()
def user():
    u = MagicMock()
    u.username = "test_user"
    return u


def test_parameter_unification_script_execution(user):
    """测试脚本执行的参数统一性"""
    script_data = {
        "script_content": 'echo "test"',
        "script_type": "shell",
        "timeout": 300,
        "global_variables": {"account_id": 123},
        "target_host_ids": [1, 2, 3],
        "agent_server_id": 1,
    }

    # 提取参数
    execution_params = QuickExecuteService._extract_execution_params(script_data)

    # 验证参数正确提取
    assert execution_params["account_id"] == 123
    assert execution_params["timeout"] == 300

    # 验证参数在后续处理中被正确使用
    with patch("apps.quick_execute.services.QuickExecuteService._get_target_hosts_from_data") as mock_hosts:
        host = MagicMock()
        host.id = 1
        host.name = "host-1"
        host.ip_address = "127.0.0.1"
        mock_hosts.return_value = [host]

        with patch("apps.quick_execute.services.AgentExecutionService.execute_script_via_agent") as mock_execute:
            mock_execute.return_value = {"success": True, "success_count": 2, "failed_count": 1, "results": []}

            with patch("apps.quick_execute.services.ExecutionRecordService.create_execution_record") as mock_create:
                mock_record = MagicMock()
                mock_record.execution_id = "test-123"
                mock_record.id = 123
                mock_record.execution_parameters = {}
                mock_record.execution_results = {}
                mock_record.save = MagicMock()
                mock_create.return_value = mock_record

                with patch("apps.quick_execute.services.ExecutionRecordService.update_execution_status") as mock_update:
                    result = QuickExecuteService.execute_script(user, script_data)
                    assert mock_update

                saved_params = mock_create.call_args.kwargs["execution_parameters"]
                assert saved_params["execution_backend"] == "agent"
                assert saved_params["execution_mode"] == "parallel"
                assert "agent_server_id" not in saved_params
                # 验证execute_script_via_agent被调用时使用了提取的参数
                mock_execute.assert_called_once()
                call_args = mock_execute.call_args
                assert call_args.kwargs["timeout"] == 300
                assert "agent_server_id" not in call_args.kwargs
                assert result["success"] is True


def test_parameter_unification_file_transfer():
    """测试文件传输的参数统一性"""
    transfer_data = {
        "local_path": "/tmp/test.txt",
        "remote_path": "/tmp/test.txt",
        "timeout": 600,
        "bandwidth_limit": 2,
        "target_host_ids": [1, 2],
        "agent_server_id": 1,
        "sources": [
            {
                "type": "local",
                "file_field": "file1",
                "remote_path": "/tmp/test.txt",
            }
        ],
    }

    # 提取参数
    execution_params = QuickExecuteService._extract_execution_params(transfer_data, ["timeout", "bandwidth_limit"])

    # 验证参数正确提取和转换
    assert execution_params["timeout"] == 600
    assert execution_params["bandwidth_limit"] == 2


def test_agent_architecture_consistency(user):
    """测试Agent架构一致性 - 确保所有执行都通过Agent"""
    # 这个测试验证没有直接SSH调用的代码路径
    # 我们通过检查代码中是否还有绕过Agent的SSH调用

    # 测试脚本执行
    with patch("apps.quick_execute.services.QuickExecuteService._get_target_hosts_from_data") as mock_hosts:
        host = MagicMock()
        host.id = 1
        host.name = "host-1"
        host.ip_address = "127.0.0.1"
        mock_hosts.return_value = [host]

        with patch("apps.quick_execute.services.AgentExecutionService.execute_script_via_agent") as mock_execute:
            mock_execute.return_value = {"success": True, "success_count": 1, "failed_count": 0, "results": []}

            script_data = {
                "script_content": 'echo "test"',
                "script_type": "shell",
                "target_host_ids": [1],
                "agent_server_id": 1,
            }

            with patch("apps.quick_execute.services.ExecutionRecordService.create_execution_record") as mock_create:
                mock_record = MagicMock()
                mock_record.execution_id = "test-123"
                mock_record.id = 123
                mock_record.execution_parameters = {}
                mock_record.execution_results = {}
                mock_record.save = MagicMock()
                mock_create.return_value = mock_record

                with patch("apps.quick_execute.services.ExecutionRecordService.update_execution_status") as mock_update:
                    result = QuickExecuteService.execute_script(user, script_data)
                    assert mock_update

                # 验证通过Agent执行，而不是直接SSH
                mock_execute.assert_called_once()
                assert result["success"] is True


def test_workflow_server_type_removal():
    """测试工作流中server类型已被移除"""
    # 这个测试验证execute_workflow_via_agent不再支持server类型的文件传输

    with patch("apps.agents.execution_service.ExecutionRecordService.create_execution_step") as mock_create_step:
        with patch("apps.agents.execution_service.ExecutionRecordService.update_step_status") as mock_update:
            with patch("apps.agents.execution_service.ExecutionRecordService.update_execution_status") as mock_update_exec:

                mock_step = MagicMock()
                mock_step.id = 123
                mock_create_step.return_value = mock_step

                execution_record = MagicMock()
                execution_record.execution_id = "test-123"

                plan_steps = [
                    {
                        "step_name": "Test Step",
                        "step_type": "file_transfer",
                        "file_sources": [
                            {
                                "type": "server",  # 这个类型应该被拒绝
                                "remote_path": "/tmp/test.txt",
                            }
                        ],
                        "ignore_error": False,
                    }
                ]

                target_hosts = [MagicMock()]
                target_hosts[0].id = 1

                # 调用工作流执行
                result = AgentExecutionService.execute_workflow_via_agent(execution_record, plan_steps, target_hosts)

                # 验证结果失败，因为server类型不被支持
                assert result["success"] is False

                # 避免unused-variable警告
                assert mock_update
                assert mock_update_exec


def test_log_field_consistency():
    """测试日志字段命名一致性"""
    # 测试consume_streams正确处理log_type字段

    from apps.agents.management.commands import consume_streams

    fields_with_log_type = {
        "execution_id": "123",
        "task_id": "test-123_1_1_abc",
        "log_type": "stdout",
        "stream": "stderr",  # 这个应该被忽略
        "content": "test log",
        "timestamp": 1234567890.123,
    }

    with patch("apps.agents.management.commands.consume_streams._store_log") as mock_store:
        ok = consume_streams.Command.handle_log("1-0", fields_with_log_type)
        assert ok is True
        mock_store.assert_called_once()
        stored = mock_store.call_args.args[0]
        assert stored["log_type"] == "stdout"




def test_result_consumer_routes_by_task_id():
    """结果流必须把完整 task_id 交给任务结果处理器。"""
    from apps.agents.management.commands import consume_streams

    fields = {
        "execution_id": "123456",
        "task_id": "123456_9_7_abcd",
        "status": "success",
        "exit_code": "0",
        "progress": "100",
    }

    with patch("apps.agents.management.commands.consume_streams._flush_log_store"), patch(
        "apps.agents.management.commands.consume_streams.AgentExecutionService.handle_task_result",
        return_value={"success": True},
    ) as handle_result:
        ok = consume_streams.Command.handle_result("1-0", fields)

    assert ok is True
    assert handle_result.call_args.kwargs["task_id"] == fields["task_id"]


def test_quick_file_transfer_uses_valid_type_and_terminal_status(user):
    """同步等待 Agent 返回后，文件传输必须写入真实终态。"""
    host = MagicMock(id=7, name="host-7", ip_address="127.0.0.7")
    record = MagicMock()
    record.execution_id = 123456
    record.id = 42
    record.execution_parameters = {}

    transfer_data = {
        "transfer_name": "package",
        "target_host_ids": [host.id],
        "agent_server_id": 1,
        "sources": [{
            "type": "server",
            "source_server_host": "files.internal",
            "source_server_path": "/release/app.tar.gz",
            "remote_path": "/opt/app.tar.gz",
        }],
    }
    artifact = {
        "type": "artifact",
        "download_url": "https://files.internal/app.tar.gz",
        "sha256": "abc",
        "size": 10,
        "remote_path": "/opt/app.tar.gz",
    }

    with patch(
        "apps.quick_execute.services.QuickExecuteService._get_target_hosts_from_data",
        return_value=[host],
    ), patch(
        "apps.quick_execute.services.AgentExecutionService._fetch_server_source_to_artifact_http",
        return_value=artifact,
    ), patch(
        "apps.quick_execute.services.AgentExecutionService.execute_file_transfer_via_agent",
        return_value={"success": True, "success_count": 1, "failed_count": 0, "results": []},
    ), patch(
        "apps.quick_execute.services.ExecutionRecordService.create_execution_record",
        return_value=record,
    ) as create_record, patch(
        "apps.quick_execute.services.ExecutionRecordService.update_execution_status",
    ) as update_status:
        result = QuickExecuteService.transfer_file(user, transfer_data)

    assert create_record.call_args.kwargs["execution_type"] == "quick_file_transfer"
    assert update_status.call_args.kwargs["status"] == "success"
    assert result["status"] == "success"
    saved_params = create_record.call_args.kwargs["execution_parameters"]
    assert saved_params["execution_backend"] == "agent"
    assert "agent_server_id" not in saved_params

def test_retry_parameter_handling(user):
    """测试重试参数处理"""
    execution_record = MagicMock()
    execution_record.execution_type = "quick_script"
    execution_record.execution_parameters = {
        "script_content": 'echo "retry test"',
        "script_type": "shell",
        "target_host_ids": [1, 2],
        "timeout": 300,
    }

    # 测试基于IP的重试
    root_execution = MagicMock()
    root_execution.retry_count = 0
    root_execution.max_retries = 3
    root_execution.total_retry_count = 1
    root_execution.name = "root"
    root_execution.save = MagicMock()
    execution_record.get_root_execution.return_value = root_execution

    with patch("apps.agents.execution_service.ExecutionRecord") as mock_execution_model:
        mock_execution_model.objects.filter.return_value.select_for_update.return_value.count.return_value = 0
        mock_execution_model.objects.filter.return_value.exclude.return_value.update.return_value = 1
        new_execution = MagicMock()
        new_execution.id = 456
        new_execution.execution_id = "exec-new"
        new_execution.save = MagicMock()
        mock_execution_model.objects.get.return_value = new_execution

        with patch("apps.quick_execute.services.QuickExecuteService.execute_script") as mock_execute:
            mock_execute.return_value = {"success": True, "execution_record_id": 456}

            result = AgentExecutionService.retry_execution_record(
                execution_record, user, retry_type="full", ip_list=["192.168.1.1"]
            )

            # 验证成功（因为没有其他验证逻辑）
            assert result["success"] is True


def test_concurrent_retry_limit(user):
    """测试并发重试限制"""
    execution_record = MagicMock()
    execution_record.execution_type = "quick_script"

    # 模拟达到并发限制
    root_execution = MagicMock()
    root_execution.retry_count = 0
    root_execution.max_retries = 3
    root_execution.total_retry_count = 1
    root_execution.save = MagicMock()
    execution_record.get_root_execution.return_value = root_execution

    with patch("apps.agents.execution_service.ExecutionRecord") as mock_execution_model:
        mock_execution_model.objects.filter.return_value.select_for_update.return_value.count.return_value = 15

        result = AgentExecutionService.retry_execution_record(execution_record, user)

        # 验证失败并带有提示信息
        assert result["success"] is False
        assert "并发" in result["error"]


def test_quick_file_transfer_accepts_trusted_retry_artifacts(user, monkeypatch):
    """重试应复用已落库 artifact，不能再次按公开 sources 解析。"""
    monkeypatch.setenv("E2E_CONTROL_PLANE", "1")
    host = MagicMock(id=7, name="host-7", ip_address="127.0.0.7")
    record = MagicMock(
        execution_id=123456,
        id=42,
        execution_parameters={},
        execution_results={},
    )
    artifact = {
        "type": "artifact",
        "download_url": "https://storage.internal/signed/app.tar.gz",
        "sha256": "abc",
        "size": 10,
        "remote_path": "/opt/app.tar.gz",
        "auth_headers": {"Authorization": "signed"},
    }

    with patch(
        "apps.quick_execute.services.QuickExecuteService._get_target_hosts_from_data",
        return_value=[host],
    ), patch(
        "apps.quick_execute.services.AgentExecutionService.execute_file_transfer_via_agent",
        return_value={"success": True, "success_count": 1, "failed_count": 0, "results": []},
    ) as execute_transfer, patch(
        "apps.quick_execute.services.ExecutionRecordService.create_execution_record",
        return_value=record,
    ), patch(
        "apps.quick_execute.services.ExecutionRecordService.update_execution_status",
    ):
        result = QuickExecuteService.transfer_file(
            user,
            {
                "target_host_ids": [host.id],
                "agent_server_id": 1,
                "artifact_sources": [artifact],
            },
        )

    assert result["success"] is True
    assert execute_transfer.call_args.kwargs["download_url"] == artifact["download_url"]
    assert record.execution_parameters["file_sources"] == [artifact]


def test_quick_file_transfer_retry_passes_internal_artifacts(user):
    execution_record = MagicMock()
    execution_record.execution_type = "quick_file_transfer"
    execution_record.execution_parameters = {
        "file_sources": [{
            "type": "artifact",
            "download_url": "https://storage.internal/signed/app.tar.gz",
            "remote_path": "/opt/app.tar.gz",
        }],
        "target_host_ids": [7],
    }
    root_execution = MagicMock(retry_count=0, max_retries=3, total_retry_count=1)
    execution_record.get_root_execution.return_value = root_execution

    with patch("apps.agents.execution_service.ExecutionRecord") as execution_model, patch(
        "apps.quick_execute.services.QuickExecuteService.transfer_file",
        return_value={"success": True, "execution_record_id": 456},
    ) as transfer_file:
        execution_model.objects.filter.return_value.select_for_update.return_value.count.return_value = 0
        execution_model.objects.filter.return_value.exclude.return_value.update.return_value = 1
        execution_model.objects.get.return_value = MagicMock(id=456, execution_id="exec-new")

        result = AgentExecutionService.retry_execution_record(execution_record, user)

    assert result["success"] is True
    transfer_data = transfer_file.call_args.kwargs["transfer_data"]
    assert transfer_data["artifact_sources"] == execution_record.execution_parameters["file_sources"]
    assert "file_sources" not in transfer_data


def test_quick_execute_serializers_route_by_target_agent_binding():
    from apps.quick_execute.serializers import (
        QuickFileTransferSerializer,
        QuickScriptExecuteSerializer,
    )

    script = QuickScriptExecuteSerializer(data={
        "script_content": "echo ok",
        "target_host_ids": [1],
    })
    transfer = QuickFileTransferSerializer(data={
        "sources": [{
            "type": "server",
            "source_server_host": "files.internal",
            "source_server_path": "/release/app.tar.gz",
            "account_id": 1,
            "remote_path": "/opt/app.tar.gz",
        }],
        "target_host_ids": [1],
    })

    assert script.is_valid(), script.errors
    assert transfer.is_valid(), transfer.errors
    assert "agent_server_id" not in script.validated_data
    assert "agent_server_id" not in transfer.validated_data


def test_cancel_routes_through_each_target_agent_binding():
    record = MagicMock(execution_id=123456, execution_parameters={})
    step = MagicMock(host_results=[{"task_id": "task-1", "host_id": 7}])
    agent = MagicMock(host_id=7, agent_uid="00000000-0000-4000-8000-000000000007", agent_server_id=3)
    host = MagicMock(agent=agent)

    with patch(
        "apps.agents.execution_service.ExecutionStep.objects.filter",
        return_value=[step],
    ), patch(
        "apps.agents.execution_service.Host.objects.get",
        return_value=host,
    ), patch.object(
        AgentExecutionService,
        "_cancel_tasks_via_agent_server",
        return_value={"success": True},
    ) as cancel_tasks:
        result = AgentExecutionService.cancel_task_via_agent(record)

    assert result["success"] is True
    assert set(cancel_tasks.call_args.kwargs) == {"agent_task_map"}
    assert cancel_tasks.call_args.kwargs["agent_task_map"]["00000000-0000-4000-8000-000000000007"]["agent"] is agent
