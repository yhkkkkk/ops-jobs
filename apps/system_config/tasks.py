"""
系统配置相关定时任务
"""
import logging
import requests
import json
from django.utils import timezone
from datetime import timedelta
from .models import ConfigManager

logger = logging.getLogger(__name__)


def send_dingtalk_notification(webhook: str, keyword: str, message: str) -> bool:
    """发送钉钉通知"""
    if not webhook:
        return False
    
    try:
        # 如果设置了关键词，需要在消息前面加上关键词
        if keyword:
            message = f"{keyword}\n{message}"
        
        payload = {
            'msgtype': 'text',
            'text': {'content': message}
        }
        
        response = requests.post(webhook, json=payload, timeout=10)
        return response.status_code == 200
    except Exception as e:
        logger.error(f"发送钉钉通知失败: {e}")
        return False


def send_feishu_notification(webhook: str, keyword: str, message: str) -> bool:
    """发送飞书通知"""
    if not webhook:
        return False
    
    try:
        # 如果设置了关键词，需要在消息前面加上关键词
        if keyword:
            message = f"{keyword}\n{message}"
        
        payload = {
            'msg_type': 'text',
            'content': json.dumps({'text': message})
        }
        
        response = requests.post(webhook, json=payload, timeout=10)
        return response.status_code == 200
    except Exception as e:
        logger.error(f"发送飞书通知失败: {e}")
        return False


def send_wechatwork_notification(webhook: str, keyword: str, message: str) -> bool:
    """发送企业微信通知"""
    if not webhook:
        return False
    
    try:
        # 如果设置了关键词，需要在消息前面加上关键词
        if keyword:
            message = f"{keyword}\n{message}"
        
        payload = {
            'msgtype': 'text',
            'text': {'content': message}
        }
        
        response = requests.post(webhook, json=payload, timeout=10)
        return response.status_code == 200
    except Exception as e:
        logger.error(f"发送企业微信通知失败: {e}")
        return False


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
            status__in=['success', 'failed', 'cancelled', 'timeout']
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


def check_system_health():
    """检查系统健康状态"""
    try:
        from apps.hosts.models import Host
        
        # 检查主机状态
        total_hosts = Host.objects.count()
        online_hosts = Host.objects.filter(status='online').count()
        
        # 检查系统负载
        health_status = {
            'timestamp': timezone.now().isoformat(),
            'total_hosts': total_hosts,
            'online_hosts': online_hosts,
            'hosts_online_rate': (online_hosts / total_hosts) * 100 if total_hosts > 0 else 0,
            'status': 'healthy'
        }
        
        # 判断系统状态
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


def send_system_notifications():
    """发送系统通知"""
    try:
        # 获取通知配置
        notification_levels = ConfigManager.get('notification.levels', ['error', 'warning'])
        
        # 钉钉配置
        dingtalk_enabled = ConfigManager.get('notification.dingtalk_enabled', False)
        dingtalk_webhook = ConfigManager.get('notification.dingtalk_webhook', '')
        dingtalk_keyword = ConfigManager.get('notification.dingtalk_keyword', '')
        
        # 飞书配置
        feishu_enabled = ConfigManager.get('notification.feishu_enabled', False)
        feishu_webhook = ConfigManager.get('notification.feishu_webhook', '')
        feishu_keyword = ConfigManager.get('notification.feishu_keyword', '')
        
        # 企业微信配置
        wechatwork_enabled = ConfigManager.get('notification.wechatwork_enabled', False)
        wechatwork_webhook = ConfigManager.get('notification.wechatwork_webhook', '')
        wechatwork_keyword = ConfigManager.get('notification.wechatwork_keyword', '')
        
        notifications_sent = 0
        
        # 检查系统健康状态
        health_status = check_system_health()
        
        if health_status.get('status') in notification_levels:
            status_emoji = '⚠️' if health_status.get('status') == 'warning' else '🚨'
            message = f"{status_emoji} 系统状态: {health_status.get('status')}\n"
            message += f"主机在线率: {health_status.get('hosts_online_rate', 0):.1f}%\n"
            message += f"在线主机: {health_status.get('online_hosts', 0)}/{health_status.get('total_hosts', 0)}\n"
            if health_status.get('message'):
                message += f"详情: {health_status.get('message')}"
            
            # 发送钉钉通知
            if dingtalk_enabled:
                if send_dingtalk_notification(dingtalk_webhook, dingtalk_keyword, message):
                    notifications_sent += 1
                    logger.info("发送钉钉系统状态通知成功")
            
            # 发送飞书通知
            if feishu_enabled:
                if send_feishu_notification(feishu_webhook, feishu_keyword, message):
                    notifications_sent += 1
                    logger.info("发送飞书系统状态通知成功")
            
            # 发送企业微信通知
            if wechatwork_enabled:
                if send_wechatwork_notification(wechatwork_webhook, wechatwork_keyword, message):
                    notifications_sent += 1
                    logger.info("发送企业微信系统状态通知成功")
        
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
