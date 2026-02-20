"""
统一执行记录API视图
"""
from django_filters import OrderingFilter
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from django_filters.rest_framework import DjangoFilterBackend
from django.db.models import Q
from django.contrib.contenttypes.models import ContentType
from utils.pagination import CustomPagination
from utils.responses import SycResponse
from .models import ExecutionRecord, ExecutionStep
from .serializers import (
    ExecutionRecordSerializer,
    ExecutionRecordDetailSerializer,
    ExecutionStepContentSerializer,
    ExecutionStepResultSerializer,
    ExecutionOperationLogSerializer,
)
from .filters import ExecutionRecordFilter
from apps.permissions.permissions import ExecutionRecordPermission
from apps.executor.services import ExecutionRecordService
from apps.agents.execution_service import AgentExecutionService
from apps.hosts.models import Host
from apps.permissions.models import AuditLog
from utils.audit_service import AuditLogService
import logging

logger = logging.getLogger(__name__)


class ExecutionRecordViewSet(viewsets.ReadOnlyModelViewSet):
    """统一执行记录ViewSet"""

    queryset = ExecutionRecord.objects.all()
    serializer_class = ExecutionRecordSerializer
    permission_classes = [IsAuthenticated, ExecutionRecordPermission]
    pagination_class = CustomPagination
    filter_backends = [DjangoFilterBackend]
    filterset_class = ExecutionRecordFilter

    def _log_execution_action(self, request, execution_record, action, success, description='', extra_data=None, error_message=''):
        """
        记录执行相关操作的审计日志，失败不影响主流程
        """
        try:
            AuditLogService.log_action(
                user=request.user,
                action=action,
                description=description or '',
                request=request,
                success=success,
                error_message=error_message or '',
                resource_type=ContentType.objects.get_for_model(ExecutionRecord),
                resource_id=execution_record.id,
                resource_name=str(execution_record),
                extra_data=extra_data or {}
            )
        except Exception as e:
            logger.warning(f"审计日志记录失败: {e}")

    def get_serializer_class(self):
        if self.action == 'retrieve':
            return ExecutionRecordDetailSerializer
        return ExecutionRecordSerializer

    def get_queryset(self):
        """获取查询集 - 支持混合模式"""
        queryset = super().get_queryset().select_related('executed_by', 'content_type').order_by('-created_at')

        # 默认只返回最新的执行记录（混合模式）
        if self.request.query_params.get('include_retries') != 'true':
            queryset = queryset.filter(is_latest=True)

        return queryset

    def list(self, request, *args, **kwargs):
        """获取执行记录列表"""
        queryset = self.filter_queryset(self.get_queryset())
        page = self.paginate_queryset(queryset)

        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)

        serializer = self.get_serializer(queryset, many=True)
        return SycResponse.success(
            content=serializer.data,
            message="获取执行记录列表成功"
        )

    def retrieve(self, request, *args, **kwargs):
        """获取执行记录详情（日志另行按需拉取）"""
        execution_record = self.get_object()
        serializer = self.get_serializer(execution_record)

        if execution_record.is_running:
            return SycResponse.success(
                content=serializer.data,
                message='执行正在进行中，可使用实时日志接口'
            )

        return SycResponse.success(
            content=serializer.data,
            message='执行记录详情获取成功'
        )

    @action(detail=True, methods=['get'])
    def logs(self, request, pk=None):
        """基于 log_pointer 获取历史日志（聚合后的 step_logs）"""
        execution_record = self.get_object()
        from utils.log_archive_service import log_archive_service

        try:
            limit = int(request.query_params.get('limit', 500))
        except Exception:
            limit = 500

        pointer = request.query_params.get('pointer')
        logs_meta = {}
        if isinstance(execution_record.execution_results, dict):
            logs_meta = execution_record.execution_results.get('logs_meta', {}) or {}
            pointer = pointer or logs_meta.get('log_pointer')

        if not pointer:
            return SycResponse.error(message='缺少日志指针，无法回源')

        result = log_archive_service.get_execution_logs_by_pointer(pointer, limit=limit)
        if result.get('success'):
            content = result['data']
            content['logs_meta'] = {**logs_meta, 'log_pointer': pointer}
            return SycResponse.success(
                content=content,
                message='历史日志获取成功'
            )

        return SycResponse.error(message=result.get('message', '历史日志获取失败'))

    @action(detail=True, methods=['get'], url_path='steps/(?P<step_id>[^/.]+)/content')
    def step_content(self, request, pk=None, step_id=None):
        """获取单个步骤的脚本/参数内容（懒加载，默认掩码敏感字段）"""
        execution_record = self.get_object()
        try:
            step = execution_record.steps.get(id=step_id)
        except ExecutionStep.DoesNotExist:
            return SycResponse.error(message='步骤不存在')

        serializer = ExecutionStepContentSerializer(step)
        return SycResponse.success(content=serializer.data, message='步骤内容获取成功')

    @action(detail=True, methods=['get'], url_path='steps/(?P<step_id>[^/.]+)/result')
    def step_result(self, request, pk=None, step_id=None):
        """获取步骤执行结果（主机列表/状态/耗时）"""
        execution_record = self.get_object()
        try:
            step = execution_record.steps.get(id=step_id)
        except ExecutionStep.DoesNotExist:
            return SycResponse.error(message='步骤不存在')

        serializer = ExecutionStepResultSerializer(step)
        data = serializer.data

        host_ids = [h.get('id') for h in data.get('hosts', []) if h.get('id')]
        if host_ids:
            hosts = Host.objects.filter(id__in=host_ids)
            host_map = {str(h.id): h for h in hosts}
            for item in data['hosts']:
                hid = item.get('id')
                if hid is None:
                    continue
                host_obj = host_map.get(str(hid))
                if not host_obj:
                    continue
                if not item.get('name'):
                    item['name'] = host_obj.name
                if not item.get('ip'):
                    item['ip'] = host_obj.internal_ip or host_obj.public_ip or ''

        return SycResponse.success(content=data, message='步骤结果获取成功')

    @action(detail=True, methods=['get'], url_path='steps/(?P<step_id>[^/.]+)/hosts/(?P<host_id>[^/.]+)/logs')
    def host_logs(self, request, pk=None, step_id=None, host_id=None):
        """获取步骤内单主机日志（pointer+limit 分页）"""
        execution_record = self.get_object()
        try:
            step = execution_record.steps.get(id=step_id)
        except ExecutionStep.DoesNotExist:
            return SycResponse.error(message='步骤不存在')

        try:
            limit = int(request.query_params.get('limit', 500))
        except Exception:
            limit = 500

        pointer = request.query_params.get('pointer')
        if not pointer:
            logs_meta = {}
            if isinstance(execution_record.execution_results, dict):
                logs_meta = execution_record.execution_results.get('logs_meta', {}) or {}
            pointer = logs_meta.get('log_pointer')

        if pointer:
            from utils.realtime_logs import realtime_log_service
            result = realtime_log_service.get_logs_by_pointer_filtered(
                pointer=pointer,
                limit=limit,
                step_name=step.step_name,
                step_order=step.step_order,
                host_id=host_id,
            )
            logs = result.get('logs', [])
            log_context = "".join([
                f"[{log.get('timestamp')}] {log.get('content')}\n" for log in logs if log.get('content')
            ])
            return SycResponse.success(
                content={
                    'log_context': log_context,
                    'finished': True,
                    'next_pointer': result.get('next_pointer'),
                },
                message='日志获取成功'
            )

        # fallback: 从归档 step_logs 中读取
        results = execution_record.execution_results or {}
        step_logs = results.get('step_logs', {}) if isinstance(results, dict) else {}
        log_context = ''
        if isinstance(step_logs, dict):
            for _, step_data in step_logs.items():
                if not isinstance(step_data, dict):
                    continue
                if step_data.get('step_order') != step.step_order and step_data.get('step_name') != step.step_name:
                    continue
                host_logs = step_data.get('hosts') or {}
                host_data = host_logs.get(str(host_id)) or host_logs.get(host_id)
                if isinstance(host_data, dict):
                    stdout = host_data.get('stdout') or ''
                    stderr = host_data.get('stderr') or ''
                    if stdout and stderr and not stdout.endswith('\n'):
                        stdout = f"{stdout}\n"
                    log_context = f"{stdout}{stderr}"
                break

        return SycResponse.success(
            content={
                'log_context': log_context,
                'finished': True,
                'next_pointer': None,
            },
            message='日志获取成功'
        )

    @action(detail=True, methods=['get'])
    def operation_logs(self, request, pk=None):
        """获取执行记录的操作审计日志"""
        execution_record = self.get_object()
        qs = AuditLog.objects.filter(
            resource_type=ContentType.objects.get_for_model(ExecutionRecord),
            resource_id=execution_record.id
        ).select_related('user').order_by('-created_at')

        action_filter = request.query_params.get('action')
        if action_filter:
            qs = qs.filter(action=action_filter)

        page = self.paginate_queryset(qs)
        if page is not None:
            serializer = ExecutionOperationLogSerializer(page, many=True)
            return self.get_paginated_response(serializer.data)

        serializer = ExecutionOperationLogSerializer(qs, many=True)
        return SycResponse.success(content=serializer.data, message='操作记录获取成功')

    @action(detail=True, methods=['post'])
    def retry(self, request, pk=None):
        """重做执行记录"""
        execution_record = self.get_object()

        # 检查是否可以重做
        if execution_record.is_running:
            self._log_execution_action(
                request,
                execution_record,
                action='retry_execution',
                success=False,
                description='重做失败：任务正在执行中',
                extra_data={'reason': 'running'}
            )
            return SycResponse.error(message='任务正在执行中，无法重做')

        if execution_record.retry_count >= execution_record.max_retries:
            self._log_execution_action(
                request,
                execution_record,
                action='retry_execution',
                success=False,
                description='重做失败：达到最大重试次数',
                extra_data={'reason': 'max_retries'}
            )
            return SycResponse.error(message=f'已达到最大重试次数 ({execution_record.max_retries})')

        try:
            # 获取重试参数
            retry_type = request.data.get('retry_type', 'full')  # full: 完整重试, step: 步骤重试
            step_id = request.data.get('step_id')
            failed_only = request.data.get('failed_only', True)
            agent_server_url = request.data.get('agent_server_url')
            extra_data = {
                'retry_type': retry_type,
                'step_id': step_id,
                'failed_only': failed_only,
                'agent_server_url': agent_server_url,
            }

            logger.info(
                f"开始重做执行记录: {execution_record.execution_id}, "
                f"类型: {execution_record.execution_type}, 重试类型: {retry_type}"
            )

            # 优先使用 AgentExecutionService 的重试方法（支持 Agent 方式和步骤重试）
            from apps.agents.execution_service import AgentExecutionService
            result = AgentExecutionService.retry_execution_record(
                execution_record=execution_record,
                user=request.user,
                retry_type=retry_type,
                step_id=step_id,
                failed_only=failed_only,
                agent_server_url=agent_server_url,
            )

            logger.info(f"重做结果: {result}")

            if result['success']:
                self._log_execution_action(
                    request,
                    execution_record,
                    action='retry_execution',
                    success=True,
                    description='重做任务启动成功',
                    extra_data=extra_data
                )
                return SycResponse.success(
                    content={
                        'execution_record_id': result.get('execution_record_id'),
                        'execution_id': result.get('execution_id'),
                    },
                    message=result.get('message', '重做任务启动成功')
                )
            else:
                self._log_execution_action(
                    request,
                    execution_record,
                    action='retry_execution',
                    success=False,
                    description='重做任务启动失败',
                    extra_data=extra_data,
                    error_message=result.get('error')
                )
                return SycResponse.error(
                    message=result.get('error', '重做任务启动失败')
                )

        except Exception as e:
            logger.error(f"重做任务失败: {str(e)}")
            self._log_execution_action(
                request,
                execution_record,
                action='retry_execution',
                success=False,
                description='重做任务异常',
                extra_data={'exception': str(e)},
                error_message=str(e)
            )
            return SycResponse.error(message=f'重做任务失败: {str(e)}')

    @action(detail=True, methods=['post'])
    def cancel(self, request, pk=None):
        """取消执行 - 支持SSH（Celery）和Agent两种方式"""
        execution_record = self.get_object()

        if execution_record.status not in ['pending', 'running']:
            self._log_execution_action(
                request,
                execution_record,
                action='cancel_execution',
                success=False,
                description='取消失败：状态不允许',
                extra_data={'status': execution_record.status}
            )
            return SycResponse.error(
                message=f'任务状态为 {execution_record.get_status_display()}，无法取消'
            )

        try:
            from django.utils import timezone
            from django.core.cache import cache
            
            # 检查执行方式
            execution_mode = execution_record.execution_parameters.get('execution_mode', 'ssh')
            agent_server_url = execution_record.execution_parameters.get('agent_server_url')
            extra_data = {
                'execution_mode': execution_mode,
                'agent_server_url': agent_server_url,
            }
            
            if execution_mode == 'agent' or agent_server_url:
                # Agent方式：调用Agent取消服务
                from apps.agents.execution_service import AgentExecutionService
                
                cancel_result = AgentExecutionService.cancel_task_via_agent(
                    execution_record=execution_record,
                    agent_server_url=agent_server_url,
                )
                
                if cancel_result['success']:
                    # 更新执行记录状态
                    execution_record.status = 'cancelled'
                    execution_record.finished_at = timezone.now()
                    execution_record.save()
                    self._log_execution_action(
                        request,
                        execution_record,
                        action='cancel_execution',
                        success=True,
                        description='Agent 方式取消任务成功',
                        extra_data={**extra_data, **{
                            'cancelled_count': cancel_result.get('cancelled_count', 0),
                            'failed_count': cancel_result.get('failed_count', 0),
                            'total_count': cancel_result.get('total_count', 0),
                        }}
                    )
                    
                    return SycResponse.success(
                        content={
                            'cancelled_count': cancel_result.get('cancelled_count', 0),
                            'failed_count': cancel_result.get('failed_count', 0),
                            'total_count': cancel_result.get('total_count', 0),
                        },
                        message=cancel_result.get('message', '任务已取消')
                    )
                else:
                    self._log_execution_action(
                        request,
                        execution_record,
                        action='cancel_execution',
                        success=False,
                        description='Agent 方式取消任务失败',
                        extra_data=extra_data,
                        error_message=cancel_result.get('error')
                    )
                    return SycResponse.error(
                        message=cancel_result.get('error', '取消任务失败')
                    )
            else:
                # 传统 SSH 方式：仅设置 Redis 取消标志，由执行侧自行检查并退出
                from django.core.cache import cache
                cache.set(f"cancel:{execution_record.execution_id}", "1", timeout=3600)
                logger.info(f"设置取消标志(SSH模式): {execution_record.execution_id}")

            # 更新执行记录状态
            execution_record.status = 'cancelled'
            execution_record.finished_at = timezone.now()
            execution_record.save()
            self._log_execution_action(
                request,
                execution_record,
                action='cancel_execution',
                success=True,
                description='SSH 方式取消任务成功',
                extra_data=extra_data
            )

            return SycResponse.success(message='任务已取消')

        except Exception as e:
            logger.error(f"取消任务失败: {str(e)}")
            self._log_execution_action(
                request,
                execution_record,
                action='cancel_execution',
                success=False,
                description='取消任务异常',
                extra_data={'exception': str(e)},
                error_message=str(e)
            )
            return SycResponse.error(message=f'取消任务失败: {str(e)}')

    @action(detail=True, methods=['get'])
    def retry_history(self, request, pk=None):
        """获取重试历史"""
        execution_record = self.get_object()
        root_execution = execution_record.get_root_execution()

        # 获取完整的重试链
        retry_chain = root_execution.get_retry_chain()

        serializer = self.get_serializer(retry_chain, many=True)
        return SycResponse.success(
            content=serializer.data,
            message=f"获取重试历史成功，共 {len(retry_chain)} 条记录"
        )


    @action(detail=True, methods=['post'], url_path='retry_step')
    def retry_step_inplace(self, request, pk=None):
        """步骤原地重试 - 不创建新的执行记录，在原记录上重试"""
        execution_record = self.get_object()
        step_id = request.data.get('step_id')
        retry_type = request.data.get('retry_type', 'failed_only')
        host_ids = request.data.get('host_ids')  # 可选，指定要重试的主机ID列表

        if not step_id:
            self._log_execution_action(
                request,
                execution_record,
                action='retry_step',
                success=False,
                description='步骤重试失败：缺少步骤ID'
            )
            return SycResponse.error(message='步骤ID不能为空')

        if retry_type not in ['failed_only', 'all']:
            self._log_execution_action(
                request,
                execution_record,
                action='retry_step',
                success=False,
                description='步骤重试失败：重试类型无效',
                extra_data={'retry_type': retry_type}
            )
            return SycResponse.error(message='重试类型无效')

        if execution_record.status not in ['failed', 'running']:
            self._log_execution_action(
                request,
                execution_record,
                action='retry_step',
                success=False,
                description='步骤重试失败：状态不允许',
                extra_data={'status': execution_record.status}
            )
            return SycResponse.error(message='只有失败或运行中的执行记录才能进行原地重试')

        # 如果指定了主机ID列表，验证格式
        if host_ids is not None:
            if not isinstance(host_ids, list):
                self._log_execution_action(
                    request,
                    execution_record,
                    action='retry_step',
                    success=False,
                    description='步骤重试失败：host_ids 必须是数组'
                )
                return SycResponse.error(message='主机ID列表必须是数组')
            if len(host_ids) == 0:
                self._log_execution_action(
                    request,
                    execution_record,
                    action='retry_step',
                    success=False,
                    description='步骤重试失败：host_ids 为空'
                )
                return SycResponse.error(message='主机ID列表不能为空')

        try:
            # 调用服务层进行原地重试
            from .services import ExecutionRecordService
            result = ExecutionRecordService.retry_step_inplace(
                execution_record=execution_record,
                step_id=step_id,
                retry_type=retry_type,
                user=request.user,
                host_ids=host_ids
            )

            if result['success']:
                self._log_execution_action(
                    request,
                    execution_record,
                    action='retry_step',
                    success=True,
                    description='步骤原地重试成功',
                    extra_data={
                        'step_id': step_id,
                        'retry_type': retry_type,
                        'host_ids': host_ids,
                    }
                )
                return SycResponse.success(
                    content={'execution_record_id': result['execution_record_id']},
                    message=result['message']
                )
            else:
                self._log_execution_action(
                    request,
                    execution_record,
                    action='retry_step',
                    success=False,
                    description='步骤原地重试失败',
                    extra_data={
                        'step_id': step_id,
                        'retry_type': retry_type,
                        'host_ids': host_ids,
                    },
                    error_message=result.get('error')
                )
                return SycResponse.error(message=result['error'])

        except Exception as e:
            logger.error(f"步骤原地重试失败: {str(e)}")
            self._log_execution_action(
                request,
                execution_record,
                action='retry_step',
                success=False,
                description='步骤原地重试异常',
                extra_data={
                    'step_id': step_id,
                    'retry_type': retry_type,
                    'host_ids': host_ids,
                    'exception': str(e),
                },
                error_message=str(e)
            )
            return SycResponse.error(message=f'步骤原地重试失败: {str(e)}')

    @action(detail=True, methods=['post'])
    def ignore_step_error(self, request, pk=None):
        """忽略步骤错误继续执行"""
        execution_record = self.get_object()
        step_id = request.data.get('step_id')

        if not step_id:
            self._log_execution_action(
                request,
                execution_record,
                action='ignore_error',
                success=False,
                description='忽略错误失败：缺少步骤ID'
            )
            return SycResponse.error(message='步骤ID不能为空')

        if execution_record.status != 'failed':
            self._log_execution_action(
                request,
                execution_record,
                action='ignore_error',
                success=False,
                description='忽略错误失败：状态不允许',
                extra_data={'status': execution_record.status}
            )
            return SycResponse.error(message='只有失败的执行记录才能忽略错误')

        try:
            # 调用服务层进行错误忽略
            from .services import ExecutionRecordService
            result = ExecutionRecordService.ignore_step_error(
                execution_record=execution_record,
                step_id=step_id,
                user=request.user
            )

            if result['success']:
                self._log_execution_action(
                    request,
                    execution_record,
                    action='ignore_error',
                    success=True,
                    description='忽略步骤错误成功',
                    extra_data={'step_id': step_id}
                )
                return SycResponse.success(message=result['message'])
            else:
                self._log_execution_action(
                    request,
                    execution_record,
                    action='ignore_error',
                    success=False,
                    description='忽略步骤错误失败',
                    extra_data={'step_id': step_id},
                    error_message=result.get('error')
                )
                return SycResponse.error(message=result['error'])

        except Exception as e:
            logger.error(f"忽略步骤错误失败: {str(e)}")
            self._log_execution_action(
                request,
                execution_record,
                action='ignore_error',
                success=False,
                description='忽略步骤错误异常',
                extra_data={'step_id': step_id, 'exception': str(e)},
                error_message=str(e)
            )
            return SycResponse.error(message=f'忽略步骤错误失败: {str(e)}')

    @action(detail=True, methods=['get'])
    def trace(self, request, pk=None):
        """获取执行链路信息"""
        execution_record = self.get_object()

        try:
            from apps.job_templates.models import ExecutionPlan, JobTemplate
            from apps.scheduler.models import ScheduledJob

            related_object = execution_record.related_object
            plan = None
            template = None

            if isinstance(related_object, ExecutionPlan):
                plan = related_object
                template = related_object.template
            elif isinstance(related_object, JobTemplate):
                template = related_object
            elif isinstance(related_object, ScheduledJob):
                plan = related_object.execution_plan
                template = plan.template if plan else None

            scheduled_jobs = []
            if plan:
                jobs = ScheduledJob.objects.filter(execution_plan=plan).only(
                    'id',
                    'name',
                    'is_active',
                    'cron_expression',
                    'timezone',
                    'last_run_time',
                    'next_run_time'
                )
                scheduled_jobs = [
                    {
                        'id': job.id,
                        'name': job.name,
                        'is_active': job.is_active,
                        'cron_expression': job.cron_expression,
                        'timezone': job.timezone,
                        'last_run_time': job.last_run_time,
                        'next_run_time': job.next_run_time,
                    }
                    for job in jobs
                ]

            chain = {
                'job_template': {
                    'id': template.id,
                    'name': template.name,
                } if template else None,
                'execution_plan': {
                    'id': plan.id,
                    'name': plan.name,
                } if plan else None,
                'scheduled_jobs': scheduled_jobs,
                'execution_record': {
                    'id': execution_record.id,
                    'execution_id': execution_record.execution_id,
                    'name': execution_record.name,
                    'status': execution_record.status,
                    'status_display': execution_record.get_status_display(),
                    'created_at': execution_record.created_at,
                    'execution_type': execution_record.execution_type,
                }
            }

            recent_qs = ExecutionRecord.objects.none()
            if execution_record.content_type_id and execution_record.object_id:
                recent_qs = ExecutionRecord.objects.filter(
                    content_type=execution_record.content_type,
                    object_id=execution_record.object_id
                ).order_by('-created_at')[:10]

            if not recent_qs.exists():
                recent_qs = ExecutionRecord.objects.filter(id=execution_record.id)

            recent_executions = [
                {
                    'id': record.id,
                    'execution_id': record.execution_id,
                    'name': record.name,
                    'status': record.status,
                    'status_display': record.get_status_display(),
                    'created_at': record.created_at,
                }
                for record in recent_qs
            ]

            return SycResponse.success(
                content={
                    'chain': chain,
                    'recent_executions': recent_executions,
                },
                message='获取执行链路成功'
            )

        except Exception as e:
            logger.error(f"获取执行链路失败: {str(e)}", exc_info=True)
            return SycResponse.error(message=f'获取执行链路失败: {str(e)}')
