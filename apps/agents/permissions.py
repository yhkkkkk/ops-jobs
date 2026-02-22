"""
Agent 相关权限类
"""
from apps.permissions.permissions import BasePermissionMixin


class AgentPermission(BasePermissionMixin):
    """
    Agent 权限：
    - 列表 / 详情默认允许（在对象级再细分）
    - 其他敏感操作需要具备对应的模型/对象级权限
    """

    def has_permission(self, request, view):
        if not request.user.is_authenticated:
            return False
        # list/retrieve 只做登录校验，具体权限在对象级控制
        if getattr(view, "action", None) in ["list", "retrieve"]:
            return True
        return True

    def has_object_permission(self, request, view, obj):
        user = request.user
        if not user.is_authenticated:
            return False

        action = getattr(view, "action", None)

        if action == "retrieve":
            allowed = user.has_perm("agents.view_agent", obj) or user.is_superuser
            return self.ensure_permission(allowed, request, view, "agents.view_agent", obj=obj)
        if action == "issue_token":
            allowed = user.has_perm("agents.issue_agent_token", obj) or user.is_superuser
            return self.ensure_permission(allowed, request, view, "agents.issue_agent_token", obj=obj)
        if action == "revoke_token":
            allowed = user.has_perm("agents.revoke_agent_token", obj) or user.is_superuser
            return self.ensure_permission(allowed, request, view, "agents.revoke_agent_token", obj=obj)
        if action == "enable_agent":
            allowed = user.has_perm("agents.enable_agent", obj) or user.is_superuser
            return self.ensure_permission(allowed, request, view, "agents.enable_agent", obj=obj)
        if action == "disable_agent":
            allowed = user.has_perm("agents.disable_agent", obj) or user.is_superuser
            return self.ensure_permission(allowed, request, view, "agents.disable_agent", obj=obj)
        if action == "update_agent_server":
            allowed = user.has_perm("agents.change_agent", obj) or user.is_superuser
            return self.ensure_permission(allowed, request, view, "agents.change_agent", obj=obj)

        # 其他情况默认按查看权限处理
        allowed = user.has_perm("agents.view_agent", obj) or user.is_superuser
        return self.ensure_permission(allowed, request, view, "agents.view_agent", obj=obj)


class AgentServerPermission(BasePermissionMixin):
    """Agent-Server 配置权限"""

    def has_permission(self, request, view):
        if not request.user.is_authenticated:
            return False

        action = getattr(view, "action", None)
        if action in ["list", "retrieve"]:
            allowed = request.user.has_perm("agents.view_agentserver") or request.user.is_superuser
            return self.ensure_permission(allowed, request, view, "agents.view_agentserver")
        if action in ["create"]:
            allowed = request.user.has_perm("agents.add_agentserver") or request.user.is_superuser
            return self.ensure_permission(allowed, request, view, "agents.add_agentserver")
        if action in ["update", "partial_update"]:
            allowed = request.user.has_perm("agents.change_agentserver") or request.user.is_superuser
            return self.ensure_permission(allowed, request, view, "agents.change_agentserver")
        if action in ["destroy"]:
            allowed = request.user.has_perm("agents.delete_agentserver") or request.user.is_superuser
            return self.ensure_permission(allowed, request, view, "agents.delete_agentserver")
        return True

    def has_object_permission(self, request, view, obj):
        # 对象级校验与 model 权限一致
        return self.has_permission(request, view)

