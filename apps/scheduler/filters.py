"""
调度管理过滤器
"""
import django_filters
from django.db import models
from .models import ScheduledJob
from apps.job_templates.models import ExecutionPlan


class ScheduledJobFilter(django_filters.FilterSet):
    """定时作业过滤器"""
    
    # 搜索过滤器
    search = django_filters.CharFilter(method='filter_search', label='搜索')
    
    # 按状态过滤
    is_active = django_filters.BooleanFilter(
        field_name='is_active',
        label='是否启用'
    )
    
    # 按执行方案过滤
    execution_plan = django_filters.ModelChoiceFilter(
        field_name='execution_plan',
        queryset=ExecutionPlan.objects.all(),
        label='执行方案'
    )
    
    class Meta:
        model = ScheduledJob
        fields = ['search', 'is_active', 'execution_plan']
    
    def filter_search(self, queryset, name, value):
        """自定义搜索过滤方法"""
        if value:
            return queryset.filter(
                models.Q(name__icontains=value) |
                models.Q(description__icontains=value) |
                models.Q(execution_plan__name__icontains=value)
            )
        return queryset
