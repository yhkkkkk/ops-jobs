"""
Agent 过滤器
"""
import django_filters
from django.db import models
from django.db.models import Q
from django.utils import timezone
from datetime import timedelta
from apps.system_config.models import ConfigManager

from apps.hosts.models import Host, HostGroup
from .models import Agent, AgentInstallRecord, AgentUninstallRecord


class AgentFilter(django_filters.FilterSet):
    """Agent 过滤器（列表页用）"""

    search = django_filters.CharFilter(method='filter_search', label='搜索')
    status = django_filters.CharFilter(method='filter_status', label='状态')
    tags = django_filters.CharFilter(method='filter_tags', label='标签')
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
        fields = ['search', 'status', 'tags', 'service_role', 'group', 'group_id']

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
                | models.Q(host__tags__icontains=term)
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

    def filter_status(self, queryset, name, value):
        """
        支持按“实时计算的状态”过滤：
          - 'pending' / 'disabled'：使用存量 DB 字段过滤（管理语义优先）
          - 'online'：根据 host 所在环境的阈值判断 last_heartbeat_at 是否在阈值内（同时排除 pending/disabled）
          - 'offline'：非 online 且非 pending/disabled（包含 last_heartbeat_at 为空的情况）
        """
        if not value:
            return queryset
        value = str(value)
        if value in ('pending', 'disabled'):
            return queryset.filter(status=value)

        now = timezone.now()
        # load thresholds
        by_env = ConfigManager.get("agent.offline_threshold_by_env", {}) or {}
        global_threshold = ConfigManager.get("agent.offline_threshold_seconds", 600) or 600

        online_q = Q()
        env_keys = [k for k in by_env.keys() if isinstance(k, str)]
        for env in env_keys:
            try:
                t = int(by_env.get(env))
            except Exception:
                continue
            cutoff = now - timedelta(seconds=t)
            online_q |= Q(host__tags__icontains=env, last_heartbeat_at__gte=cutoff)

        # default bucket: hosts whose标签未匹配 env_keys
        try:
            cutoff_def = now - timedelta(seconds=int(global_threshold))
        except Exception:
            cutoff_def = now - timedelta(seconds=600)

        # 非指定 env 标签使用全局阈值
        online_q |= Q(last_heartbeat_at__gte=cutoff_def)

        # exclude pending/disabled
        online_q &= ~Q(status__in=['pending', 'disabled'])

        if value == 'online':
            return queryset.filter(online_q).distinct()
        elif value == 'offline':
            # offline = not online AND not pending/disabled
            return queryset.exclude(online_q).exclude(status__in=['pending', 'disabled']).distinct()
        else:
            return queryset

    def _split_parts(self, value):
        if not value:
            return []
        if isinstance(value, (list, tuple)):
            raw = []
            for v in value:
                if isinstance(v, str):
                    raw.extend(v.replace(',', ' ').split())
            return [p.strip() for p in raw if p.strip()]
        return [v.strip() for v in str(value).replace(',', ' ').split() if v.strip()]

    def filter_tags(self, queryset, name, value):
        parts = self._split_parts(value)
        if not parts:
            return queryset
        q = models.Q()
        for part in parts:
            q |= models.Q(host__tags__icontains=part)
        return queryset.filter(q).distinct()


class InstallRecordFilter(django_filters.FilterSet):
    """Agent 安装记录过滤器"""

    host_id = django_filters.NumberFilter(field_name="host_id")
    status = django_filters.ChoiceFilter(choices=AgentInstallRecord.STATUS_CHOICES)
    install_mode = django_filters.ChoiceFilter(choices=AgentInstallRecord.INSTALL_MODE_CHOICES)
    # 搜索过滤器 - 支持主机名、IP地址的模糊搜索
    search = django_filters.CharFilter(method="filter_search", label="搜索")

    class Meta:
        model = AgentInstallRecord
        fields = ["host_id", "status", "install_mode", "search"]

    def filter_search(self, queryset, name, value):
        """自定义搜索过滤方法 - 支持主机名、IP地址搜索"""
        if not value:
            return queryset

        # 将搜索值按空格分割，支持多关键词搜索
        search_terms = [term.strip() for term in value.split() if term.strip()]
        if not search_terms:
            return queryset

        # 对每个搜索词构建查询条件
        query = models.Q()
        for term in search_terms:
            term_query = (
                models.Q(host__name__icontains=term)
                | models.Q(host__ip_address__icontains=term)
                | models.Q(host__hostname__icontains=term)
                | models.Q(host__public_ip__icontains=term)
                | models.Q(host__internal_ip__icontains=term)
            )
            query |= term_query

        return queryset.filter(query)


class UninstallRecordFilter(django_filters.FilterSet):
    """Agent 卸载记录过滤器"""

    host_id = django_filters.NumberFilter(field_name="host_id")
    status = django_filters.ChoiceFilter(choices=AgentUninstallRecord.STATUS_CHOICES)

    class Meta:
        model = AgentUninstallRecord
        fields = ["host_id", "status"]

