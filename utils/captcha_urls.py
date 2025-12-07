"""
验证码相关url配置
"""
from django.urls import path, include
from .captcha_views import CaptchaView

urlpatterns = [
    # django-simple-captcha 内置的图片生成接口（必须包含，否则captcha_image_url无法工作）
    # 注意：captcha.urls 会提供 captcha-image URL（路径通常是 image/<key>/），这是 captcha_image_url 函数需要的
    # 需要放在前面，避免被空路径匹配拦截
    path('', include('captcha.urls')),
    
    # 获取验证码 key 的接口（放在后面，作为兜底）
    path('', CaptchaView.as_view(), name='captcha'),
]
