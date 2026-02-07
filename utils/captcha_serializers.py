"""
验证码相关序列化器
"""
from rest_framework import serializers
from captcha.models import CaptchaStore
from captcha.helpers import captcha_image_url
from django.conf import settings
import logging

logger = logging.getLogger(__name__)


class CaptchaSerializer(serializers.Serializer):
    """验证码序列化器"""
    captcha_key = serializers.CharField(read_only=True)
    captcha_image = serializers.CharField(read_only=True)
    
    def create(self, validated_data):
        """生成新的验证码"""
        try:
            # 生成验证码
            captcha = CaptchaStore.generate_key()
            captcha_url = captcha_image_url(captcha)
            
            logger.info(f'生成验证码: {captcha}')
            
            return {
                'captcha_key': captcha,
                'captcha_image': captcha_url,
            }
        except Exception as e:
            logger.error(f'生成验证码失败: {str(e)}')
            raise serializers.ValidationError('验证码生成失败')


class CaptchaValidationSerializer(serializers.Serializer):
    """验证码验证序列化器"""
    captcha_key = serializers.CharField(required=True, help_text='验证码key')
    captcha_value = serializers.CharField(required=True, help_text='验证码值')
    
    def validate(self, attrs):
        """验证验证码"""
        if not getattr(settings, 'CAPTCHA_ENABLED', True):
            # 如果验证码被禁用，直接通过验证
            return attrs
            
        captcha_key = attrs.get('captcha_key')
        captcha_value = attrs.get('captcha_value')
        
        if not captcha_key or not captcha_value:
            raise serializers.ValidationError('验证码不能为空')
        
        try:
            # 验证验证码
            captcha_store = CaptchaStore.objects.get(hashkey=captcha_key)
            if captcha_store.response.lower() != captcha_value.lower():
                logger.warning(f'验证码验证失败: key={captcha_key}, value={captcha_value}')
                raise serializers.ValidationError('验证码错误')
            
            # 验证成功后删除验证码（一次性使用）
            captcha_store.delete()
            logger.info(f'验证码验证成功: {captcha_key}')
            
        except CaptchaStore.DoesNotExist:
            logger.warning(f'验证码不存在或已过期: {captcha_key}')
            raise serializers.ValidationError('验证码不存在或已过期')
        except Exception as e:
            logger.error(f'验证码验证异常: {str(e)}')
            raise serializers.ValidationError('验证码验证失败')
        
        return attrs


class LoginWithCaptchaSerializer(serializers.Serializer):
    """带验证码的登录序列化器"""
    username = serializers.CharField(required=True, help_text='用户名')
    password = serializers.CharField(required=True, help_text='密码')
    captcha_key = serializers.CharField(required=False, help_text='验证码key')
    captcha_value = serializers.CharField(required=False, help_text='验证码值')
    
    def validate(self, attrs):
        """验证登录信息和验证码"""
        # 如果启用了验证码，则验证验证码
        if getattr(settings, 'CAPTCHA_ENABLED', True):
            captcha_key = attrs.get('captcha_key')
            captcha_value = attrs.get('captcha_value')
            
            if not captcha_key or not captcha_value:
                raise serializers.ValidationError('请输入验证码')
            
            # 使用验证码验证序列化器验证
            captcha_serializer = CaptchaValidationSerializer(data={
                'captcha_key': captcha_key,
                'captcha_value': captcha_value
            })
            
            if not captcha_serializer.is_valid():
                raise serializers.ValidationError(captcha_serializer.errors)
        
        return attrs
