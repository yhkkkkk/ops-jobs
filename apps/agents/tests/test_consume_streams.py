import json
from unittest import mock
from datetime import datetime

import pytest
from django.test import TestCase

from apps.agents.management.commands.consume_streams import (
    Command,
    _store_log,
    _flush_log_store,
)
from apps.executor.models import ExecutionLog


class FakeRedis:
    def __init__(self):
        self.data = {}
        self.expiry = {}
        self.xadded = []

    def rpush(self, key, value):
        self.data.setdefault(key, []).append(value)

    def expire(self, key, ttl):
        self.expiry[key] = ttl

    def xadd(self, key, value):
        self.xadded.append((key, value))


class ConsumeStreamsTests(TestCase):
    def setUp(self):
        self.fake_redis = FakeRedis()

    @mock.patch("apps.agents.management.commands.consume_streams._redis_client")
    def test_store_log_writes_redis_only(self, mock_client):
        mock_client.return_value = self.fake_redis
        fields = {
            "execution_id": "123",
            "task_id": "123_main_1_abcd",
            "host_id": "1",
            "log_type": "info",
            "content": "hello",
            "timestamp": datetime.now().timestamp(),
        }
        cmd = Command()
        ok = cmd.handle_log("1-1", fields)
        self.assertTrue(ok)

        # Redis list should have one entry
        key = "agent_log_store:123"
        self.assertIn(key, self.fake_redis.data)
        stored = json.loads(self.fake_redis.data[key][0])
        self.assertEqual(stored["content"], "hello")

        # DB not written yet
        self.assertEqual(ExecutionLog.objects.count(), 0)

    @mock.patch("apps.agents.management.commands.consume_streams._redis_client")
    def test_status_bridging(self, mock_client):
        mock_client.return_value = self.fake_redis
        fields = {
            "execution_id": "789",
            "status": "running",
            "progress": "50",
        }
        cmd = Command()
        ok = cmd.handle_status("1-2", fields)
        self.assertTrue(ok)
        self.assertEqual(len(self.fake_redis.xadded), 1)
        stream, payload = self.fake_redis.xadded[0]
        self.assertTrue(stream.startswith("job_status:789"))
        self.assertEqual(payload["status"], "running")


@pytest.mark.django_db
def test_store_log_db_timestamp_parsing():
    log = {
        "execution_id": "555",
        "task_id": "t1",
        "content": "c",
        "timestamp": datetime.now().isoformat(),
    }
    # simulate flush path
    fake_redis = FakeRedis()
    fake_redis.data["agent_log_store:555"] = [json.dumps(log)]
    with mock.patch("apps.agents.management.commands.consume_streams._redis_client", return_value=fake_redis):
        _flush_log_store("555")
    assert ExecutionLog.objects.count() == 1
