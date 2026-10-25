from unittest.mock import patch

import pytest
from django.contrib.auth.models import User
from django.test import override_settings

from apps.flows.models import FlowRun, FlowTemplate
from apps.flows.notify import (
    is_safe_webhook_url,
    normalize_notify_config,
    notify_flow_run,
    should_notify,
)


pytestmark = pytest.mark.django_db


def test_normalize_notify_config_defaults():
    config = normalize_notify_config({})
    assert config["enabled"] is False
    assert config["events"] == ["success", "failed"]
    assert config["webhook_url"] == ""


def test_should_notify_requires_enabled_event_and_url():
    assert should_notify({"enabled": True, "events": ["failed"], "webhook_url": ""}, "failed") is False
    assert should_notify({"enabled": True, "events": ["failed"], "webhook_url": "http://example.com/x"}, "success") is False
    assert should_notify({"enabled": True, "events": ["failed"], "webhook_url": "http://example.com/x"}, "failed") is True
    assert should_notify({"enabled": True, "events": ["failed"], "webhook_url": "http://127.0.0.1/hook"}, "failed") is False
    assert should_notify({"enabled": True, "events": ["failed"], "webhook_url": "http://localhost/hook"}, "failed") is False


def test_is_safe_webhook_url_blocks_private_targets():
    assert is_safe_webhook_url("http://127.0.0.1/hook") is False
    assert is_safe_webhook_url("http://10.0.0.8/hook") is False
    assert is_safe_webhook_url("http://localhost/hook", resolve=False) is False
    assert is_safe_webhook_url("ftp://example.com/hook", resolve=False) is False
    assert is_safe_webhook_url("https://example.com/hook", resolve=False) is True


def test_notify_flow_run_posts_webhook_payload():
    user = User.objects.create_user("notify-user", password="pass")
    template = FlowTemplate.objects.create(
        name="notify-flow",
        created_by=user,
        notify_config={
            "enabled": True,
            "events": ["failed"],
            "webhook_url": "https://example.com/hook",
        },
    )
    flow_run = FlowRun.objects.create(
        template=template,
        name="notify-run",
        status=FlowRun.Status.FAILED,
        started_by=user,
        error_message="boom",
    )

    with patch("apps.flows.notify.post_webhook", return_value=True) as post:
        assert notify_flow_run(flow_run, "failed") is True

    payload = post.call_args.args[1]
    assert post.call_args.args[0] == "https://example.com/hook"
    assert payload["event"] == "failed"
    assert payload["flow_run"]["id"] == flow_run.id
    assert payload["executor"] == "notify-user"


@override_settings(FLOW_NOTIFY_SYNC=True)
def test_mark_finished_triggers_notify_for_failed_run():
    user = User.objects.create_user("notify-finish", password="pass")
    template = FlowTemplate.objects.create(
        name="notify-finish-flow",
        created_by=user,
        notify_config={
            "enabled": True,
            "events": ["failed"],
            "webhook_url": "https://example.com/hook",
        },
    )
    flow_run = FlowRun.objects.create(
        template=template,
        name="notify-finish-run",
        status=FlowRun.Status.RUNNING,
        started_by=user,
    )

    with patch("apps.flows.notify.post_webhook", return_value=True) as post:
        flow_run.mark_finished(FlowRun.Status.FAILED, "boom")

    assert post.called
    assert post.call_args.args[1]["event"] == "failed"


def test_post_webhook_rejects_private_ip_before_request():
    from apps.flows.notify import post_webhook

    with patch("apps.flows.notify.request.urlopen") as urlopen:
        assert post_webhook("http://127.0.0.1/hook", {"event": "failed"}) is False
        assert urlopen.called is False
