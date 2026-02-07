"""
统一的审计日志服务
"""
import logging
from typing import Optional, Dict, Any
from django.contrib.auth.models import User
from django.contrib.contenttypes.models import ContentType
from django.http import HttpRequest
from rest_framework.request import Request

logger = logging.getLogger(__name__)


class AuditLogService:
    """统一的审计日志服务"""
    
    @staticmethod
    def get_client_ip(request: HttpRequest) -> str:
        """获取客户端IP地址"""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0].strip()
        else:
            ip = request.META.get('REMOTE_ADDR', '127.0.0.1')
        return ip
    
    @staticmethod
    def get_user_agent(request: HttpRequest) -> str:
        """获取用户代理信息"""
        return request.META.get('HTTP_USER_AGENT', '')
    
    @staticmethod
    def log_action(
        user: User,
        action: str,
        description: str,
        request: Optional[HttpRequest] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        success: bool = True,
        resource_type: Optional[ContentType] = None,
        resource_id: Optional[int] = None,
        resource_name: str = '',
        error_message: str = '',
        extra_data: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        记录操作日志
        
        Args:
            user: 操作用户
            action: 操作类型
            description: 操作描述
            request: HTTP请求对象（可选）
            ip_address: IP地址（可选，如果提供request会自动获取）
            user_agent: 用户代理（可选，如果提供request会自动获取）
            success: 操作是否成功
            resource_type: 资源类型
            resource_id: 资源ID
            resource_name: 资源名称
            error_message: 错误信息
            extra_data: 额外数据
        """
        try:
            # 延迟导入避免循环导入
            from apps.permissions.models import AuditLog
            
            # 从request中获取IP和用户代理信息
            if request:
                if not ip_address:
                    ip_address = AuditLogService.get_client_ip(request)
                if not user_agent:
                    user_agent = AuditLogService.get_user_agent(request)
            
            # 默认值
            if not ip_address:
                ip_address = '127.0.0.1'
            if not user_agent:
                user_agent = ''
            if extra_data is None:
                extra_data = {}
            
            # 创建审计日志
            AuditLog.objects.create(
                user=user,
                action=action,
                resource_type=resource_type,
                resource_id=resource_id,
                resource_name=resource_name,
                description=description,
                ip_address=ip_address,
                user_agent=user_agent,
                success=success,
                error_message=error_message,
                extra_data=extra_data
            )
            
            logger.info(f"Audit log created: {user.username} - {action} - {description}")
            
        except Exception as e:
            logger.error(f"Failed to create audit log: {e}")
    
    @staticmethod
    def log_login(user: User, request: HttpRequest, success: bool = True, error_message: str = '') -> None:
        """记录登录日志"""
        AuditLogService.log_action(
            user=user,
            action='login',
            description='用户登录' if success else '用户登录失败',
            request=request,
            success=success,
            error_message=error_message
        )
    
    @staticmethod
    def log_logout(user: User, request: HttpRequest) -> None:
        """记录登出日志"""
        AuditLogService.log_action(
            user=user,
            action='logout',
            description='用户登出',
            request=request
        )
    
    @staticmethod
    def log_create(user: User, resource_obj: Any, request: Optional[HttpRequest] = None) -> None:
        """记录创建操作"""
        content_type = ContentType.objects.get_for_model(resource_obj)
        AuditLogService.log_action(
            user=user,
            action='create',
            description=f'创建{content_type.name}: {str(resource_obj)}',
            request=request,
            resource_type=content_type,
            resource_id=resource_obj.pk,
            resource_name=str(resource_obj)
        )
    
    @staticmethod
    def log_update(user: User, resource_obj: Any, request: Optional[HttpRequest] = None) -> None:
        """记录更新操作"""
        content_type = ContentType.objects.get_for_model(resource_obj)
        AuditLogService.log_action(
            user=user,
            action='update',
            description=f'更新{content_type.name}: {str(resource_obj)}',
            request=request,
            resource_type=content_type,
            resource_id=resource_obj.pk,
            resource_name=str(resource_obj)
        )
    
    @staticmethod
    def log_delete(user: User, resource_obj: Any, request: Optional[HttpRequest] = None) -> None:
        """记录删除操作"""
        content_type = ContentType.objects.get_for_model(resource_obj)
        AuditLogService.log_action(
            user=user,
            action='delete',
            description=f'删除{content_type.name}: {str(resource_obj)}',
            request=request,
            resource_type=content_type,
            resource_id=resource_obj.pk,
            resource_name=str(resource_obj)
        )
    
    @staticmethod
    def log_execute(
        user: User, 
        action_type: str, 
        description: str, 
        request: Optional[HttpRequest] = None,
        success: bool = True,
        error_message: str = '',
        extra_data: Optional[Dict[str, Any]] = None
    ) -> None:
        """记录执行操作"""
        AuditLogService.log_action(
            user=user,
            action=action_type,
            description=description,
            request=request,
            success=success,
            error_message=error_message,
            extra_data=extra_data
        )
