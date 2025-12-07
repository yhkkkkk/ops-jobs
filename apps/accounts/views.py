"""
用户认证相关视图 - 支持Session + JWT混合认证
"""
from rest_framework import viewsets, serializers
from rest_framework.decorators import api_view, action
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from rest_framework_simplejwt.tokens import RefreshToken
from django.conf import settings
from rest_framework_extensions.cache.mixins import CacheResponseMixin
from django.contrib.auth.models import User
from django.contrib.auth import authenticate, logout, login
from utils.responses import SycResponse
from utils.pagination import LogPagination
from drf_spectacular.utils import extend_schema
from .models import UserProfile
from .serializers import (
    UserSerializer,
    UserRegistrationSerializer,
    UserUpdateSerializer,
    ChangePasswordSerializer,
    CustomTokenObtainPairSerializer
)
from .utils import get_user_profile_data
from utils.audit_service import AuditLogService

# 条件导入 2FA 相关模块
TWO_FACTOR_ENABLED = getattr(settings, 'TWO_FACTOR_ENABLED', False)
if TWO_FACTOR_ENABLED:
    from django_otp import devices_for_user
    from django_otp.plugins.otp_totp.models import TOTPDevice
    from django_otp.plugins.otp_static.models import StaticDevice, StaticToken
    from django_otp.util import random_hex
    import qrcode
    import qrcode.image.svg
    from io import BytesIO
    import base64


def get_client_ip(request):
    """获取客户端IP地址"""
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0].strip()
    else:
        ip = request.META.get('REMOTE_ADDR', '127.0.0.1')
    return ip


class CustomTokenObtainPairView(TokenObtainPairView):
    """统一登录视图 - 支持JWT Token和Session，集成验证码"""
    serializer_class = CustomTokenObtainPairSerializer
    permission_classes = [AllowAny]

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data, context={'request': request})

        if not serializer.is_valid():
            return SycResponse.validation_error(
                errors=serializer.errors,
                message="登录失败"
            )

        # 获取校验的数据（提取特定字段）
        validated_data = serializer.validated_data

        # 同时设置Session和JWT Token - 支持混合认证
        # Session用于浏览器Cookie认证，JWT用于API认证
        user = serializer.user
        login(request, user, backend='django.contrib.auth.backends.ModelBackend')

        # 构建标准化的响应格式
        content = {
            'user': validated_data['user'],
            'access_token': validated_data['access'],
            'refresh_token': validated_data['refresh']
        }

        return SycResponse.success(content=content, message="登录成功")


@extend_schema(
    summary="用户登出",
    description="用户登出，清除会话和令牌",
    request=None,
    responses={200: None},
    tags=["用户认证"]
)
@api_view(['POST'])
def logout_view(request):
    """登出"""
    try:
        # 删除session
        if request.user.is_authenticated:
            logout(request)

        # JWT token加入黑名单
        refresh_token = request.data.get('refresh')
        if refresh_token:
            token = RefreshToken(refresh_token)
            token.blacklist()

        return SycResponse.success(message="登出成功")

    except Exception as e:
        return SycResponse.error(message=f"登出失败: {str(e)}")


class UserPagination(LogPagination):
    """用户分页类 - 使用正确的排序字段"""
    ordering = '-date_joined'

class UserViewSet(CacheResponseMixin, viewsets.ModelViewSet):
    """用户管理ViewSet"""
    queryset = User.objects.all()
    serializer_class = UserSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = UserPagination

    def get_serializer_class(self):
        if self.action == 'create':
            return UserRegistrationSerializer
        elif self.action in ['update', 'partial_update']:
            return UserUpdateSerializer
        return UserSerializer

    def get_permissions(self):
        """注册接口和auth_config接口允许匿名访问"""
        if self.action == 'auth_config':
            permission_classes = [AllowAny]
        else:
            permission_classes = [IsAuthenticated]
        return [permission() for permission in permission_classes]

    def retrieve(self, request, *args, **kwargs):
        """获取用户详情"""
        instance = self.get_object()
        serializer = self.get_serializer(instance)

        # 返回统一格式的响应
        return SycResponse.success(
            content=serializer.data,
            message="获取用户详情成功"
        )

    @action(detail=False, methods=['get'])
    def profile(self, request):
        """获取当前用户信息"""
        serializer = self.get_serializer(request.user)
        return SycResponse.success(content=serializer.data, message="获取用户信息成功")

    @action(detail=False, methods=['get'], permission_classes=[AllowAny])
    def auth_config(self, request):
        """获取认证配置信息（允许匿名访问）"""
        config = {
            'captcha_enabled': getattr(settings, 'CAPTCHA_ENABLED', False),
            'ldap_enabled': getattr(settings, 'LDAP_ENABLED', False),
            'two_factor_enabled': getattr(settings, 'TWO_FACTOR_ENABLED', False),
        }
        return SycResponse.success(content=config, message="获取认证配置成功")


# 2FA 相关视图（仅在启用时可用）
if TWO_FACTOR_ENABLED:
    from rest_framework.views import APIView

    @extend_schema(
        summary="获取2FA设置信息",
        description="获取双因子认证设置信息，包括二维码和密钥",
        tags=["双因子认证"]
    )
    class TwoFactorSetupView(APIView):
        """2FA设置视图 - 生成二维码和密钥"""
        permission_classes = [IsAuthenticated]

        def get(self, request):
            """获取2FA设置信息"""
            user = request.user

            # 检查是否已启用2FA
            existing_devices = list(devices_for_user(user))
            if existing_devices:
                return SycResponse.error(message="您已启用双因子认证，如需重新设置请先禁用")

            # 生成新的TOTP设备
            device = TOTPDevice.objects.create(
                user=user,
                name='default',
                confirmed=False
            )

            # 生成配置URL
            config_url = device.config_url

            # 生成二维码
            qr = qrcode.QRCode(version=1, box_size=10, border=5)
            qr.add_data(config_url)
            qr.make(fit=True)

            img = qr.make_image(fill_color="black", back_color="white")
            buffer = BytesIO()
            img.save(buffer, format='PNG')
            qr_code_base64 = base64.b64encode(buffer.getvalue()).decode()

            return SycResponse.success(content={
                'secret': device.key,
                'qr_code': f'data:image/png;base64,{qr_code_base64}',
                'config_url': config_url
            }, message="获取2FA设置信息成功")

    @extend_schema(
        summary="验证并启用2FA",
        description="验证OTP码并启用双因子认证",
        tags=["双因子认证"]
    )
    class TwoFactorVerifyView(APIView):
        """2FA验证视图 - 验证OTP码并启用2FA"""
        permission_classes = [IsAuthenticated]

        def post(self, request):
            """验证OTP码并启用2FA"""
            otp_token = request.data.get('otp_token', '')
            if not otp_token:
                return SycResponse.validation_error(
                    errors={'otp_token': ['请输入验证码']},
                    message="验证失败"
                )

            user = request.user

            # 查找未确认的设备
            devices = TOTPDevice.objects.filter(user=user, confirmed=False)
            if not devices.exists():
                return SycResponse.error(message="未找到待确认的设备，请先获取设置信息")

            device = devices.first()

            # 验证OTP码
            if device.verify_token(otp_token):
                device.confirmed = True
                device.save()

                # 生成备份码（静态令牌）
                static_device, created = StaticDevice.objects.get_or_create(
                    user=user,
                    name='backup'
                )
                if created:
                    # 生成10个备份码
                    for _ in range(10):
                        StaticToken.objects.create(device=static_device)

                # 获取备份码
                backup_tokens = list(static_device.token_set.values_list('token', flat=True))

                return SycResponse.success(content={
                    'backup_tokens': backup_tokens
                }, message="双因子认证已启用，请妥善保管备份码")
            else:
                return SycResponse.validation_error(
                    errors={'otp_token': ['验证码错误']},
                    message="验证失败"
                )

    @extend_schema(
        summary="检查2FA状态",
        description="检查当前用户的2FA启用状态",
        tags=["双因子认证"]
    )
    class TwoFactorStatusView(APIView):
        """2FA状态视图"""
        permission_classes = [IsAuthenticated]

        def get(self, request):
            """获取2FA状态"""
            user = request.user
            devices = list(devices_for_user(user))
            enabled = len(devices) > 0 and any(device.confirmed for device in devices)

            return SycResponse.success(content={
                'enabled': enabled,
                'device_count': len(devices)
            }, message="获取2FA状态成功")

    @extend_schema(
        summary="禁用2FA",
        description="禁用当前用户的双因子认证",
        tags=["双因子认证"]
    )
    class TwoFactorDisableView(APIView):
        """2FA禁用视图"""
        permission_classes = [IsAuthenticated]

        def post(self, request):
            """禁用2FA"""
            user = request.user
            devices = list(devices_for_user(user))

            if not devices:
                return SycResponse.error(message="您尚未启用双因子认证")

            # 删除所有设备
            for device in devices:
                device.delete()

            return SycResponse.success(message="双因子认证已禁用")
