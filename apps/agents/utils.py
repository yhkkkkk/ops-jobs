from ipaddress import ip_address
from urllib.parse import urlparse


def normalize_agent_server_base_url(raw_url: str) -> str:
    """Normalize agent-server URL to base http/https URL without path.

    - ws/wss -> http/https
    - ensure scheme
    - strip path/query/fragment
    """
    if not raw_url:
        return ""

    url = raw_url.strip()
    if url.startswith("ws://"):
        url = "http://" + url[5:]
    elif url.startswith("wss://"):
        url = "https://" + url[6:]

    if not url.startswith(("http://", "https://")):
        url = "http://" + url

    parsed = urlparse(url)
    scheme = parsed.scheme or "http"
    netloc = parsed.netloc or parsed.path

    if not netloc:
        return ""

    return f"{scheme}://{netloc}".rstrip("/")


def build_agent_server_netloc_map():
    """构建 Agent-Server 的 netloc 映射（netloc -> AgentServer 实例）"""
    from .models import AgentServer

    mapping = {}
    for server in AgentServer.objects.all():
        normalized = normalize_agent_server_base_url(server.base_url)
        if not normalized:
            continue
        netloc = urlparse(normalized).netloc
        if not netloc:
            continue
        mapping[netloc] = server
    return mapping


def resolve_agent_server_from_url(raw_url: str, netloc_map: dict | None = None):
    """根据 URL 解析并匹配 Agent-Server（返回实例或 None）"""
    if not raw_url:
        return None
    normalized = normalize_agent_server_base_url(raw_url)
    if not normalized:
        return None
    netloc = urlparse(normalized).netloc
    if not netloc:
        return None
    if netloc_map is None:
        netloc_map = build_agent_server_netloc_map()
    return netloc_map.get(netloc)


def validate_agent_server_websocket_url(raw_url: str) -> str:
    """Validate an Agent-to-Agent-Server WebSocket URL.

    Remote Agent connections must use WSS. Plain WS is reserved for loopback
    development only, so a generated installation config cannot silently
    downgrade transport security.
    """
    url = (raw_url or '').strip()
    parsed = urlparse(url)
    if parsed.scheme not in {'ws', 'wss'} or not parsed.hostname:
        raise ValueError('Agent-Server 地址必须是有效的 ws:// 或 wss:// URL')
    if parsed.scheme == 'wss':
        return url

    hostname = parsed.hostname.lower()
    if hostname == 'localhost':
        return url
    try:
        if ip_address(hostname).is_loopback:
            return url
    except ValueError:
        pass
    raise ValueError('远程 Agent-Server 必须使用 wss://；ws:// 仅允许 localhost 或回环地址')
