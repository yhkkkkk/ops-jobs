import logging
import time
from typing import Dict, Any

from django.core.management.base import BaseCommand
from utils.redis_stream_consumer import RedisStreamConsumer
from apps.agents.execution_service import ExecutionService

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Consume agent task results from Redis Stream (agent_results) and update execution records."

    def add_arguments(self, parser):
        parser.add_argument("--stream", default="agent_results", help="Redis Stream key")
        parser.add_argument("--group", default="control-plane", help="Consumer Group name")
        parser.add_argument("--consumer", default=None, help="Consumer name (default: host-pid)")
        parser.add_argument("--dead-letter", default="agent_results:dlq", help="Dead-letter stream key")
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
            f"Start consuming results stream={stream}, group={group}, consumer={consumer}, dlq={dead_letter}"
        ))

        def handler(msg_id, fields):
            try:
                self._apply_result(fields)
                return True
            except Exception:
                logger.exception("apply result failed", extra={"id": msg_id, "fields": fields})
                return False

        while True:
            rsc.read_and_process(handler)
            time.sleep(interval)

    def _apply_result(self, fields: Dict[str, Any]):
        """
        将 agent 结果写入 ExecutionRecord/ExecutionStep。
        使用 ExecutionService.handle_task_result 统一处理逻辑，支持步骤/主机级结果：

        - task_id: 仍使用 {execution_id}_{step_id}_{host_id}_{random} 格式
        - ExecutionService 会解析出 execution_id / step_id / host_id：
          - execution_id: 映射到 ExecutionRecord
          - step_id: 若存在且 != 'main'，更新对应 ExecutionStep.status / error_message
          - host_id: 写入 / 更新 ExecutionStep.host_results 中对应主机的状态

        Redis Stream 中的字段只要包含 task_id / status / error_msg 即可，其余字段预留扩展。
        """
        task_id = fields.get("task_id")
        status = fields.get("status")
        if not task_id or not status:
            raise ValueError("task_id/status required")

        # 从 stream 字段构造与 http 回调兼容的 result 结构
        # started_at/finished_at 是 Unix 秒时间戳（int64），需要转换为 datetime
        started_at = fields.get("started_at")
        finished_at = fields.get("finished_at")
        
        result = {
            "status": status,
            "exit_code": fields.get("exit_code"),
            "error_msg": fields.get("error_msg") or "",
            "error_code": fields.get("error_code"),
            "log_size": fields.get("log_size"),
            "started_at": started_at,
            "finished_at": finished_at,
        }

        resp = ExecutionService.handle_task_result(task_id=str(task_id), result=result)
        if not resp.get("success"):
            raise ValueError(f"handle_task_result failed: {resp.get('error')}")

