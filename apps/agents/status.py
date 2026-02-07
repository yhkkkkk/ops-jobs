"""
Agent 状态计算与缓存工具。

本模块提供基于 Agent.last_heartbeat_at 和系统配置（agent.offline_threshold*）
计算展示状态的函数，并提供短时缓存以减少批量列表查询时的重复计算。

对外接口：
 - compute_agent_status(agent) -> str
 - get_cached_agent_status(agent_id, agent_obj=None) -> Optional[str]
 - compute_and_cache_status(agent_id) -> Optional[str]
 - set_agent_status_cache(agent_id, status, ttl=None)
 - invalidate_agent_status_cache(agent_id)

缓存键格式："{CACHE_KEY_PREFIX}:{agent_id}"
"""
from typing import Optional, Any

from django.core.cache import cache
from django.utils import timezone

from apps.system_config.models import ConfigManager

# Cache configuration
CACHE_KEY_PREFIX = "agent:status"
DEFAULT_TTL = 15
DEFAULT_THRESHOLD = 600


def _get_threshold_for_agent(agent) -> int:
    """Resolve offline threshold seconds for given agent (env-aware)."""
    default = ConfigManager.get("agent.offline_threshold_seconds", DEFAULT_THRESHOLD) or DEFAULT_THRESHOLD
    by_env = ConfigManager.get("agent.offline_threshold_by_env", {}) or {}
    env = None
    # prefer从标签推断环境：取首个匹配 key 的标签
    host = getattr(agent, "host", None)
    tags = []
    if host:
        tags = getattr(host, "tags", []) or []
    if not tags:
        tags = getattr(agent, "tags", []) or []
    if isinstance(by_env, dict) and tags:
        for tag in tags:
            if isinstance(tag, str) and tag in by_env:
                env = tag
                break

    if isinstance(by_env, dict) and env:
        try:
            val = by_env.get(env)
            if isinstance(val, (int, float)):
                return int(val)
            if isinstance(val, str) and val.strip().isdigit():
                return int(val.strip())
        except Exception:
            pass
    try:
        return int(default)
    except Exception:
        return DEFAULT_THRESHOLD


def _compute_ttl(agent, status: str) -> int:
    """
    Compute cache TTL in seconds.
    - Default DEFAULT_TTL
    - If threshold is small (<60s) use smaller TTL (max(5, threshold//10))
    """
    try:
        threshold = _get_threshold_for_agent(agent)
        if threshold < 60:
            return max(5, threshold // 10)
    except Exception:
        pass
    return DEFAULT_TTL


def compute_agent_status(agent) -> str:
    """
    Compute agent status based on agent model fields and last_heartbeat_at.
    Returns one of: 'online', 'offline', 'pending', 'disabled'
    """
    # Respect explicit admin states first for 'pending' and 'disabled'
    current = getattr(agent, "status", None)
    if current in ("disabled", "pending"):
        return current

    last = getattr(agent, "last_heartbeat_at", None)
    if not last:
        return "offline"

    now = timezone.now()
    try:
        threshold = _get_threshold_for_agent(agent)
    except Exception:
        threshold = DEFAULT_THRESHOLD

    delta = (now - last).total_seconds()
    return "online" if delta <= threshold else "offline"


def _cache_key(agent_id: int) -> str:
    return f"{CACHE_KEY_PREFIX}:{agent_id}"


def get_cached_agent_status(agent_id: int, agent_obj: Optional[Any] = None) -> Optional[str]:
    """
    Return cached computed status if present; otherwise compute, cache and return.
    """
    key = _cache_key(agent_id)
    cached = cache.get(key)
    if cached and isinstance(cached, dict):
        return cached.get("status")

    # fallback to computing and caching
    return compute_and_cache_status(agent_id)


def compute_and_cache_status(agent_id: int) -> Optional[str]:
    """Compute status by loading Agent from DB and write to cache."""
    from .models import Agent  # local import to avoid cycle

    try:
        agent_obj = Agent.objects.select_related("host").get(id=agent_id)
    except Agent.DoesNotExist:
        return None

    status = compute_agent_status(agent_obj)
    ttl = _compute_ttl(agent_obj, status)
    cache.set(_cache_key(agent_id), {"status": status, "updated_at": timezone.now().isoformat(), "source": "computed"}, ttl)
    return status


def set_agent_status_cache(agent_id: int, status: str, ttl: Optional[int] = None) -> None:
    """Set agent status cache explicitly."""
    key = _cache_key(agent_id)
    if ttl is None:
        try:
            from .models import Agent

            agent_obj = Agent.objects.select_related("host").filter(id=agent_id).first()
            ttl = _compute_ttl(agent_obj, status) if agent_obj else DEFAULT_TTL
        except Exception:
            ttl = DEFAULT_TTL
    cache.set(key, {"status": status, "updated_at": timezone.now().isoformat(), "source": "explicit"}, ttl)


def invalidate_agent_status_cache(agent_id: int) -> None:
    """Delete agent status cache."""
    key = _cache_key(agent_id)
    try:
        cache.delete(key)
    except Exception:
        pass
