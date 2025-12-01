"""
调度管理过滤器
"""
import django_filters
from django.db import models
from .models import ScheduledJob
from apps.job_templates.models import ExecutionPlan


class ScheduledJobFilter(django_filters.FilterSet):
    """定时作业过滤器"""
    
    # 按任务名称精确搜索（前端“任务名称”输入框）
    name = django_filters.CharFilter(
        field_name='name',
        lookup_expr='icontains',
        label='任务名称'
    )

    # 按执行方案名称精确搜索（前端“执行方案”输入框）
    plan_name = django_filters.CharFilter(
        field_name='execution_plan__name',
        lookup_expr='icontains',
        label='执行方案名称'
    )
    
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
        fields = ['name', 'plan_name', 'is_active', 'execution_plan']
