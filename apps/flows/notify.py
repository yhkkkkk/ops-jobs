"""Minimal SOPS-like flow notifications: webhook on selected run events."""

from __future__ import annotations

import ipaddress
import json
import logging
import socket
import threading
from typing import Any
from urllib import error, request
from urllib.parse import urlparse

from django.conf import settings
from django.db import transaction
from django.utils import timezone

logger = logging.getLogger(__name__)


DEFAULT_EVENTS = ("success", "failed")
BLOCKED_HOSTNAMES = {
    "localhost",
    "localhost.localdomain",
    "metadata.google.internal",
    "metadata",
}


def normalize_notify_config(raw: Any) -> dict:
    config = raw if isinstance(raw, dict) else {}
    events = config.get("events")
    if not isinstance(events, list) or not events:
        events = list(DEFAULT_EVENTS)
    events = [str(item).strip() for item in events if str(item).strip()]
    return {
        "enabled": bool(config.get("enabled")),
        "events": events,
        "webhook_url": str(config.get("webhook_url") or "").strip(),
    }


def _is_public_ip(ip: ipaddress.IPv4Address | ipaddress.IPv6Address) -> bool:
    return not (
        ip.is_private
        or ip.is_loopback
        or ip.is_link_local
        or ip.is_reserved
        or ip.is_multicast
        or ip.is_unspecified
    )


def is_safe_webhook_url(url: str, *, resolve: bool = True) -> bool:
    """Block SSRF: http(s) only, no credentials, no private/link-local targets."""
    raw = str(url or "").strip()
    if not raw or len(raw) > 2048:
        return False
    try:
        parsed = urlparse(raw)
    except Exception:
        return False
    if parsed.scheme not in ("https", "http"):
        return False
    if parsed.username or parsed.password:
        return False
    hostname = (parsed.hostname or "").strip().lower()
    if not hostname or hostname in BLOCKED_HOSTNAMES:
        return False
    if hostname.endswith(".local") or hostname.endswith(".internal"):
        return False
    try:
        ip = ipaddress.ip_address(hostname)
        return _is_public_ip(ip)
    except ValueError:
        pass
    if not resolve:
        return True
    try:
        infos = socket.getaddrinfo(hostname, parsed.port or None, type=socket.SOCK_STREAM)
    except socket.gaierror:
        return False
    if not infos:
        return False
    for info in infos:
        sockaddr = info[4]
        if not sockaddr:
            return False
        try:
            ip = ipaddress.ip_address(sockaddr[0])
        except ValueError:
            return False
        if not _is_public_ip(ip):
            return False
    return True


def should_notify(config: dict, event: str) -> bool:
    if not config.get("enabled"):
        return False
    if event not in (config.get("events") or []):
        return False
    url = config.get("webhook_url") or ""
    if not url:
        return False
    # Shape check only here; DNS/private check happens at post time.
    return is_safe_webhook_url(url, resolve=False)


def build_payload(flow_run, event: str) -> dict:
    template = getattr(flow_run, "template", None)
    return {
        "event": event,
        "sent_at": timezone.now().isoformat(),
        "flow_run": {
            "id": flow_run.id,
            "name": flow_run.name,
            "status": flow_run.status,
            "trigger_type": flow_run.trigger_type,
            "error_message": flow_run.error_message or "",
            "started_at": flow_run.started_at.isoformat() if flow_run.started_at else None,
            "finished_at": flow_run.finished_at.isoformat() if flow_run.finished_at else None,
        },
        "template": {
            "id": getattr(template, "id", None),
            "name": getattr(template, "name", ""),
        },
        "executor": getattr(getattr(flow_run, "started_by", None), "username", "") or "",
    }


def post_webhook(url: str, payload: dict, timeout: float = 5.0) -> bool:
    if not is_safe_webhook_url(url, resolve=True):
        logger.warning("flow notify rejected unsafe webhook url")
        return False
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = request.Request(
        url,
        data=body,
        headers={"Content-Type": "application/json; charset=utf-8"},
        method="POST",
    )
    try:
        with request.urlopen(req, timeout=timeout) as resp:
            return 200 <= getattr(resp, "status", 0) < 300
    except error.URLError as exc:
        logger.warning("flow notify webhook failed: %s", exc)
        return False
    except Exception as exc:  # pragma: no cover - defensive
        logger.warning("flow notify webhook error: %s", exc)
        return False


def notify_flow_run(flow_run, event: str) -> bool:
    template = getattr(flow_run, "template", None)
    if template is None and getattr(flow_run, "template_id", None):
        from .models import FlowTemplate

        template = FlowTemplate.objects.filter(pk=flow_run.template_id).first()
        if template is not None:
            flow_run.template = template
    config = normalize_notify_config(getattr(template, "notify_config", None))
    if not should_notify(config, event):
        return False
    payload = build_payload(flow_run, event)
    return post_webhook(config["webhook_url"], payload)


def _notify_by_id(flow_run_id: int, event: str) -> None:
    from .models import FlowRun

    flow_run = (
        FlowRun.objects.select_related("template", "started_by")
        .filter(pk=flow_run_id)
        .first()
    )
    if not flow_run:
        return
    notify_flow_run(flow_run, event)


def _spawn_notify(fn) -> None:
    if getattr(settings, "FLOW_NOTIFY_SYNC", False):
        fn()
        return
    threading.Thread(target=fn, daemon=True).start()


def schedule_notify_flow_run(flow_run, event: str) -> None:
    """Fire webhook after DB commit, off the request/runner thread by default."""
    flow_run_id = getattr(flow_run, "pk", None)
    if not flow_run_id:
        return

    def _emit():
        try:
            _notify_by_id(flow_run_id, event)
        except Exception:
            logger.exception("flow notify failed for run=%s event=%s", flow_run_id, event)

    # Sync mode skips on_commit so pytest atomic wrappers still see the hook.
    if getattr(settings, "FLOW_NOTIFY_SYNC", False):
        _emit()
        return
    transaction.on_commit(lambda: _spawn_notify(_emit))
