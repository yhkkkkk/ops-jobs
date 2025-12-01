"""
统一执行记录API视图
"""
from django_filters import OrderingFilter
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from django_filters.rest_framework import DjangoFilterBackend
from django.db.models import Q
from utils.pagination import CustomPagination
from utils.responses import SycResponse
from .models import ExecutionRecord, ExecutionStep
from .serializers import ExecutionRecordSerializer, ExecutionRecordDetailSerializer
from .filters import ExecutionRecordFilter
import logging

logger = logging.getLogger(__name__)


class ExecutionRecordViewSet(viewsets.ReadOnlyModelViewSet):
    """统一执行记录ViewSet"""

    queryset = ExecutionRecord.objects.all()
    serializer_class = ExecutionRecordSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = CustomPagination
    filter_backends = [DjangoFilterBackend]
    filterset_class = ExecutionRecordFilter

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
        """获取执行记录详情和日志信息"""
        execution_record = self.get_object()

        # 如果执行正在运行，返回实时日志连接信息
        if execution_record.is_running and execution_record.celery_task_id:
            serializer = self.get_serializer(execution_record)
            return SycResponse.success(
                content=serializer.data,
                message='执行正在进行中，可使用实时日志接口'
            )
        # 如果执行已完成，返回历史日志
        elif execution_record.is_completed:
            from utils.log_archive_service import log_archive_service

            # 获取历史日志（不分页）
            result = log_archive_service.get_execution_logs(execution_record.execution_id)

            if result['success']:
                # 准备序列化器需要的数据
                log_data = {
                    'step_logs': result['data'].get('step_logs', {}),
                    'summary': result['data']['summary']
                }

                # 使用详情序列化器
                serializer = self.get_serializer(
                    execution_record,
                    log_data=log_data
                )
                
                return SycResponse.success(
                    content=serializer.data,
                    message='执行记录详情获取成功'
                )
            else:
                # 如果是取消状态且没有日志，返回空日志而不是404
                if execution_record.status == 'cancelled':
                    log_data = {
                        'step_logs': {},
                        'summary': {
                            'total_steps': 0,
                            'total_hosts': 0,
                            'success_hosts': 0,
                            'failed_hosts': 0
                        }
                    }
                    serializer = self.get_serializer(
                        execution_record,
                        log_data=log_data
                    )
                    
                    return SycResponse.success(
                        content=serializer.data,
                        message='任务已取消，暂无执行日志'
                    )
                else:
                    return SycResponse.not_found(message=f'获取历史日志失败: {result["message"]}')

        else:
            # 其他状态，返回基本信息
            serializer = self.get_serializer(execution_record)
            return SycResponse.success(
                content=serializer.data,
                message='执行记录详情获取成功'
            )

    @action(detail=True, methods=['post'])
    def retry(self, request, pk=None):
        """重做执行记录"""
        execution_record = self.get_object()

        # 检查是否可以重做
        if execution_record.is_running:
            return SycResponse.error(message='任务正在执行中，无法重做')

        if execution_record.retry_count >= execution_record.max_retries:
            return SycResponse.error(message=f'已达到最大重试次数 ({execution_record.max_retries})')

        try:
            logger.info(f"开始重做执行记录: {execution_record.execution_id}, 类型: {execution_record.execution_type}")

            # 根据执行类型进行重做
            if execution_record.execution_type == 'job_workflow':
                result = self._retry_job_workflow(execution_record, request.user)
            elif execution_record.execution_type == 'quick_script':
                result = self._retry_quick_script(execution_record, request.user)
            elif execution_record.execution_type == 'quick_file_transfer':
                result = self._retry_file_transfer(execution_record, request.user)
            else:
                return SycResponse.error(message=f'不支持重做执行类型: {execution_record.execution_type}')

            logger.info(f"重做结果: {result}")

            if result['success']:
                return SycResponse.success(content=result, message='重做任务启动成功')
            else:
                return SycResponse.error(
                    message=result.get('error', '重做任务启动失败')
                )

        except Exception as e:
            logger.error(f"重做任务失败: {str(e)}")
            return SycResponse.error(message=f'重做任务失败: {str(e)}')

    @action(detail=True, methods=['post'])
    def cancel(self, request, pk=None):
        """取消执行 - 混合方案（redis标志 + SIGUSR1信号）"""
        execution_record = self.get_object()

        if execution_record.status not in ['pending', 'running']:
            return SycResponse.error(
                message=f'任务状态为 {execution_record.get_status_display()}，无法取消'
            )

        try:
            if execution_record.celery_task_id:
                from celery import current_app
                from django.core.cache import cache
                import signal
                
                # 第一层：设置redis取消标志（优雅取消）
                cache.set(f"cancel:{execution_record.execution_id}", "1", timeout=3600)
                logger.info(f"设置取消标志: {execution_record.execution_id}")
                
                # 第二层：发送SIGUSR1信号（强制取消）
                try:
                    current_app.control.revoke(
                        execution_record.celery_task_id, 
                        terminate=True, 
                        signal='SIGUSR1'
                    )
                    logger.info(f"发送取消信号: {execution_record.celery_task_id}")
                except Exception as e:
                    logger.warning(f"发送取消信号失败: {e}")
                    pass

            # 更新执行记录状态
            from django.utils import timezone
            execution_record.status = 'cancelled'
            execution_record.finished_at = timezone.now()
            execution_record.save()

            return SycResponse.success(message='任务已取消')

        except Exception as e:
            logger.error(f"取消任务失败: {str(e)}")
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


    def retry_step_inplace(self, request, pk=None):
        """步骤原地重试 - 不创建新的执行记录，在原记录上重试"""
        execution_record = self.get_object()
        step_id = request.data.get('step_id')
        retry_type = request.data.get('retry_type', 'failed_only')

        if not step_id:
            return SycResponse.error(message='步骤ID不能为空')

        if retry_type not in ['failed_only', 'all']:
            return SycResponse.error(message='重试类型无效')

        # 检查执行记录状态
        if execution_record.status not in ['failed', 'running']:
            return SycResponse.error(message='只有失败或运行中的执行记录才能进行原地重试')

        try:
            # 调用服务层进行原地重试
            from .services import ExecutionRecordService
            result = ExecutionRecordService.retry_step_inplace(
                execution_record=execution_record,
                step_id=step_id,
                retry_type=retry_type,
                user=request.user
            )

            if result['success']:
                return SycResponse.success(
                    content={'execution_record_id': result['execution_record_id']},
                    message=result['message']
                )
            else:
                return SycResponse.error(message=result['error'])

        except Exception as e:
            logger.error(f"步骤原地重试失败: {str(e)}")
            return SycResponse.error(message=f'步骤原地重试失败: {str(e)}')

    @action(detail=True, methods=['post'])
    def ignore_step_error(self, request, pk=None):
        """忽略步骤错误继续执行"""
        execution_record = self.get_object()
        step_id = request.data.get('step_id')

        if not step_id:
            return SycResponse.error(message='步骤ID不能为空')

        # 检查执行记录状态
        if execution_record.status != 'failed':
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
                return SycResponse.success(message=result['message'])
            else:
                return SycResponse.error(message=result['error'])

        except Exception as e:
            logger.error(f"忽略步骤错误失败: {str(e)}")
            return SycResponse.error(message=f'忽略步骤错误失败: {str(e)}')

    def _retry_job_workflow(self, execution_record, user):
        """重做ExecutionPlan工作流（混合模式）"""
        logger.info(f"开始重做工作流: {execution_record.execution_id}")

        if not execution_record.related_object:
            logger.error("找不到关联的ExecutionPlan对象")
            return {'success': False, 'error': '找不到关联的ExecutionPlan对象'}

        from apps.job_templates.services import ExecutionPlanService
        from django.db import transaction

        try:
            with transaction.atomic():
                # 获取根执行记录
                root_execution = execution_record.get_root_execution()
                logger.info(f"根执行记录: {root_execution.execution_id}")

                result = ExecutionPlanService.execute_plan(
                    execution_plan=execution_record.related_object,
                    user=user,
                    trigger_type='retry',
                    name=f"重试: {root_execution.name}",
                    description=f"重试执行记录 {root_execution.execution_id}",
                    execution_parameters=execution_record.execution_parameters
                )

                logger.info(f"ExecutionPlanService.execute_plan 结果: {result}")

                if result['success']:
                    # 获取新的执行记录
                    from apps.executor.models import ExecutionRecord
                    new_execution = ExecutionRecord.objects.get(id=result['execution_record_id'])
                    logger.info(f"新执行记录: {new_execution.execution_id}")

                    # 设置重试关系
                    new_execution.parent_execution = root_execution
                    new_execution.is_latest = True
                    new_execution.retry_reason = "手动重试"
                    new_execution.save()
                    logger.info("重试关系设置完成")

                    # 将之前的所有记录标记为非最新
                    from django.db.models import Q
                    updated_count = ExecutionRecord.objects.filter(
                        Q(id=root_execution.id) |
                        Q(parent_execution=root_execution)
                    ).exclude(id=new_execution.id).update(is_latest=False)
                    logger.info(f"更新了 {updated_count} 条记录为非最新")

                    # 更新根记录的重试次数
                    root_execution.retry_count = root_execution.total_retry_count
                    root_execution.save()
                    logger.info("根记录重试次数更新完成")

            logger.info(f"工作流重做完成，返回结果: {result}")
            return result

        except Exception as e:
            logger.error(f"工作流重做失败: {str(e)}", exc_info=True)
            return {'success': False, 'error': f'工作流重做失败: {str(e)}'}

    def _retry_quick_script(self, execution_record, user):
        """重做快速脚本执行"""
        from apps.quick_execute.services import QuickExecuteService

        params = execution_record.execution_parameters

        # 从target_hosts重新构造主机ID列表
        target_host_ids = [host['id'] for host in execution_record.target_hosts]

        # 重新构造脚本执行参数
        script_data = {
            'script_content': params.get('script_content'),
            'script_type': params.get('script_type', 'shell'),
            'timeout': params.get('timeout', 300),
            'execution_mode': params.get('execution_mode', 'parallel'),
            'rolling_batch_size': params.get('rolling_batch_size', 1),
            'rolling_batch_delay': params.get('rolling_batch_delay', 0),
            'target_host_ids': target_host_ids,
            'global_variables': params.get('global_variables', {}),
            'positional_args': params.get('positional_args', []),
            'ignore_error': params.get('ignore_error', False)
        }

        result = QuickExecuteService.execute_script(
            user=user,
            script_data=script_data,
            client_ip=execution_record.client_ip,
            user_agent=execution_record.user_agent
        )

        # 更新原执行记录的重试次数
        if result['success']:
            execution_record.retry_count += 1
            execution_record.save()

        return result

    def _retry_file_transfer(self, execution_record, user):
        """重做文件传输"""
        from apps.quick_execute.services import QuickExecuteService

        params = execution_record.execution_parameters

        # 从target_hosts重新构造targets格式
        targets = [
            {'type': 'host', 'id': host['id']} 
            for host in execution_record.target_hosts
        ]

        # 重新构造文件传输参数
        transfer_data = {
            'transfer_type': params.get('transfer_type', 'upload'),
            'local_path': params.get('local_path'),
            'remote_path': params.get('remote_path'),
            'timeout': params.get('timeout', 300),
            'execution_mode': params.get('execution_mode', 'parallel'),
            'overwrite_policy': params.get('overwrite_policy', 'overwrite'),
            'rolling_batch_size': params.get('rolling_batch_size', 1),
            'rolling_batch_delay': params.get('rolling_batch_delay', 0),
            'targets': targets  # 添加目标主机列表
        }

        result = QuickExecuteService.transfer_file(
            user=user,
            transfer_data=transfer_data,
            client_ip=execution_record.client_ip,
            user_agent=execution_record.user_agent
        )

        # 更新原执行记录的重试次数
        if result['success']:
            execution_record.retry_count += 1
            execution_record.save()

        return result
