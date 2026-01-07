"""Redis Stream 消费工具：支持消费组、ACK、DLQ 的简单封装。"""
from typing import Callable, Optional
import logging
import redis
from django.conf import settings


logger = logging.getLogger(__name__)


class RedisStreamConsumer:
    def __init__(
        self,
        stream_key: str,
        group: str,
        consumer_name: str,
        dead_letter_key: Optional[str] = None,
        block_ms: int = 1000,
        count: int = 10,
    ):
        self.stream_key = stream_key
        self.group = group
        self.consumer_name = consumer_name
        self.dead_letter_key = dead_letter_key
        self.block_ms = block_ms
        self.count = count

        self.redis_client = redis.Redis(
            host=getattr(settings, "REDIS_HOST", "localhost"),
            port=getattr(settings, "REDIS_PORT", 6379),
            password=getattr(settings, "REDIS_PASSWORD", None),
            db=getattr(settings, "REDIS_DB_REALTIME", 3),
            decode_responses=True,
            socket_connect_timeout=5,
            socket_timeout=5,
            retry_on_timeout=True,
        )

    def ensure_group(self):
        """创建消费组（不存在时）。"""
        try:
            self.redis_client.xgroup_create(
                name=self.stream_key,
                groupname=self.group,
                id="0",
                mkstream=True,
            )
            logger.info(
                "redis stream group created",
                extra={"stream": self.stream_key, "group": self.group},
            )
        except redis.exceptions.ResponseError as exc:
            # BUSYGROUP means already exists
            if "BUSYGROUP" in str(exc):
                return
            raise

    def _move_to_dead_letter(self, msg_id: str, fields: dict, error: str):
        if not self.dead_letter_key:
            return
        data = dict(fields)
        data["error"] = error
        data["origin_stream"] = self.stream_key
        data["origin_id"] = msg_id
        try:
            self.redis_client.xadd(self.dead_letter_key, data)
        except Exception:  # noqa: BLE001
            logger.exception("failed to write dead-letter", extra={"id": msg_id})

    def read_and_process(self, handler: Callable[[str, dict], bool]):
        """
        读取并处理消息。handler 返回 True 则 ACK；
        返回 False 或抛异常则写入 dead-letter 并保持未 ACK（由上层重试或超时重投）。
        """
        resp = self.redis_client.xreadgroup(
            groupname=self.group,
            consumername=self.consumer_name,
            streams={self.stream_key: ">"},
            count=self.count,
            block=self.block_ms,
        )

        if not resp:
            return

        for _, msgs in resp:
            for msg_id, fields in msgs:
                try:
                    ok = handler(msg_id, fields)
                    if ok:
                        self.redis_client.xack(self.stream_key, self.group, msg_id)
                    else:
                        self._move_to_dead_letter(msg_id, fields, "handler returned False")
                        # 保持未 ACK，交由重试
                except Exception as exc:  # noqa: BLE001
                    logger.exception(
                        "handler error",
                        extra={"id": msg_id, "stream": self.stream_key},
                    )
                    self._move_to_dead_letter(msg_id, fields, str(exc))
                    # 不 ACK，留待后续重试

    def reclaim_pending(
        self,
        handler: Callable[[str, dict], bool],
        idle_ms: int = 60000,
        count: int = 50,
    ) -> dict:
        """
        回收 pending 消息：
        - 读取 pending 列表（按 idle_ms 和 count 限制）
        - XCLAIM 到当前 consumer
        - 逐条调用 handler，成功 ACK，失败写 DLQ 并不 ACK（保留以便后续再 claim）
        """
        stats = {"total": 0, "claimed": 0, "acked": 0, "failed": 0}
        try:
            pending = self.redis_client.xpending_range(
                self.stream_key, self.group, "-", "+", count
            )
        except Exception as exc:
            logger.exception(
                "pending summary failed",
                extra={"stream": self.stream_key, "group": self.group},
            )
            return stats

        msgs_to_claim = []
        for item in pending:
            try:
                msg_id, consumer, last_deliver_ms, deliveries = item
                if last_deliver_ms < idle_ms:
                    continue
                msgs_to_claim.append(msg_id)
                stats["total"] += 1
            except Exception:
                continue

        if not msgs_to_claim:
            return stats

        try:
            claimed = self.redis_client.xclaim(
                name=self.stream_key,
                groupname=self.group,
                consumername=self.consumer_name,
                min_idle_time=idle_ms,
                message_ids=msgs_to_claim,
                idle=idle_ms,
            )
        except Exception as exc:
            logger.exception(
                "xclaim failed",
                extra={"stream": self.stream_key, "group": self.group, "ids": msgs_to_claim},
            )
            return stats

        stats["claimed"] = len(claimed)
        for msg_id, fields in claimed:
            try:
                ok = handler(msg_id, fields)
                if ok:
                    self.redis_client.xack(self.stream_key, self.group, msg_id)
                    stats["acked"] += 1
                else:
                    self._move_to_dead_letter(msg_id, fields, "handler returned False (reclaim)")
                    # 不 ACK，留待后续重试
            except Exception as exc:  # noqa: BLE001
                logger.exception(
                    "handler error (reclaim)",
                    extra={"id": msg_id, "stream": self.stream_key},
                )
                self._move_to_dead_letter(msg_id, fields, str(exc))
                # 不 ACK
                stats["failed"] += 1

        return stats
