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

                # 验证execute_script_via_agent被调用时使用了提取的参数
                mock_execute.assert_called_once()
                call_args = mock_execute.call_args
                assert call_args.kwargs["timeout"] == 300
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


def test_retry_parameter_handling(user):
    """测试重试参数处理"""
    execution_record = MagicMock()
    execution_record.execution_type = "quick_script"
    execution_record.execution_parameters = {
        "script_content": 'echo "retry test"',
        "script_type": "shell",
        "target_host_ids": [1, 2],
        "timeout": 300,
        "agent_server_id": 1,
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
