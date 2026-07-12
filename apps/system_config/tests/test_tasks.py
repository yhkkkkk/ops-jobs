import uuid
from datetime import timedelta
from unittest.mock import patch

import pytest
from django.contrib.auth.models import User
from django.utils import timezone

from apps.executor.models import ExecutionRecord
from apps.hosts.models import Host
from apps.system_config.tasks import check_system_health, cleanup_old_execution_logs


pytestmark = pytest.mark.django_db


def _execution(user, status, name):
    return ExecutionRecord.objects.create(
        execution_type="quick_script",
        name=name,
        status=status,
        executed_by=user,
    )


def test_cleanup_old_execution_logs_deletes_all_terminal_execution_states():
    user = User.objects.create_user(f"cleanup-{uuid.uuid4().hex[:6]}", password="pass")
    old_success = _execution(user, "success", "old-success")
    old_failed = _execution(user, "failed", "old-failed")
    old_cancelled = _execution(user, "cancelled", "old-cancelled")
    old_timeout = _execution(user, "timeout", "old-timeout")
    old_running = _execution(user, "running", "old-running")
    cutoff = timezone.now() - timedelta(days=31)
    ExecutionRecord.objects.filter(
        id__in=[old_success.id, old_failed.id, old_cancelled.id, old_timeout.id, old_running.id]
    ).update(created_at=cutoff)

    with patch("apps.system_config.tasks.ConfigManager.get", return_value=30):
        result = cleanup_old_execution_logs()

    assert result["success"] is True
    assert not ExecutionRecord.objects.filter(
        id__in=[old_success.id, old_failed.id, old_cancelled.id, old_timeout.id]
    ).exists()
    assert ExecutionRecord.objects.filter(id=old_running.id).exists()


def test_system_health_uses_host_status_field_and_reports_warning_threshold():
    user = User.objects.create_user(f"health-{uuid.uuid4().hex[:6]}", password="pass")
    Host.objects.create(
        name=f"online-{uuid.uuid4().hex[:6]}",
        os_type="linux",
        device_type="physical",
        status="online",
        created_by=user,
    )
    Host.objects.create(
        name=f"offline-{uuid.uuid4().hex[:6]}",
        os_type="linux",
        device_type="physical",
        status="offline",
        created_by=user,
    )

    result = check_system_health()

    assert result["status"] == "warning"
    assert result["total_hosts"] == 2
    assert result["online_hosts"] == 1
    assert result["hosts_online_rate"] == 50