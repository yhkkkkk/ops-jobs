from datetime import timedelta

from django.db import IntegrityError, transaction
from django.utils import timezone

from .models import SchedulerLease


class SchedulerLeaseService:
    """Acquire and renew a lease that is shared by every scheduler process."""

    @staticmethod
    def acquire(name, holder, ttl_seconds, now=None):
        now = now or timezone.now()
        expires_at = now + timedelta(seconds=ttl_seconds)

        try:
            with transaction.atomic():
                lease = SchedulerLease.objects.select_for_update().filter(name=name).first()
                if lease is None:
                    SchedulerLease.objects.create(name=name, holder=holder, expires_at=expires_at)
                    return True
                if lease.holder != holder and lease.expires_at > now:
                    return False
                lease.holder = holder
                lease.expires_at = expires_at
                lease.save(update_fields=['holder', 'expires_at', 'updated_at'])
                return True
        except IntegrityError:
            # Another process inserted the lease first; it owns this acquisition attempt.
            return False

    @staticmethod
    def renew(name, holder, ttl_seconds, now=None):
        now = now or timezone.now()
        expires_at = now + timedelta(seconds=ttl_seconds)
        return SchedulerLease.objects.filter(
            name=name,
            holder=holder,
            expires_at__gt=now,
        ).update(expires_at=expires_at, updated_at=now) == 1

    @staticmethod
    def release(name, holder):
        SchedulerLease.objects.filter(name=name, holder=holder).delete()