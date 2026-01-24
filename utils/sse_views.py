"""
Server-Sent Events (SSE) 视图 - 实时日志推送
基于 redis stream 实时日志服务，完全异步实现以支持 ASGI 环境
"""
import asyncio
import json
import logging
from django.http import StreamingHttpResponse, HttpResponse, JsonResponse
from django.views import View
from django.conf import settings
from django.utils import timezone
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.exceptions import InvalidToken, TokenError
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from asgiref.sync import sync_to_async
from .realtime_logs import realtime_log_service

logger = logging.getLogger(__name__)


class SSEBaseView(View):
    """
    SSE 异步基础视图
    - 支持 Session 和 JWT 认证
    - CORS 支持
    - 完全异步实现，适配 ASGI 环境
    """

    # 子类可覆盖的配置
    heartbeat_interval = 2  # 心跳间隔（秒）
    max_consecutive_errors = 5  # 最大连续错误次数

    # ==================== 工具方法 ====================

    @staticmethod
    def format_sse_message(data, event_id=None):
        """格式化 SSE 消息"""
        message = ""
        if event_id:
            message += f"id: {event_id}\n"
        message += "event: message\n"
        message += f"data: {json.dumps(data, ensure_ascii=False)}\n\n"
        return message

    @staticmethod
    def normalize_log_message(log_data, execution_id: str):
        """容错并补全日志字段"""
        data = dict(log_data or {})
        missing_fields = []

        # 执行 ID - 主要标识符
        data.setdefault('execution_id', str(execution_id))
        # task_id 只在复杂工作流中设置，不在这里强制设置
        data['id'] = data.get('id')

        # 通道标记
        channel = data.get('channel') or data.get('log_channel') or 'redis_stream'
        data['channel'] = channel
        data['fallback_channel'] = channel not in ('redis_stream', 'redis', 'default')

        # 步骤信息
        step_order = data.get('step_order')
        try:
            step_order = int(step_order) if step_order is not None else 0
        except Exception:
            step_order = 0
        data['step_order'] = step_order

        step_name = data.get('step_name') or data.get('step') or ''
        if not step_name:
            missing_fields.append('step')
            step_name = '未解析步骤'
        data['step_name'] = step_name
        data['step_id'] = data.get('step_id') or (f"step_{step_order}" if step_order else 'unknown_step')

        # 主机信息
        host_id = data.get('host_id') or data.get('host_name') or data.get('host_ip')
        if not host_id:
            missing_fields.append('host')
            host_id = 'unknown_host'
        data['host_id'] = host_id
        data['host_name'] = data.get('host_name') or host_id
        data['host_ip'] = data.get('host_ip') or ''

        # 日志类型/时间戳
        data['log_type'] = data.get('log_type') or data.get('stream') or 'info'
        data['timestamp'] = data.get('timestamp') or timezone.now().isoformat()

        data['structure_missing'] = bool(missing_fields)
        data['missing_fields'] = missing_fields
        data['structured'] = not data['structure_missing']
        return data

    # ==================== 认证方法 ====================

    def authenticate_user(self, request):
        """认证用户 - 支持 Session 和 JWT Token"""
        # 1. 尝试 session 认证
        if hasattr(request, 'user') and request.user.is_authenticated:
            return request.user

        # 2. 尝试从 Authorization header 获取 jwt
        auth_header = request.headers.get('Authorization', '')
        if auth_header.startswith('Bearer '):
            token = auth_header[7:]
            try:
                jwt_auth = JWTAuthentication()
                validated_token = jwt_auth.get_validated_token(token)
                return jwt_auth.get_user(validated_token)
            except (InvalidToken, TokenError, Exception) as e:
                logger.warning(f"jwt认证失败: {str(e)}")
                return None

        return None

    def check_permission(self, user, resource_id):
        """
        权限检查 - 子类应覆盖此方法
        默认实现：超级用户通过
        """
        return user.is_superuser

    # ==================== 请求处理 ====================

    def options(self, request, *args, **kwargs):
        """处理 CORS 预检请求"""
        response = HttpResponse()
        cors_headers = self._build_cors_headers(request)
        for k, v in cors_headers.items():
            response[k] = v
        response['Access-Control-Max-Age'] = '86400'
        return response

    def dispatch(self, request, *args, **kwargs):
        """统一的认证和权限检查"""
        # 获取资源 ID（子类通过 get_resource_id 方法定义）
        resource_id = self.get_resource_id(kwargs)
        logger.info(f"SSE dispatch: method={request.method}, resource_id={resource_id}")

        # OPTIONS 请求直接返回
        if request.method == 'OPTIONS':
            return self.options(request, *args, **kwargs)

        # 认证检查
        user = self.authenticate_user(request)
        if not user:
            logger.warning(f"用户认证失败: resource_id={resource_id}")
            return HttpResponse("Unauthorized", status=401)

        logger.info(f"用户认证成功: user={user.username}, resource_id={resource_id}")
        request.user = user

        # 权限检查
        if resource_id and not self.check_permission(user, resource_id):
            logger.warning(f"权限检查失败: user={user.username}, resource_id={resource_id}")
            return HttpResponse("Forbidden", status=403)

        logger.info(f"权限检查通过: user={user.username}, resource_id={resource_id}")
        return super().dispatch(request, *args, **kwargs)

    def get_resource_id(self, kwargs):
        """获取资源 ID - 子类应覆盖"""
        return kwargs.get('execution_id') or kwargs.get('install_task_id')

    # ==================== SSE 响应创建 ====================

    def create_sse_response(self, async_generator, request=None):
        """创建SSE响应"""
        response = StreamingHttpResponse(
            async_generator,
            content_type='text/event-stream; charset=utf-8'
        )

        # SSE必需的头
        response['Cache-Control'] = 'no-cache, no-store, must-revalidate'
        response['Pragma'] = 'no-cache'
        response['Expires'] = '0'
        response['Connection'] = 'keep-alive'
        response['X-Accel-Buffering'] = 'no'

        # CORS设置
        cors_headers = self._build_cors_headers(request)
        for k, v in cors_headers.items():
            response[k] = v

        return response

    def _build_cors_headers(self, request):
        """
        基于 settings 和请求 Origin 构建 CORS 头，支持凭证。
        """
        origin = request.headers.get('Origin') if request else None
        allow_all = getattr(settings, 'CORS_ALLOW_ALL_ORIGINS', False)
        allow_credentials = getattr(settings, 'CORS_ALLOW_CREDENTIALS', False)
        allowed_origins = [o for o in getattr(settings, 'CORS_ALLOWED_ORIGINS', []) if o] if not allow_all else []

        acao = '*'
        credentials_enabled = False

        if allow_credentials:
            if allow_all and origin:
                acao = origin
                credentials_enabled = True
            elif origin and origin in allowed_origins:
                acao = origin
                credentials_enabled = True
        else:
            if not allow_all and origin and origin in allowed_origins:
                acao = origin

        headers = {
            'Access-Control-Allow-Origin': acao,
            'Access-Control-Allow-Headers': 'Cache-Control, Authorization, Content-Type',
            'Access-Control-Allow-Methods': 'GET, OPTIONS',
            'Access-Control-Expose-Headers': 'Cache-Control, Content-Type',
        }
        if credentials_enabled:
            headers['Access-Control-Allow-Credentials'] = 'true'
        return headers

    # ==================== 异步 redis 操作 ====================

    @staticmethod
    async def redis_xread(streams_dict, count=200, block=2000):
        """异步 redis xread"""
        return await sync_to_async(
            realtime_log_service.redis_client.xread
        )(streams_dict, count=count, block=block)

    @staticmethod
    async def redis_xrevrange(stream_key, count=20):
        """异步 redis xrevrange"""
        return await sync_to_async(
            realtime_log_service.redis_client.xrevrange
        )(stream_key, count=count)

    @staticmethod
    async def redis_ensure_connection():
        """异步确保 redis 连接"""
        return await sync_to_async(
            realtime_log_service._ensure_connection
        )()

    @staticmethod
    async def get_historical_logs_async(execution_id, limit=50, stream_key=None):
        """异步获取历史日志"""
        return await sync_to_async(
            realtime_log_service.get_historical_logs
        )(execution_id, limit=limit, stream_key=stream_key)


# ==================== 作业执行 SSE 视图 ====================

@method_decorator(csrf_exempt, name='dispatch')
class JobLogsSSEView(SSEBaseView):
    """作业日志SSE视图"""

    def check_permission(self, user, execution_id):
        """检查执行记录访问权限"""
        try:
            from apps.executor.models import ExecutionRecord

            record = ExecutionRecord.objects.filter(execution_id=execution_id).first()
            if not record:
                logger.warning(f"执行记录不存在: {execution_id}")
                return False

            if user.is_superuser:
                return True

            if record.executed_by == user:
                return True

            if record.related_object:
                perm = f'view_{record.related_object._meta.model_name}'
                return user.has_perm(perm, record.related_object)

            return user.has_perm('executor.view_executionrecord')

        except Exception as e:
            logger.error(f"权限检查异常: {execution_id} - {e}")
            return False

    def get(self, request, execution_id):
        """获取作业日志流"""
        logger.info(f"SSE日志连接: 用户={request.user.username}, 执行ID={execution_id}")

        last_id = request.GET.get('last_id', '0')
        filter_host_id = request.GET.get('host_id')
        filter_step_id = request.GET.get('step_id')

        async def event_stream():
            nonlocal last_id
            try:
                # 连接建立消息
                yield self.format_sse_message({
                    'type': 'connection_established',
                    'message': f'已连接到执行记录 {execution_id} 的日志流',
                    'execution_id': execution_id,
                    'channel': 'redis_stream',
                    'filters': {'host_id': filter_host_id, 'step_id': filter_step_id}
                }).encode('utf-8')

                # 发送历史日志
                if last_id == '0':
                    historical_logs = await self.get_historical_logs_async(execution_id, limit=50)
                    logger.info(f"发送历史日志: {len(historical_logs)} 条")
                    for log in historical_logs:
                        normalized = self.normalize_log_message(log, execution_id)
                        # 应用过滤器
                        if filter_host_id and normalized.get('host_id') != filter_host_id:
                            continue
                        if filter_step_id and normalized.get('step_id') != filter_step_id:
                            continue
                        last_id = normalized.get('id') or log.get('id', '0')
                        yield self.format_sse_message({
                            'type': 'log', **normalized
                        }, event_id=last_id).encode('utf-8')

                # 实时日志流
                logger.info(f"开始实时日志流: execution_id={execution_id}")
                stream_key = realtime_log_service.log_stream_key
                consecutive_errors = 0

                while True:
                    try:
                        if not await self.redis_ensure_connection():
                            consecutive_errors += 1
                            if consecutive_errors >= self.max_consecutive_errors:
                                yield self.format_sse_message({
                                    'type': 'error', 'message': 'redis连接失败'
                                }).encode('utf-8')
                                break
                            await asyncio.sleep(2)
                            continue

                        consecutive_errors = 0
                        messages = await self.redis_xread({stream_key: last_id}, count=200, block=2000)

                        if messages:
                            for stream, msgs in messages:
                                for msg_id, fields in msgs:
                                    # 使用execution_id进行过滤，不再有fallback逻辑
                                    exec_id = fields.get('execution_id')
                                    if str(exec_id) != execution_id:
                                        continue
                                    last_id = msg_id
                                    normalized = self.normalize_log_message(fields, execution_id)
                                    # 应用过滤器
                                    if filter_host_id and normalized.get('host_id') != filter_host_id:
                                        continue
                                    if filter_step_id and normalized.get('step_id') != filter_step_id:
                                        continue
                                    yield self.format_sse_message({
                                        'type': 'log', **normalized
                                    }, event_id=msg_id).encode('utf-8')
                        else:
                            # 心跳
                            yield self.format_sse_message({
                                'type': 'heartbeat',
                                'timestamp': timezone.now().isoformat()
                            }).encode('utf-8')

                    except Exception as e:
                        consecutive_errors += 1
                        logger.error(f"日志流异常 ({consecutive_errors}): {e}")
                        if consecutive_errors >= self.max_consecutive_errors:
                            yield self.format_sse_message({
                                'type': 'error', 'message': str(e)
                            }).encode('utf-8')
                            break
                        await asyncio.sleep(1)

            except Exception as e:
                logger.error(f"SSE日志流异常: {execution_id} - {e}")
                yield self.format_sse_message({
                    'type': 'error', 'message': str(e)
                }).encode('utf-8')

        return self.create_sse_response(event_stream(), request)


@method_decorator(csrf_exempt, name='dispatch')
class JobStatusSSEView(SSEBaseView):
    """作业状态 SSE 视图 - 从 agent_results stream 读取进度"""

    def check_permission(self, user, execution_id):
        """复用 JobLogsSSEView 的权限检查"""
        return JobLogsSSEView.check_permission(self, user, execution_id)

    def get(self, request, execution_id):
        """获取作业状态流"""
        logger.info(f"SSE状态连接: 用户={request.user.username}, 执行ID={execution_id}")

        last_id = request.GET.get('last_id', '0')

        async def event_stream():
            nonlocal last_id
            try:
                # 连接建立消息
                yield self.format_sse_message({
                    'type': 'connection_established',
                    'message': f'已连接到执行记录 {execution_id} 的状态流',
                    'execution_id': execution_id
                }).encode('utf-8')

                # 从 agent_results stream 读取进度
                logger.info(f"开始实时状态流: execution_id={execution_id}")
                result_stream_key = getattr(settings, "RESULT_STREAM_KEY", "agent_results")
                consecutive_errors = 0

                while True:
                    try:
                        if not await self.redis_ensure_connection():
                            consecutive_errors += 1
                            if consecutive_errors >= self.max_consecutive_errors:
                                yield self.format_sse_message({
                                    'type': 'error', 'message': 'redis连接失败'
                                }).encode('utf-8')
                                break
                            await asyncio.sleep(2)
                            continue

                        consecutive_errors = 0
                        messages = await self.redis_xread({result_stream_key: last_id}, count=100, block=2000)

                        if messages:
                            for stream, msgs in messages:
                                for msg_id, fields in msgs:
                                    last_id = msg_id
                                    # 从 agent_results 中提取进度信息
                                    progress_fields = {
                                        'type': 'status',
                                        'execution_id': execution_id,
                                        'progress': fields.get('progress'),
                                        'total_hosts': fields.get('total_hosts'),
                                        'success_hosts': fields.get('success_hosts'),
                                        'failed_hosts': fields.get('failed_hosts'),
                                        'running_hosts': fields.get('running_hosts'),
                                        'pending_hosts': fields.get('pending_hosts'),
                                        'timestamp': fields.get('received_at') or fields.get('timestamp'),
                                    }
                                    yield self.format_sse_message(progress_fields, event_id=msg_id).encode('utf-8')
                        else:
                            yield self.format_sse_message({
                                'type': 'heartbeat',
                                'timestamp': timezone.now().isoformat()
                            }).encode('utf-8')

                    except Exception as e:
                        consecutive_errors += 1
                        logger.error(f"状态流异常 ({consecutive_errors}): {e}")
                        if consecutive_errors >= self.max_consecutive_errors:
                            yield self.format_sse_message({
                                'type': 'error', 'message': str(e)
                            }).encode('utf-8')
                            break
                        await asyncio.sleep(1)

            except Exception as e:
                logger.error(f"SSE状态流异常: {execution_id} - {e}")
                yield self.format_sse_message({
                    'type': 'error', 'message': str(e)
                }).encode('utf-8')

        return self.create_sse_response(event_stream(), request)


@method_decorator(csrf_exempt, name='dispatch')
class JobCombinedSSEView(SSEBaseView):
    """作业日志和状态合并 SSE 视图 - 从 agent_logs 和 agent_results 读取"""

    def check_permission(self, user, execution_id):
        """复用 JobLogsSSEView 的权限检查"""
        return JobLogsSSEView.check_permission(self, user, execution_id)

    def get(self, request, execution_id):
        """获取作业日志和状态的合并流"""
        logger.info(f"SSE合并流连接: 用户={request.user.username}, 执行ID={execution_id}")

        last_id = request.GET.get('last_id', '0')

        async def event_stream():
            log_last_id = last_id
            result_last_id = last_id

            try:
                # 连接建立消息
                yield self.format_sse_message({
                    'type': 'connection_established',
                    'message': f'已连接到执行记录 {execution_id} 的合并流',
                    'execution_id': execution_id,
                    'channel': 'redis_stream'
                }).encode('utf-8')

                # 发送历史日志
                if last_id == '0':
                    historical_logs = await self.get_historical_logs_async(execution_id, limit=100)
                    logger.info(f"发送历史日志: {len(historical_logs)} 条")
                    for log in historical_logs:
                        normalized = self.normalize_log_message(log, execution_id)
                        log_last_id = normalized.get('id') or log.get('id', '0')
                        yield self.format_sse_message({
                            'type': 'log', **normalized
                        }, event_id=log_last_id).encode('utf-8')

                # 实时合并流
                logger.info(f"开始实时合并流: execution_id={execution_id}")
                log_stream_key = realtime_log_service.log_stream_key
                result_stream_key = getattr(settings, "RESULT_STREAM_KEY", "agent_results")
                consecutive_errors = 0

                while True:
                    try:
                        if not await self.redis_ensure_connection():
                            consecutive_errors += 1
                            if consecutive_errors >= self.max_consecutive_errors:
                                yield self.format_sse_message({
                                    'type': 'error', 'message': 'redis连接失败'
                                }).encode('utf-8')
                                break
                            await asyncio.sleep(2)
                            continue

                        consecutive_errors = 0

                        # 同时监听日志流和结果流
                        messages = await self.redis_xread({
                            log_stream_key: log_last_id,
                            result_stream_key: result_last_id
                        }, count=200, block=2000)

                        if messages:
                            for stream, msgs in messages:
                                for msg_id, fields in msgs:
                                    if stream == result_stream_key:
                                        # 从 agent_results 读取进度状态
                                        msg_exec_id = fields.get('execution_id')
                                        if str(msg_exec_id) != execution_id:
                                            continue
                                        result_last_id = msg_id
                                        progress_fields = {
                                            'type': 'status',
                                            'execution_id': execution_id,
                                            'progress': fields.get('progress'),
                                            'total_hosts': fields.get('total_hosts'),
                                            'success_hosts': fields.get('success_hosts'),
                                            'failed_hosts': fields.get('failed_hosts'),
                                            'running_hosts': fields.get('running_hosts'),
                                            'pending_hosts': fields.get('pending_hosts'),
                                            'timestamp': fields.get('received_at') or fields.get('timestamp'),
                                        }
                                        yield self.format_sse_message(progress_fields, event_id=msg_id).encode('utf-8')
                                    elif stream == log_stream_key:
                                        # 使用execution_id进行过滤
                                        exec_id = fields.get('execution_id')
                                        if str(exec_id) != execution_id:
                                            continue
                                        log_last_id = msg_id
                                        normalized = self.normalize_log_message(fields, execution_id)
                                        yield self.format_sse_message({
                                            'type': 'log', **normalized
                                        }, event_id=msg_id).encode('utf-8')
                        else:
                            yield self.format_sse_message({
                                'type': 'heartbeat',
                                'timestamp': timezone.now().isoformat()
                            }).encode('utf-8')

                    except Exception as e:
                        consecutive_errors += 1
                        logger.error(f"合并流异常 ({consecutive_errors}): {e}")
                        if consecutive_errors >= self.max_consecutive_errors:
                            yield self.format_sse_message({
                                'type': 'error', 'message': str(e)
                            }).encode('utf-8')
                            break
                        await asyncio.sleep(1)

            except Exception as e:
                logger.error(f"SSE合并流异常: {execution_id} - {e}")
                yield self.format_sse_message({
                    'type': 'error', 'message': str(e)
                }).encode('utf-8')

        return self.create_sse_response(event_stream(), request)
