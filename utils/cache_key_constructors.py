"""
自定义缓存键构造器
"""
import hashlib
from rest_framework_extensions.key_constructor.constructors import DefaultKeyConstructor
from rest_framework_extensions.key_constructor.bits import (
    KeyBitBase,
    RetrieveSqlQueryKeyBit,
    ListSqlQueryKeyBit,
    PaginationKeyBit,
    QueryParamsKeyBit,
    UniqueMethodIdKeyBit,
    UniqueViewIdKeyBit,
    UserKeyBit,
    LanguageKeyBit,
    FormatKeyBit,
    RequestMetaKeyBit
)


class UserContextKeyBit(KeyBitBase):
    """基于用户上下文（用户名、IP、User-Agent）的缓存键位"""
    
    def get_data(self, **kwargs):
        request = kwargs.get('request')
        if not request:
            return ''
        
        # 获取用户名
        username = getattr(request.user, 'username', 'anonymous')
        
        # 获取客户端IP
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0].strip()
        else:
            ip = request.META.get('REMOTE_ADDR', '')
        
        # 获取User-Agent（截取前100个字符避免过长）
        user_agent = request.META.get('HTTP_USER_AGENT', '')[:100]
        
        # 组合并生成哈希
        context_string = f"{username}:{ip}:{user_agent}"
        return hashlib.md5(context_string.encode('utf-8')).hexdigest()[:16]


class CustomKeyConstructor(DefaultKeyConstructor):
    """自定义缓存键构造器，包含用户上下文信息"""
    unique_method_id = UniqueMethodIdKeyBit()
    unique_view_id = UniqueViewIdKeyBit()
    user_context = UserContextKeyBit()  # 使用自定义的用户上下文键位
    language = LanguageKeyBit()
    format = FormatKeyBit()
    query_params = QueryParamsKeyBit()
    pagination = PaginationKeyBit()


class DashboardKeyConstructor(DefaultKeyConstructor):
    """Dashboard专用的缓存键构造器"""
    unique_method_id = UniqueMethodIdKeyBit()
    unique_view_id = UniqueViewIdKeyBit()
    user_context = UserContextKeyBit()  # 基于用户上下文的缓存
    query_params = QueryParamsKeyBit()  # 包含查询参数
