"""
系统配置应用配置
"""
from django.apps import AppConfig


class SystemConfigConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.system_config'
    verbose_name = '系统配置'
    
    def ready(self):
        """应用就绪时初始化默认配置"""
        try:
            from .models import init_default_configs
            init_default_configs()
        except Exception:
            pass
