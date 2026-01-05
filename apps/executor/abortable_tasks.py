"""
任务取消标志工具
原先为 Celery Task 基类，现在仅保留基于 Redis 的取消标志逻辑，供 Agent / 传统执行路径复用。
"""
from django.core.cache import cache


def check_task_cancellation(execution_id):
    """检查任务是否被取消"""
    return cache.get(f"cancel:{execution_id}") is not None


def raise_if_cancelled(execution_id):
    """如果任务被取消则抛出异常"""
    if check_task_cancellation(execution_id):
        raise RuntimeError("任务已被用户取消")


def clear_cancellation_flag(execution_id):
    """清除取消标志"""
    cache.delete(f"cancel:{execution_id}")
