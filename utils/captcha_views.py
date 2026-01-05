"""
验证码相关视图
"""
from rest_framework.views import APIView
from rest_framework.permissions import AllowAny
from django.conf import settings
from drf_spectacular.utils import extend_schema, extend_schema_view
from utils.responses import SycResponse
from .captcha_serializers import CaptchaSerializer
import logging

logger = logging.getLogger(__name__)


@extend_schema_view(
    get=extend_schema(
        summary="获取验证码",
        description="生成新的验证码图片",
        tags=["验证码"]
    ),
    post=extend_schema(
        summary="刷新验证码",
        description="刷新生成新的验证码图片",
        tags=["验证码"]
    )
)
class CaptchaView(APIView):
    """验证码视图 - 只负责生成验证码，验证逻辑在登录接口中处理"""
    permission_classes = [AllowAny]
    serializer_class = CaptchaSerializer

    def get(self, request):
        """获取验证码"""
        try:
            # 检查是否启用验证码
            if not getattr(settings, 'CAPTCHA_ENABLED', True):
                return SycResponse.success(
                    content={'enabled': False},
                    message="验证码功能已禁用"
                )

            # 生成验证码
            serializer = CaptchaSerializer()
            captcha_data = serializer.create({})

            return SycResponse.success(
                content={
                    'enabled': True,
                    'captcha_key': captcha_data['captcha_key'],
                    'captcha_image': captcha_data['captcha_image'],
                },
                message="验证码生成成功"
            )

        except Exception as e:
            logger.error(f'获取验证码失败: {str(e)}')
            return SycResponse.error(message="验证码生成失败")

    def post(self, request):
        """刷新验证码"""
        return self.get(request)
