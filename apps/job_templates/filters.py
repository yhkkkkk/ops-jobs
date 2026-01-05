"""
作业模板过滤器
"""
import django_filters
from django.db import models
from .models import JobTemplate, ExecutionPlan


class JobTemplateFilter(django_filters.FilterSet):
    """作业模板过滤器"""

    # 搜索过滤器
    search = django_filters.CharFilter(method='filter_search', label='搜索')

    # 按分类过滤
    category = django_filters.CharFilter(
        field_name='category',
        lookup_expr='exact',
        label='分类'
    )

    # 按标签过滤（搜索JSON字段中的键或值）
    tag = django_filters.CharFilter(
        method='filter_by_tag',
        label='标签'
    )

    # 按多个标签过滤
    tags = django_filters.CharFilter(
        method='filter_by_tags',
        label='多个标签'
    )

    # 按创建人过滤
    created_by = django_filters.NumberFilter(
        field_name='created_by_id',
        label='创建人ID'
    )

    def filter_search(self, queryset, name, value):
        """自定义搜索过滤方法"""
        if value:
            return queryset.filter(
                models.Q(name__icontains=value) |
                models.Q(description__icontains=value) |
                models.Q(category__icontains=value)
            )
        return queryset

    def filter_by_tag(self, queryset, name, value):
        """按标签过滤：搜索JSON字段中的键或值"""
        if not value:
            return queryset

        # 搜索标签的键或值
        from django.db.models import Q
        return queryset.filter(
            Q(tags_json__has_key=value) |  # 搜索键
            Q(tags_json__icontains=value)  # 搜索值
        )

    def filter_by_tags(self, queryset, name, value):
        """按多个标签过滤"""
        if not value:
            return queryset

        # 如果value是字符串，尝试解析为列表
        if isinstance(value, str):
            try:
                import json
                tags = json.loads(value) if value.startswith('[') else [value]
            except:
                tags = [tag.strip() for tag in value.split(',') if tag.strip()]
        else:
            tags = value if isinstance(value, list) else [value]

        if not tags:
            return queryset

        # 搜索包含任一标签的模板
        from django.db.models import Q
        q = Q()
        for tag in tags:
            if ':' in tag:
                # 处理 "key:value" 格式
                key, val = tag.split(':', 1)
                key = key.strip()
                val = val.strip()
                # 检查指定键是否存在且值匹配
                q |= Q(**{f'tags_json__{key}': val})
            else:
                # 处理单个键或值
                q |= Q(tags_json__has_key=tag) | Q(tags_json__icontains=tag)

        return queryset.filter(q)

    class Meta:
        model = JobTemplate
        fields = ['search', 'category', 'tag', 'tags', 'created_by']


class ExecutionPlanFilter(django_filters.FilterSet):
    """执行方案过滤器"""
    
    # 搜索过滤器
    search = django_filters.CharFilter(method='filter_search', label='搜索')
    
    # 按模板过滤
    template = django_filters.ModelChoiceFilter(
        field_name='template',
        queryset=JobTemplate.objects.all(),
        label='作业模板'
    )
    
    # 按创建人过滤
    created_by = django_filters.NumberFilter(
        field_name='created_by_id',
        label='创建人ID'
    )

    # 按同步状态过滤
    needs_sync = django_filters.BooleanFilter(
        method='filter_needs_sync',
        label='是否需要同步'
    )

    class Meta:
        model = ExecutionPlan
        fields = ['search', 'template', 'created_by', 'needs_sync']
    
    def filter_search(self, queryset, name, value):
        """自定义搜索过滤方法"""
        if value:
            return queryset.filter(
                models.Q(name__icontains=value) |
                models.Q(description__icontains=value)
            )
        return queryset

    def filter_needs_sync(self, queryset, name, value):
        """按同步状态过滤"""
        if value is not None:
            # needs_sync是一个属性，需要通过Python代码过滤
            # 这里简化处理，实际可能需要更复杂的查询
            if value:
                # 需要同步的方案
                return queryset.filter(is_synced=False)
            else:
                # 已同步的方案
                return queryset.filter(is_synced=True)
        return queryset
