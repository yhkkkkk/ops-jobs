"""
用户认证相关视图 - 支持Session + JWT混合认证
"""
from rest_framework import serializers, viewsets
from rest_framework.authentication import BasicAuthentication
from rest_framework.decorators import (
    action,
    api_view,
    authentication_classes,
    permission_classes,
)
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework_extensions.cache.mixins import CacheResponseMixin
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

from django.conf import settings
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.models import User

from drf_spectacular.utils import extend_schema

from utils.audit_service import AuditLogService
from utils.responses import SycResponse
from .models import UserProfile
from .pagination import UserPagination
from .serializers import (
    CustomTokenObtainPairSerializer,
    UserRegistrationSerializer,
    UserSerializer,
    UserUpdateSerializer,
)
from .utils import get_user_profile_data

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

        # 获取校验的数据
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
            try:
                token = RefreshToken(refresh_token)
                token.blacklist()
            except TokenError:
                pass

        return SycResponse.success(message="登出成功")

    except Exception as e:
        return SycResponse.error(message=f"登出失败: {str(e)}")

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


# 2FA相关视图
if TWO_FACTOR_ENABLED:
    @extend_schema(
        summary="检查用户是否需要2FA验证",
        description="登录前检查用户是否启用了2FA",
        tags=["双因子认证"]
    )
    @api_view(['POST'])
    @authentication_classes([])  # 不使用任何认证，避免csrf检查
    @permission_classes([AllowAny])
    def check_2fa_required(request):
        """检查用户是否需要2FA验证"""
        username = request.data.get('username')
        password = request.data.get('password')
        
        if not username or not password:
            return SycResponse.validation_error(
                errors={'non_field_errors': ['用户名和密码不能为空']},
                message="参数错误"
            )
        
        # 验证用户名密码
        user = authenticate(username=username, password=password)
        if not user:
            # 不暴露用户是否存在的信息，统一返回不需要2FA
            return SycResponse.success(content={'requires_2fa': False}, message="检查完成")
        
        # 检查用户是否启用了2FA
        devices = list(devices_for_user(user))
        requires_2fa = len(devices) > 0
        
        return SycResponse.success(
            content={'requires_2fa': requires_2fa},
            message="检查完成"
        )

    @extend_schema(
        summary="获取2FA设置信息",
        description="获取TOTP的secret和QR码，用于绑定验证器APP",
        tags=["双因子认证"]
    )
    @api_view(['GET'])
    @permission_classes([IsAuthenticated])
    def two_factor_setup(request):
        """获取2FA设置信息（生成QR码）"""
        user = request.user
        
        # 检查是否已经启用2FA
        existing_devices = list(devices_for_user(user))
        if existing_devices:
            return SycResponse.error(message="您已经启用了双因子认证，如需重新设置请先禁用")
        
        # 生成新的TOTP设备（未确认状态）
        device = TOTPDevice.objects.create(
            user=user,
            name='default',
            confirmed=False
        )
        
        # 生成QR码
        otp_issuer = getattr(settings, 'OTP_TOTP_ISSUER', 'Ops Job Platform')
        config_url = device.config_url.replace('otpauth://totp/', f'otpauth://totp/{otp_issuer}:')
        
        # 生成QR码图片（SVG格式）
        img = qrcode.make(config_url, image_factory=qrcode.image.svg.SvgImage)
        buffer = BytesIO()
        img.save(buffer)
        qr_code_svg = buffer.getvalue().decode('utf-8')
        
        return SycResponse.success(
            content={
                'secret': device.bin_key.hex(),
                'qr_code': qr_code_svg,
                'config_url': config_url
            },
            message="获取2FA设置信息成功"
        )

    @extend_schema(
        summary="验证并启用2FA",
        description="验证用户输入的OTP码，验证成功后启用2FA",
        tags=["双因子认证"]
    )
    @api_view(['POST'])
    @permission_classes([IsAuthenticated])
    def two_factor_verify(request):
        """验证并启用2FA"""
        user = request.user
        otp_token = request.data.get('otp_token')
        
        if not otp_token:
            return SycResponse.validation_error(
                errors={'otp_token': ['验证码不能为空']},
                message="参数错误"
            )
        
        # 查找未确认的TOTP设备
        devices = TOTPDevice.objects.filter(user=user, confirmed=False)
        if not devices.exists():
            return SycResponse.error(message="未找到待激活的2FA设备，请先获取设置信息")
        
        device = devices.first()
        
        # 验证OTP
        if not device.verify_token(otp_token):
            return SycResponse.error(message="验证码错误，请重试")
        
        # 验证成功，确认设备
        device.confirmed = True
        device.save()
        
        # 生成备份令牌（可选）
        backup_tokens = []
        # 如果需要备份令牌，可以在这里生成StaticDevice和StaticToken
        
        return SycResponse.success(
            content={
                'backup_tokens': backup_tokens,
                'message': '双因子认证已成功启用'
            },
            message="2FA启用成功"
        )

    @extend_schema(
        summary="获取2FA状态",
        description="查询当前用户的2FA启用状态",
        tags=["双因子认证"]
    )
    @api_view(['GET'])
    @permission_classes([IsAuthenticated])
    def two_factor_status(request):
        """获取2FA状态"""
        user = request.user
        devices = list(devices_for_user(user))
        
        # 只统计已确认的设备
        confirmed_devices = [d for d in devices if d.confirmed]
        
        return SycResponse.success(
            content={
                'enabled': len(confirmed_devices) > 0,
                'device_count': len(confirmed_devices)
            },
            message="获取2FA状态成功"
        )

    @extend_schema(
        summary="禁用2FA",
        description="禁用当前用户的2FA",
        tags=["双因子认证"]
    )
    @api_view(['POST'])
    @permission_classes([IsAuthenticated])
    def two_factor_disable(request):
        """禁用2FA"""
        user = request.user
        
        # 删除所有TOTP设备
        TOTPDevice.objects.filter(user=user).delete()
        
        # 删除所有静态备份令牌设备（如果有）
        if 'django_otp.plugins.otp_static' in settings.INSTALLED_APPS:
            StaticDevice.objects.filter(user=user).delete()
        
        return SycResponse.success(message="2FA已成功禁用")
else:
    # 如果未启用2FA，提供占位函数返回错误
    @api_view(['POST'])
    @permission_classes([AllowAny])
    def check_2fa_required(request):
        return SycResponse.error(message="2FA功能未启用", status_code=501)
    
    @api_view(['GET'])
    @permission_classes([IsAuthenticated])
    def two_factor_setup(request):
        return SycResponse.error(message="2FA功能未启用", status_code=501)
    
    @api_view(['POST'])
    @permission_classes([IsAuthenticated])
    def two_factor_verify(request):
        return SycResponse.error(message="2FA功能未启用", status_code=501)
    
    @api_view(['GET'])
    @permission_classes([IsAuthenticated])
    def two_factor_status(request):
        return SycResponse.error(message="2FA功能未启用", status_code=501)
    
    @api_view(['POST'])
    @permission_classes([IsAuthenticated])
    def two_factor_disable(request):
        return SycResponse.error(message="2FA功能未启用", status_code=501)