from django.apps import AppConfig


class AccountsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.accounts'
    verbose_name = '账号管理'
    
    def ready(self):
        """应用加载完成后的初始化"""
        try:
            import apps.accounts.admin  # 确保 admin 配置被加载
        except ImportError:
            pass