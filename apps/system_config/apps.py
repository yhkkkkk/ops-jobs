"""
系统配置应用配置
"""
import logging
from django.apps import AppConfig
from django.db.models.signals import post_migrate

logger = logging.getLogger(__name__)


class SystemConfigConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.system_config'
    verbose_name = '系统配置'

    def ready(self):
        """应用就绪时连接信号"""
        # 使用post_migrate信号代替ready()方法中的数据库操作，这样可以避免在应用初始化时访问数据库的警告
        post_migrate.connect(self.init_default_configs, sender=self)

    def init_default_configs(self, sender, **kwargs):
        """在数据库迁移完成后初始化默认配置"""
        # 只在system_config应用迁移完成后执行，避免重复执行
        if sender.name != self.name:
            return

        try:
            from .models import init_default_configs, SystemConfig

            # 检查是否已经初始化过，避免重复创建
            if SystemConfig.objects.exists():
                return

            init_default_configs()

            logger.info("系统默认配置初始化完成")

        except Exception as e:
            logger.warning(f"初始化系统默认配置失败: {e}")
