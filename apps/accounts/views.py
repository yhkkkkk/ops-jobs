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
        """注册接口允许匿名访问"""
        if self.action == 'create':
            permission_classes = [AllowAny]
        else:
            permission_classes = [IsAuthenticated]
        return [permission() for permission in permission_classes]

    def create(self, request, *args, **kwargs):
        """用户注册"""
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()

        AuditLogService.log_create(user, user, request)

        # 生成jwt
        refresh = RefreshToken.for_user(user)

        content = {
            'user': UserSerializer(user).data,
            'tokens': {
                'refresh': str(refresh),
                'access': str(refresh.access_token),
            }
        }

        return SycResponse.success(content=content, message="注册成功")

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

    @action(detail=False, methods=['put'])
    def update_profile(self, request):
        """更新当前用户信息"""
        serializer = UserUpdateSerializer(request.user, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()

        return SycResponse.success(message="信息更新成功")

    @action(detail=False, methods=['post'])
    def change_password(self, request):
        """修改密码"""
        serializer = ChangePasswordSerializer(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)

        # 设置新密码
        request.user.set_password(serializer.validated_data['new_password'])
        request.user.save()

        AuditLogService.log_action(
            user=request.user,
            action='update',
            description='密码修改成功',
            request=request
        )

        return SycResponse.success(message="密码修改成功")
