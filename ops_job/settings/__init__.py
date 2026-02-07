"""
Django settings for ops_job project.

This package contains environment-specific settings.
"""

import os
from pathlib import Path

try:
    from dotenv import load_dotenv

    BASE_DIR = Path(__file__).resolve().parent.parent.parent
    env_path = BASE_DIR / '.env'

    if env_path.exists():
        load_dotenv(env_path)
    else:
        # 在生产环境避免 stdout 噪音，保留静默失败以兼容无 .env 场景
        pass

except ImportError:
    print("Warning: python-dotenv not installed. Install it with: pip install python-dotenv")

# 获取环境变量，默认为开发环境
ENVIRONMENT = os.getenv('DJANGO_ENVIRONMENT', 'development')

if ENVIRONMENT == 'production':
    from .production import *
elif ENVIRONMENT == 'development':
    from .development import *
else:
    from .development import *
