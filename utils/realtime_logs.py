"""
实时日志服务 - 基于Redis Stream的实时日志推送
"""
import redis
import logging
from django.conf import settings
from typing import Dict, Any, Generator
from datetime import datetime

logger = logging.getLogger(__name__)


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
        self.log_stream_prefix = "job_logs:"
        self.status_stream_prefix = "job_status:"
        self._connection_pool = None

    def _ensure_connection(self):
        """确保Redis连接可用"""
        max_retries = 3
        for attempt in range(max_retries):
            try:
                # 测试连接
                self.redis_client.ping()
                return True
            except (redis.ConnectionError, redis.TimeoutError) as e:
                logger.warning(f"Redis连接测试失败 (尝试 {attempt + 1}/{max_retries}): {e}")
                if attempt < max_retries - 1:
                    import time
                    time.sleep(1)  # 等待1秒后重试
                else:
                    logger.error(f"Redis连接最终失败，已重试{max_retries}次")
                    return False
        return False
    
    def push_log(self, task_id: str, host_id: str, log_data: Dict[str, Any]):
        """推送日志到Redis Stream

        Args:
            task_id: 执行ID (execution_id)，用于标识执行记录
            host_id: 主机ID
            log_data: 日志数据
        """
        try:
            # 快速失败策略，避免阻塞
            if not self._ensure_connection():
                logger.error(f"Redis连接不可用，跳过日志推送: {task_id}")
                return

            stream_key = f"{self.log_stream_prefix}{task_id}"

            # 构建日志消息
            message = {
                'timestamp': datetime.now().isoformat(),
                'host_id': str(host_id),
                'host_name': log_data.get('host_name', ''),
                'host_ip': log_data.get('host_ip', ''),
                'log_type': log_data.get('log_type', 'stdout'),  # stdout, stderr, info, error
                'content': log_data.get('content', ''),
                'step_name': log_data.get('step_name', ''),
                'step_order': log_data.get('step_order', 0)
            }

            # 使用pipeline批量操作，提高性能
            pipe = self.redis_client.pipeline()
            pipe.xadd(stream_key, message)
            pipe.expire(stream_key, 43200)  # 设置过期时间（12小时）
            pipe.execute()

            logger.debug(f"推送日志到 {stream_key}: {message}")

        except (redis.ConnectionError, redis.TimeoutError) as e:
            logger.error(f"Redis连接错误，推送日志失败: {task_id} - {e}")
        except Exception as e:
            logger.error(f"推送日志失败: {task_id} - {e}")

    def push_log_async(self, task_id: str, host_id: str, log_data: Dict[str, Any]):
        """
        异步推送日志，避免阻塞主线程
        """
        import threading

        def push_worker():
            self.push_log(task_id, host_id, log_data)

        # 创建守护线程
        thread = threading.Thread(target=push_worker, daemon=True)
        thread.start()
    
    def push_status(self, task_id: str, status_data: Dict[str, Any]):
        """推送状态更新到Redis Stream

        Args:
            task_id: 执行ID (execution_id)，用于标识执行记录
            status_data: 状态数据
        """
        max_retries = 3
        for attempt in range(max_retries):
            try:
                # 确保连接可用
                if not self._ensure_connection():
                    logger.error(f"Redis连接不可用，跳过状态推送: {task_id}")
                    return

                stream_key = f"{self.status_stream_prefix}{task_id}"

                # 构建状态消息
                message = {
                    'timestamp': datetime.now().isoformat(),
                    'status': status_data.get('status', ''),
                    'progress': status_data.get('progress', 0),
                    'current_step': status_data.get('current_step', ''),
                    'total_hosts': status_data.get('total_hosts', 0),
                    'success_hosts': status_data.get('success_hosts', 0),
                    'failed_hosts': status_data.get('failed_hosts', 0),
                    'running_hosts': status_data.get('running_hosts', 0),
                    'message': status_data.get('message', '')
                }

                # 推送到Redis Stream
                self.redis_client.xadd(stream_key, message)

                # 设置过期时间（24小时）
                self.redis_client.expire(stream_key, 86400)

                logger.debug(f"推送状态到 {stream_key}: {message}")
                break  # 成功则跳出重试循环

            except (redis.ConnectionError, redis.TimeoutError) as e:
                logger.error(f"Redis连接错误，推送状态失败 (尝试 {attempt + 1}/{max_retries}): {task_id} - {e}")
                if attempt < max_retries - 1:
                    import time
                    time.sleep(1)  # 重试前等待更长时间
            except Exception as e:
                logger.error(f"推送状态失败 (尝试 {attempt + 1}/{max_retries}): {task_id} - {e}")
                if attempt == max_retries - 1:
                    logger.error(f"推送状态最终失败: {task_id}")
                else:
                    import time
                    time.sleep(0.5)  # 重试前等待
    
    def get_logs_stream(self, task_id: str, last_id: str = '0') -> Generator[Dict[str, Any], None, None]:
        """获取日志流 - 用于SSE"""
        stream_key = f"{self.log_stream_prefix}{task_id}"
        consecutive_errors = 0
        max_consecutive_errors = 5

        try:
            while True:
                try:
                    # 确保连接可用
                    if not self._ensure_connection():
                        yield {
                            'id': last_id,
                            'type': 'error',
                            'data': {'message': 'Redis连接不可用'}
                        }
                        break

                    # 从Redis Stream读取新消息
                    messages = self.redis_client.xread({stream_key: last_id}, count=10, block=1000)

                    if messages:
                        consecutive_errors = 0  # 重置错误计数
                        for stream, msgs in messages:
                            for msg_id, fields in msgs:
                                yield {
                                    'id': msg_id,
                                    'type': 'log',
                                    'data': fields
                                }
                                last_id = msg_id
                    else:
                        # 没有新消息时发送心跳
                        yield {
                            'id': last_id,
                            'type': 'heartbeat',
                            'data': {'timestamp': datetime.now().isoformat()}
                        }

                except (redis.ConnectionError, redis.TimeoutError) as e:
                    consecutive_errors += 1
                    logger.warning(f"Redis连接错误 (连续错误: {consecutive_errors}): {task_id} - {e}")

                    if consecutive_errors >= max_consecutive_errors:
                        logger.error(f"连续Redis错误过多，停止日志流: {task_id}")
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
            logger.error(f"获取日志流失败: {task_id} - {e}")
            yield {
                'id': last_id,
                'type': 'error',
                'data': {'message': str(e)}
            }
    
    def get_status_stream(self, task_id: str, last_id: str = '0') -> Generator[Dict[str, Any], None, None]:
        """获取状态流 - 用于SSE"""
        stream_key = f"{self.status_stream_prefix}{task_id}"
        
        try:
            while True:
                # 从Redis Stream读取新消息
                messages = self.redis_client.xread({stream_key: last_id}, count=10, block=1000)
                
                if messages:
                    for stream, msgs in messages:
                        for msg_id, fields in msgs:
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
                        'data': {'timestamp': datetime.now().isoformat()}
                    }
                    
        except Exception as e:
            logger.error(f"获取状态流失败: {task_id} - {e}")
            yield {
                'id': last_id,
                'type': 'error',
                'data': {'message': str(e)}
            }
    
    def get_historical_logs(self, task_id: str, limit: int = 100) -> list:
        """获取历史日志"""
        stream_key = f"{self.log_stream_prefix}{task_id}"
        
        try:
            # 获取最近的日志
            messages = self.redis_client.xrevrange(stream_key, count=limit)
            
            logs = []
            for msg_id, fields in messages:
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
            
            # 按时间顺序排序
            logs.reverse()
            logger.info(f"获取历史日志: {len(logs)} 条，Stream中总消息数: {len(messages)}")
            return logs
            
        except Exception as e:
            logger.error(f"获取历史日志失败: {task_id} - {e}")
            return []
    
    def cleanup_logs(self, task_id: str):
        """清理日志"""
        try:
            log_stream_key = f"{self.log_stream_prefix}{task_id}"
            status_stream_key = f"{self.status_stream_prefix}{task_id}"
            
            self.redis_client.delete(log_stream_key)
            self.redis_client.delete(status_stream_key)
            
            logger.info(f"清理日志: {task_id}")
            
        except Exception as e:
            logger.error(f"清理日志失败: {task_id} - {e}")


# 全局实例
realtime_log_service = RealtimeLogService()
