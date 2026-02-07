import atexit
import logging

from django.apps import AppConfig

logger = logging.getLogger(__name__)


class AgentsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.agents"
    verbose_name = "agent 管理"

    def ready(self):
        """Django 应用启动时注册关闭钩子"""
        # 注册 atexit 钩子以确保全局线程池在进程退出时优雅关闭
        atexit.register(self._shutdown_global_resources)

    @staticmethod
    def _shutdown_global_resources():
        """关闭全局资源（线程池等）"""
        # atexit 阶段日志处理器可能已关闭，避免再次触发 logging error。
        logging.raiseExceptions = False
        try:
            from utils.thread_pool import get_global_thread_pool
            pool = get_global_thread_pool()
            pool.shutdown(wait=True)
        except Exception:
            pass
