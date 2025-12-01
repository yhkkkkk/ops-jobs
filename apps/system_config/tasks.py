"""
系统配置相关定时任务
"""
import logging
from celery import shared_task
from django.utils import timezone
from datetime import timedelta
from .models import ConfigManager

logger = logging.getLogger(__name__)


@shared_task
def cleanup_old_execution_logs():
    """清理过期的执行记录日志"""
    try:
        # 获取系统配置的日志保留天数
        cleanup_days = ConfigManager.get('task.cleanup_days', 60)
        cutoff_date = timezone.now() - timedelta(days=cleanup_days)
        
        from apps.executor.models import ExecutionRecord
        
        # 删除过期的执行记录
        deleted_count = ExecutionRecord.objects.filter(
            created_at__lt=cutoff_date,
            status__in=['completed', 'failed', 'cancelled']
        ).delete()[0]
        
        logger.info(f"清理过期执行记录完成，删除了 {deleted_count} 条记录，保留天数: {cleanup_days}")
        
        return {
            'success': True,
            'deleted_count': deleted_count,
            'cleanup_days': cleanup_days,
            'cutoff_date': cutoff_date.isoformat()
        }
        
    except Exception as e:
        logger.error(f"清理过期执行记录失败: {e}")
        return {
            'success': False,
            'error': str(e)
        }


@shared_task
def check_system_health():
    """检查系统健康状态"""
    try:
        from apps.executor.models import ExecutionRecord
        from apps.hosts.models import Host
        
        # 获取系统配置
        max_concurrent_jobs = ConfigManager.get('task.max_concurrent_jobs', 10)
        
        # 检查当前运行的任务数
        running_jobs_count = ExecutionRecord.objects.filter(
            status__in=['pending', 'running']
        ).count()
        
        # 检查主机状态
        total_hosts = Host.objects.count()
        online_hosts = Host.objects.filter(is_online=True).count()
        
        # 检查系统负载
        health_status = {
            'timestamp': timezone.now().isoformat(),
            'running_jobs_count': running_jobs_count,
            'max_concurrent_jobs': max_concurrent_jobs,
            'concurrent_jobs_usage': (running_jobs_count / max_concurrent_jobs) * 100 if max_concurrent_jobs > 0 else 0,
            'total_hosts': total_hosts,
            'online_hosts': online_hosts,
            'hosts_online_rate': (online_hosts / total_hosts) * 100 if total_hosts > 0 else 0,
            'status': 'healthy'
        }
        
        # 判断系统状态
        if running_jobs_count >= max_concurrent_jobs:
            health_status['status'] = 'warning'
            health_status['message'] = f'当前运行任务数({running_jobs_count})已达到最大并发限制({max_concurrent_jobs})'
        
        if online_hosts / total_hosts < 0.8 if total_hosts > 0 else False:
            health_status['status'] = 'warning'
            health_status['message'] = f'主机在线率较低: {online_hosts}/{total_hosts}'
        
        logger.info(f"系统健康检查完成: {health_status['status']}")
        
        return health_status
        
    except Exception as e:
        logger.error(f"系统健康检查失败: {e}")
        return {
            'success': False,
            'error': str(e),
            'timestamp': timezone.now().isoformat(),
            'status': 'error'
        }


@shared_task
def send_system_notifications():
    """发送系统通知"""
    try:
        # 获取通知配置
        email_enabled = ConfigManager.get('notification.email_enabled', False)
        webhook_enabled = ConfigManager.get('notification.webhook_enabled', False)
        notification_levels = ConfigManager.get('notification.levels', ['error', 'warning'])
        email_recipients = ConfigManager.get('notification.email_recipients', [])
        
        notifications_sent = 0
        
        # 检查系统健康状态
        health_status = check_system_health()
        
        if health_status.get('status') in notification_levels:
            # 发送邮件通知
            if email_enabled and email_recipients:
                # 这里可以集成邮件发送服务
                logger.info(f"发送系统状态邮件通知到: {email_recipients}")
                notifications_sent += 1
            
            # 发送Webhook通知
            if webhook_enabled:
                # 这里可以集成Webhook服务
                logger.info("发送系统状态Webhook通知")
                notifications_sent += 1
        
        logger.info(f"系统通知发送完成，发送了 {notifications_sent} 条通知")
        
        return {
            'success': True,
            'notifications_sent': notifications_sent,
            'health_status': health_status
        }
        
    except Exception as e:
        logger.error(f"发送系统通知失败: {e}")
        return {
            'success': False,
            'error': str(e)
        }
