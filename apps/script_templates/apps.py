"""
脚本模板应用配置
"""
from django.apps import AppConfig


class ScriptTemplatesConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.script_templates'
    verbose_name = '脚本模板'
