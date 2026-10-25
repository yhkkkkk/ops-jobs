"""Minimal SOPS-like flow notifications: webhook on selected run events."""

from __future__ import annotations

import json
import logging
from typing import Any
from urllib import error, request

from django.utils import timezone

logger = logging.getLogger(__name__)


DEFAULT_EVENTS = ("success", "failed")


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


def should_notify(config: dict, event: str) -> bool:
    if not config.get("enabled"):
        return False
    if event not in (config.get("events") or []):
        return False
    return bool(config.get("webhook_url"))


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
