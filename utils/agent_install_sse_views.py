"""
Agent 安装进度 SSE 视图
"""
import json
import logging
import uuid
from datetime import datetime
from django.http import StreamingHttpResponse, HttpResponse
from django.views import View
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.exceptions import InvalidToken, TokenError
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from django.conf import settings
from .sse_views import SSEBaseView
from .realtime_logs import realtime_log_service

logger = logging.getLogger(__name__)


@method_decorator(csrf_exempt, name='dispatch')
class AgentInstallProgressSSEView(SSEBaseView):
    """Agent 安装进度 SSE 视图"""

    def dispatch(self, request, *args, **kwargs):
        """统一的认证和权限检查"""
        install_task_id = kwargs.get('install_task_id')
        logger.info(f"SSE dispatch开始: method={request.method}, install_task_id={install_task_id}")

        # 1. 检查用户认证
        user = self.authenticate_user(request)
        if not user:
            logger.warning(f"用户认证失败: install_task_id={install_task_id}")
            return HttpResponse("Unauthorized", status=401)

        logger.info(f"用户认证成功: user={user.username}, install_task_id={install_task_id}")
        # 设置认证用户
        request.user = user

        # 2. 检查安装任务访问权限
        if install_task_id:
            if not self.check_execution_permission(request.user, install_task_id):
                logger.warning(f"权限检查失败: user={user.username}, install_task_id={install_task_id}")
                return HttpResponse("Forbidden", status=403)
            logger.info(f"权限检查通过: user={user.username}, install_task_id={install_task_id}")

        return super(SSEBaseView, self).dispatch(request, *args, **kwargs)

    def check_execution_permission(self, user, install_task_id):
        """检查用户是否有权限访问安装任务"""
        try:
            from apps.agents.models import AgentInstallRecord

            # 检查是否有安装记录
            install_record = AgentInstallRecord.objects.filter(
                install_task_id=install_task_id
            ).first()

            if not install_record:
                logger.warning(f"安装任务不存在: {install_task_id}")
                return False

            # 超级用户权限
            if user.is_superuser:
                return True

            # 安装者权限
            if install_record.installed_by == user:
                return True

            # 检查主机权限
            from guardian.shortcuts import get_objects_for_user
            from apps.hosts.models import Host
            allowed_hosts = get_objects_for_user(
                user,
                'view_host',
                klass=Host,
                accept_global_perms=False
            )
            return install_record.host in allowed_hosts

        except Exception as e:
            logger.error(f"权限检查异常: {install_task_id} - {e}")
            return False

    def get(self, request, install_task_id):
        """获取安装进度流"""
        logger.info(f"SSE安装进度连接: 用户={request.user.username}, 任务ID={install_task_id}")

        # 获取起始ID
        last_id = request.GET.get('last_id', '0')

        def event_stream():
            """事件流生成器：合并状态与日志流"""
            try:
                status_prefix = getattr(settings, "INSTALL_STATUS_STREAM_PREFIX", "agent_install_status:")
                log_stream_key = getattr(settings, "INSTALL_LOG_STREAM_KEY", "agent_install_logs")
                status_stream_key = f"{status_prefix}{install_task_id}"
                status_last_id = last_id
                log_last_id = last_id

                # 发送连接建立消息
                yield self.format_sse_message({
                    'type': 'connection_established',
                    'message': f'已连接到安装任务 {install_task_id} 的进度流',
                    'install_task_id': install_task_id
                })

                # 发送历史状态与日志
                if last_id == '0':
                    try:
                        # 尝试获取历史状态（从 Redis Stream 读取最近 N 条）
                        try:
                            status_history = realtime_log_service.redis_client.xrevrange(
                                status_stream_key, count=20
                            )
                            for msg_id, fields in reversed(status_history):
                                status_last_id = msg_id
                                yield self.format_sse_message({
                                    'type': 'status',
                                    **fields
                                }, event_id=msg_id)
                        except Exception as e:
                            logger.warning(f"获取历史状态失败: {e}")

                        # 历史日志
                        historical_logs = realtime_log_service.get_historical_logs(install_task_id, limit=50)
                        logger.info(f"发送历史日志: {len(historical_logs)} 条")
                        for log in historical_logs:
                            normalized_log = self.normalize_log_message(log, install_task_id)
                            log_last_id = normalized_log.get('id') or log.get('id', '0')
                            yield self.format_sse_message({
                                'type': 'log',
                                **normalized_log
                            }, event_id=log_last_id)
                    except Exception as e:
                        logger.warning(f"发送历史状态/日志失败: {e}")

                # 开始实时合并流
                logger.info(f"开始实时进度流: install_task_id={install_task_id}")
                while True:
                    try:
                        if not realtime_log_service._ensure_connection():
                            yield self.format_sse_message({
                                'type': 'error',
                                'message': 'Redis连接不可用'
                            })
                            break
                        messages = realtime_log_service.redis_client.xread(
                            {
                                status_stream_key: status_last_id,
                                log_stream_key: log_last_id
                            },
                            count=200,
                            block=2000
                        )

                        if messages:
                            for stream, msgs in messages:
                                for msg_id, fields in msgs:
                                    if stream == status_stream_key:
                                        status_last_id = msg_id
                                        yield self.format_sse_message({
                                            'type': 'status',
                                            **fields
                                        }, event_id=msg_id)
                                    elif stream == log_stream_key:
                                        exec_id = fields.get('execution_id') or fields.get('task_id')
                                        if str(exec_id) != str(install_task_id):
                                            continue
                                        log_last_id = msg_id
                                        normalized_log = self.normalize_log_message(fields, install_task_id)
                                        yield self.format_sse_message({
                                            'type': 'log',
                                            **normalized_log
                                        }, event_id=msg_id)
                        else:
                            # 心跳，保持连接
                            yield self.format_sse_message({
                                'type': 'heartbeat',
                                'timestamp': datetime.now().isoformat()
                            })

                    except Exception as e:
                        logger.error(f"实时进度流异常: {install_task_id} - {e}")
                        yield self.format_sse_message({
                            'type': 'error',
                            'message': str(e)
                        })
                        break

            except Exception as e:
                logger.error(f"SSE进度流异常: {install_task_id} - {e}")
                yield self.format_sse_message({
                    'type': 'error',
                    'message': str(e)
                })
                return

        return self.create_sse_response(event_stream())
