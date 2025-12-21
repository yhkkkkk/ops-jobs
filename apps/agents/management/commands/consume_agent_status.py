import logging
import time
from typing import Dict, Any
from datetime import datetime, timezone as dt_timezone

from django.core.management.base import BaseCommand
from django.utils import timezone

from utils.redis_stream_consumer import RedisStreamConsumer
from apps.agents.models import Agent

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Consume agent status heartbeat from Redis Stream (agent_status) and update Agent model."

    def add_arguments(self, parser):
        parser.add_argument("--stream", default="agent_status", help="Redis Stream key")
        parser.add_argument("--group", default="control-plane", help="Consumer Group name")
        parser.add_argument("--consumer", default=None, help="Consumer name (default: host-pid)")
        parser.add_argument("--dead-letter", default="agent_status:dlq", help="Dead-letter stream key")
        parser.add_argument("--interval", type=float, default=0.5, help="Sleep seconds when no message")

    def handle(self, *args, **options):
        stream = options["stream"]
        group = options["group"]
        consumer = options["consumer"]
        dead_letter = options["dead_letter"]
        interval = options["interval"]

        if not consumer:
            import os

            consumer = f"{os.uname().nodename}-{os.getpid()}"

        rsc = RedisStreamConsumer(
            stream_key=stream,
            group=group,
            consumer_name=consumer,
            dead_letter_key=dead_letter,
            block_ms=1000,
            count=100,
        )

        rsc.ensure_group()
        self.stdout.write(
            self.style.SUCCESS(
                f"Start consuming status stream={stream}, group={group}, consumer={consumer}, dlq={dead_letter}"
            )
        )

        def handler(msg_id, fields):
            try:
                self._apply_status(fields)
                return True
            except Exception:
                logger.exception("apply status failed", extra={"id": msg_id, "fields": fields})
                return False

        while True:
            rsc.read_and_process(handler)
            time.sleep(interval)

    def _apply_status(self, fields: Dict[str, Any]):
        """
        将 agent 状态写入 Agent 模型：
          - 依据 agent_id 关联 Agent（通过 Host.agent 绑定）
          - 更新 status（online/offline）、last_heartbeat_at

        约定字段：
          - agent_id: agent-server 侧的 Agent ID（当前通过 Host.agent.endpoint 映射，后续可显式存）
          - status: online/offline
          - last_heartbeat: 毫秒时间戳（可为空，默认使用当前时间）
        """
        agent_id = fields.get("agent_id")
        status = fields.get("status")

        if not agent_id or not status:
            raise ValueError("agent_id/status required")

        # 这里假设 Agent.endpoint 中存放了 agent-server 注册时的 agent_id
        try:
            agent = Agent.objects.select_related("host").get(endpoint=agent_id)
        except Agent.DoesNotExist:
            # 没有关联上的情况下暂时忽略（可能是还未在控制面注册等）
            logger.debug("agent not found for status update", extra={"agent_id": agent_id})
            return

        # 映射状态
        mapped_status = "online" if status == "online" else "offline"

        # 更新时间
        ts_ms = fields.get("last_heartbeat")
        if isinstance(ts_ms, (int, float)):
            dt = datetime.fromtimestamp(float(ts_ms) / 1000.0, tz=dt_timezone.utc)
        else:
            dt = timezone.now()

        # 仅在状态变化或时间更新时写入，避免无意义写 DB
        changed = False
        if agent.status != mapped_status:
            agent.status = mapped_status
            changed = True

        if not agent.last_heartbeat_at or dt > agent.last_heartbeat_at:
            agent.last_heartbeat_at = dt
            changed = True

        if changed:
            agent.save(update_fields=["status", "last_heartbeat_at", "updated_at"])
            logger.info(
                "agent status updated",
                extra={
                    "agent_id": agent_id,
                    "db_id": agent.id,
                    "status": mapped_status,
                    "last_heartbeat_at": agent.last_heartbeat_at.isoformat(),
                },
            )
            try:
                # update cache to reflect fresh heartbeat
                from apps.agents.status import set_agent_status_cache

                set_agent_status_cache(agent.id, mapped_status)
            except Exception:
                pass


