"""
账户相关工具函数
"""
from .models import UserProfile


def get_user_profile_data(user):
    """获取用户扩展信息"""
    try:
        profile = user.userprofile
        return {
            'phone': profile.phone,
            'department': profile.department,
            'position': profile.position,
        }
    except UserProfile.DoesNotExist:
        return None

