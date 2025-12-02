import django_filters
from datetime import datetime, timedelta
from .models import AuditLog


class AuditLogFilter(django_filters.FilterSet):
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

    class Meta:
        model = AuditLog
        fields = ['user_id', 'action', 'success', 'resource_type', 'start_date', 'end_date', 'ip_address']
