import logging
import time

from django.core.management.base import BaseCommand

from utils.redis_stream_consumer import RedisStreamConsumer

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Consume agent logs from Redis Stream (Consumer Group)."

    def add_arguments(self, parser):
        parser.add_argument("--stream", default="agent_logs", help="Redis Stream key")
        parser.add_argument("--group", default="control-plane", help="Consumer Group name")
        parser.add_argument("--consumer", default=None, help="Consumer name (default: host-pid)")
        parser.add_argument("--dead-letter", default="agent_logs:dlq", help="Dead-letter stream key")
        parser.add_argument("--interval", type=float, default=0.2, help="Sleep seconds when no message")

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
        self.stdout.write(self.style.SUCCESS(
            f"Start consuming stream={stream}, group={group}, consumer={consumer}, dlq={dead_letter}"
        ))

        def handler(msg_id, fields):
            # 1) 转发到旧的 per-task SSE 通道（便于前端无感知继续使用）
            try:
                self._forward_to_task_stream(fields)
            except Exception as exc:  # noqa: BLE001
                logger.exception("forward agent log to task stream failed", extra={"id": msg_id})
                # 转发失败不影响 ACK，可按需要返回 False

            return True

        while True:
            rsc.read_and_process(handler)
            time.sleep(interval)

    def _forward_to_task_stream(self, fields: dict):
        """
        将统一流的日志转发到旧的 per-task Redis Stream，保持前端 SSE 无感使用。

        旧实现使用 utils.realtime_logs，Stream key 形如 job_logs:{task_id}。
        需要字段：
          - task_id: 用于定位 Stream
          - content: 日志内容
          - stream/log_type: stdout/stderr
          - timestamp: 日志时间（秒/毫秒均可作为字符串存储）
        这里用 agent_id 作为 host_id 占位。
        """
        from utils.realtime_logs import realtime_log_service

        task_id = fields.get("task_id")
        if not task_id:
            return

        log_type = fields.get("stream") or fields.get("log_type") or "stdout"
        content = fields.get("content", "")
        ts = fields.get("timestamp") or fields.get("received_at")
        agent_id = fields.get("agent_id", "")

        log_data = {
            "host_id": agent_id or "agent",
            "host_name": "",
            "host_ip": "",
            "log_type": log_type,
            "content": content,
            "step_name": "",
            "step_order": 0,
            "timestamp": ts or "",
        }
        realtime_log_service.push_log(str(task_id), str(agent_id), log_data)

