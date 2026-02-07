import django_filters
from datetime import datetime, timedelta
from .models import AuditLog


class AuditLogFilter(django_filters.FilterSet):
    # 搜索字段：支持描述、资源名、用户名模糊匹配
    search = django_filters.CharFilter(method='filter_search', label='搜索')
    # 用户
    user_id = django_filters.NumberFilter(field_name='user_id')
    # 操作类型
    action = django_filters.CharFilter(field_name='action')
    # 成功状态
    success = django_filters.BooleanFilter(field_name='success')
    # 资源类型（model 名）
    resource_type = django_filters.CharFilter(
        field_name='resource_type__model'
    )
    # 时间范围：开始、结束（结束为当天 23:59:59）
    start_date = django_filters.DateFilter(method='filter_start_date')
    end_date = django_filters.DateFilter(method='filter_end_date')
    # IP 地址
    ip_address = django_filters.CharFilter(field_name='ip_address')

    def filter_start_date(self, queryset, name, value):
        if not value:
            return queryset
        return queryset.filter(created_at__gte=value)

    def filter_end_date(self, queryset, name, value):
        if not value:
            return queryset
        end_datetime = datetime.combine(value, datetime.min.time()) + timedelta(days=1)
        return queryset.filter(created_at__lt=end_datetime)

    def filter_search(self, queryset, name, value):
        """按描述 / 资源名称 / 用户名模糊搜索"""
        if not value:
            return queryset

        from django.db.models import Q
        return queryset.filter(
            Q(description__icontains=value) |
            Q(resource_name__icontains=value) |
            Q(user__username__icontains=value)
        )

    class Meta:
        model = AuditLog
        fields = [
            'search',
            'user_id',
            'action',
            'success',
            'resource_type',
            'start_date',
            'end_date',
            'ip_address',
        ]
