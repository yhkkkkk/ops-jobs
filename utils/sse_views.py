"""
Server-Sent Events (SSE) 视图 - 实时日志推送
基于现有的Redis Stream实时日志服务，支持ASGI异步环境
"""
import json
import time
import logging
import uuid
import threading
import queue
import asyncio
from datetime import datetime
from django.http import StreamingHttpResponse, HttpResponse, JsonResponse
from django.views import View
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.exceptions import InvalidToken, TokenError
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from asgiref.sync import sync_to_async
from .realtime_logs import realtime_log_service

logger = logging.getLogger(__name__)


class SSEBaseView(View):
    """SSE基础视图 - 支持Session和JWT认证，CORS支持"""

    def options(self, request, *args, **kwargs):
        """处理CORS预检请求"""
        response = JsonResponse({})
        response['Access-Control-Allow-Origin'] = '*'
        response['Access-Control-Allow-Methods'] = 'GET, OPTIONS'
        response['Access-Control-Allow-Headers'] = 'Cache-Control, Authorization, Content-Type'
        response['Access-Control-Max-Age'] = '86400'  # 24小时
        return response

    def dispatch(self, request, *args, **kwargs):
        """统一的认证和权限检查"""
        execution_id = kwargs.get('execution_id')
        logger.info(f"SSE dispatch开始: method={request.method}, execution_id={execution_id}")

        # 1. 检查用户认证
        user = self.authenticate_user(request)
        if not user:
            logger.warning(f"用户认证失败: execution_id={execution_id}")
            return HttpResponse("Unauthorized", status=401)

        logger.info(f"用户认证成功: user={user.username}, execution_id={execution_id}")
        # 设置认证用户
        request.user = user

        # 2. 检查执行记录访问权限
        if execution_id:
            if not self.check_execution_permission(request.user, execution_id):
                logger.warning(f"权限检查失败: user={user.username}, execution_id={execution_id}")
                return HttpResponse("Forbidden", status=403)
            logger.info(f"权限检查通过: user={user.username}, execution_id={execution_id}")

        return super().dispatch(request, *args, **kwargs)

    def authenticate_user(self, request):
        """认证用户 - 支持Session和JWT Token"""
        # 1. 尝试Session认证
        if request.user.is_authenticated:
            return request.user

        # 2. 尝试JWT Token认证（从URL参数）
        token = request.GET.get('token')
        if token:
            try:
                jwt_auth = JWTAuthentication()
                validated_token = jwt_auth.get_validated_token(token)
                user = jwt_auth.get_user(validated_token)
                return user

            except (InvalidToken, TokenError, Exception) as e:
                logger.warning(f"JWT认证失败: {str(e)}")
                return None

        # 3. 尝试从Authorization header获取token
        auth_header = request.META.get('HTTP_AUTHORIZATION', '')
        if auth_header.startswith('Bearer '):
            token = auth_header[7:]
            try:
                jwt_auth = JWTAuthentication()
                validated_token = jwt_auth.get_validated_token(token)
                user = jwt_auth.get_user(validated_token)
                return user

            except (InvalidToken, TokenError, Exception) as e:
                logger.warning(f"JWT认证失败: {str(e)}")
                return None

        return None

    def check_execution_permission(self, user, execution_id):
        """检查用户是否有权限访问执行记录"""
        try:
            from apps.executor.models import ExecutionRecord

            execution_record = ExecutionRecord.objects.filter(
                execution_id=execution_id
            ).first()

            if not execution_record:
                logger.warning(f"执行记录不存在: {execution_id}")
                return False

            # 超级用户权限
            if user.is_superuser:
                return True

            # 执行者权限
            if execution_record.executed_by == user:
                return True

            # 对象级权限检查
            if execution_record.related_object:
                permission_name = f'view_{execution_record.related_object._meta.model_name}'
                return user.has_perm(permission_name, execution_record.related_object)

            # 如果没有相关对象，检查是否有查看执行记录的权限
            return user.has_perm('executor.view_executionrecord')

        except Exception as e:
            logger.error(f"权限检查异常: {execution_id} - {e}")
            return False

    def create_sse_response(self, event_stream):
        """创建SSE响应"""
        response = StreamingHttpResponse(
            event_stream,
            content_type='text/event-stream; charset=utf-8'
        )

        # 设置SSE必需的头
        response['Cache-Control'] = 'no-cache, no-store, must-revalidate'
        response['Pragma'] = 'no-cache'
        response['Expires'] = '0'
        response['Connection'] = 'keep-alive'  # ASGI 服务器支持
        response['X-Accel-Buffering'] = 'no'  # 禁用nginx缓冲

        # CORS设置
        response['Access-Control-Allow-Origin'] = '*'
        response['Access-Control-Allow-Headers'] = 'Cache-Control, Authorization, Content-Type'
        response['Access-Control-Allow-Methods'] = 'GET, OPTIONS'
        response['Access-Control-Expose-Headers'] = 'Cache-Control, Content-Type'

        return response

    def format_sse_message(self, data, event_type='message', event_id=None):
        """格式化SSE消息 - 参考标准SSE格式"""
        message = ""

        if event_id:
            message += f"id: {event_id}\n"

        message += f"event: {event_type}\n"
        message += f"data: {json.dumps(data, ensure_ascii=False)}\n\n"

        return message

    def _create_error_stream(self, error_message):
        """创建错误流"""
        def error_generator():
            yield self.format_sse_message({
                'type': 'error',
                'message': error_message,
                'timestamp': datetime.now().isoformat()
            })
        return error_generator()


@method_decorator(csrf_exempt, name='dispatch')
class JobLogsSSEView(SSEBaseView):
    """作业日志SSE视图"""

    def get(self, request, execution_id):
        """获取作业日志流"""
        logger.info(f"SSE日志连接: 用户={request.user.username}, 执行ID={execution_id}")

        # 直接使用execution_id作为task_id，因为日志推送时使用的就是execution_id
        task_id = str(execution_id)
        logger.info(f"SSE日志连接: 执行ID={execution_id}, 任务ID={task_id}")

        # 获取起始ID
        last_id = request.GET.get('last_id', '0')

        def event_stream():
            """事件流生成器"""
            try:
                # 发送连接建立消息
                yield self.format_sse_message({
                    'type': 'connection_established',
                    'message': f'已连接到执行记录 {execution_id} 的日志流',
                    'execution_id': execution_id,
                    'task_id': task_id
                }, event_type='message')

                # 如果是新连接，先发送历史日志
                if last_id == '0':
                    historical_logs = realtime_log_service.get_historical_logs(task_id, limit=50)
                    logger.info(f"发送历史日志: {len(historical_logs)} 条")
                    for log in historical_logs:
                        yield self.format_sse_message({
                            'type': 'log',
                            **log
                        }, event_type='message', event_id=log['id'])
                        # 更新 last_id 为最后一条历史日志的 ID
                        last_id = log['id']

                # 开始实时日志流
                logger.info(f"开始实时日志流: task_id={task_id}")
                for message in realtime_log_service.get_logs_stream(task_id, last_id):
                    if message['type'] == 'log':
                        yield self.format_sse_message({
                            'type': 'log',
                            **message['data']
                        }, event_type='message', event_id=message['id'])
                    elif message['type'] == 'heartbeat':
                        yield self.format_sse_message({
                            'type': 'heartbeat',
                            **message['data']
                        }, event_type='heartbeat')
                    elif message['type'] == 'error':
                        yield self.format_sse_message({
                            'type': 'error',
                            **message['data']
                        }, event_type='message')
                        break

            except Exception as e:
                logger.error(f"SSE日志流异常: {execution_id} - {e}")
                yield self.format_sse_message({
                    'type': 'error',
                    'message': str(e)
                }, event_type='message')

        return self.create_sse_response(event_stream())


@method_decorator(csrf_exempt, name='dispatch')
class JobStatusSSEView(SSEBaseView):
    """作业状态SSE视图"""

    def get(self, request, execution_id):
        """获取作业状态流"""
        logger.info(f"SSE状态连接: 用户={request.user.username}, 执行ID={execution_id}")

        # 直接使用execution_id作为task_id
        task_id = str(execution_id)
        logger.info(f"SSE状态连接: 执行ID={execution_id}, 任务ID={task_id}")

        # 获取起始ID
        last_id = request.GET.get('last_id', '0')

        def event_stream():
            """事件流生成器"""
            try:
                # 发送连接建立消息
                yield self.format_sse_message({
                    'type': 'connection_established',
                    'message': f'已连接到执行记录 {execution_id} 的状态流',
                    'execution_id': execution_id,
                    'task_id': task_id
                }, event_type='message')

                # 开始实时状态流
                logger.info(f"开始实时状态流: task_id={task_id}")
                for message in realtime_log_service.get_status_stream(task_id, last_id):
                    if message['type'] == 'status':
                        yield self.format_sse_message({
                            'type': 'status',
                            **message['data']
                        }, event_type='message', event_id=message['id'])
                    elif message['type'] == 'heartbeat':
                        yield self.format_sse_message({
                            'type': 'heartbeat',
                            **message['data']
                        }, event_type='heartbeat')
                    elif message['type'] == 'error':
                        yield self.format_sse_message({
                            'type': 'error',
                            **message['data']
                        }, event_type='message')
                        break

            except Exception as e:
                logger.error(f"SSE状态流异常: {execution_id} - {e}")
                yield self.format_sse_message({
                    'type': 'error',
                    'message': str(e)
                }, event_type='message')

        return self.create_sse_response(event_stream())


@method_decorator(csrf_exempt, name='dispatch')
class JobCombinedSSEView(SSEBaseView):
    """作业日志和状态合并SSE视图 - 异步实现以支持ASGI环境"""

    def get(self, request, execution_id):
        """获取作业日志和状态的合并流"""
        try:
            logger.info(f"SSE合并流连接: 用户={request.user.username}, 执行ID={execution_id}")

            # 直接使用execution_id作为task_id
            task_id = str(execution_id)
            logger.info(f"SSE合并流连接: 执行ID={execution_id}, 任务ID={task_id}")

            # 创建异步SSE流
            response = StreamingHttpResponse(
                self._build_log_stream_async(task_id, execution_id),
                content_type='text/event-stream; charset=utf-8'
            )

            # 设置SSE相关的HTTP头
            response['Cache-Control'] = 'no-cache, no-store, must-revalidate'
            response['Pragma'] = 'no-cache'
            response['Expires'] = '0'
            response['Access-Control-Allow-Origin'] = '*'
            response['Access-Control-Allow-Headers'] = 'Cache-Control, Authorization, Content-Type'
            response['Access-Control-Allow-Methods'] = 'GET, OPTIONS'
            response['X-Accel-Buffering'] = 'no'  # 禁用nginx缓冲

            return response
            
        except Exception as e:
            logger.error(f"创建SSE流失败: {str(e)}", exc_info=True)
            return StreamingHttpResponse(
                self._create_error_stream(f"服务器错误: {str(e)}"),
                content_type='text/event-stream; charset=utf-8'
            )

    async def _build_log_stream_async(self, task_id, execution_id):
        """异步生成日志流"""
        # 生成唯一的客户端ID
        client_id = str(uuid.uuid4())
        
        try:
            # 发送连接建立消息
            yield self.format_sse_message({
                'type': 'connection_established',
                'message': f'已连接到执行记录 {execution_id} 的合并流',
                'execution_id': execution_id,
                'task_id': task_id,
                'timestamp': datetime.now().isoformat()
            })

            # 发送历史日志
            last_id = '0'
            try:
                historical_logs = realtime_log_service.get_historical_logs(task_id, limit=50)
                logger.info(f"发送历史日志: {len(historical_logs)} 条")
                
                for log in historical_logs:
                    yield self.format_sse_message({
                        'type': 'log',
                        **log
                    }, event_type='message', event_id=log.get('id'))
                    # 更新 last_id 为最后一条历史日志的 ID
                    last_id = log.get('id', '0')

            except Exception as e:
                logger.error(f"获取历史日志失败: {task_id} - {e}")
                yield self.format_sse_message({
                    'type': 'error',
                    'message': f'获取历史日志失败: {str(e)}'
                })

            # 开始实时日志流
            heartbeat_counter = 0
            message_count = 0
            
            # 获取异步日志流，使用历史日志的最后一条 ID 作为起始点
            async for log_msg in self._async_log_stream(task_id, client_id, last_id):
                if log_msg is None:
                    # 心跳包
                    heartbeat_counter += 1
                    if heartbeat_counter >= 30:  # 每30秒发送一次心跳
                        yield self.format_sse_message({
                            'type': 'heartbeat',
                            'timestamp': int(time.time())
                        }, event_type='heartbeat')
                        heartbeat_counter = 0
                    continue
                
                # 重置心跳计数器
                heartbeat_counter = 0
                message_count += 1
                
                # 处理不同类型的消息
                if log_msg['type'] == 'log':
                    yield self.format_sse_message({
                        'type': 'log',
                        **log_msg['data']
                    }, event_type='message', event_id=log_msg['id'])
                elif log_msg['type'] == 'status':
                    yield self.format_sse_message({
                        'type': 'status',
                        **log_msg['data']
                    }, event_type='message', event_id=log_msg['id'])
                elif log_msg['type'] == 'error':
                    yield self.format_sse_message({
                        'type': 'error',
                        **log_msg['data']
                    }, event_type='message')
                    break
                
        except Exception as e:
            logger.error(f"生成日志流时发生错误: {str(e)}", exc_info=True)
            yield self.format_sse_message({
                'type': 'error',
                'message': f'日志流发生错误: {str(e)}'
            })

    async def _async_log_stream(self, task_id, client_id, last_id='0'):
        """异步日志流生成器"""
        async_queue = None
        thread = None
        stop_event = None
        
        try:
            async_queue = asyncio.Queue(maxsize=1000)  # 限制队列大小
            stop_event = asyncio.Event()
            loop = asyncio.get_running_loop()
            error_count = 0
            max_errors = 5
            
            def sync_log_reader():
                """在单独线程中读取同步日志流"""
                nonlocal error_count
                try:
                    logger.info(f"开始同步日志读取器: task_id={task_id}, last_id={last_id}")
                    for message in realtime_log_service.get_logs_stream(task_id, last_id):
                        if stop_event.is_set():
                            logger.info(f"停止事件已设置，退出同步日志读取器")
                            break
                        
                        # 使用线程安全的方式添加到异步队列
                        try:
                            asyncio.run_coroutine_threadsafe(
                                async_queue.put(message), loop
                            ).result(timeout=0.1)
                            error_count = 0  # 重置错误计数
                        except Exception as queue_error:
                            error_count += 1
                            logger.debug(f"队列添加失败 ({error_count}/{max_errors}): {queue_error}")
                            if error_count >= max_errors:
                                logger.warning(f"队列错误过多，退出同步日志读取器")
                                break
                    
                    # 发送结束信号
                    try:
                        asyncio.run_coroutine_threadsafe(
                            async_queue.put(StopAsyncIteration), loop
                        ).result(timeout=0.1)
                    except Exception:
                        pass  # 忽略结束信号发送失败
                        
                except Exception as e:
                    logger.error(f"同步日志读取器出错: {str(e)}", exc_info=True)
                    try:
                        asyncio.run_coroutine_threadsafe(
                            async_queue.put(StopAsyncIteration), loop
                        ).result(timeout=0.1)
                    except Exception:
                        pass
            
            # 在线程池中启动同步日志读取器
            thread = threading.Thread(target=sync_log_reader, daemon=True)
            thread.start()
            
            try:
                while True:
                    try:
                        # 异步等待日志消息，使用较短的超时以提供更好的响应性
                        log_msg = await asyncio.wait_for(async_queue.get(), timeout=1.0)
                        
                        if log_msg is StopAsyncIteration:
                            logger.info(f"收到结束信号，退出异步日志流")
                            break
                        
                        yield log_msg
                        
                    except asyncio.TimeoutError:
                        # 超时，发送心跳
                        yield None
                        
                    except Exception as e:
                        logger.error(f"异步日志流处理错误: {str(e)}")
                        error_count += 1
                        if error_count >= max_errors:
                            logger.warning(f"异步日志流错误过多，退出")
                            break
                        yield None
                        
            finally:
                # 设置停止事件，清理资源
                if stop_event:
                    stop_event.set()
                if thread and thread.is_alive():
                    thread.join(timeout=2.0)
                
        except Exception as e:
            logger.error(f"异步日志流错误: {str(e)}", exc_info=True)
            yield None  # 确保生成器正常结束
