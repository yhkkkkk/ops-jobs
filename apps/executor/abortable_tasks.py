"""
可取消的任务基类
支持Redis标志 + SIGUSR1信号的混合取消方案
"""
from celery import Task
from celery.exceptions import SoftTimeLimitExceeded
from django.core.cache import cache
import logging

logger = logging.getLogger(__name__)


class AbortableTask(Task):
    """可取消的任务基类"""
    
    def is_aborted(self, execution_id=None):
        """检查任务是否被取消"""
        if execution_id:
            return cache.get(f"cancel:{execution_id}") is not None
        return False
    
    def check_abort(self, execution_id=None):
        """检查并抛出取消异常"""
        if self.is_aborted(execution_id):
            logger.info(f"任务被取消: {execution_id}")
            raise SoftTimeLimitExceeded("任务已被用户取消")
    
    def on_soft_time_limit_exceeded(self, exc, task_id, args, kwargs):
        """处理软超时（包括取消）"""
        execution_id = kwargs.get('execution_id')
        if self.is_aborted(execution_id):
            logger.info(f"任务被用户取消: {execution_id}")
            return {
                'success': False,
                'message': '任务已被用户取消',
                'cancelled': True
            }
        else:
            logger.warning(f"任务超时: {execution_id}")
            return {
                'success': False,
                'message': '任务执行超时',
                'timeout': True
            }
    
    def on_success(self, retval, task_id, args, kwargs):
        """任务成功完成时清理取消标志"""
        execution_id = kwargs.get('execution_id')
        if execution_id:
            clear_cancellation_flag(execution_id)
            logger.debug(f"清理取消标志: {execution_id}")
    
    def on_failure(self, exc, task_id, args, kwargs, einfo):
        """任务失败时清理取消标志"""
        execution_id = kwargs.get('execution_id')
        if execution_id:
            clear_cancellation_flag(execution_id)
            logger.debug(f"清理取消标志: {execution_id}")


def check_task_cancellation(execution_id):
    """检查任务是否被取消"""
    return cache.get(f"cancel:{execution_id}") is not None


def raise_if_cancelled(execution_id):
    """如果任务被取消则抛出异常"""
    if check_task_cancellation(execution_id):
        raise SoftTimeLimitExceeded("任务已被用户取消")


def clear_cancellation_flag(execution_id):
    """清除取消标志"""
    cache.delete(f"cancel:{execution_id}")
