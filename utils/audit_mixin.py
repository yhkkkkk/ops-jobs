"""
审计日志通用 Mixin
"""
from django.contrib.contenttypes.models import ContentType
from utils.audit_service import AuditLogService


class AuditLogMixin:
    """提供审计日志快捷方法的 Mixin"""

    def _get_audit_user(self):
        user = getattr(self.request, 'user', None)
        if user and getattr(user, 'is_authenticated', False):
            return user
        return None

    def audit_log_create(self, obj):
        user = self._get_audit_user()
        if not user or obj is None:
            return
        AuditLogService.log_create(user=user, resource_obj=obj, request=self.request)

    def audit_log_update(self, obj):
        user = self._get_audit_user()
        if not user or obj is None:
            return
        AuditLogService.log_update(user=user, resource_obj=obj, request=self.request)

    def audit_log_delete(self, obj):
        user = self._get_audit_user()
        if not user or obj is None:
            return
        AuditLogService.log_delete(user=user, resource_obj=obj, request=self.request)

    def audit_log_action(
        self,
        action,
        description,
        success=True,
        resource_obj=None,
        resource_id=None,
        resource_name='',
        error_message='',
        extra_data=None,
    ):
        user = self._get_audit_user()
        if not user:
            return

        resource_type = None
        if resource_obj is not None:
            resource_type = ContentType.objects.get_for_model(resource_obj)
            resource_id = resource_obj.pk
            resource_name = str(resource_obj)

        AuditLogService.log_action(
            user=user,
            action=action,
            description=description,
            request=self.request,
            success=success,
            error_message=error_message or '',
            resource_type=resource_type,
            resource_id=resource_id,
            resource_name=resource_name or '',
            extra_data=extra_data,
        )
