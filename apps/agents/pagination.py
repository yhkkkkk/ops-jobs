"""
Agent 相关分页类
"""
from utils.pagination import CustomPagination


class AgentPagination(CustomPagination):
    """
    Agent 列表分页
    - 默认每页 20 条
    其他行为复用全局 CustomPagination
    """

    page_size = 20


