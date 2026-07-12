from datetime import timedelta

import pytest
from django.utils import timezone

from apps.scheduler.lease import SchedulerLeaseService


pytestmark = pytest.mark.django_db


def test_scheduler_lease_is_exclusive_until_it_expires():
    now = timezone.now()

    assert SchedulerLeaseService.acquire("scheduler", "owner-a", 60, now=now) is True
    assert SchedulerLeaseService.acquire("scheduler", "owner-b", 60, now=now + timedelta(seconds=30)) is False
    assert SchedulerLeaseService.acquire("scheduler", "owner-b", 60, now=now + timedelta(seconds=61)) is True


def test_scheduler_lease_owner_can_renew_without_allowing_takeover():
    now = timezone.now()

    assert SchedulerLeaseService.acquire("scheduler", "owner-a", 60, now=now) is True
    assert SchedulerLeaseService.renew("scheduler", "owner-a", 60, now=now + timedelta(seconds=30)) is True
    assert SchedulerLeaseService.acquire("scheduler", "owner-b", 60, now=now + timedelta(seconds=61)) is False
    assert SchedulerLeaseService.renew("scheduler", "owner-b", 60, now=now + timedelta(seconds=31)) is False