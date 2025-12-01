"""
工具类Celery任务
"""
import logging
from celery import shared_task

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3)
def archive_execution_logs(self, execution_id: int, task_id: str):
    """归档执行日志任务"""
    try:
        from .log_archive_service import log_archive_service
        
        logger.info(f"开始归档日志任务: execution_id={execution_id}, task_id={task_id}")
        
        # 执行归档
        success = log_archive_service.archive_execution_logs(execution_id, task_id)
        
        if success:
            logger.info(f"日志归档成功: execution_id={execution_id}")
            return {
                'success': True,
                'execution_id': execution_id,
                'task_id': task_id,
                'message': '日志归档完成'
            }
        else:
            logger.error(f"日志归档失败: execution_id={execution_id}")
            # 重试
            raise self.retry(countdown=60, max_retries=3)
            
    except Exception as e:
        logger.error(f"日志归档任务异常: execution_id={execution_id}, task_id={task_id} - {e}")
        
        # 如果还有重试次数，则重试
        if self.request.retries < self.max_retries:
            raise self.retry(countdown=60 * (self.request.retries + 1))
        else:
            # 最终失败，记录错误
            logger.error(f"日志归档最终失败: execution_id={execution_id}, task_id={task_id}")
            return {
                'success': False,
                'execution_id': execution_id,
                'task_id': task_id,
                'error': str(e)
            }
