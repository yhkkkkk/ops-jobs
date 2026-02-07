"""
QuickExecuteService 单元测试
"""
import pytest

from apps.quick_execute.services import QuickExecuteService


pytestmark = pytest.mark.django_db


def test_extract_execution_params_default():
    """测试默认参数提取"""
    data = {}
    params = QuickExecuteService._extract_execution_params(data)

    assert params["account_id"] is None
    assert params["bandwidth_limit"] == 0
    assert isinstance(params["timeout"], int)  # 应该有默认值


def test_extract_execution_params_account_id_from_root():
    """测试从根层级提取account_id"""
    data = {"account_id": 123}
    params = QuickExecuteService._extract_execution_params(data, ["account_id"])

    assert params["account_id"] == 123


def test_extract_execution_params_account_id_from_global_variables():
    """测试从global_variables提取account_id"""
    data = {"global_variables": {"account_id": 456}}
    params = QuickExecuteService._extract_execution_params(data, ["account_id"])

    assert params["account_id"] == 456


def test_extract_execution_params_account_id_priority():
    """测试account_id提取优先级（根层级优先）"""
    data = {
        "account_id": 123,
        "global_variables": {"account_id": 456},
    }
    params = QuickExecuteService._extract_execution_params(data, ["account_id"])

    assert params["account_id"] == 123


def test_extract_execution_params_bandwidth_limit_kbps():
    """测试带宽限制KB/s格式"""
    data = {"bandwidth_limit": "1024kbps"}
    params = QuickExecuteService._extract_execution_params(data, ["bandwidth_limit"])

    assert params["bandwidth_limit"] == 0


def test_extract_execution_params_bandwidth_limit_mbps():
    """测试带宽限制MB/s格式"""
    data = {"bandwidth_limit": "2mbps"}
    params = QuickExecuteService._extract_execution_params(data, ["bandwidth_limit"])

    assert params["bandwidth_limit"] == 0


def test_extract_execution_params_bandwidth_limit_numeric():
    """测试带宽限制数字格式"""
    data = {"bandwidth_limit": 512}
    params = QuickExecuteService._extract_execution_params(data, ["bandwidth_limit"])

    assert params["bandwidth_limit"] == 512


def test_extract_execution_params_bandwidth_limit_invalid():
    """测试无效带宽限制值"""
    data = {"bandwidth_limit": "invalid"}
    params = QuickExecuteService._extract_execution_params(data, ["bandwidth_limit"])

    assert params["bandwidth_limit"] == 0


def test_extract_execution_params_timeout_valid():
    """测试有效timeout值"""
    data = {"timeout": 600}
    params = QuickExecuteService._extract_execution_params(data, ["timeout"])

    assert params["timeout"] == 600


def test_extract_execution_params_timeout_string():
    """测试字符串timeout值"""
    data = {"timeout": "300"}
    params = QuickExecuteService._extract_execution_params(data, ["timeout"])

    assert params["timeout"] == 300


def test_extract_execution_params_timeout_default():
    """测试timeout默认值"""
    data = {}  # 没有指定timeout
    params = QuickExecuteService._extract_execution_params(data, ["timeout"])

    assert params["timeout"] == 300


def test_extract_execution_params_timeout_invalid():
    """测试无效timeout值"""
    data = {"timeout": "invalid"}
    params = QuickExecuteService._extract_execution_params(data, ["timeout"])

    # 应该使用默认值
    assert isinstance(params["timeout"], int)
    assert params["timeout"] > 0


def test_extract_execution_params_partial_types():
    """测试部分参数类型提取"""
    data = {
        "account_id": 123,
        "bandwidth_limit": 512,
        "timeout": 600,
        "other_param": "ignored",
    }

    # 只提取account_id
    params = QuickExecuteService._extract_execution_params(data, ["account_id"])
    assert params["account_id"] == 123
    assert "bandwidth_limit" not in params
    assert "timeout" not in params


def test_extract_execution_params_bandwidth_limit_direct_mb():
    """测试bandwidth_limit直接使用前端MB/s值"""
    data = {"bandwidth_limit": 5}  # 前端传递的5表示5MB/s
    params = QuickExecuteService._extract_execution_params(data, ["bandwidth_limit"])

    # 应该直接返回5，不进行任何转换
    assert params["bandwidth_limit"] == 5


def test_extract_execution_params_bandwidth_limit_float():
    """测试bandwidth_limit浮点数转换"""
    data = {"bandwidth_limit": 2.5}
    params = QuickExecuteService._extract_execution_params(data, ["bandwidth_limit"])

    # 应该转换为整数
    assert params["bandwidth_limit"] == 2


def test_extract_execution_params_bandwidth_limit_zero():
    """测试bandwidth_limit为0的情况"""
    data = {"bandwidth_limit": 0}
    params = QuickExecuteService._extract_execution_params(data, ["bandwidth_limit"])

    assert params["bandwidth_limit"] == 0


def test_extract_execution_params_bandwidth_limit_none():
    """测试bandwidth_limit为None的情况"""
    data = {"bandwidth_limit": None}
    params = QuickExecuteService._extract_execution_params(data, ["bandwidth_limit"])

    assert params["bandwidth_limit"] == 0


def test_extract_execution_params_bandwidth_limit_invalid_string():
    """测试bandwidth_limit无效字符串的情况"""
    data = {"bandwidth_limit": "invalid"}
    params = QuickExecuteService._extract_execution_params(data, ["bandwidth_limit"])

    # 应该返回0，不抛出异常
    assert params["bandwidth_limit"] == 0
