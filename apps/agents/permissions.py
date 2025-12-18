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
            return user.has_perm("agents.view_agent", obj) or user.is_superuser
        if action == "issue_token":
            return user.has_perm("agents.issue_agent_token", obj) or user.is_superuser
        if action == "revoke_token":
            return user.has_perm("agents.revoke_agent_token", obj) or user.is_superuser
        if action == "enable_agent":
            return user.has_perm("agents.enable_agent", obj) or user.is_superuser
        if action == "disable_agent":
            return user.has_perm("agents.disable_agent", obj) or user.is_superuser

        # 其他情况默认按查看权限处理
        return user.has_perm("agents.view_agent", obj) or user.is_superuser


