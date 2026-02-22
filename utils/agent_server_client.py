import time
from typing import Any, Dict, Optional

import requests
from django.conf import settings

from utils.agent_server_auth import compute_agent_server_hmac


class AgentServerClient:
    """
    封装对 agent-server 的 HTTP 调用，统一附加 HMAC 签名。

    签名规则需与 agent-server 内部的 computeHMAC 保持一致：
      - Header:
          X-Timestamp: 秒级时间戳（int）
          X-Signature: hex(hmac_sha256(secret, ts + "\n" + method + "\n" + path + "\n" + body))
    """

    def __init__(
        self,
        shared_secret: str,
        session: Optional[requests.Session] = None,
        timeout: int = 10,
    ):
        self.shared_secret = shared_secret or ""
        self.session = session or requests.Session()
        self.timeout = timeout

    @classmethod
    def from_settings(cls) -> "AgentServerClient":
        secret = getattr(settings, "AGENT_SERVER_SHARED_SECRET", "")
        timeout = getattr(settings, "AGENT_SERVER_TIMEOUT", 10)
        return cls(shared_secret=secret, timeout=timeout)

    def post(self, url: str, json: Optional[Dict[str, Any]] = None, headers: Optional[Dict[str, str]] = None, timeout: int = None):
        data = b""
        if json is not None:
            import json as _json

            data = _json.dumps(json, separators=(",", ":")).encode("utf-8")

        headers = headers.copy() if headers else {}
        headers.setdefault("Content-Type", "application/json")

        ts = str(int(time.time()))
        headers["X-Timestamp"] = ts

        if self.shared_secret:
            sig = compute_agent_server_hmac(self.shared_secret, "POST", url, ts, data)
            headers["X-Signature"] = sig

        return self.session.post(url, data=data, headers=headers, timeout=timeout or self.timeout)

    def get(self, url: str, params: Optional[Dict[str, Any]] = None, headers: Optional[Dict[str, str]] = None, timeout: int = None):
        """
        发送 GET 请求到 Agent-Server，带 HMAC 签名

        Args:
            url: 请求 URL
            params: 查询参数
            headers: 自定义请求头
            timeout: 超时时间（秒），默认使用实例配置

        Returns:
            requests.Response: 响应对象
        """
        headers = headers.copy() if headers else {}

        ts = str(int(time.time()))
        headers["X-Timestamp"] = ts

        # GET 请求的 body 为空
        if self.shared_secret:
            sig = compute_agent_server_hmac(self.shared_secret, "GET", url, ts, b"")
            headers["X-Signature"] = sig

        return self.session.get(url, params=params, headers=headers, timeout=timeout or self.timeout)
