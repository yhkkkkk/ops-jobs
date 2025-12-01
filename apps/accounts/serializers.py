"""
用户认证相关序列化器
"""
from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from django.conf import settings
from django.contrib.auth.models import User
from django.contrib.auth.password_validation import validate_password

from utils.audit_service import AuditLogService
from utils.captcha_serializers import CaptchaValidationSerializer
from .models import UserProfile
from .utils import get_user_profile_data


class UserProfileSerializer(serializers.ModelSerializer):
    """用户扩展信息序列化器"""

    class Meta:
        model = UserProfile
        fields = ['phone', 'department', 'position']


class UserSerializer(serializers.ModelSerializer):
    """用户序列化器"""
    profile = UserProfileSerializer(source='userprofile', read_only=True)

    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'first_name', 'last_name',
                 'is_staff', 'is_superuser', 'date_joined', 'last_login', 'profile']
        read_only_fields = ['id', 'date_joined', 'last_login', 'is_staff', 'is_superuser']


class UserRegistrationSerializer(serializers.ModelSerializer):
    """用户注册序列化器"""
    password = serializers.CharField(write_only=True, validators=[validate_password])
    password_confirm = serializers.CharField(write_only=True)
    phone = serializers.CharField(max_length=20, required=False, allow_blank=True)
    department = serializers.CharField(max_length=100, required=False, allow_blank=True)
    position = serializers.CharField(max_length=100, required=False, allow_blank=True)

    class Meta:
        model = User
        fields = ['username', 'email', 'first_name', 'last_name',
                 'password', 'password_confirm', 'phone', 'department', 'position']

    def validate(self, attrs):
        if attrs['password'] != attrs['password_confirm']:
            raise serializers.ValidationError("两次输入的密码不一致")
        return attrs

    def validate_username(self, value):
        if User.objects.filter(username=value).exists():
            raise serializers.ValidationError("用户名已存在")
        return value

    def validate_email(self, value):
        if value and User.objects.filter(email=value).exists():
            raise serializers.ValidationError("邮箱已被使用")
        return value

    def create(self, validated_data):
        # 移除确认密码和扩展字段
        password_confirm = validated_data.pop('password_confirm')
        phone = validated_data.pop('phone', '')
        department = validated_data.pop('department', '')
        position = validated_data.pop('position', '')

        # 创建用户
        user = User.objects.create_user(**validated_data)

        # 创建用户扩展信息
        UserProfile.objects.create(
            user=user,
            phone=phone,
            department=department,
            position=position
        )

        return user


class UserUpdateSerializer(serializers.ModelSerializer):
    """用户信息更新序列化器"""
    phone = serializers.CharField(max_length=20, required=False, allow_blank=True)
    department = serializers.CharField(max_length=100, required=False, allow_blank=True)
    position = serializers.CharField(max_length=100, required=False, allow_blank=True)

    class Meta:
        model = User
        fields = ['first_name', 'last_name', 'email', 'phone', 'department', 'position']

    def validate_email(self, value):
        user = self.instance
        if value and User.objects.filter(email=value).exclude(id=user.id).exists():
            raise serializers.ValidationError("邮箱已被使用")
        return value

    def update(self, instance, validated_data):
        # 分离扩展字段
        phone = validated_data.pop('phone', None)
        department = validated_data.pop('department', None)
        position = validated_data.pop('position', None)

        # 更新用户基本信息
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()

        # 更新扩展信息
        profile, created = UserProfile.objects.get_or_create(user=instance)
        if phone is not None:
            profile.phone = phone
        if department is not None:
            profile.department = department
        if position is not None:
            profile.position = position
        profile.save()

        return instance


class ChangePasswordSerializer(serializers.Serializer):
    """修改密码序列化器"""
    old_password = serializers.CharField(required=True)
    new_password = serializers.CharField(required=True, validators=[validate_password])
    new_password_confirm = serializers.CharField(required=True)

    def validate(self, attrs):
        if attrs['new_password'] != attrs['new_password_confirm']:
            raise serializers.ValidationError("两次输入的新密码不一致")
        return attrs

    def validate_old_password(self, value):
        user = self.context['request'].user
        if not user.check_password(value):
            raise serializers.ValidationError("旧密码错误")
        return value


class CustomTokenObtainPairSerializer(TokenObtainPairSerializer):
    """自定义JWT Token序列化器 - 支持验证码验证"""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # 如果启用验证码，动态添加验证码字段
        captcha_enabled = getattr(settings, 'CAPTCHA_ENABLED', True)
        if captcha_enabled:
            self.fields['captcha_key'] = serializers.CharField(required=False, allow_blank=True)  # pyright: ignore[reportIndexIssue]
            self.fields['captcha_value'] = serializers.CharField(required=False, allow_blank=True)  # pyright: ignore[reportIndexIssue]

    def validate(self, attrs):
        # 如果启用验证码，先验证验证码
        captcha_enabled = getattr(settings, 'CAPTCHA_ENABLED', True)
        if captcha_enabled:
            # 提取验证码字段
            captcha_key = attrs.pop('captcha_key', None)
            captcha_value = attrs.pop('captcha_value', None)

            # 使用 CaptchaValidationSerializer 验证
            captcha_serializer = CaptchaValidationSerializer(data={
                'captcha_key': captcha_key,
                'captcha_value': captcha_value
            })
            if not captcha_serializer.is_valid():
                raise serializers.ValidationError(captcha_serializer.errors)

        # 尝试获取用户对象用于审计日志（验证失败时也能记录用户名）
        username = attrs.get('username')
        login_user = None
        if username:
            try:
                login_user = User.objects.get(username=username)
            except User.DoesNotExist:
                pass

        # 调用父类验证（包含用户认证）
        try:
            data = super().validate(attrs)
        except serializers.ValidationError as e:
            # 记录登录失败日志
            request = self.context.get('request')
            if request:
                AuditLogService.log_login(
                    user=login_user,
                    request=request,
                    success=False
                )
            raise

        # 检查用户是否被禁用
        if not self.user.is_active:
            raise serializers.ValidationError({
                'non_field_errors': ['账户已被禁用']
            })

        # 添加用户信息到响应
        data['user'] = {
            'id': self.user.id,
            'username': self.user.username,
            'email': self.user.email,
            'first_name': self.user.first_name,
            'last_name': self.user.last_name,
            'is_staff': self.user.is_staff,
            'is_superuser': self.user.is_superuser,
            'profile': get_user_profile_data(self.user)
        }

        # 记录登录成功日志
        request = self.context.get('request')
        if request:
            AuditLogService.log_login(self.user, request, success=True)

        return data
