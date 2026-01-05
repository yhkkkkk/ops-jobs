"""
QuickExecuteService 单元测试
"""
import unittest
from unittest.mock import patch, MagicMock
from apps.quick_execute.services import QuickExecuteService


class TestQuickExecuteService(unittest.TestCase):
    """QuickExecuteService 测试类"""

    def test_extract_execution_params_default(self):
        """测试默认参数提取"""
        data = {}
        params = QuickExecuteService._extract_execution_params(data)

        self.assertIsNone(params['account_id'])
        self.assertEqual(params['bandwidth_limit'], 0)
        self.assertIsInstance(params['timeout'], int)  # 应该有默认值

    def test_extract_execution_params_account_id_from_root(self):
        """测试从根层级提取account_id"""
        data = {'account_id': 123}
        params = QuickExecuteService._extract_execution_params(data, ['account_id'])

        self.assertEqual(params['account_id'], 123)

    def test_extract_execution_params_account_id_from_global_variables(self):
        """测试从global_variables提取account_id"""
        data = {'global_variables': {'account_id': 456}}
        params = QuickExecuteService._extract_execution_params(data, ['account_id'])

        self.assertEqual(params['account_id'], 456)

    def test_extract_execution_params_account_id_priority(self):
        """测试account_id提取优先级（根层级优先）"""
        data = {
            'account_id': 123,
            'global_variables': {'account_id': 456}
        }
        params = QuickExecuteService._extract_execution_params(data, ['account_id'])

        self.assertEqual(params['account_id'], 123)

    def test_extract_execution_params_bandwidth_limit_kbps(self):
        """测试带宽限制KB/s格式"""
        data = {'bandwidth_limit': '1024kbps'}
        params = QuickExecuteService._extract_execution_params(data, ['bandwidth_limit'])

        self.assertEqual(params['bandwidth_limit'], 1024)

    def test_extract_execution_params_bandwidth_limit_mbps(self):
        """测试带宽限制MB/s格式"""
        data = {'bandwidth_limit': '2mbps'}
        params = QuickExecuteService._extract_execution_params(data, ['bandwidth_limit'])

        self.assertEqual(params['bandwidth_limit'], 2048)  # 2MB/s = 2048KB/s

    def test_extract_execution_params_bandwidth_limit_numeric(self):
        """测试带宽限制数字格式"""
        data = {'bandwidth_limit': 512}
        params = QuickExecuteService._extract_execution_params(data, ['bandwidth_limit'])

        self.assertEqual(params['bandwidth_limit'], 512)

    def test_extract_execution_params_bandwidth_limit_invalid(self):
        """测试无效带宽限制值"""
        data = {'bandwidth_limit': 'invalid'}
        params = QuickExecuteService._extract_execution_params(data, ['bandwidth_limit'])

        self.assertEqual(params['bandwidth_limit'], 0)

    def test_extract_execution_params_timeout_valid(self):
        """测试有效timeout值"""
        data = {'timeout': 600}
        params = QuickExecuteService._extract_execution_params(data, ['timeout'])

        self.assertEqual(params['timeout'], 600)

    def test_extract_execution_params_timeout_string(self):
        """测试字符串timeout值"""
        data = {'timeout': '300'}
        params = QuickExecuteService._extract_execution_params(data, ['timeout'])

        self.assertEqual(params['timeout'], 300)

    @patch('apps.quick_execute.services.ConfigManager')
    def test_extract_execution_params_timeout_default(self, mock_config):
        """测试timeout默认值"""
        mock_config.get.return_value = 450  # 默认超时时间

        data = {}  # 没有指定timeout
        params = QuickExecuteService._extract_execution_params(data, ['timeout'])

        self.assertEqual(params['timeout'], 450)

    def test_extract_execution_params_timeout_invalid(self):
        """测试无效timeout值"""
        data = {'timeout': 'invalid'}
        params = QuickExecuteService._extract_execution_params(data, ['timeout'])

        # 应该使用默认值
        self.assertIsInstance(params['timeout'], int)
        self.assertGreater(params['timeout'], 0)

    def test_extract_execution_params_partial_types(self):
        """测试部分参数类型提取"""
        data = {
            'account_id': 123,
            'bandwidth_limit': 512,
            'timeout': 600,
            'other_param': 'ignored'
        }

        # 只提取account_id
        params = QuickExecuteService._extract_execution_params(data, ['account_id'])
        self.assertEqual(params['account_id'], 123)
        self.assertNotIn('bandwidth_limit', params)
        self.assertNotIn('timeout', params)

    def test_extract_execution_params_bandwidth_limit_direct_mb(self):
        """测试bandwidth_limit直接使用前端MB/s值"""
        data = {'bandwidth_limit': 5}  # 前端传递的5表示5MB/s
        params = QuickExecuteService._extract_execution_params(data, ['bandwidth_limit'])

        # 应该直接返回5，不进行任何转换
        self.assertEqual(params['bandwidth_limit'], 5)

    def test_extract_execution_params_bandwidth_limit_float(self):
        """测试bandwidth_limit浮点数转换"""
        data = {'bandwidth_limit': 2.5}
        params = QuickExecuteService._extract_execution_params(data, ['bandwidth_limit'])

        # 应该转换为整数
        self.assertEqual(params['bandwidth_limit'], 2)

    def test_extract_execution_params_bandwidth_limit_zero(self):
        """测试bandwidth_limit为0的情况"""
        data = {'bandwidth_limit': 0}
        params = QuickExecuteService._extract_execution_params(data, ['bandwidth_limit'])

        self.assertEqual(params['bandwidth_limit'], 0)

    def test_extract_execution_params_bandwidth_limit_none(self):
        """测试bandwidth_limit为None的情况"""
        data = {'bandwidth_limit': None}
        params = QuickExecuteService._extract_execution_params(data, ['bandwidth_limit'])

        self.assertEqual(params['bandwidth_limit'], 0)

    def test_extract_execution_params_bandwidth_limit_invalid_string(self):
        """测试bandwidth_limit无效字符串的情况"""
        data = {'bandwidth_limit': 'invalid'}
        params = QuickExecuteService._extract_execution_params(data, ['bandwidth_limit'])

        # 应该返回0，不抛出异常
        self.assertEqual(params['bandwidth_limit'], 0)

        # 只提取bandwidth_limit
        params = QuickExecuteService._extract_execution_params(data, ['bandwidth_limit'])
        self.assertEqual(params['bandwidth_limit'], 512)
        self.assertNotIn('account_id', params)
        self.assertNotIn('timeout', params)


if __name__ == '__main__':
    unittest.main()
