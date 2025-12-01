"""
验证码相关url配置
"""
from django.urls import path, include
from .captcha_views import CaptchaView

urlpatterns = [
    # 获取验证码 key 的接口
    path('', CaptchaView.as_view(), name='captcha'),

    # django-simple-captcha 内置的图片生成接口
    # path('', include('captcha.urls')),
]
