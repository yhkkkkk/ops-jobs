"""
Accounts 相关分页
"""
from utils.pagination import LogPagination


class UserPagination(LogPagination):
    """用户分页类 - 使用正确的排序字段"""

    ordering = "-date_joined"


