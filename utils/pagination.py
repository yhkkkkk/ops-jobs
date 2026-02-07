"""
自定义分页类
"""
from collections import OrderedDict
from rest_framework.pagination import PageNumberPagination
from .responses import SycResponse


class CustomPagination(PageNumberPagination):
    """自定义分页类"""
    # 默认每页显示的数量
    page_size = 10
    page_size_query_param = 'page_size'
    page_query_param = 'page'
    # 每页最大显示数量
    max_page_size = 100
    ordering = '-id'  # 默认按id倒序排序（按需调整字段名）

    def paginate_queryset(self, queryset, request, view=None):
        if not queryset.ordered:
            queryset = queryset.order_by(self.ordering)
        return super().paginate_queryset(queryset, request, view)

    def get_paginated_response(self, data):
        pagination_data = OrderedDict([
            ('total', self.page.paginator.count),  # 总记录数
            ('page_size', self.get_page_size(self.request)),  # 当前页大小
            ('page', self.page.number),  # 当前页码
            ('results', data)  # 当前页数据
        ])
        return SycResponse.success(content=pagination_data)


class HostPagination(CustomPagination):
    """主机分页类"""
    page_size = 20


class LogPagination(CustomPagination):
    """日志分页类"""
    page_size = 50
