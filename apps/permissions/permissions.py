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
    
    # 如果没有action属性，根据http方法判断
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

    def ensure_permission(
        self,
        allowed: bool,
        request,
        view,
        required_permissions,
        obj=None,
        reason: str = ''
    ) -> bool:
        if allowed:
            return True
        self._deny_permission(
            request=request,
            view=view,
            required_permissions=required_permissions,
            obj=obj,
            reason=reason
        )
        return False

    def _deny_permission(
        self,
        request,
        view,
        required_permissions,
        obj=None,
        reason: str = ''
    ) -> None:
        action = getattr(view, 'action', None) or get_view_action(view, request)
        permissions = required_permissions
        if isinstance(permissions, (set, tuple)):
            permissions = list(permissions)
        elif isinstance(permissions, str):
            permissions = [permissions]

        resource_type = None
        resource_id = None
        resource_name = ''

        if obj is not None:
            resource_id = getattr(obj, 'pk', None)
            resource_name = str(obj)
            if hasattr(obj, '_meta'):
                resource_type = obj._meta.model_name
        else:
            model = getattr(getattr(view, 'queryset', None), 'model', None)
            if model is None:
                try:
                    model = view.get_queryset().model
                except Exception:
                    model = None
            if model is not None:
                resource_type = model._meta.model_name

        detail = {
            'resource_type': resource_type,
            'resource_id': resource_id,
            'resource_name': resource_name,
            'action': action,
            'required_permissions': permissions,
            'reason': reason or 'permission_denied',
            'path': getattr(request, 'path', None),
            'method': getattr(request, 'method', None)
        }

        raise PermissionDenied(detail=detail)


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
            allowed = request.user.has_perm('permissions.create_jobs') or request.user.is_superuser
            return self.ensure_permission(
                allowed,
                request,
                view,
                'permissions.create_jobs',
                reason='create_requires_permission'
            )

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
        allowed = request.user.has_perm(permission, obj)
        return self.ensure_permission(allowed, request, view, permission, obj=obj)


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
            allowed = request.user.has_perm('permissions.create_jobs') or request.user.is_superuser
            return self.ensure_permission(
                allowed,
                request,
                view,
                'permissions.create_jobs',
                reason='create_requires_permission'
            )

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
        allowed = request.user.has_perm(permission, obj)
        return self.ensure_permission(allowed, request, view, permission, obj=obj)


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
            allowed = request.user.has_perm('permissions.manage_hosts') or request.user.is_superuser
            return self.ensure_permission(
                allowed,
                request,
                view,
                'permissions.manage_hosts',
                reason='create_requires_permission'
            )

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
        allowed = request.user.has_perm(permission, obj)
        return self.ensure_permission(allowed, request, view, permission, obj=obj)


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
            allowed = request.user.has_perm('permissions.execute_scripts') or request.user.is_superuser
            return self.ensure_permission(
                allowed,
                request,
                view,
                'permissions.execute_scripts',
                reason='create_requires_permission'
            )

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
        allowed = request.user.has_perm(permission, obj)
        return self.ensure_permission(allowed, request, view, permission, obj=obj)


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
            allowed = request.user.has_perm('permissions.create_jobs') or request.user.is_superuser
            return self.ensure_permission(
                allowed,
                request,
                view,
                'permissions.create_jobs',
                reason='create_requires_permission'
            )

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
        allowed = request.user.has_perm(permission, obj)
        return self.ensure_permission(allowed, request, view, permission, obj=obj)


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
            allowed = request.user.has_perm('permissions.manage_hosts') or request.user.is_superuser
            return self.ensure_permission(
                allowed,
                request,
                view,
                'permissions.manage_hosts',
                reason='create_requires_permission'
            )

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
        allowed = request.user.has_perm(permission, obj)
        return self.ensure_permission(allowed, request, view, permission, obj=obj)


class ExecutionRecordPermission(permissions.BasePermission, BasePermissionMixin):
    """执行记录权限

    对列表/查看放宽，对重做/重试/取消等敏感操作使用对象级权限：
    - 超级管理员始终允许
    - job_workflow：基于关联 ExecutionPlan / JobTemplate 的 execute_* 对象级权限
    - quick_script / quick_file_transfer：沿用全局脚本执行权限（execute_scripts）
    """

    def has_permission(self, request, view):
        if not request.user.is_authenticated:
            return False

        # 列表 / 详情本身允许，具体敏感操作在 has_object_permission 中判断
        return True

    def has_object_permission(self, request, view, obj):
        user = request.user
        if not user.is_authenticated:
            return False
        if user.is_superuser:
            return True

        from apps.executor.models import ExecutionRecord
        from apps.job_templates.models import ExecutionPlan, JobTemplate

        assert isinstance(obj, ExecutionRecord)
        action = getattr(view, "action", None)

        # 只读操作：查看详情 / 重试历史
        if action in ["retrieve", "retry_history"]:
            allowed = user.has_perm("executor.view_executionrecord", obj)
            return self.ensure_permission(
                allowed,
                request,
                view,
                "executor.view_executionrecord",
                obj=obj
            )

        # 敏感操作：重做、取消、步骤重试/忽略错误
        if action in ["retry", "cancel", "retry_step_inplace", "ignore_step_error"]:
            exec_type = obj.execution_type
            related = obj.related_object

            if exec_type == "job_workflow":
                if isinstance(related, ExecutionPlan):
                    allowed = user.has_perm("job_templates.execute_executionplan", related)
                    return self.ensure_permission(
                        allowed,
                        request,
                        view,
                        "job_templates.execute_executionplan",
                        obj=related,
                        reason='execute_plan_required'
                    )
                if isinstance(related, JobTemplate):
                    allowed = user.has_perm("job_templates.execute_jobtemplate", related)
                    return self.ensure_permission(
                        allowed,
                        request,
                        view,
                        "job_templates.execute_jobtemplate",
                        obj=related,
                        reason='execute_template_required'
                    )
                return self.ensure_permission(
                    False,
                    request,
                    view,
                    "job_templates.execute_jobtemplate",
                    obj=obj,
                    reason='related_resource_missing'
                )

            if exec_type in ["quick_script", "quick_file_transfer"]:
                # 快速脚本/文件传输目前仍使用全局脚本执行权限
                allowed = user.has_perm("permissions.execute_scripts")
                return self.ensure_permission(
                    allowed,
                    request,
                    view,
                    "permissions.execute_scripts",
                    obj=obj,
                    reason='execute_scripts_required'
                )

            # 其他执行类型暂不支持在执行记录界面发起敏感操作
            return self.ensure_permission(
                False,
                request,
                view,
                "executor.view_executionrecord",
                obj=obj,
                reason='unsupported_execution_type'
            )

        # 其他未明确定义的操作，默认按“查看执行记录”处理
        allowed = user.has_perm("executor.view_executionrecord", obj)
        return self.ensure_permission(
            allowed,
            request,
            view,
            "executor.view_executionrecord",
            obj=obj
        )

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
