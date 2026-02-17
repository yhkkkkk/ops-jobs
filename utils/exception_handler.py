from typing import Any, Optional

from rest_framework import status
from rest_framework.exceptions import PermissionDenied
from rest_framework.response import Response
from rest_framework.views import exception_handler

from utils.audit_service import AuditLogService
from utils.responses import SycResponse


def custom_exception_handler(exc: Exception, context: dict) -> Optional[Response]:
    response = exception_handler(exc, context)

    if isinstance(exc, PermissionDenied):
        request = context.get('request') if context else None
        detail = getattr(exc, 'detail', None)
        if isinstance(detail, dict):
            detail_payload: dict[str, Any] = detail
        else:
            detail_payload = {'reason': str(detail or 'permission_denied')}

        response = SycResponse._build_response(
            code=status.HTTP_403_FORBIDDEN,
            message='权限不足',
            success=False,
            content=detail_payload,
            http_status=status.HTTP_403_FORBIDDEN
        )

        try:
            user = getattr(request, 'user', None) if request is not None else None
            if user and getattr(user, 'is_authenticated', False):
                resource_type = detail_payload.get('resource_type')
                resource_id = detail_payload.get('resource_id')
                required_permissions = detail_payload.get('required_permissions') or []
                action = detail_payload.get('action')

                description_parts = ['权限不足']
                if resource_type:
                    description_parts.append(f"资源: {resource_type}")
                if resource_id:
                    description_parts.append(f"ID: {resource_id}")
                if action:
                    description_parts.append(f"动作: {action}")
                if required_permissions:
                    description_parts.append(f"权限: {', '.join(required_permissions)}")

                AuditLogService.log_action(
                    user=user,
                    action='permission_denied',
                    description='; '.join(description_parts),
                    request=request,
                    success=False,
                    error_message='permission_denied',
                    extra_data=detail_payload
                )
        except Exception:
            # 避免审计异常影响主流程
            pass

    return response
