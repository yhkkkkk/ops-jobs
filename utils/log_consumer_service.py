"""
统一的 Redis Stream 消费服务：多流共享生命周期，定期回收 pending，支持 DLQ。
"""
from dataclasses import dataclass
import logging
import threading
import time
from typing import Callable, List, Optional

from utils.redis_stream_consumer import RedisStreamConsumer

logger = logging.getLogger(__name__)


Handler = Callable[[str, dict], bool]


@dataclass
class StreamConfig:
    stream_key: str
    group: str
    consumer_name: str
    handler: Handler
    dead_letter_key: Optional[str] = None
    block_ms: int = 1000
    count: int = 100
    reclaim_idle_ms: int = 60000
    reclaim_count: int = 50


class StreamConsumerService:
    """在单进程内运行多个 Redis Stream 消费者。"""

    def __init__(
        self,
        configs: List[StreamConfig],
        reclaim_interval_sec: int = 60,
        sleep_on_error_sec: int = 2,
    ):
        self.configs = configs
        self.reclaim_interval_sec = reclaim_interval_sec
        self.sleep_on_error_sec = sleep_on_error_sec
        self._stop_event = threading.Event()
        self._threads: List[threading.Thread] = []

    def start(self):
        """Start consuming all configured streams."""
        if not self.configs:
            logger.warning("No stream configs provided; nothing to consume")
            return

        for cfg in self.configs:
            t = threading.Thread(
                target=self._run_stream, args=(cfg,), daemon=True
            )
            t.start()
            self._threads.append(t)
            logger.info(
                "Started consumer thread",
                extra={"stream": cfg.stream_key, "group": cfg.group, "consumer": cfg.consumer_name},
            )

        try:
            while not self._stop_event.is_set():
                time.sleep(1)
        except KeyboardInterrupt:
            logger.info("Received KeyboardInterrupt, stopping consumers")
        finally:
            self.stop()

    def stop(self):
        """Signal stop to all workers."""
        self._stop_event.set()
        for t in self._threads:
            t.join(timeout=5)

    def _run_stream(self, cfg: StreamConfig):
        consumer = RedisStreamConsumer(
            stream_key=cfg.stream_key,
            group=cfg.group,
            consumer_name=cfg.consumer_name,
            dead_letter_key=cfg.dead_letter_key,
            block_ms=cfg.block_ms,
            count=cfg.count,
        )
        consumer.ensure_group()
        last_reclaim = time.time()

        while not self._stop_event.is_set():
            try:
                consumer.read_and_process(cfg.handler)
            except Exception as exc:  # noqa: BLE001
                logger.exception(
                    "Stream consume error",
                    extra={
                        "stream": cfg.stream_key,
                        "group": cfg.group,
                        "consumer": cfg.consumer_name,
                        "error": str(exc),
                    },
                )
                time.sleep(self.sleep_on_error_sec)

            now = time.time()
            if now - last_reclaim >= self.reclaim_interval_sec:
                try:
                    stats = consumer.reclaim_pending(
                        handler=cfg.handler,
                        idle_ms=cfg.reclaim_idle_ms,
                        count=cfg.reclaim_count,
                    )
                    logger.info(
                        "pending reclaim",
                        extra={
                            "stream": cfg.stream_key,
                            "group": cfg.group,
                            "claimed": stats.get("claimed"),
                            "acked": stats.get("acked"),
                            "failed": stats.get("failed"),
                            "total_pending_checked": stats.get("total"),
                        },
                    )
                except Exception as exc:  # noqa: BLE001
                    logger.exception(
                        "Pending reclaim error",
                        extra={
                            "stream": cfg.stream_key,
                            "group": cfg.group,
                            "error": str(exc),
                        },
                    )
                last_reclaim = now

        logger.info(
            "Consumer thread stopped",
            extra={"stream": cfg.stream_key, "group": cfg.group, "consumer": cfg.consumer_name},
        )
