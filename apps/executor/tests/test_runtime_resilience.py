import pytest
from unittest.mock import patch

from django.contrib.auth.models import User

from apps.executor.models import ExecutionRecord
from apps.executor.services import ExecutionRecordService


from utils.execution_id import ExecutionIDGenerator


def test_pytest_uses_local_runtime_backends(settings):
    """普通测试不应依赖外部 Redis，避免登录/权限/API 测试被网络阻塞。"""

    assert settings.CACHES["default"]["BACKEND"] == "django.core.cache.backends.locmem.LocMemCache"
    assert settings.CHANNEL_LAYERS["default"]["BACKEND"] == "channels.layers.InMemoryChannelLayer"
    assert settings.REDIS_PASSWORD in (None, "")


def test_execution_id_generator_does_not_use_cache_by_default(settings, monkeypatch):
    """默认 worker_id 生成不应依赖外部 cache，避免 Redis 不可用时阻塞。"""

    calls = {"get": 0, "set": 0}

    def _mark_get(*args, **kwargs):
        calls["get"] += 1
        return 0

    def _mark_set(*args, **kwargs):
        calls["set"] += 1
        return True


    monkeypatch.setattr("django_redis.cache.RedisCache.get", _mark_get)
    monkeypatch.setattr("django_redis.cache.RedisCache.set", _mark_set)

    generator = ExecutionIDGenerator()
    assert 0 <= generator.worker_id <= generator.MAX_WORKER_ID
    assert calls == {"get": 0, "set": 0}


@pytest.mark.django_db
def test_completed_execution_cannot_be_reopened_by_late_event():
    user = User.objects.create_user("terminal-state-user", password="pass")
    record = ExecutionRecord.objects.create(
        execution_type="quick_script",
        name="cancelled execution",
        executed_by=user,
        status="cancelled",
    )

    with patch("utils.realtime_logs.realtime_log_service.push_status"), patch(
        "utils.log_archive_service.log_archive_service.archive_execution_logs",
        return_value=True,
    ):
        ExecutionRecordService.update_execution_status(record, "running")

    record.refresh_from_db()
    assert record.status == "cancelled"


@pytest.mark.django_db
def test_agent_result_cannot_overwrite_cancelled_execution():
    from apps.agents.execution_service import AgentExecutionService

    user = User.objects.create_user("late-agent-result-user", password="pass")
    record = ExecutionRecord.objects.create(
        execution_type="quick_script",
        name="cancelled before agent result",
        executed_by=user,
        status="cancelled",
    )
    finished_at = record.finished_at

    result = AgentExecutionService.handle_task_result(
        task_id=f"{record.execution_id}_main_unknown_result",
        result={"status": "success", "finished_at": 1893456000},
        progress={"progress": 100, "success_hosts": 1},
    )

    record.refresh_from_db()
    assert result == {
        "success": True,
        "execution_record_id": record.id,
        "status": "cancelled",
        "ignored": True,
    }
    assert record.status == "cancelled"
    assert record.finished_at == finished_at
    assert record.execution_results == {}


@pytest.mark.django_db
def test_agent_result_rolls_back_record_when_step_update_fails():
    from apps.agents.execution_service import AgentExecutionService
    from apps.executor.models import ExecutionStep

    user = User.objects.create_user("agent-result-rollback-user", password="pass")
    record = ExecutionRecord.objects.create(
        execution_type="job_workflow",
        name="step result rollback",
        executed_by=user,
        status="running",
    )
    step = ExecutionStep.objects.create(
        execution_record=record,
        step_name="script",
        step_type="script",
        step_order=1,
        status="running",
    )

    with patch(
        "apps.agents.execution_service.ExecutionStep.save",
        side_effect=RuntimeError("step write failed"),
    ):
        result = AgentExecutionService.handle_task_result(
            task_id=f"{record.execution_id}_{step.id}_unknown_result",
            result={"status": "success"},
        )

    record.refresh_from_db()
    assert result["success"] is False
    assert record.status == "running"
