import pytest

from apps.agents.tests.test_e2e_control_plane import _e2e_redis_settings


def test_e2e_redis_settings_use_dedicated_local_defaults(monkeypatch):
    monkeypatch.delenv("E2E_REDIS_HOST", raising=False)
    monkeypatch.delenv("E2E_REDIS_PORT", raising=False)
    monkeypatch.delenv("E2E_REDIS_PASSWORD", raising=False)
    monkeypatch.delenv("E2E_REDIS_DB", raising=False)

    assert _e2e_redis_settings() == ("127.0.0.1", "16379", "", 8)


def test_e2e_redis_settings_allow_explicit_overrides(monkeypatch):
    monkeypatch.setenv("E2E_REDIS_HOST", "redis.test")
    monkeypatch.setenv("E2E_REDIS_PORT", "6388")
    monkeypatch.setenv("E2E_REDIS_PASSWORD", "secret")
    monkeypatch.setenv("E2E_REDIS_DB", "11")

    assert _e2e_redis_settings() == ("redis.test", "6388", "secret", 11)