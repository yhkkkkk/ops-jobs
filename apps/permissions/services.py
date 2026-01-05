"""
权限管理服务 - 基于 Guardian 对象级权限
"""
import logging
from django.contrib.auth.models import User, Group
from django.contrib.contenttypes.models import ContentType
from guardian.shortcuts import get_objects_for_user, get_perms, assign_perm, remove_perm
from guardian.models import UserObjectPermission, GroupObjectPermission
from .models import AuditLog

logger = logging.getLogger(__name__)


class AuditService:
    """审计服务 - 记录详细的操作日志"""
    
    @staticmethod
    def log_action(user, action, description, ip_address, success=True,
                   resource_type=None, resource_id=None, resource_name='',
                   user_agent='', error_message='', extra_data=None):
        """记录操作日志"""
        try:
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
                extra_data=extra_data or {}
            )
            logger.info(f"记录审计日志: {user.username} - {action} - {description}")
        except Exception as e:
            logger.error(f"记录审计日志失败: {e}")
    
    @staticmethod
    def log_login(user, ip_address, user_agent='', success=True, error_message=''):
        """记录登录日志"""
        AuditService.log_action(
            user=user,
            action='login',
            description=f"用户 {user.username} 登录",
            ip_address=ip_address,
            user_agent=user_agent,
            success=success,
            error_message=error_message
        )
    
    @staticmethod
    def log_logout(user, ip_address, user_agent=''):
        """记录登出日志"""
        AuditService.log_action(
            user=user,
            action='logout',
            description=f"用户 {user.username} 登出",
            ip_address=ip_address,
            user_agent=user_agent,
            success=True
        )
    
    @staticmethod
    def log_script_execution(user, hosts, script_content, ip_address, success=True, error_message=''):
        """记录脚本执行日志"""
        AuditService.log_action(
            user=user,
            action='execute_script',
            description=f"在 {len(hosts)} 台主机上执行脚本",
            ip_address=ip_address,
            success=success,
            error_message=error_message,
            extra_data={
                'host_count': len(hosts),
                'host_names': [h.name for h in hosts],
                'script_preview': script_content[:200] + '...' if len(script_content) > 200 else script_content
            }
        )
    
    @staticmethod
    def log_file_transfer(user, source_host, target_hosts, file_path, ip_address, success=True, error_message=''):
        """记录文件传输日志"""
        AuditService.log_action(
            user=user,
            action='transfer_file',
            description=f"从 {source_host.name} 传输文件到 {len(target_hosts)} 台主机",
            ip_address=ip_address,
            success=success,
            error_message=error_message,
            extra_data={
                'source_host': source_host.name,
                'target_host_count': len(target_hosts),
                'file_path': file_path,
            }
        )
    
    @staticmethod
    def log_job_execution(user, job, ip_address, success=True, error_message=''):
        """记录作业执行日志"""
        AuditService.log_action(
            user=user,
            action='execute_job',
            description=f"执行作业: {job.name}",
            ip_address=ip_address,
            success=success,
            error_message=error_message,
            extra_data={
                'job_id': job.id,
                'job_name': job.name,
                'job_type': getattr(job, 'job_type', 'unknown')
            }
        )
    
    @staticmethod
    def log_permission_change(user, target_user, action, ip_address, success=True, error_message=''):
        """记录权限变更日志"""
        AuditService.log_action(
            user=user,
            action=f'permission_{action}',
            description=f"为用户 {target_user.username} {action}权限",
            ip_address=ip_address,
            success=success,
            error_message=error_message,
            extra_data={
                'target_user_id': target_user.id,
                'target_username': target_user.username,
                'permission_action': action
            }
        )
    
    @staticmethod
    def get_user_audit_logs(user, limit=100):
        """获取用户审计日志"""
        return AuditLog.objects.filter(user=user).order_by('-created_at')[:limit]
    
    @staticmethod
    def get_system_audit_logs(limit=1000):
        """获取系统审计日志"""
        return AuditLog.objects.all().order_by('-created_at')[:limit]
    
    @staticmethod
    def get_audit_statistics(days=30):
        """获取审计统计信息"""
        return AuditLog.get_system_stats(days)
    
    @staticmethod
    def get_user_action_summary(user, days=30):
        """获取用户操作摘要"""
        return AuditLog.get_user_actions(user, days)


class GroupPermissionService:
    """用户组权限管理服务"""
    
    @staticmethod
    def create_default_groups():
        """创建默认用户组"""
        default_groups = {
            'admin': '系统管理员',
            'operator': '运维工程师', 
            'developer': '开发工程师',
            'viewer': '只读用户'
        }
        
        created_groups = []
        for group_name, description in default_groups.items():
            group, created = Group.objects.get_or_create(
                name=group_name,
                defaults={'name': group_name}
            )
            if created:
                logger.info(f"创建用户组: {group_name}")
            created_groups.append(group)
        
        return created_groups
    
    @staticmethod
    def assign_user_to_group(user, group_name):
        """将用户分配到指定组"""
        try:
            group = Group.objects.get(name=group_name)
            user.groups.add(group)
            logger.info(f"将用户 {user.username} 分配到组 {group_name}")
            return True
        except Group.DoesNotExist:
            logger.error(f"用户组 {group_name} 不存在")
            return False
        except Exception as e:
            logger.error(f"分配用户到组失败: {e}")
            return False
    
    @staticmethod
    def remove_user_from_group(user, group_name):
        """从指定组中移除用户"""
        try:
            group = Group.objects.get(name=group_name)
            user.groups.remove(group)
            logger.info(f"从组 {group_name} 中移除用户 {user.username}")
            return True
        except Group.DoesNotExist:
            logger.error(f"用户组 {group_name} 不存在")
            return False
        except Exception as e:
            logger.error(f"从组中移除用户失败: {e}")
            return False
    
    @staticmethod
    def get_group_users(group_name):
        """获取指定组的所有用户"""
        try:
            group = Group.objects.get(name=group_name)
            return group.user_set.all()
        except Group.DoesNotExist:
            return []
    
    @staticmethod
    def get_user_groups(user):
        """获取用户所属的所有组"""
        return user.groups.all()
