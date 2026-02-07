"""
作业调度服务（改为 APScheduler，弃用 Celery Beat）
"""
import logging
from datetime import datetime
from django.utils import timezone
from django.db import transaction
from croniter import croniter
from .models import ScheduledJob
from apps.executor.services import ExecutionRecordService

logger = logging.getLogger(__name__)


class SchedulerService:
    """调度服务"""
    
    @staticmethod
    def create_scheduled_job(name, execution_plan, cron_expression, created_by=None, **kwargs):
        """创建定时作业"""
        try:
            # 预验证cron表达式
            cron_expression = cron_expression.strip()
            if not croniter.is_valid(cron_expression):
                raise ValueError(f"无效的Cron表达式: {cron_expression}")

            # 验证时区
            timezone_name = kwargs.get('timezone', 'Asia/Shanghai')
            try:
                import pytz
                pytz.timezone(timezone_name)
            except pytz.exceptions.UnknownTimeZoneError:
                raise ValueError(f"无效的时区: {timezone_name}")

            with transaction.atomic():
                # 创建定时作业（仅持久化调度配置，APScheduler 负责加载/执行）
                scheduled_job = ScheduledJob.objects.create(
                    name=name,
                    description=kwargs.get('description', ''),
                    execution_plan=execution_plan,
                    cron_expression=cron_expression,
                    timezone=kwargs.get('timezone', 'Asia/Shanghai'),
                    is_active=kwargs.get('is_active', False),
                    created_by=created_by
                )
                logger.info(f"创建定时作业成功（APScheduler）：{name}")
                return scheduled_job
                
        except Exception as e:
            logger.error(f"创建定时作业失败: {name} - {e}")
            raise
    
    @staticmethod
    def update_scheduled_job(scheduled_job, **kwargs):
        """更新定时作业"""
        try:
            with transaction.atomic():
                # 更新基本信息
                for field in ['name', 'description', 'cron_expression', 'timezone', 'is_active']:
                    if field in kwargs:
                        setattr(scheduled_job, field, kwargs[field])
                
                # 删除目标主机更新逻辑，因为目标主机在JobStep中配置
                
                scheduled_job.save()
                
                logger.info(f"更新定时作业成功（APScheduler）：{scheduled_job.name}")
                return scheduled_job
                
        except Exception as e:
            logger.error(f"更新定时作业失败: {scheduled_job.name} - {e}")
            raise
    
    @staticmethod
    def delete_scheduled_job(scheduled_job):
        """删除定时作业"""
        try:
            with transaction.atomic():
                # 删除定时作业
                job_name = scheduled_job.name
                scheduled_job.delete()
                
                logger.info(f"删除定时作业成功: {job_name}")
                return True
                
        except Exception as e:
            logger.error(f"删除定时作业失败: {scheduled_job.name} - {e}")
            return False
    
    # 注意：移除了 execute_scheduled_job_now；定时作业不支持“立即执行”

    @staticmethod
    def enable_scheduled_job(scheduled_job):
        """启用定时作业"""
        try:
            # 更新数据库状态
            scheduled_job.is_active = True
            scheduled_job.save()

            # 启用Celery Beat任务
            if scheduled_job.periodic_task:
                scheduled_job.periodic_task.enabled = True
                scheduled_job.periodic_task.save()
                logger.info(f"启用定时作业成功: {scheduled_job.name}")
            else:
                logger.warning(f"定时作业 {scheduled_job.name} 没有关联的Celery Beat任务")

        except Exception as e:
            logger.error(f"启用定时作业失败: {scheduled_job.name} - {e}")
            raise

    @staticmethod
    def disable_scheduled_job(scheduled_job):
        """禁用定时作业"""
        try:
            # 更新数据库状态
            scheduled_job.is_active = False
            scheduled_job.save()

            # 禁用Celery Beat任务
            if scheduled_job.periodic_task:
                scheduled_job.periodic_task.enabled = False
                scheduled_job.periodic_task.save()
                logger.info(f"禁用定时作业成功: {scheduled_job.name}")
            else:
                logger.warning(f"定时作业 {scheduled_job.name} 没有关联的Celery Beat任务")

        except Exception as e:
            logger.error(f"禁用定时作业失败: {scheduled_job.name} - {e}")
            raise
