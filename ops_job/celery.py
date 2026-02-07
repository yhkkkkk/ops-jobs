import functools
import os
from celery import Celery, platforms

# 设置Django设置模块
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'ops_job.settings')

app = Celery('ops_job')

# 从Django设置中加载配置
app.config_from_object('django.conf:settings', namespace='CELERY')

# 自动从所有已注册的Django应用中加载任务
from django.conf import settings
app.autodiscover_tasks(lambda: settings.INSTALLED_APPS)
platforms.C_FORCE_ROOT = True

@app.task(bind=True)
def debug_task(self):
    print(f'Request: {self.request!r}')

def retry_base_task_error():
    """celery 失败重试装饰器"""
    def wraps(func):
        @app.task(bind=True, retry_delay=180, max_retries=3)
        @functools.wraps(func)
        def wrapper(self, *args, **kwargs):
            try:
                return func(*args, **kwargs)
            except Exception as exc:
                raise self.retry(exc=exc)

        return wrapper
