"""Test settings.

Keep ordinary pytest runs independent from external Redis or Channels
backends. E2E tests that need Redis override these values in their fixtures.
"""

from .development import *  # noqa: F401,F403


DEBUG = False
TESTING = True

REDIS_HOST = "127.0.0.1"
REDIS_PORT = "6379"
REDIS_PASSWORD = None

CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
        "LOCATION": "ops-job-test-cache",
    }
}

CHANNEL_LAYERS = {
    "default": {
        "BACKEND": "channels.layers.InMemoryChannelLayer",
    }
}

AXES_ENABLED = False
CAPTCHA_ENABLED = False
TWO_FACTOR_ENABLED = False
