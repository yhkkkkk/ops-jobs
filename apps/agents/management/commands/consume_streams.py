import json
import logging
import os
import socket
import uuid
import time
from datetime import datetime
from django.utils import timezone

from django.conf import settings
from django.core.management.base import BaseCommand

from utils.log_consumer_service import StreamConsumerService, StreamConfig
from apps.agents.execution_service import AgentExecutionService
from apps.agents.models import Agent, AgentTaskStats
from apps.executor.models import ExecutionLog
import redis


logger = logging.getLogger(__name__)

# redis 存储日志的默认过期时间（30 天）
LOG_STORE_TTL_SECONDS = 30 * 24 * 60 * 60


class Command(BaseCommand):
    help = "单进程消费 Agent 日志/结果/状态 redis streams。"

    def add_arguments(self, parser):
        parser.add_argument("--log-stream", default=getattr(settings, "LOG_STREAM_KEY", "agent_logs"))
        parser.add_argument("--log-group", default=getattr(settings, "LOG_STREAM_GROUP", "control-plane"))
        parser.add_argument("--result-stream", default=getattr(settings, "RESULT_STREAM_KEY", "agent_results"))
        parser.add_argument("--result-group", default=getattr(settings, "RESULT_STREAM_GROUP", "control-plane"))
        parser.add_argument("--status-stream", default=getattr(settings, "STATUS_STREAM_KEY", "agent_status"))
        parser.add_argument("--status-group", default=getattr(settings, "STATUS_STREAM_GROUP", "control-plane"))
        parser.add_argument("--agent-status-stream", default=getattr(settings, "AGENT_STATUS_STREAM_KEY", "agent_status"))
        parser.add_argument("--agent-status-group", default=getattr(settings, "AGENT_STATUS_STREAM_GROUP", "control-plane"))
        parser.add_argument("--task-stats-stream", default=getattr(settings, "TASK_STATS_STREAM_KEY", "agent_task_stats"))
        parser.add_argument("--task-stats-group", default=getattr(settings, "TASK_STATS_STREAM_GROUP", "control-plane"))
        parser.add_argument("--count", type=int, default=100)
        parser.add_argument("--block-ms", type=int, default=1000)
        parser.add_argument("--reclaim-interval", type=int, default=60)
        parser.add_argument("--reclaim-idle-ms", type=int, default=60000)
        parser.add_argument("--reclaim-count", type=int, default=50)

    def handle(self, *args, **options):
        consumer_name = self._consumer_name()
        count = options["count"]
        block_ms = options["block_ms"]
        reclaim_interval = options["reclaim_interval"]
        reclaim_idle_ms = options["reclaim_idle_ms"]
        reclaim_count = options["reclaim_count"]

        configs = []

        log_stream = options["log_stream"]
        if log_stream:
            configs.append(
                StreamConfig(
                    stream_key=log_stream,
                    group=options["log_group"],
                    consumer_name=consumer_name,
                    handler=self.handle_log,
                    dead_letter_key=f"{log_stream}:dlq",
                    count=count,
                    block_ms=block_ms,
                    reclaim_idle_ms=reclaim_idle_ms,
                    reclaim_count=reclaim_count,
                )
            )

        result_stream = options["result_stream"]
        if result_stream:
            configs.append(
                StreamConfig(
                    stream_key=result_stream,
                    group=options["result_group"],
                    consumer_name=consumer_name,
                    handler=self.handle_result,
                    dead_letter_key=f"{result_stream}:dlq",
                    count=count,
                    block_ms=block_ms,
                    reclaim_idle_ms=reclaim_idle_ms,
                    reclaim_count=reclaim_count,
                )
            )

        status_stream = options["status_stream"]
        # status_stream 不再独立消费，进度信息从 agent_results 中聚合计算

        agent_status_stream = options["agent_status_stream"]
        if agent_status_stream:
            configs.append(
                StreamConfig(
                    stream_key=agent_status_stream,
                    group=options["agent_status_group"],
                    consumer_name=consumer_name,
                    handler=self.handle_agent_status,
                    dead_letter_key=f"{agent_status_stream}:dlq",
                    count=count,
                    block_ms=block_ms,
                    reclaim_idle_ms=reclaim_idle_ms,
                    reclaim_count=reclaim_count,
                )
            )

        # 添加任务统计流处理
        task_stats_stream = options["task_stats_stream"]
        if task_stats_stream:
            configs.append(
                StreamConfig(
                    stream_key=task_stats_stream,
                    group=options["task_stats_group"],
                    consumer_name=consumer_name,
                    handler=self.handle_agent_task_stats,
                    dead_letter_key=f"{task_stats_stream}:dlq",
                    count=count,
                    block_ms=block_ms,
                    reclaim_idle_ms=reclaim_idle_ms,
                    reclaim_count=reclaim_count,
                )
            )

        if not configs:
            self.stdout.write(self.style.WARNING("No streams configured; exiting."))
            return

        service = StreamConsumerService(
            configs=configs,
            reclaim_interval_sec=reclaim_interval,
        )
        self.stdout.write(
            self.style.SUCCESS(
                f"启动统一消费者: streams={len(configs)}, consumer={consumer_name}"
            )
        )
        service.start()

    @staticmethod
    def _consumer_name():
        hostname = socket.gethostname()
        pid = os.getpid()
        return f"{hostname}-{pid}-{uuid.uuid4().hex[:6]}"

    @staticmethod
    def handle_log(msg_id: str, fields: dict) -> bool:
        try:
            # 使用 execution_id 作为主要标识符
            execution_id = fields.get("execution_id")
            if not execution_id:
                logger.warning("log message missing execution_id", extra={"id": msg_id})
                return True  # 不阻塞

            normalized = {
                "id": msg_id,
                "timestamp": fields.get("timestamp") or time.time(),
                "execution_id": execution_id,
                "task_id": fields.get("task_id"),  # 可选，用于复杂工作流
                "host_id": fields.get("host_id"),
                "host_name": fields.get("host_name"),
                "host_ip": fields.get("host_ip"),
                "log_type": fields.get("log_type") or fields.get("stream") or "info",
                "content": fields.get("content") or "",
                "step_name": fields.get("step_name"),
                "step_order": _maybe_int(fields.get("step_order")) or 0,
                "step_id": fields.get("step_id"),
                "agent_id": fields.get("agent_id"),
                "received_at": time.time(),
            }
            _store_log(normalized)
            return True
        except Exception as exc:
            logger.exception("处理日志消息失败", extra={"id": msg_id, "error": str(exc)})
            return False

    @staticmethod
    def handle_result(msg_id: str, fields: dict) -> bool:
        """
        处理 agent_results stream 中的任务结果消息。
        提取结果基础字段和进度字段，并更新任务状态。
        """
        try:
            # 使用 execution_id 作为主要标识符
            execution_id = fields.get("execution_id")
            if not execution_id:
                logger.warning("result message missing execution_id", extra={"id": msg_id})
                return True  # 不阻塞

            # 提取结果基础字段
            result_payload = {
                "status": fields.get("status"),
                "exit_code": _maybe_int(fields.get("exit_code")),
                "error_msg": fields.get("error_msg"),
                "error_code": fields.get("error_code"),
                "log_size": _maybe_int(fields.get("log_size")),
                "log_pointer": fields.get("log_pointer"),
                "started_at": _maybe_int(fields.get("started_at")),
                "finished_at": _maybe_int(fields.get("finished_at")),
            }

            # 提取进度字段（从 agent_results stream 中的聚合计算结果）
            progress_payload = {
                "execution_id": execution_id,
                "progress": _maybe_int(fields.get("progress")),
                "total_hosts": _maybe_int(fields.get("total_hosts")),
                "success_hosts": _maybe_int(fields.get("success_hosts")),
                "failed_hosts": _maybe_int(fields.get("failed_hosts")),
                "running_hosts": _maybe_int(fields.get("running_hosts")),
                "pending_hosts": _maybe_int(fields.get("pending_hosts")),
            }

            # 先将redis日志缓存批量刷入db
            _flush_log_store(execution_id=str(execution_id))

            # 调用处理服务，传入结果和进度
            resp = AgentExecutionService.handle_task_result(
                execution_id=str(execution_id),
                result=result_payload,
                progress=progress_payload
            )

            return bool(resp.get("success"))
        except Exception as exc:
            logger.exception("处理结果消息失败", extra={"id": msg_id, "error": str(exc)})
            return False

    @staticmethod
    def handle_agent_status(msg_id: str, fields: dict) -> bool:
        """
        处理Agent状态流消息（心跳）
        """
        try:
            # 获取Agent ID
            agent_id = fields.get("agent_id") or fields.get("id")
            if not agent_id:
                logger.warning("Agent状态消息缺少agent_id", extra={"msg_id": msg_id, "fields": fields})
                return True  # 不阻塞处理

            # 查找 Agent
            try:
                agent = Agent.objects.get(id=int(agent_id))
            except (Agent.DoesNotExist, ValueError):
                logger.warning("Agent状态更新失败：Agent不存在", extra={"msg_id": msg_id, "agent_id": agent_id})
                return True

            # 解析时间戳
            timestamp = fields.get("timestamp") or fields.get("last_heartbeat") or timezone.now()
            if isinstance(timestamp, (int, float)):
                timestamp = datetime.fromtimestamp(timestamp, tz=timezone.get_current_timezone())
            elif isinstance(timestamp, str) and timestamp.endswith('Z'):
                timestamp = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
                if timezone.is_naive(timestamp):
                    timestamp = timezone.make_aware(timestamp)

            # 更新 Agent 状态
            new_status = fields.get("status", "online")
            if new_status in ['online', 'offline', 'pending', 'disabled']:
                agent.status = new_status
                agent.last_heartbeat_at = timestamp
                agent.last_error_code = fields.get("error_code") or ""
                agent.save(update_fields=['status', 'last_heartbeat_at', 'last_error_code', 'updated_at'])

            logger.debug("更新Agent状态", extra={
                "msg_id": msg_id,
                "agent_id": agent_id,
                "status": new_status,
                "timestamp": timestamp.isoformat()
            })

            return True

        except Exception as exc:
            logger.exception("处理Agent状态消息失败", extra={"msg_id": msg_id, "error": str(exc)})
            return False

    @staticmethod
    def handle_agent_task_stats(msg_id: str, fields: dict) -> bool:
        """
        处理 Agent 任务统计流消息

        消息格式:
        {
            'agent_id': str,
            'total': int,
            'success': int,
            'failed': int,
            'cancelled': int,
            'avg_duration_ms': float,
            'success_rate': float,
            'timestamp': int,  # Unix timestamp in milliseconds
        }
        """
        try:
            agent_id = fields.get('agent_id')
            if not agent_id:
                logger.warning("任务统计消息缺少agent_id", extra={"msg_id": msg_id, "fields": fields})
                return True  # 不阻塞处理

            # 查找 Agent
            try:
                agent = Agent.objects.get(id=int(agent_id))
            except (Agent.DoesNotExist, ValueError):
                logger.warning(f"Agent {agent_id} not found, skipping task_stats", extra={"msg_id": msg_id})
                return True  # 返回 True 避免重试

            # 更新或创建统计记录
            stats, created = AgentTaskStats.objects.update_or_create(
                agent=agent,
                defaults={
                    'total_tasks': int(fields.get('total', 0)),
                    'success_tasks': int(fields.get('success', 0)),
                    'failed_tasks': int(fields.get('failed', 0)),
                    'cancelled_tasks': int(fields.get('cancelled', 0)),
                    'avg_duration_ms': float(fields.get('avg_duration_ms', 0)),
                }
            )

            logger.debug("保存Agent任务统计", extra={
                "msg_id": msg_id,
                "agent_id": agent_id,
                "total": stats.total_tasks,
                "success": stats.success_tasks,
                "failed": stats.failed_tasks,
                "cancelled": stats.cancelled_tasks,
                "success_rate": stats.success_rate,
            })

            return True

        except Exception as exc:
            logger.exception("处理Agent任务统计消息失败", extra={"msg_id": msg_id, "error": str(exc)})
            return False


def _maybe_int(value):
    try:
        if value is None:
            return None
        return int(value)
    except Exception:
        return value


def _redis_client():
    return redis.Redis(
        host=getattr(settings, "REDIS_HOST", "localhost"),
        port=getattr(settings, "REDIS_PORT", 6379),
        password=getattr(settings, "REDIS_PASSWORD", None),
        db=getattr(settings, "REDIS_DB_REALTIME", 3),
        decode_responses=True,
        socket_connect_timeout=5,
        socket_timeout=5,
        retry_on_timeout=True,
    )


def _store_log(log: dict):
    """将日志追加到每个执行的redis列表中，设置TTL以避免丢弃。"""
    exec_id = log.get("execution_id")
    if not exec_id:
        return
    key_prefix = getattr(settings, "LOG_STORE_PREFIX", "agent_log_store:")
    key = f"{key_prefix}{exec_id}"
    rc = _redis_client()
    rc.rpush(key, json.dumps(log, ensure_ascii=False))
    rc.expire(key, getattr(settings, "LOG_STORE_TTL", LOG_STORE_TTL_SECONDS))


def _store_log_db(log: dict):
    try:
        ts = log.get("timestamp")
        ts_dt = None
        if ts:
            try:
                ts_dt = datetime.fromtimestamp(float(ts), tz=timezone.utc)
            except Exception:
                try:
                    ts_dt = datetime.fromisoformat(str(ts))
                except Exception:
                    ts_dt = None
        ts_dt = ts_dt or timezone.now()

        execution_id = int(log.get("execution_id"))
        task_id = str(log.get("task_id") or "")
        host_id = _maybe_int(log.get("host_id"))
        step_name = log.get("step_name") or ""
        step_order = _maybe_int(log.get("step_order")) or 0
        log_type = log.get("log_type") or "info"
        content = log.get("content") or ""

        ExecutionLog.objects.create(
            execution_id=execution_id,
            task_id=task_id,
            host_id=host_id,
            step_name=step_name,
            step_order=step_order,
            log_type=log_type,
            content=content,
            timestamp=ts_dt,
        )
    except Exception as exc:
        logger.exception("存储日志到db失败", extra={"error": str(exc)})


def _flush_log_store(task_id: str):
    """读取缓存的redis列表，批量插入到ExecutionLog。"""
    if not task_id:
        return
    prefix = getattr(settings, "LOG_STORE_PREFIX", "agent_log_store:")
    key = f"{prefix}{task_id}"
    rc = _redis_client()
    try:
        entries = rc.lrange(key, 0, -1)
        if not entries:
            return
        objs = []
        for raw in entries:
            try:
                log = json.loads(raw)
            except Exception:
                continue
            ts = log.get("timestamp")
            ts_dt = None
            if ts:
                try:
                    ts_dt = datetime.fromtimestamp(float(ts), tz=timezone.utc)
                except Exception:
                    try:
                        ts_dt = datetime.fromisoformat(str(ts))
                    except Exception:
                        ts_dt = None
            ts_dt = ts_dt or timezone.now()
            objs.append(
                ExecutionLog(
                    execution_id=int(log.get("execution_id")),
                    task_id=str(log.get("task_id") or ""),
                    host_id=_maybe_int(log.get("host_id")),
                    step_name=log.get("step_name") or "",
                    step_order=_maybe_int(log.get("step_order")) or 0,
                    log_type=log.get("log_type") or "info",
                    content=log.get("content") or "",
                    timestamp=ts_dt,
                )
            )
        if objs:
            batch_size = getattr(settings, "LOG_DB_BULK_BATCH", 500)
            ExecutionLog.objects.bulk_create(objs, batch_size=batch_size)
        rc.delete(key)
    except Exception as exc:
        logger.exception("刷新日志缓存到db失败", extra={"task_id": task_id, "error": str(exc)})
