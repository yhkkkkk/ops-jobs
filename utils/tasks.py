"""
工具类任务（原 Celery 任务，现直接由业务代码调用同步归档）。
"""
import logging

logger = logging.getLogger(__name__)


def archive_execution_logs(execution_id: int, task_id: str):
    """归档执行日志任务（同步调用）。"""
    try:
        from .log_archive_service import log_archive_service

        logger.info(f"开始归档日志任务: execution_id={execution_id}, task_id={task_id}")

        success = log_archive_service.archive_execution_logs(execution_id, task_id)
        if success:
            logger.info(f"日志归档成功: execution_id={execution_id}")
            return {
                'success': True,
                'execution_id': execution_id,
                'task_id': task_id,
                'message': '日志归档完成',
            }

        logger.error(f"日志归档失败: execution_id={execution_id}")
        return {
            'success': False,
            'execution_id': execution_id,
            'task_id': task_id,
            'error': 'archive_execution_logs returned False',
        }

    except Exception as e:
        logger.error(f"日志归档任务异常: execution_id={execution_id}, task_id={task_id} - {e}")
        return {
            'success': False,
            'execution_id': execution_id,
            'task_id': task_id,
            'error': str(e),
        }
