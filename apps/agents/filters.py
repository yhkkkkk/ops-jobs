"""
Agent 过滤器
"""
import django_filters
from django.db import models

from apps.hosts.models import Host, HostGroup
from .models import Agent


class AgentFilter(django_filters.FilterSet):
    """Agent 过滤器"""

    search = django_filters.CharFilter(method='filter_search', label='搜索')
    status = django_filters.ChoiceFilter(choices=Agent.STATUS_CHOICES, label='状态')
    environment = django_filters.ChoiceFilter(
        field_name='host__environment',
        choices=Host.ENVIRONMENT_CHOICES,
        label='环境'
    )
    business_system = django_filters.ModelChoiceFilter(
        field_name='host__business_system',
        queryset=None,  # 将在 __init__ 中设置
        label='业务系统'
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # 动态设置业务系统的查询集
        from apps.hosts.models import BusinessSystem
        self.filters['business_system'].queryset = BusinessSystem.objects.filter(is_active=True)
    service_role = django_filters.CharFilter(
        field_name='host__service_role',
        lookup_expr='icontains',
        label='服务角色'
    )
    group = django_filters.ModelChoiceFilter(
        field_name='host__groups',
        queryset=HostGroup.objects.all(),
        label='主机分组'
    )
    group_id = django_filters.NumberFilter(
        method='filter_group_id',
        label='主机分组ID'
    )

    class Meta:
        model = Agent
        fields = ['search', 'status', 'environment', 'business_system', 'service_role', 'group', 'group_id']

    def filter_search(self, queryset, name, value):
        if not value:
            return queryset
        terms = [t.strip() for t in value.split() if t.strip()]
        if not terms:
            return queryset
        query = models.Q()
        for term in terms:
            query |= (
                models.Q(host__name__icontains=term)
                | models.Q(host__internal_ip__icontains=term)
                | models.Q(host__public_ip__icontains=term)
                | models.Q(host__hostname__icontains=term)
                | models.Q(host__business_system__name__icontains=term)
                | models.Q(host__service_role__icontains=term)
                | models.Q(version__icontains=term)
                | models.Q(last_error_code__icontains=term)
            )
        return queryset.filter(query)

    def filter_group_id(self, queryset, name, value):
        """按分组过滤：包含当前分组及其所有子分组的 Agent"""
        if not value:
            return queryset
        try:
            group = HostGroup.objects.get(id=value)
        except HostGroup.DoesNotExist:
            return queryset.none()
        group_ids = [g.id for g in group.get_descendants(include_self=True)]
        return queryset.filter(host__groups__in=group_ids).distinct()

