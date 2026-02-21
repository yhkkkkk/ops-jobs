"""
主机管理过滤器
"""
import django_filters
from django.db import models
from .models import Host, HostGroup, ServerAccount


class HostFilter(django_filters.FilterSet):
    """主机过滤器"""

    # 搜索过滤器 - 支持名称、IP地址、描述的模糊搜索
    search = django_filters.CharFilter(method='filter_search', label='搜索')

    # 状态过滤器
    status = django_filters.ChoiceFilter(
        choices=Host.STATUS_CHOICES,
        label='状态'
    )

    # OS类型过滤器
    os_type = django_filters.ChoiceFilter(
        choices=Host.OS_CHOICES,
        label='操作系统'
    )

    # 云厂商过滤器
    cloud_provider = django_filters.ChoiceFilter(
        choices=Host.CLOUD_PROVIDER_CHOICES,
        label='云厂商',
        method='filter_cloud_provider'
    )

    # 设备类型过滤器
    device_type = django_filters.ChoiceFilter(
        choices=Host.DEVICE_TYPE_CHOICES,
        label='设备类型'
    )

    # 标签过滤器（支持多值 OR 模糊匹配）
    tags = django_filters.CharFilter(
        method='filter_tags',
        label='标签'
    )

    # 分组过滤器（仅匹配当前分组）
    group = django_filters.ModelChoiceFilter(
        field_name='groups',
        queryset=HostGroup.objects.all(),
        label='主机分组'
    )

    # 分组ID过滤器（前端使用）：匹配当前分组及其所有子分组的主机
    group_id = django_filters.NumberFilter(
        method='filter_group_id',
        label='主机分组ID'
    )


    # CPU核心数范围过滤器
    cpu_cores_min = django_filters.NumberFilter(
        field_name='cpu_cores',
        lookup_expr='gte',
        label='最小CPU核心数'
    )
    cpu_cores_max = django_filters.NumberFilter(
        field_name='cpu_cores',
        lookup_expr='lte',
        label='最大CPU核心数'
    )
    # CPU架构
    cpu_arch = django_filters.CharFilter(
        field_name='cpu_arch',
        lookup_expr='icontains',
        label='CPU架构'
    )
    # CPU逻辑核心数（精确匹配）
    cpu_cores = django_filters.NumberFilter(
        field_name='cpu_cores',
        label='CPU逻辑核心数'
    )
    # 负责人
    owner = django_filters.CharFilter(
        field_name='owner',
        lookup_expr='icontains',
        label='负责人'
    )
    # 所属部门
    department = django_filters.CharFilter(
        field_name='department',
        lookup_expr='icontains',
        label='所属部门'
    )

    # 内存范围过滤器
    memory_gb_min = django_filters.NumberFilter(
        field_name='memory_gb',
        lookup_expr='gte',
        label='最小内存(GB)'
    )
    memory_gb_max = django_filters.NumberFilter(
        field_name='memory_gb',
        lookup_expr='lte',
        label='最大内存(GB)'
    )

    class Meta:
        model = Host
        fields = [
            'search', 'status', 'os_type', 'cloud_provider', 'device_type',
            'tags', 'group', 'group_id', 'cpu_cores_min', 'cpu_cores_max',
            'cpu_arch', 'cpu_cores', 'memory_gb_min', 'memory_gb_max', 'owner', 'department'
        ]

    def filter_search(self, queryset, name, value):
        """自定义搜索过滤方法 - 支持多关键词搜索"""
        if not value:
            return queryset

        search_terms = [term.strip() for term in value.split() if term.strip()]
        if not search_terms:
            return queryset

        query = models.Q()
        for term in search_terms:
            term_query = (
                models.Q(name__icontains=term) |
                models.Q(public_ip__icontains=term) |
                models.Q(internal_ip__icontains=term) |
                models.Q(hostname__icontains=term) |
                models.Q(tags__icontains=term) |
                models.Q(service_role__icontains=term) |
                models.Q(owner__icontains=term) |
                models.Q(department__icontains=term) |
                models.Q(description__icontains=term)
            )
            query |= term_query

        return queryset.filter(query)

    def filter_group_id(self, queryset, name, value):
        if not value:
            return queryset
        try:
            group = HostGroup.objects.get(id=value)
        except HostGroup.DoesNotExist:
            return queryset.none()
        group_ids = [g.id for g in group.get_descendants(include_self=True)]
        return queryset.filter(groups__in=group_ids).distinct()

    def filter_cloud_provider(self, queryset, name, value):
        if not value:
            return queryset
        if value == 'other':
            common_providers = [p for p, _ in Host.CLOUD_PROVIDER_CHOICES if p != 'other']
            return queryset.exclude(cloud_provider__in=common_providers)
        return queryset.filter(cloud_provider=value)

    def filter_tags(self, queryset, name, value):
        """支持多值（逗号/空格分隔），兼容 key=value 与单词匹配；兼容不支持 JSON contains 的数据库"""
        if not value:
            return queryset

        if isinstance(value, (list, tuple)):
            raw = []
            for v in value:
                if isinstance(v, str):
                    raw.extend(v.replace(',', ' ').split())
            parts = [p.strip() for p in raw if p and p.strip()]
        else:
            parts = [v.strip() for v in value.replace(',', ' ').split() if v.strip()]

        if not parts:
            return queryset

        kv_parts = []
        keywords = []
        for part in parts:
            if '=' in part:
                k, v = part.split('=', 1)
                k = k.strip()
                v = v.strip()
                if k and v:
                    kv_parts.append((k.lower(), v.lower()))
                    continue
            keywords.append(part.lower())

        annotated = queryset.annotate(
            tags_text=models.functions.Lower(models.functions.Cast('tags', models.TextField()))
        )

        for k, v in kv_parts:
            annotated = annotated.filter(
                models.Q(tags_text__icontains=f'"key":"{k}"') |
                models.Q(tags_text__icontains=f'"key": "{k}"') |
                models.Q(tags_text__icontains=k)
            ).filter(tags_text__icontains=v)

        if keywords:
            q = models.Q()
            for kw in keywords:
                q |= models.Q(tags_text__icontains=kw)
            annotated = annotated.filter(q)

        return annotated


class HostGroupFilter(django_filters.FilterSet):
    """主机分组过滤器"""

    search = django_filters.CharFilter(method='filter_search', label='搜索')

    class Meta:
        model = HostGroup
        fields = ['search']

    def filter_search(self, queryset, name, value):
        if value:
            return queryset.filter(
                models.Q(name__icontains=value) |
                models.Q(description__icontains=value)
            )
        return queryset


class ServerAccountFilter(django_filters.FilterSet):
    """服务器账号过滤器"""

    search = django_filters.CharFilter(method='filter_search', label='搜索')
    auth_type = django_filters.CharFilter(method='filter_auth_type', label='认证方式')

    class Meta:
        model = ServerAccount
        fields = ['search', 'auth_type']

    def filter_search(self, queryset, name, value):
        if value:
            return queryset.filter(
                models.Q(name__icontains=value) |
                models.Q(username__icontains=value) |
                models.Q(description__icontains=value)
            )
        return queryset

    def filter_auth_type(self, queryset, name, value):
        if not value:
            return queryset
        if value == 'password':
            return queryset.filter(password__isnull=False).exclude(password='').filter(
                models.Q(private_key__isnull=True) | models.Q(private_key='')
            )
        elif value == 'key':
            return queryset.filter(private_key__isnull=False).exclude(private_key='').filter(
                models.Q(password__isnull=True) | models.Q(password='')
            )
        elif value == 'both':
            return queryset.filter(
                password__isnull=False, private_key__isnull=False
            ).exclude(password='').exclude(private_key='')
        elif value == 'none':
            return queryset.filter(
                models.Q(password__isnull=True) | models.Q(password='')
            ).filter(
                models.Q(private_key__isnull=True) | models.Q(private_key='')
            )
        return queryset
