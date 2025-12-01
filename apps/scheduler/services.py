"""
作业调度服务
"""
import logging
from datetime import datetime
from django.utils import timezone
from django.db import transaction
from django_celery_beat.models import PeriodicTask, CrontabSchedule
from celery import current_app
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
                # 创建定时作业（简化版，只包含调度配置）
                scheduled_job = ScheduledJob.objects.create(
                    name=name,
                    description=kwargs.get('description', ''),
                    execution_plan=execution_plan,
                    cron_expression=cron_expression,
                    timezone=kwargs.get('timezone', 'Asia/Shanghai'),
                    is_active=kwargs.get('is_active', False),
                    created_by=created_by
                )
                
                # 总是创建Celery Beat周期任务，根据is_active状态设置enabled属性
                SchedulerService._create_periodic_task(scheduled_job)
                
                logger.info(f"创建定时作业成功: {name}")
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
                
                # 更新Celery Beat任务
                if scheduled_job.periodic_task:
                    # 如果已有Celery任务，更新它
                    SchedulerService._update_periodic_task(scheduled_job)
                else:
                    # 如果没有Celery任务，创建一个
                    SchedulerService._create_periodic_task(scheduled_job)
                
                logger.info(f"更新定时作业成功: {scheduled_job.name}")
                return scheduled_job
                
        except Exception as e:
            logger.error(f"更新定时作业失败: {scheduled_job.name} - {e}")
            raise
    
    @staticmethod
    def delete_scheduled_job(scheduled_job):
        """删除定时作业"""
        try:
            with transaction.atomic():
                # 删除Celery Beat任务
                if scheduled_job.periodic_task:
                    SchedulerService._delete_periodic_task(scheduled_job)
                
                # 删除定时作业
                job_name = scheduled_job.name
                scheduled_job.delete()
                
                logger.info(f"删除定时作业成功: {job_name}")
                return True
                
        except Exception as e:
            logger.error(f"删除定时作业失败: {scheduled_job.name} - {e}")
            return False
    
    # 注意：移除了execute_scheduled_job_now方法
    # 定时作业不应该有"立即执行"功能
    # 如果需要立即执行，应该直接执行ExecutionPlan
    
    @staticmethod
    def _create_periodic_task(scheduled_job):
        """创建Celery Beat周期任务"""
        try:
            # 使用croniter验证Cron表达式
            cron_expression = scheduled_job.cron_expression.strip()

            # 验证cron表达式的有效性
            if not croniter.is_valid(cron_expression):
                raise ValueError(f"无效的Cron表达式: {cron_expression}")

            # 解析Cron表达式
            cron_parts = cron_expression.split()
            if len(cron_parts) != 5:
                raise ValueError(f"Cron表达式必须包含5个字段: {cron_expression}")

            minute, hour, day_of_month, month_of_year, day_of_week = cron_parts

            # 使用croniter验证表达式并获取下次执行时间
            try:
                cron = croniter(cron_expression, timezone.now())
                next_run = cron.get_next(datetime)
                logger.info(f"定时作业 {scheduled_job.name} 下次执行时间: {next_run}")
            except Exception as e:
                raise ValueError(f"Cron表达式解析失败: {cron_expression} - {e}")
            
            # 创建或获取CrontabSchedule
            schedule, created = CrontabSchedule.objects.get_or_create(
                minute=minute,
                hour=hour,
                day_of_month=day_of_month,
                month_of_year=month_of_year,
                day_of_week=day_of_week,
                timezone=scheduled_job.timezone
            )
            
            # 准备任务参数
            task_kwargs = {
                'scheduled_job_id': scheduled_job.id
            }
            
            # 创建周期任务
            periodic_task = PeriodicTask.objects.create(
                name=f"scheduled_job_{scheduled_job.id}_{scheduled_job.name}",
                task='scheduler.tasks.execute_scheduled_job',
                crontab=schedule,
                kwargs=task_kwargs,
                enabled=scheduled_job.is_active
            )
            
            # 关联到定时作业
            scheduled_job.periodic_task = periodic_task
            scheduled_job.save()
            
            logger.info(f"创建Celery Beat任务成功: {periodic_task.name}")
            
        except Exception as e:
            logger.error(f"创建Celery Beat任务失败: {scheduled_job.name} - {e}")
            raise
    
    @staticmethod
    def _update_periodic_task(scheduled_job):
        """更新Celery Beat周期任务"""
        try:
            if not scheduled_job.periodic_task:
                return
            
            # 使用croniter验证Cron表达式
            cron_expression = scheduled_job.cron_expression.strip()

            # 验证cron表达式的有效性
            if not croniter.is_valid(cron_expression):
                raise ValueError(f"无效的Cron表达式: {cron_expression}")

            # 解析Cron表达式
            cron_parts = cron_expression.split()
            if len(cron_parts) != 5:
                raise ValueError(f"Cron表达式必须包含5个字段: {cron_expression}")

            minute, hour, day_of_month, month_of_year, day_of_week = cron_parts

            # 使用croniter验证表达式并获取下次执行时间
            try:
                cron = croniter(cron_expression, timezone.now())
                next_run = cron.get_next(datetime)
                logger.info(f"更新定时作业 {scheduled_job.name} 下次执行时间: {next_run}")
            except Exception as e:
                raise ValueError(f"Cron表达式解析失败: {cron_expression} - {e}")
            
            # 创建或获取CrontabSchedule
            schedule, created = CrontabSchedule.objects.get_or_create(
                minute=minute,
                hour=hour,
                day_of_month=day_of_month,
                month_of_year=month_of_year,
                day_of_week=day_of_week,
                timezone=scheduled_job.timezone
            )
            
            # 更新周期任务
            periodic_task = scheduled_job.periodic_task
            periodic_task.name = f"scheduled_job_{scheduled_job.id}_{scheduled_job.name}"
            periodic_task.crontab = schedule
            periodic_task.enabled = scheduled_job.is_active
            periodic_task.save()
            
            logger.info(f"更新Celery Beat任务成功: {periodic_task.name}")
            
        except Exception as e:
            logger.error(f"更新Celery Beat任务失败: {scheduled_job.name} - {e}")
            raise
    
    @staticmethod
    def _delete_periodic_task(scheduled_job):
        """删除Celery Beat周期任务"""
        try:
            if scheduled_job.periodic_task:
                task_name = scheduled_job.periodic_task.name
                scheduled_job.periodic_task.delete()
                scheduled_job.periodic_task = None
                scheduled_job.save()
                
                logger.info(f"删除Celery Beat任务成功: {task_name}")
                
        except Exception as e:
            logger.error(f"删除Celery Beat任务失败: {scheduled_job.name} - {e}")
            raise

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
