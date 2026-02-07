"""
任务结果等待器

等待 Agent 任务执行结果，支持单个和批量等待。
基于 Redis Stream 订阅任务结果。
"""
import logging
import time
from typing import Any, Dict, List, Optional, Set, Callable

import redis
from django.conf import settings

logger = logging.getLogger(__name__)


class TaskResultWaiter:
    """
    任务结果等待器

    等待 Agent-Server 推送到 Redis Stream 的任务执行结果。

    使用方式:
        waiter = TaskResultWaiter()
        result = waiter.wait_for_result('task_id_123', timeout=300)
        results = waiter.wait_for_results(['task_1', 'task_2'], timeout=300)

    配置项:
        - REDIS_HOST, REDIS_PORT, REDIS_PASSWORD, REDIS_DB_REALTIME: Redis 连接配置
        - RESULT_STREAM_KEY: 任务结果流的 key，默认 'task_results'
    """

    def __init__(
        self,
        redis_client: Optional[redis.Redis] = None,
        stream_key: Optional[str] = None
    ):
        """
        初始化任务结果等待器

        Args:
            redis_client: Redis 客户端实例，如果不提供则自动创建
            stream_key: 结果流的 key，如果不提供则从配置读取
        """
        if redis_client is not None:
            self.redis_client = redis_client
        else:
            self._init_redis_client()

        self.stream_key = stream_key or self._get_stream_key()

    def _init_redis_client(self) -> None:
        """初始化 Redis 客户端"""
        try:
            connection_pool = redis.ConnectionPool(
                host=getattr(settings, 'REDIS_HOST', 'localhost'),
                port=getattr(settings, 'REDIS_PORT', 6379),
                password=getattr(settings, 'REDIS_PASSWORD', None),
                db=getattr(settings, 'REDIS_DB_REALTIME', 3),
                decode_responses=True,
                socket_connect_timeout=5,
                socket_timeout=5,
                socket_keepalive=True,
                retry_on_timeout=True,
                max_connections=20
            )
            self.redis_client = redis.Redis(connection_pool=connection_pool)
        except Exception as e:
            logger.error(f"初始化 Redis 客户端失败: {e}")
            self.redis_client = None

    def _get_stream_key(self) -> str:
        """获取结果流的 key"""
        try:
            from apps.system_config.models import ConfigManager
            return ConfigManager.get('result_stream.key', 'task_results')
        except Exception:
            return getattr(settings, 'RESULT_STREAM_KEY', 'task_results')

    def _ensure_connection(self) -> bool:
        """确保 Redis 连接可用"""
        if self.redis_client is None:
            return False
        try:
            self.redis_client.ping()
            return True
        except Exception as e:
            logger.warning(f"Redis 连接不可用: {e}")
            return False

    def wait_for_result(
        self,
        task_id: str,
        timeout: int = 300,
        poll_interval: float = 0.5
    ) -> Dict[str, Any]:
        """
        等待单个任务的执行结果

        Args:
            task_id: 任务 ID
            timeout: 超时时间（秒）
            poll_interval: 轮询间隔（秒）

        Returns:
            Dict: 任务结果，包含:
                - task_id: 任务 ID
                - status: 状态 (completed/failed/timeout)
                - exit_code: 退出码
                - error_msg: 错误信息
                - started_at: 开始时间
                - finished_at: 结束时间
                - success: 是否成功
        """
        results = self.wait_for_results([task_id], timeout, poll_interval)
        return results.get(task_id, {
            'task_id': task_id,
            'status': 'timeout',
            'success': False,
            'error_msg': f'等待结果超时 ({timeout}秒)'
        })

    def wait_for_results(
        self,
        task_ids: List[str],
        timeout: int = 300,
        poll_interval: float = 0.5
    ) -> Dict[str, Dict[str, Any]]:
        """
        等待多个任务的执行结果

        Args:
            task_ids: 任务 ID 列表
            timeout: 超时时间（秒）
            poll_interval: 轮询间隔（秒）

        Returns:
            Dict[str, Dict]: 任务 ID 到结果的映射
        """
        if not task_ids:
            return {}

        if not self._ensure_connection():
            logger.error("Redis 连接不可用，无法等待任务结果")
            return {
                task_id: {
                    'task_id': task_id,
                    'status': 'error',
                    'success': False,
                    'error_msg': 'Redis 连接不可用'
                }
                for task_id in task_ids
            }

        pending_tasks: Set[str] = set(task_ids)
        results: Dict[str, Dict[str, Any]] = {}
        start_time = time.time()
        last_id = '0'  # 从流的开头开始读取

        # 获取轮询间隔配置
        try:
            from apps.system_config.models import ConfigManager
            poll_interval = ConfigManager.get('result_stream.poll_interval', poll_interval)
        except Exception:
            pass

        logger.info(f"开始等待 {len(task_ids)} 个任务结果: {task_ids[:5]}{'...' if len(task_ids) > 5 else ''}")

        while pending_tasks and (time.time() - start_time) < timeout:
            try:
                # 使用 XREAD 阻塞读取，但设置较短的阻塞时间以便检查超时
                block_ms = int(poll_interval * 1000)
                response = self.redis_client.xread(
                    {self.stream_key: last_id},
                    count=100,
                    block=block_ms
                )

                if response:
                    for stream_name, messages in response:
                        for message_id, data in messages:
                            last_id = message_id
                            task_id = data.get('task_id')

                            if task_id and task_id in pending_tasks:
                                result = self._parse_result(data)
                                results[task_id] = result
                                pending_tasks.discard(task_id)

                                logger.debug(
                                    f"收到任务结果: task_id={task_id}, "
                                    f"status={result.get('status')}, "
                                    f"剩余 {len(pending_tasks)} 个任务"
                                )

                                if not pending_tasks:
                                    break

            except redis.ConnectionError as e:
                logger.warning(f"Redis 连接错误，尝试重连: {e}")
                time.sleep(poll_interval)
                continue
            except Exception as e:
                logger.error(f"等待任务结果时出错: {e}", exc_info=True)
                time.sleep(poll_interval)
                continue

        # 处理超时的任务
        for task_id in pending_tasks:
            results[task_id] = {
                'task_id': task_id,
                'status': 'timeout',
                'success': False,
                'error_msg': f'等待结果超时 ({timeout}秒)',
                'exit_code': -1
            }
            logger.warning(f"任务 {task_id} 等待超时")

        elapsed = time.time() - start_time
        completed = len(task_ids) - len(pending_tasks)
        logger.info(
            f"等待完成: {completed}/{len(task_ids)} 个任务在 {elapsed:.1f}秒内返回结果"
        )

        return results

    def _parse_result(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        解析 Redis Stream 中的任务结果

        Args:
            data: Redis Stream 消息数据

        Returns:
            Dict: 标准化的任务结果
        """
        status = data.get('status', 'unknown')
        exit_code = data.get('exit_code')

        # 尝试将 exit_code 转为整数
        if exit_code is not None:
            try:
                exit_code = int(exit_code)
            except (ValueError, TypeError):
                exit_code = -1

        # 获取 host_id（Agent-Server 从 task_id 中解析并写入）
        host_id = data.get('host_id')
        if host_id is not None:
            try:
                host_id = int(host_id)
            except (ValueError, TypeError):
                host_id = 0

        # 判断是否成功
        success = (status == 'completed' or status == 'success') and exit_code == 0

        return {
            'task_id': data.get('task_id', ''),
            'agent_id': data.get('agent_id', ''),
            'host_id': host_id,  # 添加 host_id 字段
            'status': status,
            'exit_code': exit_code,
            'error_msg': data.get('error_msg', ''),
            'error_code': data.get('error_code', ''),
            'started_at': data.get('started_at', ''),
            'finished_at': data.get('finished_at', ''),
            'log_size': data.get('log_size', 0),
            'log_pointer': data.get('log_pointer', ''),
            'success': success,
            'received_at': data.get('received_at', '')
        }

    def subscribe_results(
        self,
        task_ids: Set[str],
        callback: Callable[[str, Dict[str, Any]], None],
        timeout: int = 300,
        poll_interval: float = 0.5
    ) -> Set[str]:
        """
        订阅任务结果，有结果时调用回调

        Args:
            task_ids: 要等待的任务 ID 集合
            callback: 收到结果时的回调函数，参数为 (task_id, result)
            timeout: 超时时间（秒）
            poll_interval: 轮询间隔（秒）

        Returns:
            Set[str]: 超时未完成的任务 ID 集合
        """
        if not task_ids:
            return set()

        if not self._ensure_connection():
            logger.error("Redis 连接不可用，无法订阅任务结果")
            return task_ids

        pending_tasks = set(task_ids)
        start_time = time.time()
        last_id = '0'

        while pending_tasks and (time.time() - start_time) < timeout:
            try:
                block_ms = int(poll_interval * 1000)
                response = self.redis_client.xread(
                    {self.stream_key: last_id},
                    count=100,
                    block=block_ms
                )

                if response:
                    for stream_name, messages in response:
                        for message_id, data in messages:
                            last_id = message_id
                            task_id = data.get('task_id')

                            if task_id and task_id in pending_tasks:
                                result = self._parse_result(data)
                                pending_tasks.discard(task_id)

                                try:
                                    callback(task_id, result)
                                except Exception as e:
                                    logger.error(f"结果回调执行失败: task_id={task_id}, error={e}")

            except redis.ConnectionError as e:
                logger.warning(f"Redis 连接错误: {e}")
                time.sleep(poll_interval)
            except Exception as e:
                logger.error(f"订阅任务结果时出错: {e}", exc_info=True)
                time.sleep(poll_interval)

        return pending_tasks


# 全局实例（延迟初始化）
_task_result_waiter: Optional[TaskResultWaiter] = None


def get_task_result_waiter() -> TaskResultWaiter:
    """
    获取任务结果等待器的全局实例

    Returns:
        TaskResultWaiter: 全局实例
    """
    global _task_result_waiter
    if _task_result_waiter is None:
        _task_result_waiter = TaskResultWaiter()
    return _task_result_waiter
