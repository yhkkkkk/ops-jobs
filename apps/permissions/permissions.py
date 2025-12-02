"""
权限系统模块

提供基于Django Guardian的对象级权限控制，支持细粒度的权限管理。
"""

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.contrib.contenttypes.models import ContentType
from django.db import transaction
from django.db.models import Q
from django.utils.translation import gettext_lazy as _
from rest_framework import permissions
from rest_framework.exceptions import PermissionDenied

User = get_user_model()


def get_view_action(view, request):
    """获取视图操作类型，兼容 ViewSet 和 APIView"""
    # 优先使用 ViewSet 的 action 属性
    action = getattr(view, 'action', None)
    
    # 如果没有 action 属性，根据 HTTP 方法判断
    if action is None:
        if request.method == 'GET':
            action = 'list'
        elif request.method == 'POST':
            action = 'create'
        elif request.method in ['PUT', 'PATCH']:
            action = 'update'
        elif request.method == 'DELETE':
            action = 'destroy'
        else:
            action = 'unknown'
    
    return action


class BasePermissionMixin:
    """权限基类混入，提供通用权限检查方法"""

    def check_global_permission(self, user, permission_name):
        """检查全局权限"""
        return user.has_perm(permission_name) or user.is_superuser

    def check_object_permission(self, user, permission_name, obj):
        """检查对象级权限"""
        return user.has_perm(permission_name, obj)

    def get_permission_name(self, action, model_name):
        """获取权限名称"""
        if action == 'retrieve':
            return f'view_{model_name}'
        elif action in ['update', 'partial_update']:
            return f'change_{model_name}'
        elif action == 'destroy':
            return f'delete_{model_name}'
        else:
            return f'{action}_{model_name}'


class ScheduledJobPermission(permissions.BasePermission, BasePermissionMixin):
    """调度作业权限 - 使用Guardian对象级权限"""

    def has_permission(self, request, view):
        """检查是否有访问权限"""
        if not request.user.is_authenticated:
            return False

        # 对于列表操作，允许访问（具体权限在has_object_permission中检查）
        if view.action == 'list':
            return True
        elif view.action == 'create':
            # 创建权限检查全局权限
            return request.user.has_perm('permissions.create_jobs') or request.user.is_superuser

        return True  # 其他操作在has_object_permission中检查

    def has_object_permission(self, request, view, obj):
        """检查对象级权限"""
        if not request.user.is_authenticated:
            return False

        # 构建权限名称
        if view.action == 'retrieve':
            permission = 'view_scheduledjob'
        elif view.action in ['update', 'partial_update']:
            permission = 'change_scheduledjob'
        elif view.action == 'destroy':
            permission = 'delete_scheduledjob'
        else:
            permission = f'{view.action}_scheduledjob'

        # 使用 Guardian 检查对象级权限
        return request.user.has_perm(permission, obj)


class JobTemplatePermission(permissions.BasePermission, BasePermissionMixin):
    """作业模板权限 - 使用Guardian对象级权限"""

    def has_permission(self, request, view):
        """检查是否有访问权限"""
        if not request.user.is_authenticated:
            return False

        # 对于列表操作，允许访问（具体权限在has_object_permission中检查）
        if view.action == 'list':
            return True
        elif view.action == 'create':
            # 创建权限检查全局权限
            return request.user.has_perm('permissions.create_jobs') or request.user.is_superuser

        return True  # 其他操作在has_object_permission中检查

    def has_object_permission(self, request, view, obj):
        """检查对象级权限"""
        if not request.user.is_authenticated:
            return False

        # 构建权限名称
        if view.action == 'retrieve':
            permission = 'view_jobtemplate'
        elif view.action in ['update', 'partial_update']:
            permission = 'change_jobtemplate'
        elif view.action == 'destroy':
            permission = 'delete_jobtemplate'
        else:
            permission = f'{view.action}_jobtemplate'

        # 使用 Guardian 检查对象级权限
        return request.user.has_perm(permission, obj)


class HostManagementPermission(permissions.BasePermission, BasePermissionMixin):
    """主机管理权限 - 使用Guardian对象级权限"""

    def has_permission(self, request, view):
        """检查是否有访问权限"""
        if not request.user.is_authenticated:
            return False

        # 对于列表操作，允许访问（具体权限在has_object_permission中检查）
        if view.action == 'list':
            return True
        elif view.action == 'create':
            # 创建权限检查全局权限
            return request.user.has_perm('permissions.manage_hosts') or request.user.is_superuser

        return True  # 其他操作在has_object_permission中检查

    def has_object_permission(self, request, view, obj):
        """检查对象级权限"""
        if not request.user.is_authenticated:
            return False

        # 构建权限名称
        if view.action == 'retrieve':
            permission = 'view_host'
        elif view.action in ['update', 'partial_update']:
            permission = 'change_host'
        elif view.action == 'destroy':
            permission = 'delete_host'
        else:
            permission = f'{view.action}_host'

        # 使用 Guardian 检查对象级权限
        return request.user.has_perm(permission, obj)


class ScriptExecutionPermission(permissions.BasePermission, BasePermissionMixin):
    """脚本执行权限 - 使用Guardian对象级权限"""

    def has_permission(self, request, view):
        """检查是否有访问权限"""
        if not request.user.is_authenticated:
            return False

        # 获取操作类型
        action = get_view_action(view, request)

        # 对于列表操作，允许访问（具体权限在has_object_permission中检查）
        if action == 'list':
            return True
        elif action == 'create':
            # 创建权限检查全局权限
            return request.user.has_perm('permissions.execute_scripts') or request.user.is_superuser

        return True  # 其他操作在has_object_permission中检查

    def has_object_permission(self, request, view, obj):
        """检查对象级权限"""
        if not request.user.is_authenticated:
            return False

        # 获取操作类型
        action = get_view_action(view, request)

        # 构建权限名称
        if action == 'retrieve':
            permission = 'view_scripttemplate'
        elif action in ['update', 'partial_update']:
            permission = 'change_scripttemplate'
        elif action == 'destroy':
            permission = 'delete_scripttemplate'
        else:
            permission = f'{action}_scripttemplate'

        # 使用 Guardian 检查对象级权限
        return request.user.has_perm(permission, obj)


class ExecutionPlanPermission(permissions.BasePermission, BasePermissionMixin):
    """执行计划权限 - 使用Guardian对象级权限"""

    def has_permission(self, request, view):
        """检查是否有访问权限"""
        if not request.user.is_authenticated:
            return False

        # 对于列表操作，允许访问（具体权限在has_object_permission中检查）
        if view.action == 'list':
            return True
        elif view.action == 'create':
            # 创建权限检查全局权限
            return request.user.has_perm('permissions.create_jobs') or request.user.is_superuser

        return True  # 其他操作在has_object_permission中检查

    def has_object_permission(self, request, view, obj):
        """检查对象级权限"""
        if not request.user.is_authenticated:
            return False

        # 构建权限名称
        if view.action == 'retrieve':
            permission = 'view_executionplan'
        elif view.action in ['update', 'partial_update']:
            permission = 'change_executionplan'
        elif view.action == 'destroy':
            permission = 'delete_executionplan'
        else:
            permission = f'{view.action}_executionplan'

        # 使用 Guardian 检查对象级权限
        return request.user.has_perm(permission, obj)


class ServerAccountPermission(permissions.BasePermission, BasePermissionMixin):
    """服务器账号权限 - 使用Guardian对象级权限"""

    def has_permission(self, request, view):
        """检查是否有访问权限"""
        if not request.user.is_authenticated:
            return False

        # 对于列表操作，允许访问（具体权限在has_object_permission中检查）
        if view.action == 'list':
            return True
        elif view.action == 'create':
            # 创建权限检查全局权限
            return request.user.has_perm('permissions.manage_hosts') or request.user.is_superuser

        return True  # 其他操作在has_object_permission中检查

    def has_object_permission(self, request, view, obj):
        """检查对象级权限"""
        if not request.user.is_authenticated:
            return False

        # 构建权限名称
        if view.action == 'retrieve':
            permission = 'view_serveraccount'
        elif view.action in ['update', 'partial_update']:
            permission = 'change_serveraccount'
        elif view.action == 'destroy':
            permission = 'delete_serveraccount'
        else:
            permission = f'{view.action}_serveraccount'

        # 使用 Guardian 检查对象级权限
        return request.user.has_perm(permission, obj)

class IsSuperUser(permissions.BasePermission):
    """
    只允许超级用户访问
    """

    def has_permission(self, request, view):
        return bool(
            request.user and
            request.user.is_authenticated and
            request.user.is_superuser
        )
