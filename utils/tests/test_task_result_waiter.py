import time
from typing import Any, Dict, List, Tuple

from utils.task_result_waiter import TaskResultWaiter


class FakeRedisStream:
    def __init__(
        self,
        initial_messages: List[Tuple[str, Dict[str, Any]]],
        future_messages: List[Tuple[str, Dict[str, Any]]] = None,
    ):
        self.messages = list(initial_messages)
        self.future_messages = list(future_messages or [])
        self._future_emitted = False

    @staticmethod
    def _parse_stream_id(stream_id: str) -> Tuple[int, int]:
        ms, seq = str(stream_id).split("-", 1)
        return int(ms), int(seq)

    def ping(self):
        return True

    def xrevrange(self, key, max="+", min="-", count=None):
        max_id = (float("inf"), float("inf")) if max == "+" else self._parse_stream_id(max)
        min_id = (-1, -1) if min == "-" else self._parse_stream_id(min)

        filtered = []
        for msg_id, data in self.messages:
            mid = self._parse_stream_id(msg_id)
            if min_id <= mid <= max_id:
                filtered.append((msg_id, data))

        filtered.sort(key=lambda item: self._parse_stream_id(item[0]), reverse=True)
        if count is not None:
            filtered = filtered[:count]
        return filtered

    def xread(self, streams, count=100, block=0):
        stream_key, last_id = next(iter(streams.items()))
        last_tuple = self._parse_stream_id(last_id)

        if self.future_messages and not self._future_emitted:
            self.messages.extend(self.future_messages)
            self._future_emitted = True

        new_messages = [
            (msg_id, data)
            for msg_id, data in self.messages
            if self._parse_stream_id(msg_id) > last_tuple
        ]
        new_messages.sort(key=lambda item: self._parse_stream_id(item[0]))
        if count is not None:
            new_messages = new_messages[:count]

        if not new_messages:
            return []
        return [(stream_key, new_messages)]


def test_wait_for_result_ignores_old_same_task_history():
    now_ms = int(time.time() * 1000)
    old_id = f"{now_ms - 60000}-0"

    redis_client = FakeRedisStream(
        initial_messages=[
            (old_id, {"task_id": "task-old", "status": "success", "exit_code": "0"}),
        ]
    )

    waiter = TaskResultWaiter(redis_client=redis_client, stream_key="task_results")
    result = waiter.wait_for_result("task-old", timeout=1, poll_interval=0.01)

    assert result["status"] == "timeout"
    assert result["success"] is False


def test_wait_for_result_prefetches_recent_result():
    now_ms = int(time.time() * 1000)
    recent_id = f"{now_ms - 1000}-0"

    redis_client = FakeRedisStream(
        initial_messages=[
            (recent_id, {"task_id": "task-recent", "status": "success", "exit_code": "0"}),
        ]
    )

    waiter = TaskResultWaiter(redis_client=redis_client, stream_key="task_results")
    result = waiter.wait_for_result("task-recent", timeout=1, poll_interval=0.01)

    assert result["status"] == "success"
    assert result["success"] is True


def test_wait_for_result_prefers_new_result_after_snapshot():
    now_ms = int(time.time() * 1000)
    old_id = f"{now_ms - 60000}-0"
    new_id = f"{now_ms + 100}-0"

    redis_client = FakeRedisStream(
        initial_messages=[
            (old_id, {"task_id": "task-race", "status": "failed", "exit_code": "1"}),
        ],
        future_messages=[
            (new_id, {"task_id": "task-race", "status": "success", "exit_code": "0"}),
        ],
    )

    waiter = TaskResultWaiter(redis_client=redis_client, stream_key="task_results")
    result = waiter.wait_for_result("task-race", timeout=2, poll_interval=0.01)

    assert result["status"] == "success"
    assert result["success"] is True
    assert result["exit_code"] == 0
