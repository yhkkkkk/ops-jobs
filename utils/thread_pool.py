"""
全局线程池管理器

提供共享的全局线程池，避免每次请求创建新的 ThreadPoolExecutor。
使用单例模式确保整个应用使用同一个线程池实例。
"""
import logging
import os
import threading
from concurrent.futures import ThreadPoolExecutor, Future
from typing import Callable, Any, Optional

logger = logging.getLogger(__name__)


class GlobalThreadPool:
    """
    全局共享线程池（单例模式）

    使用方式:
        pool = GlobalThreadPool.get_instance()
        future = pool.submit(my_function, arg1, arg2)

    配置项 (通过 ConfigManager):
        - thread_pool.max_workers: 最大工作线程数，默认 CPU 核心数 * 2
        - thread_pool.thread_name_prefix: 线程名前缀，默认 'global-pool'
    """

    _instance: Optional['GlobalThreadPool'] = None
    _lock = threading.Lock()
    _initialized = False

    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                # 双重检查锁定
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        # 避免重复初始化
        if GlobalThreadPool._initialized:
            return

        with GlobalThreadPool._lock:
            if GlobalThreadPool._initialized:
                return

            self._executor: Optional[ThreadPoolExecutor] = None
            self._shutdown = False
            self._executor_lock = threading.Lock()
            GlobalThreadPool._initialized = True

    @classmethod
    def get_instance(cls) -> 'GlobalThreadPool':
        """
        获取全局线程池实例

        Returns:
            GlobalThreadPool: 全局线程池单例
        """
        return cls()

    def _get_max_workers(self) -> int:
        """
        获取最大工作线程数配置

        Returns:
            int: 最大工作线程数
        """
        try:
            from apps.system_config.models import ConfigManager
            return ConfigManager.get('thread_pool.max_workers', os.cpu_count() * 2 or 8)
        except Exception:
            # 如果 ConfigManager 不可用，使用默认值
            return os.cpu_count() * 2 or 8

    def _get_thread_name_prefix(self) -> str:
        """
        获取线程名前缀配置

        Returns:
            str: 线程名前缀
        """
        try:
            from apps.system_config.models import ConfigManager
            return ConfigManager.get('thread_pool.thread_name_prefix', 'global-pool')
        except Exception:
            return 'global-pool'

    def _ensure_executor(self) -> ThreadPoolExecutor:
        """
        确保线程池已初始化（延迟初始化）

        Returns:
            ThreadPoolExecutor: 线程池实例

        Raises:
            RuntimeError: 如果线程池已关闭
        """
        if self._shutdown:
            raise RuntimeError("线程池已关闭，无法提交新任务")

        if self._executor is None:
            with self._executor_lock:
                if self._executor is None and not self._shutdown:
                    max_workers = self._get_max_workers()
                    thread_name_prefix = self._get_thread_name_prefix()
                    self._executor = ThreadPoolExecutor(
                        max_workers=max_workers,
                        thread_name_prefix=thread_name_prefix
                    )
                    logger.info(
                        f"全局线程池已初始化: max_workers={max_workers}, "
                        f"thread_name_prefix={thread_name_prefix}"
                    )

        return self._executor

    def submit(self, fn: Callable, *args, **kwargs) -> Future:
        """
        提交任务到线程池

        Args:
            fn: 要执行的函数
            *args: 位置参数
            **kwargs: 关键字参数

        Returns:
            Future: 任务的 Future 对象

        Raises:
            RuntimeError: 如果线程池已关闭
        """
        executor = self._ensure_executor()
        return executor.submit(fn, *args, **kwargs)

    def submit_async_task(self, fn: Callable, *args, **kwargs) -> str:
        """
        提交异步任务（不关心返回值）

        与 submit() 的区别是不返回 Future，适用于 fire-and-forget 场景。

        Args:
            fn: 要执行的函数
            *args: 位置参数
            **kwargs: 关键字参数

        Returns:
            str: 任务描述信息
        """
        def wrapper():
            try:
                fn(*args, **kwargs)
            except Exception as e:
                logger.error(f"异步任务执行失败: {e}", exc_info=True)

        self.submit(wrapper)
        return f"Task submitted: {fn.__name__ if hasattr(fn, '__name__') else str(fn)}"

    def shutdown(self, wait: bool = True, cancel_futures: bool = False) -> None:
        """
        关闭线程池

        Args:
            wait: 是否等待所有任务完成
            cancel_futures: 是否取消待执行的任务 (Python 3.9+)
        """
        with self._executor_lock:
            if self._shutdown:
                logger.warning("线程池已经关闭")
                return

            self._shutdown = True

            if self._executor is not None:
                logger.info(f"正在关闭全局线程池 (wait={wait})...")
                try:
                    import sys
                    if sys.version_info >= (3, 9):
                        self._executor.shutdown(wait=wait, cancel_futures=cancel_futures)
                    else:
                        self._executor.shutdown(wait=wait)
                    logger.info("全局线程池已关闭")
                except Exception as e:
                    logger.error(f"关闭线程池时出错: {e}", exc_info=True)
                finally:
                    self._executor = None

    @property
    def max_workers(self) -> int:
        """
        获取当前配置的最大工作线程数

        Returns:
            int: 最大工作线程数
        """
        return self._get_max_workers()

    @property
    def is_shutdown(self) -> bool:
        """
        检查线程池是否已关闭

        Returns:
            bool: 是否已关闭
        """
        return self._shutdown

    @classmethod
    def reset_instance(cls) -> None:
        """
        重置单例实例（仅用于测试）

        警告: 生产环境不应调用此方法
        """
        with cls._lock:
            if cls._instance is not None:
                cls._instance.shutdown(wait=True)
            cls._instance = None
            cls._initialized = False


# 便捷函数
def get_global_thread_pool() -> GlobalThreadPool:
    """
    获取全局线程池实例的便捷函数

    Returns:
        GlobalThreadPool: 全局线程池单例
    """
    return GlobalThreadPool.get_instance()
