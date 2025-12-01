"""
作业模板信号处理
基于内容变更检测的同步机制
"""
from django.db.models.signals import post_save, post_delete, m2m_changed
from django.dispatch import receiver
from .models import JobTemplate, JobStep, ExecutionPlan, PlanStep
import logging

logger = logging.getLogger(__name__)


@receiver(post_save, sender=JobStep)
def handle_job_step_change(sender, instance, created, **kwargs):
    """当作业步骤发生变化时，标记相关执行方案为未同步"""
    try:
        # 标记所有基于此模板的执行方案为未同步
        instance.template.mark_plans_as_unsynced()

        if created:
            logger.info(f'新增作业步骤: {instance.name}，已标记相关执行方案为未同步')
        else:
            logger.info(f'修改作业步骤: {instance.name}，已标记相关执行方案为未同步')

    except Exception as e:
        logger.error(f'处理作业步骤变化信号失败: {str(e)}')


@receiver(post_delete, sender=JobStep)
def handle_job_step_delete(sender, instance, **kwargs):
    """当作业步骤被删除时，标记相关执行方案为未同步"""
    try:
        # 标记所有基于此模板的执行方案为未同步
        instance.template.mark_plans_as_unsynced()
        logger.info(f'删除作业步骤: {instance.name}，已标记相关执行方案为未同步')

    except Exception as e:
        logger.error(f'处理作业步骤删除信号失败: {str(e)}')


@receiver(m2m_changed, sender=JobStep.target_hosts.through)
@receiver(m2m_changed, sender=JobStep.target_groups.through)
def handle_job_step_targets_change(sender, instance, action, **kwargs):
    """当作业步骤的目标主机或分组发生变化时，标记相关执行方案为未同步"""
    if action in ['post_add', 'post_remove', 'post_clear']:
        try:
            instance.template.mark_plans_as_unsynced()
            logger.info(f'作业步骤 {instance.name} 的目标配置已变化，已标记相关执行方案为未同步')

        except Exception as e:
            logger.error(f'处理作业步骤目标变化信号失败: {str(e)}')


@receiver(post_save, sender=JobTemplate)
def handle_job_template_change(sender, instance, created, **kwargs):
    """当作业模板发生变化时的处理"""
    if not created:  # 只处理更新，不处理创建
        try:
            # 标记所有执行方案为未同步
            instance.mark_plans_as_unsynced()
            logger.info(f'作业模板 {instance.name} 已更新，已标记相关执行方案为未同步')

        except Exception as e:
            logger.error(f'处理作业模板变化信号失败: {str(e)}')
