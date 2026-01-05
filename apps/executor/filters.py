"""
执行记录过滤器
"""
import django_filters
from django.db.models import Q
from .models import ExecutionRecord


class ExecutionRecordFilter(django_filters.FilterSet):
    """执行记录过滤器"""

    # 按执行类型过滤
    execution_type = django_filters.ChoiceFilter(
        choices=ExecutionRecord.EXECUTION_TYPE_CHOICES,
        label='执行类型'
    )

    # 按状态过滤
    status = django_filters.ChoiceFilter(
        choices=ExecutionRecord.STATUS_CHOICES,
        label='状态'
    )

    # 按时间范围过滤
    start_date = django_filters.DateFilter(
        field_name='created_at',
        lookup_expr='gte',
        label='开始日期'
    )
    
    end_date = django_filters.DateFilter(
        field_name='created_at',
        lookup_expr='lte',
        label='结束日期'
    )

    # 按执行用户过滤
    executed_by = django_filters.CharFilter(
        field_name='executed_by__username',
        lookup_expr='icontains',
        label='执行用户'
    )

    # 按执行名称过滤
    name = django_filters.CharFilter(
        field_name='name',
        lookup_expr='icontains',
        label='执行名称'
    )

    # 按定时任务ID过滤 - 通过ExecutionPlan关联
    scheduled_job_id = django_filters.NumberFilter(
        method='filter_by_scheduled_job',
        label='定时任务ID'
    )

    def filter_by_scheduled_job(self, queryset, name, value):
        """通过定时任务ID过滤执行记录"""
        if not value:
            return queryset
        
        try:
            scheduled_job_id = int(value)
            # 获取ScheduledJob的ContentType
            from django.contrib.contenttypes.models import ContentType
            from apps.scheduler.models import ScheduledJob
            
            scheduled_job_ct = ContentType.objects.get_for_model(ScheduledJob)
            return queryset.filter(
                execution_type='scheduled_job',
                content_type=scheduled_job_ct,
                object_id=scheduled_job_id
            )
        except (ValueError, TypeError):
            return queryset.none()

    class Meta:
        model = ExecutionRecord
        fields = [
            'execution_type', 'status',
            'start_date', 'end_date', 'executed_by', 'name', 'scheduled_job_id'
        ]
