"""
实时日志服务 - 基于redis stream的实时日志推送
"""
import logging
from typing import Any, Dict, Generator

import redis
from django.conf import settings
from django.utils import timezone
from tenacity import (
    before_sleep_log,
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

logger = logging.getLogger(__name__)

# 统一的 redis 重试策略
_REDIS_RETRY = dict(
    retry=retry_if_exception_type((redis.ConnectionError, redis.TimeoutError)),
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=0.5, min=0.2, max=5),
    before_sleep=before_sleep_log(logger, logging.WARNING),
    reraise=True,
)


class RealtimeLogService:
    """实时日志服务"""
    def __init__(self):
        # 创建连接池
        self.connection_pool = redis.ConnectionPool(
            host=getattr(settings, 'REDIS_HOST', 'localhost'),
            port=getattr(settings, 'REDIS_PORT', 6379),
            password=getattr(settings, 'REDIS_PASSWORD', None),
            db=getattr(settings, 'REDIS_DB_REALTIME', 3),
            decode_responses=True,
            socket_connect_timeout=5,  # 连接超时
            socket_timeout=5,  # 读写超时
            socket_keepalive=True,  # 启用TCP keepalive
            socket_keepalive_options={},
            retry_on_timeout=True,  # 超时重试
            retry_on_error=[redis.ConnectionError, redis.TimeoutError],  # 连接错误时重试
            health_check_interval=30,  # 健康检查间隔
            max_connections=50  # 增加连接池大小
        )

        self.redis_client = redis.Redis(connection_pool=self.connection_pool)
        self.log_stream_key = getattr(settings, "LOG_STREAM_KEY", "agent_logs")
        self.status_stream_key = getattr(settings, "STATUS_STREAM_KEY", "agent_status")
        self._connection_pool = None

    @retry(**_REDIS_RETRY)
    def _ensure_connection(self):
        """确保redis连接可用"""
        self.redis_client.ping()
        return True

    @retry(**_REDIS_RETRY)
    def _xadd(self, key, fields):
        """包装 xadd 以提供重试"""
        return self.redis_client.xadd(key, fields)

    @retry(**_REDIS_RETRY)
    def _expire(self, key, seconds):
        """包装 expire 以提供重试"""
        return self.redis_client.expire(key, seconds)
    
    def push_log(self, execution_id: str, host_id: str, log_data: Dict[str, Any], task_id: str = None, stream_key: str = None):
        """推送日志到redis stream
        Args:
            execution_id: 执行ID，用于标识执行记录
            host_id: 主机ID
            log_data: 日志数据
            task_id: 可选，任务ID（用于复杂工作流中的任务实例标识）
            stream_key: 可选，覆盖默认日志流
        """
        log_stream = stream_key or self.log_stream_key
        logger.info(f"push_log 开始: execution_id={execution_id}, task_id={task_id}, host_id={host_id}, stream_key={log_stream}")
        try:
            self._ensure_connection()
        except Exception as e:
            logger.error(f"redis连接不可用，跳过日志推送: {execution_id} - {e}")
            return

        try:
            # 构建日志消息 - 统一字段名
            message = {
                'timestamp': timezone.now().isoformat(),
                'execution_id': str(execution_id),  # 主要执行标识
                'host_id': str(host_id),
                'host_name': log_data.get('host_name', ''),
                'host_ip': log_data.get('host_ip', ''),
                'log_type': log_data.get('log_type', log_data.get('stream', 'stdout')),  # 统一使用log_type
                'content': log_data.get('content', ''),
                'step_name': log_data.get('step_name', ''),
                'step_order': log_data.get('step_order', 0),
                'step_id': log_data.get('step_id', ''),
                'agent_id': log_data.get('agent_id', '')
            }

            # 如果提供了task_id，添加到消息中（用于复杂工作流）
            if task_id:
                message['task_id'] = str(task_id)

            # 同时写入统一日志流（agent_logs），便于consume_agent_logs处理
            unified_message = message.copy()
            unified_message['received_at'] = timezone.now().timestamp() * 1000  # 毫秒时间戳

            # 仅写入统一日志流
            msg_id = self._xadd(log_stream, unified_message)

            logger.info(f"push_log 成功: execution_id={execution_id}, stream={log_stream}, msg_id={msg_id}")
        except Exception as e:
            logger.error(f"推送日志失败: {execution_id} - {e}")

    def push_log_async(self, execution_id: str, host_id: str, log_data: Dict[str, Any], task_id: str = None):
        """
        异步推送日志，避免阻塞主线程
        """
        import threading

        def push_worker():
            self.push_log(execution_id, host_id, log_data, task_id)

        # 创建守护线程
        thread = threading.Thread(target=push_worker, daemon=True)
        thread.start()

    def push_status(self, execution_id: str, status_data: Dict[str, Any], stream_key: str = None):
        """推送状态更新到redis stream（单一 key）"""
        key = stream_key or self.status_stream_key
        try:
            self._ensure_connection()
        except Exception as e:
            logger.error(f"redis连接不可用，跳过状态推送: {execution_id} - {e}")
            return

        try:
            # 构建状态消息（支持作业执行和Agent安装两种格式）
            message = {
                'timestamp': timezone.now().isoformat(),
                'execution_id': str(execution_id),
                'status': status_data.get('status', ''),
                'progress': status_data.get('progress', 0),
                'current_step': status_data.get('current_step', ''),
                'total_hosts': status_data.get('total_hosts', status_data.get('total', 0)),
                'success_hosts': status_data.get('success_hosts', status_data.get('success_count', 0)),
                'failed_hosts': status_data.get('failed_hosts', status_data.get('failed_count', 0)),
                'running_hosts': status_data.get('running_hosts', 0),
                'completed': status_data.get('completed', 0),
                'total': status_data.get('total', status_data.get('total_hosts', 0)),
                'success_count': status_data.get('success_count', status_data.get('success_hosts', 0)),
                'failed_count': status_data.get('failed_count', status_data.get('failed_hosts', 0)),
                'message': status_data.get('message', '')
            }

            # 推送到redis stream
            msg_id = self._xadd(key, message)

            # 设置过期时间（24小时）
            self._expire(key, 86400)

            logger.debug(f"推送状态到 {key}: {message}，msg_id={msg_id}")

        except Exception as e:
            logger.error(f"推送状态失败: {execution_id} - {e}")

    def get_logs_stream(self, execution_id: str, last_id: str = '0') -> Generator[Dict[str, Any], None, None]:
        """获取日志流 - 用于SSE，直接读取统一流 agent_logs 并按 execution_id 过滤"""
        stream_key = self.log_stream_key
        consecutive_errors = 0
        max_consecutive_errors = 5

        try:
            while True:
                try:
                    # 确保连接可用
                    try:
                        self._ensure_connection()
                    except Exception as e:
                        yield {
                            'id': last_id,
                            'type': 'error',
                            'data': {'message': f'redis连接不可用: {e}'}
                        }
                        break

                    # 从redis stream读取新消息
                    # count增加到100，block增加到5秒，减少轮询频率
                    messages = self.redis_client.xread(
                        {stream_key: last_id},
                        count=200,
                        block=5000
                    )

                    if messages:
                        consecutive_errors = 0  # 重置错误计数
                        for stream, msgs in messages:
                            for msg_id, fields in msgs:
                                last_id = msg_id
                                # 使用execution_id进行过滤，不再有fallback逻辑
                                exec_id = fields.get("execution_id")
                                if exec_id != execution_id:
                                    continue
                                yield {
                                    'id': msg_id,
                                    'type': 'log',
                                    'data': fields
                                }
                    else:
                        # 没有新消息时发送心跳
                        yield {
                            'id': last_id,
                            'type': 'heartbeat',
                            'data': {'timestamp': timezone.now().isoformat()}
                        }

                except (redis.ConnectionError, redis.TimeoutError) as e:
                    consecutive_errors += 1
                    logger.warning(f"redis连接错误 (连续错误: {consecutive_errors}): {execution_id} - {e}")

                    if consecutive_errors >= max_consecutive_errors:
                        logger.error(f"连续redis错误过多，停止日志流: {execution_id}")
                        yield {
                            'id': last_id,
                            'type': 'error',
                            'data': {'message': f'连接错误过多: {str(e)}'}
                        }
                        break

                    # 等待后重试
                    import time
                    time.sleep(2)

        except Exception as e:
            logger.error(f"获取日志流失败: {execution_id} - {e}")
            yield {
                'id': last_id,
                'type': 'error',
                'data': {'message': str(e)}
            }

    def get_status_stream(self, execution_id: str, last_id: str = '0') -> Generator[Dict[str, Any], None, None]:
        """获取状态流 - 用于SSE"""
        stream_key = self.status_stream_key

        try:
            while True:
                # 从redis stream读取新消息
                messages = self.redis_client.xread({stream_key: last_id}, count=10, block=1000)

                if messages:
                    for stream, msgs in messages:
                        for msg_id, fields in msgs:
                            if fields.get("execution_id") != str(execution_id):
                                continue
                            yield {
                                'id': msg_id,
                                'type': 'status',
                                'data': fields
                            }
                            last_id = msg_id
                else:
                    # 没有新消息时发送心跳
                    yield {
                        'id': last_id,
                        'type': 'heartbeat',
                        'data': {'timestamp': timezone.now().isoformat()}
                    }

        except Exception as e:
            logger.error(f"获取状态流失败: {execution_id} - {e}")
            yield {
                'id': last_id,
                'type': 'error',
                'data': {'message': str(e)}
            }
    
    def get_historical_logs(self, execution_id: str, limit: int = 100, stream_key: str = None) -> list:
        """获取历史日志（从指定流过滤 execution_id）"""
        stream_key = stream_key or self.log_stream_key
        logger.info(f"get_historical_logs: execution_id={execution_id}, stream_key={stream_key}, limit={limit}")

        try:
            messages = self.redis_client.xrevrange(stream_key, count=limit * 10)
            logger.info(f"redis xrevrange: stream_key={stream_key}, count={limit * 10}, messages_count={len(messages)}")

            logs = []
            for msg_id, fields in messages:
                # 使用execution_id进行过滤，不再有fallback逻辑
                exec_id = fields.get("execution_id")
                if exec_id != execution_id:
                    continue
                logs.append({
                    'id': msg_id,
                    'timestamp': fields.get('timestamp'),
                    'host_id': fields.get('host_id'),
                    'host_name': fields.get('host_name'),
                    'host_ip': fields.get('host_ip'),
                    'log_type': fields.get('log_type'),
                    'content': fields.get('content'),
                    'step_name': fields.get('step_name'),
                    'step_order': int(fields.get('step_order', 0))
                })
                if len(logs) >= limit:
                    break

            # 按时间顺序排序
            logs.reverse()
            logger.info(f"获取历史日志: {len(logs)} 条（过滤后），原始读取: {len(messages)}")
            return logs

        except Exception as e:
            logger.error(f"获取历史日志失败: {execution_id} - {e}")
            return []

    def cleanup_logs(self, execution_id: str):
        """清理日志"""
        try:
            self.redis_client.delete(self.status_stream_key)
            logger.info(f"清理状态流: {self.status_stream_key}")

        except Exception as e:
            logger.error(f"清理日志失败: {execution_id} - {e}")

    def _parse_redis_pointer(self, pointer: str):
        """
        解析 storage_uri 风格的 redis 指针。
        格式示例：redis:agent_logs/<execution_id>@<last_id>
        返回 (execution_id, max_id)
        """
        if not pointer or not pointer.startswith("redis:"):
            return None, None

        body = pointer[len("redis:") :]
        path, max_id = (body.split("@", 1) + [""])[:2]
        # 兼容 agent_logs/<id> 或 agent_logs:<id>
        execution_id = path.replace("agent_logs/", "").replace("agent_logs:", "")
        return execution_id, max_id or None

    def get_logs_by_pointer(self, pointer: str, limit: int = 500):
        """
        通过 storage_uri 指针获取历史日志（默认返回最新 limit 条，按时间正序）
        """
        task_id, max_id = self._parse_redis_pointer(pointer)
        if not task_id:
            return []

        stream_key = self.log_stream_key
        try:
            messages = self.redis_client.xrevrange(
                stream_key,
                max=max_id or "+",
                count=limit,
            )
            logs = []
            for msg_id, fields in messages:
                logs.append(
                    {
                        "id": msg_id,
                        "timestamp": fields.get("timestamp"),
                        "host_id": fields.get("host_id"),
                        "host_name": fields.get("host_name"),
                        "host_ip": fields.get("host_ip"),
                        "log_type": fields.get("log_type"),
                        "content": fields.get("content"),
                        "step_name": fields.get("step_name"),
                        "step_order": int(fields.get("step_order", 0)),
                    }
                )
            logs.reverse()
            return logs
        except Exception as e:
            logger.error(f"通过指针获取历史日志失败 pointer={pointer}: {e}")
            return []


# 全局实例
realtime_log_service = RealtimeLogService()
