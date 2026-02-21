"""
作业模板过滤器
"""
import django_filters
from django.db import models
from django.db.models.functions import Cast, Lower
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

    # 按更新人过滤
    updated_by = django_filters.NumberFilter(
        field_name='updated_by_id',
        label='更新人ID'
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
        """按标签过滤：文本包含匹配，兼容不支持 JSON contains 的数据库"""
        if not value:
            return queryset
        txt = str(value).strip().lower()
        annotated = queryset.annotate(tags_text=Lower(Cast('tags_json', models.TextField())))
        return annotated.filter(tags_text__icontains=txt)

    def filter_by_tags(self, queryset, name, value):
        """按多个标签过滤（OR），兼容 JSON 不支持 contains/has_key 的场景"""
        if not value:
            return queryset

        if isinstance(value, str):
            try:
                import json
                tags = json.loads(value) if value.startswith('[') else [v.strip() for v in value.split(',') if v.strip()]
            except Exception:
                tags = [v.strip() for v in value.split(',') if v.strip()]
        else:
            tags = value if isinstance(value, list) else [value]

        tags = [str(t).strip().lower() for t in tags if str(t).strip()]
        if not tags:
            return queryset

        annotated = queryset.annotate(tags_text=Lower(Cast('tags_json', models.TextField())))
        from django.db.models import Q
        q = Q()
        for tag in tags:
            if ':' in tag or '=' in tag:
                sep = ':' if ':' in tag else '='
                key, val = tag.split(sep, 1)
                key = key.strip().lower()
                val = val.strip().lower()
                if not key or not val:
                    continue
                q |= (Q(tags_text__icontains=f'"{key}"') & Q(tags_text__icontains=val))
            else:
                q |= Q(tags_text__icontains=tag)

        return annotated.filter(q)

    class Meta:
        model = JobTemplate
        fields = ['search', 'category', 'tag', 'tags', 'created_by', 'updated_by']


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

    # 按更新人过滤
    updated_by = django_filters.NumberFilter(
        field_name='updated_by_id',
        label='更新人ID'
    )

    # 按同步状态过滤
    needs_sync = django_filters.BooleanFilter(
        method='filter_needs_sync',
        label='是否需要同步'
    )

    class Meta:
        model = ExecutionPlan
        fields = ['search', 'template', 'created_by', 'updated_by', 'needs_sync']
    
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
