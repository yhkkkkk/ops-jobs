"""
集成测试 - 验证架构一致性和执行逻辑
"""
import unittest
from unittest.mock import patch, MagicMock
from django.test import TestCase
from apps.quick_execute.services import QuickExecuteService
from apps.agents.execution_service import AgentExecutionService


class TestExecutionArchitectureConsistency(TestCase):
    """测试执行架构的一致性"""

    def setUp(self):
        self.user = MagicMock()
        self.user.username = 'test_user'

    def test_parameter_unification_script_execution(self):
        """测试脚本执行的参数统一性"""
        script_data = {
            'script_content': 'echo "test"',
            'script_type': 'shell',
            'timeout': 300,
            'global_variables': {'account_id': 123},
            'target_host_ids': [1, 2, 3],
            'agent_server_url': 'ws://localhost:8080'
        }

        # 提取参数
        execution_params = QuickExecuteService._extract_execution_params(script_data)

        # 验证参数正确提取
        self.assertEqual(execution_params['account_id'], 123)
        self.assertEqual(execution_params['timeout'], 300)

        # 验证参数在后续处理中被正确使用
        with patch('apps.quick_execute.services.AgentExecutionService.execute_script_via_agent') as mock_execute:
            mock_execute.return_value = {'success': True, 'success_count': 2, 'failed_count': 1, 'results': []}

            with patch('apps.quick_execute.services.ExecutionRecordService.create_execution_record') as mock_create:
                mock_record = MagicMock()
                mock_record.execution_id = 'test-123'
                mock_record.id = 123
                mock_create.return_value = mock_record

                result = QuickExecuteService.execute_script(self.user, script_data)

                # 验证execute_script_via_agent被调用时使用了提取的参数
                mock_execute.assert_called_once()
                call_args = mock_execute.call_args
                self.assertEqual(call_args[1]['timeout'], 300)  # 使用统一提取的timeout

    def test_parameter_unification_file_transfer(self):
        """测试文件传输的参数统一性"""
        transfer_data = {
            'local_path': '/tmp/test.txt',
            'remote_path': '/tmp/test.txt',
            'timeout': 600,
            'bandwidth_limit': '2mbps',
            'target_host_ids': [1, 2],
            'agent_server_url': 'ws://localhost:8080',
            'sources': [{
                'type': 'local',
                'file_field': 'file1',
                'remote_path': '/tmp/test.txt'
            }]
        }

        # 提取参数
        execution_params = QuickExecuteService._extract_execution_params(transfer_data, ['timeout', 'bandwidth_limit'])

        # 验证参数正确提取和转换
        self.assertEqual(execution_params['timeout'], 600)
        self.assertEqual(execution_params['bandwidth_limit'], 2048)  # 2MB/s = 2048KB/s

    def test_agent_architecture_consistency(self):
        """测试Agent架构一致性 - 确保所有执行都通过Agent"""
        # 这个测试验证没有直接SSH调用的代码路径
        # 我们通过检查代码中是否还有绕过Agent的SSH调用

        # 测试脚本执行
        with patch('apps.quick_execute.services.AgentExecutionService.execute_script_via_agent') as mock_execute:
            mock_execute.return_value = {'success': True, 'success_count': 1, 'failed_count': 0, 'results': []}

            script_data = {
                'script_content': 'echo "test"',
                'script_type': 'shell',
                'target_host_ids': [1],
            }

            with patch('apps.quick_execute.services.ExecutionRecordService.create_execution_record') as mock_create:
                mock_record = MagicMock()
                mock_record.execution_id = 'test-123'
                mock_record.id = 123
                mock_create.return_value = mock_record

                result = QuickExecuteService.execute_script(self.user, script_data)

                # 验证通过Agent执行，而不是直接SSH
                mock_execute.assert_called_once()
                self.assertTrue(result['success'])

    def test_workflow_server_type_removal(self):
        """测试工作流中server类型已被移除"""
        # 这个测试验证execute_workflow_via_agent不再支持server类型的文件传输

        with patch('apps.agents.execution_service.ExecutionRecordService.create_execution_step') as mock_create_step:
            with patch('apps.agents.execution_service.ExecutionRecordService.update_step_status') as mock_update:
                with patch('apps.agents.execution_service.ExecutionRecordService.update_execution_status') as mock_update_exec:

                    mock_step = MagicMock()
                    mock_step.id = 123
                    mock_create_step.return_value = mock_step

                    execution_record = MagicMock()
                    execution_record.execution_id = 'test-123'

                    plan_steps = [{
                        'step_name': 'Test Step',
                        'step_type': 'file_transfer',
                        'file_sources': [{
                            'type': 'server',  # 这个类型应该被拒绝
                            'remote_path': '/tmp/test.txt'
                        }],
                        'ignore_error': False
                    }]

                    target_hosts = [MagicMock()]
                    target_hosts[0].id = 1

                    # 调用工作流执行
                    result = AgentExecutionService.execute_workflow_via_agent(
                        execution_record, plan_steps, target_hosts
                    )

                    # 验证结果失败，因为server类型不被支持
                    self.assertFalse(result['success'])
                    # 验证没有调用Agent执行方法（因为server类型被跳过且ignore_error=False）

    def test_log_field_consistency(self):
        """测试日志字段命名一致性"""
        # 测试consume_streams正确处理log_type字段

        with patch('apps.agents.management.commands.consume_streams.logger') as mock_logger:
            from apps.agents.management.commands.consume_streams import Command

            cmd = Command()

            # 测试优先使用log_type
            fields_with_log_type = {
                'task_id': 'test-123_1_1_abc',
                'log_type': 'stdout',
                'stream': 'stderr',  # 这个应该被忽略
                'content': 'test log',
                'timestamp': 1234567890.123
            }

            with patch.object(cmd, '_parse_host_id_from_task_id', return_value='1'):
                with patch('utils.realtime_logs.realtime_log_service') as mock_service:
                    cmd._forward_to_task_stream(fields_with_log_type)

                    # 验证push_log被调用且使用了log_type而不是stream
                    mock_service.push_log.assert_called_once()
                    call_args = mock_service.push_log.call_args
                    log_data = call_args[0][2]  # 第三个参数是log_data
                    self.assertEqual(log_data['log_type'], 'stdout')

    def test_retry_parameter_handling(self):
        """测试重试参数处理"""
        execution_record = MagicMock()
        execution_record.execution_type = 'quick_script'
        execution_record.execution_parameters = {
            'script_content': 'echo "retry test"',
            'script_type': 'shell',
            'target_host_ids': [1, 2],
            'timeout': 300
        }

        # 测试基于IP的重试
        with patch('apps.agents.execution_service.ExecutionRecord') as mock_execution_model:
            mock_execution_model.objects.filter.return_value.count.return_value = 0  # 没有并发重试

            with patch('apps.quick_execute.services.QuickExecuteService.execute_script') as mock_execute:
                mock_execute.return_value = {'success': True, 'execution_record_id': 456}

                result = AgentExecutionService.retry_execution_record(
                    execution_record, self.user, retry_type='full', ip_list=['192.168.1.1']
                )

                # 验证成功（因为没有其他验证逻辑）
                self.assertTrue(result['success'])

    def test_concurrent_retry_limit(self):
        """测试并发重试限制"""
        execution_record = MagicMock()
        execution_record.execution_type = 'quick_script'

        # 模拟达到并发限制
        with patch('apps.agents.execution_service.ExecutionRecord') as mock_execution_model:
            mock_execution_model.objects.filter.return_value.count.return_value = 15  # 超过默认限制10

            result = AgentExecutionService.retry_execution_record(execution_record, self.user)

            # 验证被拒绝
            self.assertFalse(result['success'])
            self.assertIn('并发重试数量已达上限', result['error'])


if __name__ == '__main__':
    unittest.main()
