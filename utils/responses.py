"""
自定义响应类
提供统一的API响应格式和更好的数据结构控制
"""
import datetime
from collections import OrderedDict
from rest_framework.response import Response
from rest_framework import status
from django.http import JsonResponse


class ResponseCode:
    """响应状态码常量"""
    SUCCESS = 200
    CREATED = 201
    BAD_REQUEST = 400
    UNAUTHORIZED = 401
    FORBIDDEN = 403
    NOT_FOUND = 404
    ACCOUNT_LOCKED = 423  # 账户被锁定


class SycResponse:
    """
    统一响应类
    """

    @classmethod
    def _build_response(cls, code, message, success, content=None, http_status=status.HTTP_200_OK):
        """构建统一的响应格式"""
        data = OrderedDict([
            ('code', code),
            ('message', message),
            ('success', success)
        ])

        if content is not None:
            data['content'] = content

        return Response(data, status=http_status)

    @classmethod
    def success(cls, content=None, message="操作成功", code=200):
        """成功响应"""
        return cls._build_response(code, message, True, content, status.HTTP_200_OK)
    
    @classmethod
    def error(cls, message="操作失败", code=400, content=None):
        """错误响应"""
        return cls._build_response(code, message, False, content, status.HTTP_400_BAD_REQUEST)

    @classmethod
    def validation_error(cls, errors, message="数据验证失败", code=400):
        """验证错误响应"""
        # 将DRF的验证错误转换为有序字典
        if hasattr(errors, 'items'):
            error_content = OrderedDict()
            for field, field_errors in errors.items():
                if isinstance(field_errors, list):
                    error_content[field] = field_errors
                else:
                    error_content[field] = [str(field_errors)]
        else:
            error_content = {'non_field_errors': [str(errors)]}

        content = OrderedDict([('errors', error_content)])
        return cls._build_response(code, message, False, content, status.HTTP_400_BAD_REQUEST)
    
    @classmethod
    def unauthorized(cls, message="未授权访问", code=401):
        """未授权响应"""
        return cls._build_response(code, message, False, None, status.HTTP_401_UNAUTHORIZED)

    @classmethod
    def forbidden(cls, message="禁止访问", code=403):
        """禁止访问响应"""
        return cls._build_response(code, message, False, None, status.HTTP_403_FORBIDDEN)

    @classmethod
    def not_found(cls, message="资源不存在", code=404):
        """资源不存在响应"""
        return cls._build_response(code, message, False, None, status.HTTP_404_NOT_FOUND)


def account_locked(request, credentials: dict = None) -> JsonResponse:
    """
    账户锁定响应 - 集成 django-axes
    Args:
        request: 请求对象
        credentials: 凭证信息
    """
    from axes.handlers.proxy import AxesProxyHandler
    from django.conf import settings

    handler = AxesProxyHandler()

    # 获取配置
    cooloff_time = getattr(settings, 'AXES_COOLOFF_TIME', None)
    failure_limit = getattr(settings, 'AXES_FAILURE_LIMIT', 5)

    if cooloff_time:
        unlock_time = datetime.datetime.now() + cooloff_time
        unlock_time_str = unlock_time.strftime('%Y-%m-%d %H:%M:%S')
        cooloff_time_minutes = int(cooloff_time.total_seconds() / 60)
    else:
        unlock_time_str = None
        cooloff_time_minutes = None

    return JsonResponse({
        'code': ResponseCode.ACCOUNT_LOCKED,
        'message': '账户已被锁定',
        'success': False,
        'content': {
            'failure_limit': failure_limit,
            'cooloff_time_minutes': cooloff_time_minutes,
            'unlock_time': unlock_time_str,
            'failures_remaining': max(0, failure_limit - handler.get_failures(request, credentials)),
        }
    }, status=status.HTTP_423_LOCKED)
