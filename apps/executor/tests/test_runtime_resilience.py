import pytest

from utils.execution_id import ExecutionIDGenerator


def test_pytest_uses_local_runtime_backends(settings):
    """普通测试不应依赖外部 Redis，避免登录/权限/API 测试被网络阻塞。"""

    assert settings.CACHES["default"]["BACKEND"] == "django.core.cache.backends.locmem.LocMemCache"
    assert settings.CHANNEL_LAYERS["default"]["BACKEND"] == "channels.layers.InMemoryChannelLayer"
    assert settings.REDIS_PASSWORD in (None, "")


def test_execution_id_generator_does_not_use_cache_by_default(settings, monkeypatch):
    """默认 worker_id 生成不应依赖外部 cache，避免 Redis 不可用时阻塞。"""

    calls = {"get": 0, "set": 0}

    def _mark_get(*args, **kwargs):
        calls["get"] += 1
        return 0

    def _mark_set(*args, **kwargs):
        calls["set"] += 1
        return True

    monkeypatch.setattr("django_redis.cache.RedisCache.get", _mark_get)
    monkeypatch.setattr("django_redis.cache.RedisCache.set", _mark_set)

    generator = ExecutionIDGenerator()
    assert 0 <= generator.worker_id <= generator.MAX_WORKER_ID
    assert calls == {"get": 0, "set": 0}
