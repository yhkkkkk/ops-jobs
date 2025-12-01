"""
脚本模板应用配置
"""
from django.apps import AppConfig


class ScriptTemplatesConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.script_templates'
    verbose_name = '脚本模板'
    
    def ready(self):
        """应用就绪时的初始化"""
        # 创建默认模板
        try:
            from .services import ScriptTemplateService
            ScriptTemplateService.create_default_templates()
        except Exception:
            pass
