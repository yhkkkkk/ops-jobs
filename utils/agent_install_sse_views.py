"""
Agent 安装进度 SSE 视图 - 继承 SSEBaseView 异步实现
"""
import asyncio
import logging
from datetime import datetime
from django.conf import settings
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from .sse_views import SSEBaseView
from .realtime_logs import realtime_log_service

logger = logging.getLogger(__name__)


@method_decorator(csrf_exempt, name='dispatch')
class AgentInstallProgressSSEView(SSEBaseView):
    """Agent 安装/卸载进度 SSE 视图"""

    terminal_statuses = {'completed', 'completed_with_errors', 'failed', 'success', 'error', 'stopped'}

    def get_resource_id(self, kwargs):
        """获取安装任务 ID"""
        return kwargs.get('install_task_id')

    def check_permission(self, user, install_task_id):
        """检查用户是否有权限访问安装任务"""
        try:
            from apps.agents.models import AgentInstallRecord

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

        last_id = request.GET.get('last_id', '0')

        async def event_stream():
            status_prefix = getattr(settings, "INSTALL_STATUS_STREAM_PREFIX", "agent_install_status:")
            log_stream_key = getattr(settings, "INSTALL_LOG_STREAM_KEY", "agent_install_logs")
            status_stream_key = f"{status_prefix}{install_task_id}"
            status_last_id = last_id
            log_last_id = last_id
            finished = False

            try:
                # 发送连接建立消息
                yield self.format_sse_message({
                    'type': 'connection_established',
                    'message': f'已连接到安装任务 {install_task_id} 的进度流',
                    'install_task_id': install_task_id
                }).encode('utf-8')

                # 发送历史状态与日志
                if last_id == '0':
                    try:
                        # 获取历史状态
                        try:
                            status_history = await self.redis_xrevrange(status_stream_key, count=20)
                            for msg_id, fields in reversed(status_history):
                                status_last_id = msg_id
                                status_value = str(fields.get('status') or '').lower()
                                if status_value in self.terminal_statuses:
                                    finished = True
                                yield self.format_sse_message({
                                    'type': 'status', **fields
                                }, event_id=msg_id).encode('utf-8')
                        except Exception as e:
                            logger.warning(f"获取历史状态失败: {e}")

                        # 获取历史日志
                        logger.info(f"获取历史日志: install_task_id={install_task_id}, stream_key={log_stream_key}")
                        historical_logs = await self.get_historical_logs_async(
                            install_task_id, limit=50, stream_key=log_stream_key
                        )
                        logger.info(f"发送历史日志: {len(historical_logs)} 条")
                        for log in historical_logs:
                            normalized = self.normalize_log_message(log, install_task_id)
                            log_last_id = normalized.get('id') or log.get('id', '0')
                            yield self.format_sse_message({
                                'type': 'log', **normalized
                            }, event_id=log_last_id).encode('utf-8')
                    except Exception as e:
                        logger.warning(f"发送历史状态/日志失败: {e}")

                # 如果历史中已经包含终态，则直接结束
                if finished:
                    logger.info(f"安装任务 {install_task_id} 已达终态（历史），关闭 SSE")
                    return

                # 开始实时合并流
                logger.info(f"开始实时进度流: install_task_id={install_task_id}")
                consecutive_errors = 0

                while True:
                    try:
                        if finished:
                            logger.info(f"安装任务 {install_task_id} 已达终态，关闭实时进度流")
                            break

                        # 检查 redis 连接
                        if not await self.redis_ensure_connection():
                            consecutive_errors += 1
                            if consecutive_errors >= self.max_consecutive_errors:
                                yield self.format_sse_message({
                                    'type': 'error',
                                    'message': 'redis连接不可用，重试次数过多'
                                }).encode('utf-8')
                                break
                            yield self.format_sse_message({
                                'type': 'error',
                                'message': f'redis连接不可用，正在重试 ({consecutive_errors}/{self.max_consecutive_errors})'
                            }).encode('utf-8')
                            await asyncio.sleep(2)
                            continue

                        consecutive_errors = 0

                        # 从 redis 读取消息（同时监听状态流和日志流）
                        messages = await self.redis_xread({
                            status_stream_key: status_last_id,
                            log_stream_key: log_last_id
                        }, count=200, block=2000)

                        if messages:
                            for stream, msgs in messages:
                                for msg_id, fields in msgs:
                                    if stream == status_stream_key:
                                        status_last_id = msg_id
                                        status_value = str(fields.get('status') or '').lower()
                                        yield self.format_sse_message({
                                            'type': 'status', **fields
                                        }, event_id=msg_id).encode('utf-8')
                                        if status_value in self.terminal_statuses:
                                            finished = True
                                    elif stream == log_stream_key:
                                        exec_id = fields.get('execution_id') or fields.get('task_id')
                                        if str(exec_id) != str(install_task_id):
                                            continue
                                        log_last_id = msg_id
                                        normalized = self.normalize_log_message(fields, install_task_id)
                                        yield self.format_sse_message({
                                            'type': 'log', **normalized
                                        }, event_id=msg_id).encode('utf-8')
                        else:
                            # 心跳
                            yield self.format_sse_message({
                                'type': 'heartbeat',
                                'timestamp': datetime.now().isoformat()
                            }).encode('utf-8')

                    except Exception as e:
                        consecutive_errors += 1
                        logger.error(f"实时进度流异常 ({consecutive_errors}/{self.max_consecutive_errors}): {install_task_id} - {e}")
                        yield self.format_sse_message({
                            'type': 'error',
                            'message': f'实时流异常: {str(e)}'
                        }).encode('utf-8')

                        if consecutive_errors >= self.max_consecutive_errors:
                            logger.error(f"实时进度流错误过多，退出: {install_task_id}")
                            break

                        await asyncio.sleep(1)

            except Exception as e:
                logger.error(f"SSE进度流异常: {install_task_id} - {e}")
                yield self.format_sse_message({
                    'type': 'error',
                    'message': str(e)
                }).encode('utf-8')

        return self.create_sse_response(event_stream())
