"""
测试基础类和工具
"""
from django.test import TestCase, TransactionTestCase
from django.contrib.auth.models import User
from rest_framework.test import APITestCase, APIClient
from rest_framework_simplejwt.tokens import RefreshToken
from django.urls import reverse
import json


class BaseTestCase(TestCase):
    """基础测试类"""
    
    def setUp(self):
        """设置测试数据"""
        self.admin_user = User.objects.create_superuser(
            username='admin',
            email='admin@test.com',
            password='testpass123'
        )
        
        self.normal_user = User.objects.create_user(
            username='testuser',
            email='user@test.com',
            password='testpass123'
        )
    
    def create_test_user(self, username='testuser2', is_staff=False, is_superuser=False):
        """创建测试用户"""
        return User.objects.create_user(
            username=username,
            email=f'{username}@test.com',
            password='testpass123',
            is_staff=is_staff,
            is_superuser=is_superuser
        )


class BaseAPITestCase(APITestCase):
    """API 测试基础类"""
    
    def setUp(self):
        """设置测试数据"""
        self.client = APIClient()
        
        # 创建测试用户
        self.admin_user = User.objects.create_superuser(
            username='admin',
            email='admin@test.com',
            password='testpass123'
        )
        
        self.normal_user = User.objects.create_user(
            username='testuser',
            email='user@test.com',
            password='testpass123'
        )
        
        # 生成 JWT Token
        self.admin_token = self.get_jwt_token(self.admin_user)
        self.user_token = self.get_jwt_token(self.normal_user)
    
    def get_jwt_token(self, user):
        """获取用户的 JWT Token"""
        refresh = RefreshToken.for_user(user)
        return str(refresh.access_token)
    
    def authenticate_admin(self):
        """使用管理员身份认证"""
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.admin_token}')
    
    def authenticate_user(self):
        """使用普通用户身份认证"""
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.user_token}')
    
    def logout(self):
        """退出登录"""
        self.client.credentials()
    
    def assertResponseSuccess(self, response, status_code=200):
        """断言响应成功"""
        self.assertEqual(response.status_code, status_code)
        data = response.json()
        self.assertTrue(data.get('success', False))
        return data
    
    def assertResponseError(self, response, status_code=400):
        """断言响应错误"""
        self.assertEqual(response.status_code, status_code)
        data = response.json()
        self.assertFalse(data.get('success', True))
        return data
    
    def assertResponseUnauthorized(self, response):
        """断言未授权响应"""
        self.assertEqual(response.status_code, 401)
    
    def assertResponseForbidden(self, response):
        """断言禁止访问响应"""
        self.assertEqual(response.status_code, 403)
    
    def assertPaginatedResponse(self, response, expected_count=None):
        """断言分页响应格式"""
        data = self.assertResponseSuccess(response)
        content = data.get('content', {})
        
        # 检查分页字段
        self.assertIn('total', content)
        self.assertIn('page_size', content)
        self.assertIn('page', content)
        self.assertIn('results', content)
        
        if expected_count is not None:
            self.assertEqual(len(content['results']), expected_count)
        
        return content


class BaseModelTestCase(BaseTestCase):
    """模型测试基础类"""
    
    def assertModelFieldExists(self, model, field_name):
        """断言模型字段存在"""
        self.assertTrue(hasattr(model, field_name))
    
    def assertModelMethodExists(self, model, method_name):
        """断言模型方法存在"""
        self.assertTrue(hasattr(model, method_name))
        self.assertTrue(callable(getattr(model, method_name)))


class TestDataMixin:
    """测试数据混入类"""
    
    @staticmethod
    def get_test_host_data():
        """获取测试主机数据"""
        return {
            'name': '测试主机',
            'ip': '192.168.1.100',
            'port': 22,
            'username': 'root',
            'auth_type': 'password',
            'password': 'testpass123',
            'description': '测试用主机'
        }
    
    @staticmethod
    def get_test_script_data():
        """获取测试脚本数据"""
        return {
            'name': '测试脚本',
            'description': '测试用脚本',
            'script_type': 'shell',
            'content': '#!/bin/bash\necho "Hello World"',
            'parameters': [
                {
                    'name': 'message',
                    'type': 'string',
                    'default': 'Hello',
                    'description': '消息内容'
                }
            ],
            'tags': ['test', 'demo']
        }
    
    @staticmethod
    def get_test_template_data():
        """获取测试作业模板数据"""
        return {
            'name': '测试作业模板',
            'description': '测试用作业模板',
            'category': 'test',
            'tags': ['test']
        }
    
    @staticmethod
    def get_test_step_data():
        """获取测试步骤数据"""
        return {
            'name': '测试步骤',
            'description': '测试用步骤',
            'step_type': 'script',
            'order': 1,
            'step_parameters': {
                'script_content': 'echo "test"',
                'script_type': 'shell'
            },
            'timeout': 300
        }


class MockSSHMixin:
    """SSH 连接模拟混入类"""
    
    def mock_ssh_success(self):
        """模拟 SSH 连接成功"""
        from unittest.mock import patch, MagicMock
        
        mock_ssh = MagicMock()
        mock_ssh.connect.return_value = True
        mock_ssh.exec_command.return_value = (None, MagicMock(), MagicMock())
        mock_ssh.exec_command.return_value[1].read.return_value = b'success'
        mock_ssh.exec_command.return_value[2].read.return_value = b''
        mock_ssh.exec_command.return_value[1].channel.recv_exit_status.return_value = 0
        
        return patch('paramiko.SSHClient', return_value=mock_ssh)
    
    def mock_ssh_failure(self):
        """模拟 SSH 连接失败"""
        from unittest.mock import patch
        
        def side_effect(*args, **kwargs):
            raise Exception("SSH connection failed")
        
        return patch('paramiko.SSHClient.connect', side_effect=side_effect)


class TestRunner:
    """测试运行器"""
    
    @staticmethod
    def run_all_tests():
        """运行所有测试"""
        import subprocess
        import sys
        
        # 运行所有测试
        result = subprocess.run([
            sys.executable, 'manage.py', 'test',
            '--verbosity=2',
            '--keepdb'
        ], capture_output=True, text=True)
        
        return result.returncode == 0, result.stdout, result.stderr
    
    @staticmethod
    def run_app_tests(app_name):
        """运行指定应用的测试"""
        import subprocess
        import sys
        
        result = subprocess.run([
            sys.executable, 'manage.py', 'test', app_name,
            '--verbosity=2',
            '--keepdb'
        ], capture_output=True, text=True)
        
        return result.returncode == 0, result.stdout, result.stderr
    
    @staticmethod
    def run_coverage_test():
        """运行覆盖率测试"""
        import subprocess
        import sys
        
        # 安装 coverage 如果没有的话
        try:
            import coverage
        except ImportError:
            subprocess.run([sys.executable, '-m', 'pip', 'install', 'coverage'])
        
        # 运行覆盖率测试
        commands = [
            [sys.executable, '-m', 'coverage', 'run', '--source=.', 'manage.py', 'test'],
            [sys.executable, '-m', 'coverage', 'report'],
            [sys.executable, '-m', 'coverage', 'html']
        ]
        
        for cmd in commands:
            result = subprocess.run(cmd, capture_output=True, text=True)
            if result.returncode != 0:
                return False, result.stdout, result.stderr
        
        return True, "Coverage test completed", ""
