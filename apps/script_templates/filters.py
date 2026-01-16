"""
脚本模板过滤器
"""
import django_filters
from django.db import models
from .models import ScriptTemplate, UserFavorite


class ScriptTemplateFilter(django_filters.FilterSet):
    """脚本模板过滤器"""

    # 按名称搜索
    # 不区分大小写的包含查询
    name = django_filters.CharFilter(lookup_expr='icontains', label='模板名称')

    # 搜索过滤器（支持名称和描述）
    search = django_filters.CharFilter(method='filter_search', label='搜索')

    # 按脚本类型过滤
    script_type = django_filters.ChoiceFilter(
        choices=ScriptTemplate.SCRIPT_TYPE_CHOICES,
        label='脚本类型'
    )

    # 按分类过滤
    category = django_filters.ChoiceFilter(
        choices=ScriptTemplate.CATEGORY_CHOICES,
        label='分类'
    )

    # 按模板类型过滤
    template_type = django_filters.ChoiceFilter(
        choices=ScriptTemplate.TEMPLATE_TYPE_CHOICES,
        label='模板类型'
    )

    # 按标签过滤（使用新的tags_json字段）
    tags = django_filters.CharFilter(method='filter_tags', label='标签')

    # 按创建者过滤
    created_by = django_filters.NumberFilter(field_name='created_by', label='创建者ID')

    class Meta:
        model = ScriptTemplate
        fields = ['name', 'search', 'script_type', 'category', 'template_type', 'tags', 'created_by']

    def filter_search(self, queryset, name, value):
        """自定义搜索过滤方法"""
        if value:
            return queryset.filter(
                models.Q(name__icontains=value) |
                models.Q(description__icontains=value)
            )
        return queryset

    def filter_tags(self, queryset, name, value):
        """按标签过滤（使用新的tags_json字段）"""
        if not value:
            return queryset

        # 如果value是字符串，尝试解析为列表
        if isinstance(value, str):
            try:
                import json
                tags = json.loads(value) if value.startswith('[') else [tag.strip() for tag in value.split(',') if tag.strip()]
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
            if ':' in tag or '=' in tag:
                # 处理 "key:value" 或 "key=value" 格式
                sep = ':' if ':' in tag else '='
                key, val = tag.split(sep, 1)
                key = key.strip()
                val = val.strip()
                # 检查指定键是否存在且值匹配
                q |= Q(**{f'tags_json__{key}': val})
            else:
                # 处理单个键或值
                q |= Q(tags_json__has_key=tag) | Q(tags_json__icontains=tag)

        return queryset.filter(q)


class UserFavoriteFilter(django_filters.FilterSet):
    """用户收藏过滤器"""

    # 按收藏类型过滤
    favorite_type = django_filters.ChoiceFilter(
        choices=UserFavorite.FAVORITE_TYPE_CHOICES,
        label='收藏类型'
    )

    # 按分类过滤
    category = django_filters.ChoiceFilter(
        choices=UserFavorite.CATEGORY_CHOICES,
        label='分类'
    )

    class Meta:
        model = UserFavorite
        fields = ['favorite_type', 'category']
