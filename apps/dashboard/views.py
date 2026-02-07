"""
项目仪表盘视图（包含运维台相关统计）

本模块提供：
- 仪表盘概览 / 统计 / 最近活动 / 系统状态 等端点
- 运维台专用的概览接口（ops_overview），用于返回运维关注的 KPI（实时在线/离线、心跳告警、任务延时分位、失败主机TOP 等）

注意：
- 运维台的告警基于实时计算的 computed status（短时缓存），并可按环境使用不同阈值判定离线。
"""
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from django.db.models import Count
from django.utils import timezone
from datetime import timedelta, datetime
from rest_framework_extensions.cache.decorators import cache_response
from django.core.cache import cache
from drf_spectacular.utils import extend_schema
from utils.responses import SycResponse
from .serializers import (
    DashboardOverviewSerializer,
    DashboardStatisticsSerializer,
    DashboardRecentActivitySerializer,
    DashboardSystemStatusSerializer
)


def compute_percentile(values, p):
    """计算简单分位数（线性插值），values 为数值列表，p 为百分比（0-100）"""
    if not values:
        return 0.0
    vals = sorted(values)
    k = (len(vals) - 1) * (p / 100.0)
    f = int(k)
    c = min(f + 1, len(vals) - 1)
    if f == c:
        return vals[int(k)]
    d0 = vals[f] * (c - k)
    d1 = vals[c] * (k - f)
    return d0 + d1


class DashboardViewSet(viewsets.ViewSet):
    """项目仪表盘ViewSet"""
    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary="获取仪表盘概览数据",
        responses={200: DashboardOverviewSerializer},
        tags=["仪表盘"]
    )
    @cache_response(timeout=60 * 15)  # 缓存15分钟
    @action(detail=False, methods=['get'])
    def overview(self, request):
        """获取仪表盘概览数据"""
        try:
            overview_data = self._get_overview_data()
            return SycResponse.success(content=overview_data, message="获取概览数据成功")
        except Exception as e:
            return SycResponse.error(message=f"获取概览数据失败: {str(e)}")

    @extend_schema(
        summary="获取统计数据",
        responses={200: DashboardStatisticsSerializer},
        tags=["仪表盘"]
    )
    @cache_response(timeout=60 * 15)  # 缓存15分钟
    @action(detail=False, methods=['get'])
    def statistics(self, request):
        """获取统计数据"""
        try:
            stats_data = self._get_statistics_data()
            return SycResponse.success(content=stats_data, message="获取统计数据成功")
        except Exception as e:
            return SycResponse.error(message=f"获取统计数据失败: {str(e)}")

    @extend_schema(
        summary="获取最近活动",
        responses={200: DashboardRecentActivitySerializer},
        tags=["仪表盘"]
    )
    @cache_response(timeout=60 * 15)  # 缓存15分钟
    @action(detail=False, methods=['get'])
    def recent_activities(self, request):
        """获取最近活动"""
        try:
            activities_data = self._get_recent_activities()
            return SycResponse.success(content=activities_data, message="获取最近活动成功")
        except Exception as e:
            return SycResponse.error(message=f"获取最近活动失败: {str(e)}")

    @extend_schema(
        summary="获取系统状态",
        responses={200: DashboardSystemStatusSerializer},
        tags=["仪表盘"]
    )
    @cache_response(timeout=60 * 15)  # 缓存15分钟
    @action(detail=False, methods=['get'])
    def system_status(self, request):
        """获取系统状态 - 使用 django-health-check"""
        try:
            status_data = self._get_system_status()
            return SycResponse.success(content=status_data, message="获取系统状态成功")
        except Exception as e:
            return SycResponse.error(message=f"获取系统状态失败: {str(e)}")

    @extend_schema(
        summary="运维台：获取运维关注的概览数据（使用 computed_status 统计在线/离线）",
        responses={200: 'OpsOverviewSerializer'},
        tags=["运维台"]
    )
    @cache_response(timeout=60)  # 缓存 60s
    @action(detail=False, methods=['get'], url_path='ops_overview')
    def ops_overview(self, request):
        """运维台概览：基于实时计算的 Agent 状态提供运维关注的 KPI"""
        try:
            from apps.agents.models import Agent
            from apps.executor.models import ExecutionRecord
            from apps.agents.status import get_cached_agent_status

            agents = Agent.objects.select_related('host').all()
            total = agents.count()
            online = 0
            offline = 0
            pending = 0
            disabled = 0

            for agent in agents:
                # pending/disabled respect stored management state
                if agent.status in ('pending', 'disabled'):
                    if agent.status == 'pending':
                        pending += 1
                    else:
                        disabled += 1
                    continue

                # otherwise use computed cached status
                st = get_cached_agent_status(agent.id, agent)
                if st == 'online':
                    online += 1
                else:
                    offline += 1

            # heartbeat alerts: compute per-agent using compute_agent_status (env-aware thresholds)
            from apps.agents.status import compute_agent_status
            heartbeat_hosts = []
            try:
                for agent in agents:
                    # skip agents intentionally disabled or pending
                    if agent.status in ('pending', 'disabled'):
                        continue
                    try:
                        cs = compute_agent_status(agent)
                    except Exception:
                        cs = 'offline'
                    if cs == 'offline':
                        # determine threshold for reporting
                        # try to extract host env and last_heartbeat_at
                        env = getattr(agent.host, 'environment', None) if getattr(agent, 'host', None) else getattr(agent, 'environment', None)
                        last_hb = getattr(agent, 'last_heartbeat_at', None)
                        heartbeat_hosts.append({
                            'agent_id': agent.id,
                            'host_name': getattr(agent.host, 'name', None) if getattr(agent, 'host', None) else None,
                            'environment': env,
                            'last_heartbeat_at': last_hb.isoformat() if last_hb else None,
                        })
            except Exception:
                heartbeat_hosts = []

            heartbeat_alerts_count = len(heartbeat_hosts)

            # running tasks and 24h failure rate
            now = timezone.now()
            since_24h = now - timedelta(hours=24)
            running_tasks = ExecutionRecord.objects.filter(status='running').count()
            total_24h = ExecutionRecord.objects.filter(created_at__gte=since_24h).count()
            failed_24h = ExecutionRecord.objects.filter(created_at__gte=since_24h, status='failed').count()
            fail_rate = (failed_24h / total_24h * 100) if total_24h > 0 else 0.0
            # 计算任务时延分位（过去24小时已完成的任务）
            durations = []
            finished_qs = ExecutionRecord.objects.filter(
                created_at__gte=since_24h,
                started_at__isnull=False,
                finished_at__isnull=False
            ).values('started_at', 'finished_at')
            for rec in finished_qs:
                try:
                    dur = (rec['finished_at'] - rec['started_at']).total_seconds() * 1000.0
                    if dur >= 0:
                        durations.append(dur)
                except Exception:
                    continue

            def percentile(values, p):
                if not values:
                    return 0.0
                vals = sorted(values)
                k = (len(vals)-1) * (p/100.0)
                f = int(k)
                c = min(f+1, len(vals)-1)
                if f == c:
                    return vals[int(k)]
                d0 = vals[f] * (c - k)
                d1 = vals[c] * (k - f)
                return d0 + d1

            p95_ms = round(percentile(durations, 95), 1) if durations else 0.0

            # heartbeat_alerts: 简化为离线 agent 数（可扩展为阈值告警）
            # 使用 per-agent 阈值更精确判定（返回详情）
            heartbeat_alerts = heartbeat_alerts_count
            # 计算 top failure hosts (基于 ExecutionStep.host_results 中的 host_name)
            from apps.executor.models import ExecutionStep

            host_fail_counts = {}
            host_last_failed = {}
            try:
                failed_steps = ExecutionStep.objects.filter(
                    created_at__gte=since_24h,
                    status='failed'
                ).values('host_results', 'finished_at')

                for step in failed_steps:
                    host_results = step.get('host_results') or []
                    finished_at = step.get('finished_at')
                    
                    for hr in host_results:
                        try:
                            host_name = hr.get('host_name') or hr.get('host') or hr.get('hostname')
                            status = hr.get('status') or hr.get('result_status') or ''
                            if not host_name:
                                continue

                            if status in ('failed', 'error', 'timeout'):
                                host_fail_counts[host_name] = host_fail_counts.get(host_name, 0) + 1
                                if finished_at:
                                    host_last_failed[host_name] = max(host_last_failed.get(host_name) or finished_at, finished_at)
                        except Exception:
                            continue
            except Exception:
                host_fail_counts = {}
                host_last_failed = {}

            top_hosts = []
            for h, cnt in sorted(host_fail_counts.items(), key=lambda x: x[1], reverse=True)[:5]:
                last_failed = host_last_failed.get(h)
                top_hosts.append({
                    'host_name': h,
                    'fail_count': cnt,
                    'last_failed_at': last_failed.isoformat() if last_failed else None
                })

            data = {
                'agents_total': total,
                'agents_online': online,
                'agents_offline': offline,
                'agents_pending': pending,
                'agents_disabled': disabled,
                'running_tasks': running_tasks,
                'fail_rate_24h': round(fail_rate, 2),
                'task_p50_ms': round(percentile(durations, 50), 1) if durations else 0.0,
                'task_p95_ms': p95_ms,
                'task_p99_ms': round(percentile(durations, 99), 1) if durations else 0.0,
                'heartbeat_alerts': heartbeat_alerts,
                'heartbeat_alerts_hosts': heartbeat_hosts,
                'top_failure_hosts': top_hosts,
                'last_updated': timezone.now()
            }
            return SycResponse.success(content=data, message="获取运维台概览成功")
        except Exception as e:
            return SycResponse.error(message=f"获取运维台概览失败: {str(e)}")

    @extend_schema(
        summary="获取执行趋势数据",
        tags=["仪表盘"]
    )
    @cache_response(timeout=60 * 5, key_func=lambda request, *args, **kwargs: f"execution_trend_{request.GET.get('time_range', 'week')}_{request.GET.get('plan_id', '')}_{request.GET.get('start_date', '')}_{request.GET.get('end_date', '')}")  # 缓存5分钟，包含查询参数
    @action(detail=False, methods=['get'])
    def execution_trend(self, request):
        """获取执行趋势数据，支持时间范围和执行方案过滤"""
        try:
            from apps.executor.models import ExecutionRecord
            from apps.job_templates.models import ExecutionPlan
            from django.db.models import Q
            from datetime import datetime

            # 获取过滤参数
            time_range = request.GET.get('time_range', 'week')
            plan_filter = request.GET.get('plan_id', '')  # 按执行方案过滤
            start_date_str = request.GET.get('start_date', '')
            end_date_str = request.GET.get('end_date', '')

            # 根据时间范围确定日期
            end_date = timezone.now().date()

            if time_range == 'today':
                start_date = end_date
            elif time_range == 'week':
                start_date = end_date - timedelta(days=6)
            elif time_range == 'month':
                start_date = end_date - timedelta(days=29)
            elif time_range == 'custom' and start_date_str and end_date_str:
                try:
                    start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
                    end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date()
                except ValueError:
                    start_date = end_date - timedelta(days=6)
            else:
                start_date = end_date - timedelta(days=6)

            # 生成日期列表
            dates = []
            current_date = start_date
            while current_date <= end_date:
                dates.append(current_date)
                current_date += timedelta(days=1)

            # 查询每天的执行数据
            trend_data = []
            for date in dates:
                # 基础查询
                executions = ExecutionRecord.objects.filter(created_at__date=date)

                # 添加执行方案过滤
                if plan_filter:
                    from django.contrib.contenttypes.models import ContentType
                    execution_plan_ct = ContentType.objects.get_for_model(ExecutionPlan)
                    executions = executions.filter(
                        content_type=execution_plan_ct,
                        object_id=plan_filter
                    )

                daily_stats = executions.aggregate(
                    total=Count('id'),
                    success=Count('id', filter=Q(status='success')),
                    failed=Count('id', filter=Q(status='failed'))
                )

                trend_data.append({
                    'date': date.strftime('%m-%d'),
                    'total': daily_stats['total'] or 0,
                    'success': daily_stats['success'] or 0,
                    'failed': daily_stats['failed'] or 0,
                })

            return SycResponse.success(content=trend_data, message="获取执行趋势成功")

        except Exception as e:
            return SycResponse.error(message=f"获取执行趋势失败: {str(e)}")

    @extend_schema(
        summary="运维台：任务延时趋势（p50/p95）",
        tags=["运维台"]
    )
    @cache_response(timeout=60 * 30, key_func=lambda request, *args, **kwargs: f"ops_latency_trend_{request.GET.get('time_range','7d')}_{request.GET.get('granularity','day')}_{request.GET.get('start_date','')}_{request.GET.get('end_date','')}")
    @action(detail=False, methods=['get'], url_path='ops_latency_trend')
    def ops_latency_trend(self, request):
        """
        返回任务延时趋势（p50/p95），参数：
          - time_range: today/week/month/7d/30d/custom
          - granularity: hour|day
          - start_date, end_date: 自定义范围 YYYY-MM-DD
        """
        try:
            from apps.executor.models import ExecutionRecord

            time_range = request.GET.get('time_range', '7d')
            granularity = request.GET.get('granularity', 'day')
            start_date_str = request.GET.get('start_date', '')
            end_date_str = request.GET.get('end_date', '')

            now = timezone.now()
            if time_range == 'today':
                start_dt = timezone.make_aware(datetime.combine(now.date(), datetime.min.time()))
                end_dt = timezone.make_aware(datetime.combine(now.date(), datetime.max.time()))
            elif time_range == 'week':
                start_dt = timezone.make_aware(datetime.combine((now.date() - timedelta(days=6)), datetime.min.time()))
                end_dt = timezone.make_aware(datetime.combine(now.date(), datetime.max.time()))
            elif time_range == 'month':
                start_dt = timezone.make_aware(datetime.combine((now.date() - timedelta(days=29)), datetime.min.time()))
                end_dt = timezone.make_aware(datetime.combine(now.date(), datetime.max.time()))
            elif time_range.endswith('d') and time_range[:-1].isdigit():
                days = int(time_range[:-1])
                start_dt = timezone.make_aware(datetime.combine((now.date() - timedelta(days=days-1)), datetime.min.time()))
                end_dt = timezone.make_aware(datetime.combine(now.date(), datetime.max.time()))
            elif time_range == 'custom' and start_date_str and end_date_str:
                try:
                    start_dt = timezone.make_aware(datetime.strptime(start_date_str, '%Y-%m-%d'))
                    end_dt = timezone.make_aware(datetime.strptime(end_date_str, '%Y-%m-%d')) + timedelta(days=1) - timedelta(seconds=1)
                except Exception:
                    start_dt = timezone.make_aware(datetime.combine((now.date() - timedelta(days=6)), datetime.min.time()))
                    end_dt = timezone.make_aware(datetime.combine(now.date(), datetime.max.time()))
            else:
                start_dt = timezone.make_aware(datetime.combine((now.date() - timedelta(days=6)), datetime.min.time()))
                end_dt = timezone.make_aware(datetime.combine(now.date(), datetime.max.time()))

            # 收集已完成的执行的 durations（ms）
            records = ExecutionRecord.objects.filter(
                created_at__gte=start_dt,
                created_at__lte=end_dt,
                started_at__isnull=False,
                finished_at__isnull=False
            ).values('created_at', 'started_at', 'finished_at')

            # bucket by day or hour
            buckets = {}
            current = start_dt
            if granularity == 'hour':
                step = timedelta(hours=1)
                fmt = lambda dt: dt.strftime('%Y-%m-%d %H:00')
            else:
                step = timedelta(days=1)
                fmt = lambda dt: dt.strftime('%Y-%m-%d')

            # initialize buckets
            bstart = start_dt
            while bstart <= end_dt:
                buckets[fmt(bstart)] = []
                bstart += step

            for r in records:
                try:
                    finished = r['finished_at']
                    started = r['started_at']
                    dur_ms = (finished - started).total_seconds() * 1000.0
                    if dur_ms < 0:
                        continue
                    # find bucket key by created_at
                    created = r['created_at']
                    if not created:
                        created = started
                    if granularity == 'hour':
                        key = created.astimezone(timezone.get_current_timezone()).replace(minute=0, second=0, microsecond=0)
                    else:
                        key = created.astimezone(timezone.get_current_timezone()).replace(hour=0, minute=0, second=0, microsecond=0)
                    key_str = fmt(key)
                    if key_str in buckets:
                        buckets[key_str].append(dur_ms)
                except Exception:
                    continue

            series = []
            for key in sorted(buckets.keys()):
                vals = buckets[key]
                p50 = round(compute_percentile(vals, 50), 1) if vals else 0.0
                p95 = round(compute_percentile(vals, 95), 1) if vals else 0.0
                series.append({'ts': key, 'p50': p50, 'p95': p95})

            return SycResponse.success(content=series, message='获取延时趋势成功')
        except Exception as e:
            return SycResponse.error(message=f'获取延时趋势失败: {e}')

    @extend_schema(
        summary="获取任务状态分布",
        tags=["仪表盘"]
    )
    @cache_response(timeout=60 * 15)  # 缓存15分钟
    @action(detail=False, methods=['get'])
    def status_distribution(self, request):
        """获取任务状态分布"""
        try:
            from apps.executor.models import ExecutionRecord

            # 最近30天的执行状态分布
            thirty_days_ago = timezone.now() - timedelta(days=30)

            status_stats = ExecutionRecord.objects.filter(
                created_at__gte=thirty_days_ago
            ).values('status').annotate(
                count=Count('id')
            ).order_by('-count')

            # 转换为前端需要的格式
            distribution_data = []
            status_names = {
                'success': '成功',
                'failed': '失败',
                'running': '运行中',
                'pending': '等待中',
                'cancelled': '已取消'
            }

            for item in status_stats:
                distribution_data.append({
                    'name': status_names.get(item['status'], item['status']),
                    'value': item['count'],
                    'status': item['status']  # 保留原始状态，让前端决定样式
                })

            return SycResponse.success(content=distribution_data, message="获取状态分布成功")

        except Exception as e:
            return SycResponse.error(message=f"获取状态分布失败: {str(e)}")

    @extend_schema(
        summary="获取模板分类统计",
        tags=["仪表盘"]
    )
    @cache_response(timeout=60 * 15)  # 缓存15分钟
    @action(detail=False, methods=['get'])
    def template_category_stats(self, request):
        """获取模板分类统计"""
        try:
            from apps.job_templates.models import JobTemplate

            category_stats = JobTemplate.objects.values('category').annotate(
                count=Count('id')
            ).order_by('-count')

            # 转换为图表数据格式
            category_data = []

            for item in category_stats:
                category_name = item['category'] or '未分类'
                category_data.append({
                    'name': category_name,
                    'value': item['count']
                })

            return SycResponse.success(content=category_data, message="获取模板分类统计成功")

        except Exception as e:
            return SycResponse.error(message=f"获取模板分类统计失败: {str(e)}")

    @extend_schema(
        summary="获取主机状态统计",
        tags=["仪表盘"]
    )
    @cache_response(timeout=60 * 15)  # 缓存15分钟
    @action(detail=False, methods=['get'])
    def host_status_stats(self, request):
        """获取主机状态统计"""
        try:
            from apps.hosts.models import Host

            host_stats = Host.objects.values('status').annotate(
                count=Count('id')
            ).order_by('-count')

            # 转换为图表数据格式
            status_names = {
                'online': '在线',
                'offline': '离线',
                'error': '错误',
                'unknown': '未知'
            }

            host_data = []
            for item in host_stats:
                status = item['status']
                host_data.append({
                    'name': status_names.get(status, status),
                    'value': item['count'],
                    'status': status  # 保留原始状态，让前端决定样式
                })

            return SycResponse.success(content=host_data, message="获取主机状态统计成功")

        except Exception as e:
            return SycResponse.error(message=f"获取主机状态统计失败: {str(e)}")

    @extend_schema(
        summary="获取执行方案列表",
        tags=["仪表盘"]
    )
    @cache_response(timeout=60 * 15)  # 缓存15分钟
    @action(detail=False, methods=['get'])
    def execution_plans(self, request):
        """获取执行方案列表，用于dashboard过滤"""
        try:
            from apps.job_templates.models import ExecutionPlan
            from django.db.models import Count
            from apps.executor.models import ExecutionRecord
            from django.contrib.contenttypes.models import ContentType

            # 获取ExecutionPlan的ContentType
            execution_plan_ct = ContentType.objects.get_for_model(ExecutionPlan)
            
            # 获取有执行记录的方案ID列表
            plan_ids_with_executions = ExecutionRecord.objects.filter(
                content_type=execution_plan_ct
            ).values_list('object_id', flat=True).distinct()

            # 获取这些方案的详细信息
            plans_with_executions = ExecutionPlan.objects.filter(
                id__in=plan_ids_with_executions
            ).values(
                'id', 'name', 'description', 'total_executions'
            ).order_by('-total_executions')

            # 转换为前端需要的格式
            plans_data = []
            for plan in plans_with_executions:
                plans_data.append({
                    'id': plan['id'],
                    'name': plan['name'],
                    'description': plan['description'] or '',
                    'execution_count': plan['total_executions']
                })

            return SycResponse.success(content=plans_data, message="获取执行方案列表成功")

        except Exception as e:
            return SycResponse.error(message=f"获取执行方案列表失败: {str(e)}")

    @extend_schema(
        summary="获取执行热力图数据",
        tags=["仪表盘"]
    )
    @cache_response(
        timeout=60 * 15,
        key_func=lambda request, *args, **kwargs: f"execution_heatmap_{request.GET.get('time_range','')}_{request.GET.get('start_date','')}_{request.GET.get('end_date','')}"
    )
    @action(detail=False, methods=['get'])
    def execution_heatmap(self, request):
        """获取执行热力图数据（按小时和星期统计）"""
        try:
            from apps.executor.models import ExecutionRecord
            from django.db.models import Count
            from collections import defaultdict
            # 支持自定义时间范围查询：start_date/end_date 或 time_range (today/week/month/30)
            time_range = request.GET.get('time_range', '')
            start_date_str = request.GET.get('start_date', '')
            end_date_str = request.GET.get('end_date', '')

            now = timezone.now()
            clamped = False
            # 默认最近7天
            if time_range == 'today':
                start_dt = timezone.make_aware(datetime.combine(now.date(), datetime.min.time()))
                end_dt = timezone.make_aware(datetime.combine(now.date(), datetime.max.time()))
            elif time_range == 'week' or time_range == '':
                start_dt = timezone.make_aware(datetime.combine((now.date() - timedelta(days=6)), datetime.min.time()))
                end_dt = timezone.make_aware(datetime.combine(now.date(), datetime.max.time()))
            elif time_range == 'month':
                # 使用当前月的第一天到当前日期（而不是固定30天）
                first_day_of_month = now.replace(day=1).date()
                start_dt = timezone.make_aware(datetime.combine(first_day_of_month, datetime.min.time()))
                end_dt = timezone.make_aware(datetime.combine(now.date(), datetime.max.time()))
            elif time_range.isdigit():
                days = int(time_range)
                start_dt = timezone.make_aware(datetime.combine((now.date() - timedelta(days=days-1)), datetime.min.time()))
                end_dt = timezone.make_aware(datetime.combine(now.date(), datetime.max.time()))
            elif time_range == 'custom' and start_date_str and end_date_str:
                try:
                    start_dt = timezone.make_aware(datetime.strptime(start_date_str, '%Y-%m-%d'))
                    end_dt = timezone.make_aware(datetime.strptime(end_date_str, '%Y-%m-%d')) + timedelta(days=1) - timedelta(seconds=1)
                    # 限制自定义时间范围不超过 3 个月（约 92 天）；超出则截断到 max_days
                    max_days = 92
                    delta_days = (end_dt.date() - start_dt.date()).days + 1
                    if delta_days > max_days:
                        # 截断 end_dt 到 start_dt + (max_days-1)
                        end_dt = timezone.make_aware(datetime.combine((start_dt.date() + timedelta(days=max_days-1)), datetime.max.time()))
                        clamped = True
                except Exception:
                    start_dt = timezone.make_aware(datetime.combine((now.date() - timedelta(days=6)), datetime.min.time()))
                    end_dt = timezone.make_aware(datetime.combine(now.date(), datetime.max.time()))
            else:
                # 默认最近7天
                start_dt = timezone.make_aware(datetime.combine((now.date() - timedelta(days=6)), datetime.min.time()))
                end_dt = timezone.make_aware(datetime.combine(now.date(), datetime.max.time()))

            # 查询执行记录
            executions = ExecutionRecord.objects.filter(
                created_at__gte=start_dt,
                created_at__lte=end_dt
            ).select_related()

            # 处理时间提取，依据时间范围决定返回模式
            stats_dict = defaultdict(int)

            total_days = (end_dt.date() - start_dt.date()).days + 1
            # 如果时间窗口较短（<=7天），返回小时x星期模式；否则返回周列（日历）模式（类似 GitHub）
            if total_days <= 7:
                # 对于小时间窗口（<=7天），按日期顺序返回行：每一行代表一个日期
                # 先统计每个 (hour, day_index) 的次数
                for execution in executions:
                    created_time = execution.created_at
                    if created_time:
                        local_time = timezone.localtime(created_time)
                        hour = local_time.hour  # 0-23
                        day_index = (local_time.date() - start_dt.date()).days
                        if 0 <= day_index < total_days:
                            stats_dict[(hour, day_index)] += 1

                # 生成完整的热力图数据（24小时 x total_days）
                heatmap_data = []
                for day_index in range(total_days):
                    for hour in range(24):
                        count = stats_dict.get((hour, day_index), 0)
                        heatmap_data.append([hour, day_index, count])

                # 生成 y_labels：例如 "周一 11-23" 或 "11-23"
                weekday_names = ['周日', '周一', '周二', '周三', '周四', '周五', '周六']
                y_labels = []
                for i in range(total_days):
                    d = (start_dt.date() + timedelta(days=i))
                    weekday = d.weekday()
                    # weekday: Monday=0 ... Sunday=6; map to weekday_names where index 0 is 周日
                    wk_label = weekday_names[(weekday + 1) % 7]
                    y_labels.append(f"{wk_label} {d.strftime('%m-%d')}")

                return SycResponse.success(content={
                    'mode': 'hourly',
                    'data': heatmap_data,
                    'x_labels': [f"{i}:00" for i in range(24)],
                    'y_labels': y_labels,
                    'start_date': start_dt.date().strftime('%Y-%m-%d'),
                    'end_date': end_dt.date().strftime('%Y-%m-%d'),
                    'total_days': total_days,
                    'clamped': clamped
                }, message="获取执行热力图成功")
            else:
                # Calendar mode (GitHub-like): columns = weeks (starting Monday), rows = weekdays (Mon..Sun)
                # Align first column to the Monday of the week containing start_dt
                first_monday = start_dt.date() - timedelta(days=start_dt.date().weekday())
                last_sunday = end_dt.date() + timedelta(days=(6 - end_dt.date().weekday()))
                num_weeks = ((last_sunday - first_monday).days // 7) + 1

                # Aggregate counts per (week_index, weekday) where weekday: 0=Mon .. 6=Sun
                for execution in executions:
                    created_time = execution.created_at
                    if not created_time:
                        continue
                    local_time = timezone.localtime(created_time)
                    local_date = local_time.date()
                    if local_date < start_dt.date() or local_date > end_dt.date():
                        continue
                    week_idx = (local_date - first_monday).days // 7
                    weekday = local_time.weekday()  # Monday=0 .. Sunday=6
                    stats_dict[(week_idx, weekday)] += 1

                # Build heatmap data: iterate weeks (columns) then weekdays (rows)
                heatmap_data = []
                for w in range(num_weeks):
                    for weekday in range(7):
                        count = stats_dict.get((w, weekday), 0)
                        heatmap_data.append([w, weekday, count])

                # x_labels: use week start dates (MM-DD) and also return ISO week_start_dates for exact date computation in frontend
                x_labels = []
                week_start_dates = []
                for w in range(num_weeks):
                    week_start_date = first_monday + timedelta(days=w * 7)
                    x_labels.append(week_start_date.strftime('%m-%d'))
                    week_start_dates.append(week_start_date.strftime('%Y-%m-%d'))

                return SycResponse.success(content={
                    'mode': 'calendar',
                    'data': heatmap_data,
                    'x_labels': x_labels,
                    'week_start_dates': week_start_dates,
                    'y_labels': ['周一','周二','周三','周四','周五','周六','周日'],
                    'start_date': start_dt.date().strftime('%Y-%m-%d'),
                    'end_date': end_dt.date().strftime('%Y-%m-%d'),
                    'total_days': total_days,
                    'clamped': clamped
                }, message="获取执行热力图成功")

        except Exception as e:
            return SycResponse.error(message=f"获取执行热力图失败: {str(e)}")

    @extend_schema(
        summary="获取Top20执行统计",
        tags=["仪表盘"]
    )
    @cache_response(timeout=60 * 5, key_func=lambda request, *args, **kwargs: f"top_executions_{request.GET.get('time_range', 'week')}_{request.GET.get('sort_by', 'count')}_{request.GET.get('start_date', '')}_{request.GET.get('end_date', '')}")  # 缓存5分钟，包含查询参数
    @action(detail=False, methods=['get'])
    def top_executions(self, request):
        """获取Top20执行统计，支持时间范围和排序方式"""
        try:
            from apps.executor.models import ExecutionRecord
            from django.db.models import Count, Avg, Q
            from datetime import datetime

            # 获取过滤参数
            time_range = request.GET.get('time_range', 'week')
            sort_by = request.GET.get('sort_by', 'count')
            start_date_str = request.GET.get('start_date', '')
            end_date_str = request.GET.get('end_date', '')

            # 根据时间范围确定日期
            end_date = timezone.now().date()

            if time_range == 'today':
                start_date = end_date
            elif time_range == 'week':
                start_date = end_date - timedelta(days=6)
            elif time_range == 'month':
                start_date = end_date - timedelta(days=29)
            elif time_range == 'custom' and start_date_str and end_date_str:
                try:
                    start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
                    end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date()
                except ValueError:
                    start_date = end_date - timedelta(days=6)
            else:
                start_date = end_date - timedelta(days=6)

            # 查询执行记录统计 - 先获取基本统计
            executions = ExecutionRecord.objects.filter(
                created_at__date__gte=start_date,
                created_at__date__lte=end_date
            ).values('name').annotate(
                count=Count('id'),
                success_count=Count('id', filter=Q(status='success'))
            ).filter(count__gt=0)

            # 计算成功率并格式化数据
            top_data = []
            for item in executions:
                success_rate = (item['success_count'] / item['count'] * 100) if item['count'] > 0 else 0

                # 单独计算该任务名称的平均持续时间
                task_records = ExecutionRecord.objects.filter(
                    created_at__date__gte=start_date,
                    created_at__date__lte=end_date,
                    name=item['name'],
                    started_at__isnull=False,
                    finished_at__isnull=False
                )

                # 计算平均持续时间
                total_duration = 0
                duration_count = 0
                for record in task_records:
                    if record.started_at and record.finished_at:
                        duration = (record.finished_at - record.started_at).total_seconds()
                        total_duration += duration
                        duration_count += 1

                avg_duration = total_duration / duration_count if duration_count > 0 else 0

                top_data.append({
                    'name': item['name'] or '未知任务',
                    'count': item['count'],
                    'success_rate': round(success_rate, 1),
                    'avg_duration': round(avg_duration, 1)
                })

            # 根据排序方式排序
            if sort_by == 'success_rate':
                top_data.sort(key=lambda x: x['success_rate'], reverse=True)
            elif sort_by == 'avg_duration':
                top_data.sort(key=lambda x: x['avg_duration'])
            else:  # count
                top_data.sort(key=lambda x: x['count'], reverse=True)

            # 取前20条
            top_data = top_data[:20]

            return SycResponse.success(content=top_data, message="获取Top20执行统计成功")

        except Exception as e:
            return SycResponse.error(message=f"获取Top20执行统计失败: {str(e)}")

    def _get_overview_data(self):
        """获取概览数据"""
        from apps.job_templates.models import JobTemplate, ExecutionPlan
        from apps.scheduler.models import ScheduledJob
        from apps.hosts.models import Host, HostGroup
        from apps.executor.models import ExecutionRecord

        # 基础资源统计
        resources = {
            'job_templates': {
                'total': JobTemplate.objects.count(),
                'description': '作业模板总数'
            },
            'execution_plans': {
                'total': ExecutionPlan.objects.count(),
                'description': '执行方案总数'
            },
            'hosts': {
                'total': Host.objects.count(),
                'online': Host.objects.filter(status='online').count(),
                'description': '主机总数'
            },
            'host_groups': {
                'total': HostGroup.objects.count(),
                'description': '主机分组总数'
            }
        }

        # 作业执行概览（今天）
        today = timezone.now().date()
        today_start = timezone.make_aware(datetime.combine(today, datetime.min.time()))

        job_overview = {
            'today_total': ExecutionRecord.objects.filter(created_at__gte=today_start).count(),
            'today_success': ExecutionRecord.objects.filter(
                created_at__gte=today_start,
                status='success'
            ).count(),
            'today_failed': ExecutionRecord.objects.filter(
                created_at__gte=today_start,
                status='failed'
            ).count(),
            'running': ExecutionRecord.objects.filter(status='running').count(),
        }

        # 定时任务概览
        scheduled_overview = {
            'total': ScheduledJob.objects.count(),
            'active': ScheduledJob.objects.filter(is_active=True).count(),
            'inactive': ScheduledJob.objects.filter(is_active=False).count(),
        }

        return {
            'resources': resources,
            'job_overview': job_overview,
            'scheduled_overview': scheduled_overview,
            'last_updated': timezone.now()
        }

    def _get_statistics_data(self):
        """获取统计数据"""
        from apps.executor.models import ExecutionRecord
        from apps.scheduler.models import ScheduledJob
        from apps.permissions.models import AuditLog

        # 最近7天的作业执行趋势
        seven_days_ago = timezone.now() - timedelta(days=7)
        daily_jobs = []

        for i in range(7):
            date = (timezone.now() - timedelta(days=6-i)).date()
            date_start = timezone.make_aware(datetime.combine(date, datetime.min.time()))
            date_end = timezone.make_aware(datetime.combine(date, datetime.max.time()))

            daily_count = ExecutionRecord.objects.filter(
                created_at__gte=date_start,
                created_at__lte=date_end
            ).count()

            success_count = ExecutionRecord.objects.filter(
                created_at__gte=date_start,
                created_at__lte=date_end,
                status='success'
            ).count()

            daily_jobs.append({
                'date': date.strftime('%m-%d'),
                'total': daily_count,
                'success': success_count,
                'failed': daily_count - success_count
            })

        # 执行记录状态分布
        job_status_distribution = {
            'success': ExecutionRecord.objects.filter(status='success').count(),
            'failed': ExecutionRecord.objects.filter(status='failed').count(),
            'running': ExecutionRecord.objects.filter(status='running').count(),
            'pending': ExecutionRecord.objects.filter(status='pending').count(),
        }

        # 定时任务执行统计
        scheduled_stats = []
        top_scheduled_jobs = ScheduledJob.objects.filter(
            total_runs__gt=0
        ).order_by('-total_runs')[:10]

        for job in top_scheduled_jobs:
            scheduled_stats.append({
                'name': job.name,
                'total_runs': job.total_runs,
                'success_runs': job.success_runs,
                'failed_runs': job.failed_runs,
                'success_rate': job.success_rate
            })

        # 用户活动统计
        user_activity = AuditLog.objects.filter(
            created_at__gte=seven_days_ago
        ).values('action').annotate(count=Count('action')).order_by('-count')[:10]

        return {
            'daily_jobs': daily_jobs,
            'job_status_distribution': job_status_distribution,
            'scheduled_stats': scheduled_stats,
            'user_activity': list(user_activity)
        }

    def _get_recent_activities(self):
        """获取最近活动"""
        from apps.executor.models import ExecutionRecord
        import logging

        logger = logging.getLogger(__name__)
        activities = []

        try:
            # 最近的执行记录
            recent_executions = ExecutionRecord.objects.select_related('executed_by').order_by('-created_at')[:20]
            for execution in recent_executions:
                activities.append({
                    'id': execution.id,
                    'type': 'execution',
                    'user': execution.executed_by.username if execution.executed_by else 'system',
                    'action': 'execute',
                    'resource_type': 'execution',
                    'description': f'执行任务: {execution.name}',
                    'status': execution.status,
                    'created_at': execution.created_at.isoformat() if execution.created_at else None
                })
        except Exception as e:
            logger.error(f"获取执行记录失败: {str(e)}")

        # 尝试获取操作日志（如果存在的话）
        try:
            from apps.permissions.models import AuditLog
            recent_logs = AuditLog.objects.select_related('user').order_by('-created_at')[:10]

            for log in recent_logs:
                activities.append({
                    'id': f'log_{log.id}',
                    'type': 'operation',
                    'user': log.user.username if log.user else 'System',
                    'action': log.action,
                    'resource_type': str(log.resource_type) if log.resource_type else 'unknown',
                    'description': log.description or '操作记录',
                    'created_at': log.created_at.isoformat() if log.created_at else None,
                    'ip_address': log.ip_address
                })
        except Exception as e:
            logger.warning(f"获取操作日志失败: {str(e)}")

        # 按时间排序
        activities.sort(key=lambda x: x.get('created_at', ''), reverse=True)

        return {
            'activities': activities[:30],  # 返回最近30条
            'total_count': len(activities)
        }

    def _get_system_status(self):
        """获取系统状态"""
        import logging
        import platform

        logger = logging.getLogger(__name__)

        # 主机状态统计
        try:
            from apps.hosts.models import Host
            host_status = {
                'total': Host.objects.count(),
                'online': Host.objects.filter(status='online').count(),
                'offline': Host.objects.filter(status='offline').count(),
                'unknown': Host.objects.filter(status='unknown').count(),
            }
        except Exception as e:
            logger.error(f"获取主机状态失败: {str(e)}")
            host_status = {
                'total': 0,
                'online': 0,
                'offline': 0,
                'unknown': 0,
            }

        # Agent 状态统计
        try:
            from apps.agents.models import Agent
            agent_status = {
                'total': Agent.objects.count(),
                'pending': Agent.objects.filter(status='pending').count(),
                'online': Agent.objects.filter(status='online').count(),
                'offline': Agent.objects.filter(status='offline').count(),
                'disabled': Agent.objects.filter(status='disabled').count(),
            }
        except Exception as e:
            logger.error(f"获取 Agent 状态失败: {str(e)}")
            agent_status = {
                'total': 0,
                'pending': 0,
                'online': 0,
                'offline': 0,
                'disabled': 0,
            }

        # 系统信息
        try:
            import psutil
            system_info = {
                'platform': platform.system(),
                'platform_version': platform.version(),
                'python_version': platform.python_version(),
                'cpu_count': psutil.cpu_count(),
                'cpu_percent': psutil.cpu_percent(interval=0.1),  # 减少等待时间
                'memory_total': psutil.virtual_memory().total,
                'memory_used': psutil.virtual_memory().used,
                'memory_percent': psutil.virtual_memory().percent,
                'disk_usage': psutil.disk_usage('C:').percent if platform.system() == 'Windows' else psutil.disk_usage('/').percent
            }
        except ImportError:
            logger.warning("psutil未安装，使用默认系统信息")
            system_info = {
                'platform': platform.system(),
                'platform_version': platform.version(),
                'python_version': platform.python_version(),
                'cpu_count': 'N/A',
                'cpu_percent': 0,
                'memory_total': 0,
                'memory_used': 0,
                'memory_percent': 0,
                'disk_usage': 0
            }
        except Exception as e:
            logger.error(f"获取系统信息失败: {str(e)}")
            system_info = {
                'platform': platform.system(),
                'platform_version': platform.version(),
                'python_version': platform.python_version(),
                'cpu_count': 'N/A',
                'cpu_percent': 0,
                'memory_total': 0,
                'memory_used': 0,
                'memory_percent': 0,
                'disk_usage': 0
            }

        # 简化的服务状态
        service_status = {
            'database': {
                'status': 'healthy',
                'message': 'OK'
            },
            'web_server': {
                'status': 'healthy',
                'message': 'OK'
            }
        }

        return {
            'host_status': host_status,
            'agent_status': agent_status,
            'system_info': system_info,
            'service_status': service_status,
            'last_check': timezone.now().isoformat()
        }
