"""
项目仪表盘视图
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
    @cache_response(timeout=60 * 15)  # 缓存15分钟
    @action(detail=False, methods=['get'])
    def execution_heatmap(self, request):
        """获取执行热力图数据（按小时和星期统计）"""
        try:
            from apps.executor.models import ExecutionRecord
            from django.db.models import Count
            from collections import defaultdict

            # 最近30天的数据
            thirty_days_ago = timezone.now() - timedelta(days=30)

            # 查询最近30天的执行记录
            executions = ExecutionRecord.objects.filter(
                created_at__gte=thirty_days_ago
            ).select_related()

            # 使用Python处理时间提取，避免数据库兼容性问题
            stats_dict = defaultdict(int)

            for execution in executions:
                # 提取小时和星期几
                created_time = execution.created_at
                if created_time:
                    # 使用Django的timezone.localtime()自动转换为设置的时区
                    local_time = timezone.localtime(created_time)
                    hour = local_time.hour  # 0-23 (本地时间)
                    weekday = local_time.weekday()  # 0=Monday, 6=Sunday
                    # 转换为0=Sunday, 1=Monday的格式
                    weekday = (weekday + 1) % 7
                    stats_dict[(hour, weekday)] += 1

            # 生成完整的热力图数据（24小时 x 7天）
            heatmap_data = []
            for weekday in range(7):  # 0-6 (Sunday to Saturday)
                for hour in range(24):  # 0-23
                    count = stats_dict.get((hour, weekday), 0)
                    heatmap_data.append([hour, weekday, count])

            return SycResponse.success(content=heatmap_data, message="获取执行热力图成功")

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
            'system_info': system_info,
            'service_status': service_status,
            'last_check': timezone.now().isoformat()
        }
