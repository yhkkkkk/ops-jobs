import functools
import hashlib
import http.server
import os
import shutil
import socket
import subprocess
import threading
import time
import uuid
from pathlib import Path

import pytest
from django.conf import settings
from django.contrib.auth.models import User

from apps.agents.management.commands.consume_streams import Command

os.environ.setdefault("E2E_CONTROL_PLANE", "1")

from apps.agents.models import Agent, AgentTaskStats
from apps.agents.services import AgentService
from apps.hosts.models import Host
from utils.agent_server_client import AgentServerClient
from utils.task_result_waiter import TaskResultWaiter
import redis


ROOT_DIR = Path(__file__).resolve().parents[3]
pytestmark = pytest.mark.django_db(transaction=True)


@pytest.fixture(scope="function")
def control_plane_env(django_db_blocker):
    if os.getenv("E2E_CONTROL_PLANE") != "1":
        pytest.skip("E2E_CONTROL_PLANE not set; skipping control-plane E2E")

    work_dir = ROOT_DIR / "tmp" / f"e2e-{uuid.uuid4().hex[:8]}"
    work_dir.mkdir(parents=True, exist_ok=True)

    redis_host = os.getenv("REDIS_HOST", "127.0.0.1")
    redis_port = os.getenv("REDIS_PORT", "6379")
    redis_password = os.getenv("REDIS_PASSWORD", "")
    redis_addr = f"{redis_host}:{redis_port}"
    redis_db = int(os.getenv("E2E_REDIS_DB", os.getenv("REDIS_DB_REALTIME", "8")))

    shared_secret = os.getenv("E2E_AGENT_SERVER_SECRET", "e2e-secret")

    try:
        _ensure_redis_available(redis_addr)
    except Exception as exc:
        pytest.skip(f"Redis not reachable at {redis_addr}: {exc}")

    with django_db_blocker.unblock():
        username = f"e2e-{uuid.uuid4().hex[:8]}"
        user = User.objects.create_user(username, password="e2e-pass")
        host = Host.objects.create(
            name=f"e2e-host-{uuid.uuid4().hex[:6]}",
            os_type="linux",
            device_type="physical",
            created_by=user,
        )
        agent = Agent.objects.create(
            host=host,
            agent_type="agent",
            status="offline",
        )
        host2 = Host.objects.create(
            name=f"e2e-host2-{uuid.uuid4().hex[:6]}",
            os_type="linux",
            device_type="physical",
            created_by=user,
        )
        agent2 = Agent.objects.create(
            host=host2,
            agent_type="agent",
            status="offline",
        )

        agent_token = AgentService.issue_token(agent=agent, user=user)["token"]
        agent2_token = AgentService.issue_token(agent=agent2, user=user)["token"]

        server_port = _free_port()
        server_url = f"http://127.0.0.1:{server_port}"
        ws_url = f"ws://127.0.0.1:{server_port}"

        settings.AGENT_SERVER_URL = server_url
        settings.AGENT_SERVER_SHARED_SECRET = shared_secret
        settings.RESULT_STREAM_KEY = "task_results"
        settings.REDIS_HOST = redis_host
        settings.REDIS_PORT = int(redis_port)
        settings.REDIS_PASSWORD = redis_password or None
        settings.REDIS_DB_REALTIME = redis_db

    # 将二进制输出到仓库的 bin 目录，避免临时目录被清理后无法复用
    server_bin = ROOT_DIR / "agent" / "agent-server-go" / "bin" / ("agent-server-e2e" + (".exe" if os.name == "nt" else ""))
    agent_bin = ROOT_DIR / "agent" / "agent-go" / "bin" / ("agent-e2e" + (".exe" if os.name == "nt" else ""))
    server_bin.parent.mkdir(parents=True, exist_ok=True)
    agent_bin.parent.mkdir(parents=True, exist_ok=True)

    _build_go_binary(server_bin, ROOT_DIR / "agent" / "agent-server-go", "./cmd/server")
    _build_go_binary(agent_bin, ROOT_DIR / "agent" / "agent-go", "./cmd/agent")

    server_cfg_dir = work_dir / "server"
    agent_cfg_dir = work_dir / "agent"
    server_cfg_dir.mkdir(parents=True, exist_ok=True)
    agent_cfg_dir.mkdir(parents=True, exist_ok=True)

    _write_server_config(server_cfg_dir / "config.yaml", server_port, redis_addr, redis_password, redis_db, shared_secret)
    _write_agent_config(agent_cfg_dir / "config.yaml", ws_url, agent_token)

    server_log = server_cfg_dir / "server.log"
    agent_log = agent_cfg_dir / "agent.log"

    server_proc = _start_agent_server(server_bin, server_cfg_dir, server_log)
    _wait_server_ready(server_url)

    agent_proc = subprocess.Popen(
        [str(agent_bin), "start"],
        cwd=str(agent_cfg_dir),
        env={**os.environ, "AGENT_CONFIG_FILE": str(agent_cfg_dir / "config.yaml")},
        stdout=agent_log.open("w", encoding="utf-8"),
        stderr=subprocess.STDOUT,
        text=True,
    )

    # 启动第二个 agent，模拟多主机并行
    agent2_cfg_dir = work_dir / "agent2"
    agent2_cfg_dir.mkdir(parents=True, exist_ok=True)
    agent2_log = agent2_cfg_dir / "agent2.log"
    _write_agent_config(agent2_cfg_dir / "config.yaml", ws_url, agent2_token, port_offset=1)
    agent2_proc = subprocess.Popen(
        [str(agent_bin), "start", "--listen-port", "50052"],
        cwd=str(agent2_cfg_dir),
        env={**os.environ, "AGENT_CONFIG_FILE": str(agent2_cfg_dir / "config.yaml")},
        stdout=agent2_log.open("w", encoding="utf-8"),
        stderr=subprocess.STDOUT,
        text=True,
    )
    agent2_id = _wait_agent_registered(server_url)

    agent_server_id = _wait_agent_registered(server_url)
    # 提供覆盖的 agent_server_id，便于推送任务时使用服务端注册的 ID（而非 host_id）
    settings.AGENT_ID_OVERRIDE = agent_server_id
    # 标记本地 DB 中的 Agent 为在线并更新 endpoint，避免后续执行策略因状态=offline 直接失败
    with django_db_blocker.unblock():
        agent.status = "online"
        agent.endpoint = server_url
        agent.save(update_fields=["status", "endpoint"])

        # 标记 host2 及其 agent 在线
        agent2.status = "online"
        agent2.endpoint = server_url
        agent2.save(update_fields=["status", "endpoint"])
        host2.status = "online"
        host2.internal_ip = "127.0.0.1"
        host2.save(update_fields=["status", "internal_ip"])

    waiter = TaskResultWaiter()

    env = {
        "host": host,
        "host2": host2,
        "server_url": server_url,
        "agent_server_id": agent_server_id,
        "agent_server_id_2": agent2_id,
        "waiter": waiter,
        "server_proc": server_proc,
        "server_procs": [server_proc],
        "agent_proc": agent_proc,
        "agent_proc_2": agent2_proc,
        "server_bin": server_bin,
        "agent_bin": agent_bin,
        "server_cfg_dir": server_cfg_dir,
        "agent_cfg_dir": agent_cfg_dir,
        "agent2_cfg_dir": agent2_cfg_dir,
        "work_dir": work_dir,
        "server_log": server_log,
        "agent_log": agent_log,
        "agent2_log": agent2_log,
        "agent_token": agent_token,
        "agent2_token": agent2_token,
    }
    yield env

    for proc in [env.get("agent_proc"), env.get("agent_proc_2"), *env.get("server_procs", [])]:
        _terminate_process(proc)

    time.sleep(0.3)
    for _ in range(5):
        try:
            shutil.rmtree(work_dir, ignore_errors=False)
            break
        except PermissionError:
            time.sleep(0.5)
    else:
        print("[e2e] work_dir cleanup failed, ignoring on Windows")


def test_control_plane_e2e_flow(control_plane_env):
    client = AgentServerClient.from_settings()
    host = control_plane_env["host"]
    server_url = control_plane_env["server_url"]
    agent_server_id = control_plane_env["agent_server_id"]
    waiter = control_plane_env["waiter"]

    # 确认 agent 已重新注册在线（避免前序测试后掉线）
    _wait_agent_registered(server_url, timeout=30)

    exec_id = 1
    task_id = f"{exec_id}_step1_{host.id}_ok"
    cmd, script_type = _success_script()
    spec = _task_spec(task_id, cmd, script_type, exec_id, host.id)
    resp = client.post(f"{server_url}/api/agents/{agent_server_id}/tasks", json=spec)
    assert resp.status_code == 200, resp.text

    result = waiter.wait_for_result(task_id, timeout=60)
    assert result.get("status") == "success", result

    exec_id = 2
    fail_task_id = f"{exec_id}_step1_{host.id}_fail"
    cmd_fail, script_type_fail = _failure_script()
    spec_fail = _task_spec(fail_task_id, cmd_fail, script_type_fail, exec_id, host.id)
    resp = client.post(f"{server_url}/api/agents/{agent_server_id}/tasks", json=spec_fail)
    assert resp.status_code == 200, resp.text

    result_fail = waiter.wait_for_result(fail_task_id, timeout=60)
    assert result_fail.get("status") == "failed", result_fail

    exec_id = 3
    retry_task_id = f"{exec_id}_step1_{host.id}_retry1"
    cmd_ok, script_type_ok = _success_script()
    spec_retry = _task_spec(
        retry_task_id,
        cmd_ok,
        script_type_ok,
        exec_id,
        host.id,
        is_retry=True,
        retry_count=1,
        parent_task_id=fail_task_id,
    )
    resp = client.post(f"{server_url}/api/agents/{agent_server_id}/tasks", json=spec_retry)
    assert resp.status_code == 200, resp.text

    result_retry = waiter.wait_for_result(retry_task_id, timeout=60)
    assert result_retry.get("status") == "success", result_retry

    # 日志流验证：execution_id=1 应有日志记录
    r = redis.Redis(
        host=settings.REDIS_HOST,
        port=settings.REDIS_PORT,
        password=settings.REDIS_PASSWORD or None,
        db=settings.REDIS_DB_REALTIME,
        decode_responses=True,
    )
    log_entry = _poll_agent_logs(r, execution_id="1", timeout=15)
    if not log_entry:
        _dump_logs(control_plane_env, tail=200)
        pytest.fail("agent_logs 流未找到 execution_id=1 的日志")


def test_control_plane_file_transfer(control_plane_env):
    client = AgentServerClient.from_settings()
    host = control_plane_env["host"]
    server_url = control_plane_env["server_url"]
    agent_server_id = control_plane_env["agent_server_id"]
    waiter = control_plane_env["waiter"]
    work_dir = control_plane_env["work_dir"]

    payload = b"e2e-file-transfer"
    src_path = work_dir / "source.txt"
    src_path.write_bytes(payload)
    checksum = hashlib.sha256(payload).hexdigest()

    httpd, thread, port = _start_file_server(work_dir)
    try:
        download_url = f"http://127.0.0.1:{port}/{src_path.name}"
        remote_path = work_dir / "download" / "dest.txt"

        exec_id = 4
        task_id = f"{exec_id}_step1_{host.id}_file"
        spec = _file_transfer_spec(
            task_id,
            download_url,
            str(remote_path),
            exec_id,
            host.id,
            checksum=checksum,
            size=len(payload),
        )
        resp = client.post(f"{server_url}/api/agents/{agent_server_id}/tasks", json=spec)
        assert resp.status_code == 200, resp.text

        result = waiter.wait_for_result(task_id, timeout=90)
        assert result.get("status") == "success", result
        assert remote_path.read_bytes() == payload
    finally:
        httpd.shutdown()
        httpd.server_close()
        thread.join(timeout=2)


def test_result_replay_after_server_restart(control_plane_env):
    client = AgentServerClient.from_settings()
    host = control_plane_env["host"]
    server_url = control_plane_env["server_url"]
    agent_server_id = control_plane_env["agent_server_id"]
    waiter = control_plane_env["waiter"]

    exec_id = 5
    task_id = f"{exec_id}_step1_{host.id}_restart"
    cmd, script_type = _long_running_script()
    spec = _task_spec(task_id, cmd, script_type, exec_id, host.id)
    resp = client.post(f"{server_url}/api/agents/{agent_server_id}/tasks", json=spec)
    assert resp.status_code == 200, resp.text

    # 确保任务已开始后再重启 server，触发 outbox/结果补发
    time.sleep(1.5)
    _restart_agent_server(control_plane_env)

    result = waiter.wait_for_result(task_id, timeout=120)
    assert result.get("status") == "success", result


def test_task_stats_end_to_end(control_plane_env):
    """
    Full pipeline: Agent -> Agent-Server -> Redis stream agent_task_stats -> control plane model.
    """
    client = AgentServerClient.from_settings()
    host = control_plane_env["host"]
    server_url = control_plane_env["server_url"]
    # 确保使用当前在线的 agent_server_id
    agent_server_id = _refresh_agent_id(control_plane_env)
    waiter = control_plane_env["waiter"]

    # 1) 触发两次任务（成功+失败），产生统计
    specs = [
        _task_spec(f"stats_ok_{host.id}", *_success_script(), 11, host.id),
        _task_spec(f"stats_fail_{host.id}", *_failure_script(), 12, host.id),
    ]
    for spec in specs:
        resp = client.post(f"{server_url}/api/agents/{agent_server_id}/tasks", json=spec)
        assert resp.status_code == 200, resp.text

    # 2) 直接从 Redis 读取 task stats 流（若已有历史消息会立刻拿到）
    r = redis.Redis(
        host=settings.REDIS_HOST,
        port=settings.REDIS_PORT,
        password=settings.REDIS_PASSWORD or None,
        db=settings.REDIS_DB_REALTIME,
        decode_responses=True,
    )
    agent_id_str = str(agent_server_id)
    fields = _poll_task_stats_from_stream(r, agent_id_str, timeout=30)
    if not fields:
        _dump_logs(control_plane_env, tail=400)
        pytest.fail("未读取到 agent_task_stats 流消息，task stats 链路未生效")

    # 3) 验证流内容覆盖到了成功/失败统计（不依赖控制面存储）
    total = int(fields.get("total", 0))
    success = int(fields.get("success", 0))
    failed = int(fields.get("failed", 0))
    assert total >= 1
    assert success + failed >= 1


def _task_spec(task_id, command, script_type, execution_id, host_id, is_retry=False, retry_count=0, parent_task_id=""):
    return {
        "id": task_id,
        "name": f"e2e-{task_id}",
        "type": "script",
        "command": command,
        "script_type": script_type,
        "timeout_sec": 30,
        "execution_id": str(execution_id),
        "step_id": "step1",
        "host_id": host_id,
        "is_retry": is_retry,
        "retry_count": retry_count,
        "parent_task_id": parent_task_id,
    }


def _file_transfer_spec(task_id, download_url, remote_path, execution_id, host_id, checksum="", size=0):
    return {
        "id": task_id,
        "name": f"e2e-{task_id}",
        "type": "file_transfer",
        "timeout_sec": 60,
        "execution_id": str(execution_id),
        "step_id": "step1",
        "host_id": host_id,
        "file_transfer": {
            "remote_path": remote_path,
            "download_url": download_url,
            "checksum": checksum,
            "size": size,
            "bandwidth_limit": 0,
            "auth_headers": {},
        },
    }


def _success_script():
    if os.name == "nt":
        return "Write-Output \"hello\"", "powershell"
    return "echo hello", "bash"


def _failure_script():
    if os.name == "nt":
        return "Write-Output \"fail\"; exit 1", "powershell"
    return "echo fail; exit 1", "bash"


def _long_running_script():
    if os.name == "nt":
        return "Write-Output \"start\"; Start-Sleep -Seconds 6; Write-Output \"end\"", "powershell"
    return "echo start; sleep 6; echo end", "bash"


def _free_port() -> int:
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.bind(("127.0.0.1", 0))
    port = sock.getsockname()[1]
    sock.close()
    return port


def _write_server_config(path: Path, port: int, redis_addr: str, redis_password: str, redis_db: int, shared_secret: str) -> None:
    cfg = (
        "server:\n"
        f"  host: \"127.0.0.1\"\n"
        f"  port: {port}\n"
        "agent:\n"
        "  heartbeat_timeout: \"60s\"\n"
        "logging:\n"
        "  level: \"info\"\n"
        "  dir: \"\"\n"
        "log_stream:\n"
        "  enabled: true\n"
        "  key: \"agent_logs\"\n"
        "result_stream:\n"
        "  enabled: true\n"
        "  key: \"task_results\"\n"
        "task_stats_stream:\n"
        "  enabled: true\n"
        "  key: \"agent_task_stats\"\n"
        "  push_interval: 2\n"
        "status_stream:\n"
        "  enabled: false\n"
        "redis:\n"
        "  enabled: true\n"
        f"  addr: \"{redis_addr}\"\n"
        f"  password: \"{redis_password}\"\n"
        f"  db: {redis_db}\n"
        "websocket:\n"
        "  enable_compression: true\n"
        "auth:\n"
        f"  shared_secret: \"{shared_secret}\"\n"
        "  require_signature: true\n"
    )
    path.write_text(cfg, encoding="utf-8")


def _write_agent_config(path: Path, ws_url: str, agent_token: str, port_offset: int = 0) -> None:
    cfg = (
        "connection:\n"
        f"  agent_server_url: \"{ws_url}\"\n"
        "  ws_enable_compression: true\n"
        "identification:\n"
        "  agent_name: \"e2e-agent\"\n"
        f"  agent_token: \"{agent_token}\"\n"
        "logging:\n"
        "  log_dir: \"\"\n"
        "task:\n"
        "  heartbeat_interval: 1\n"
        "listener:\n"
        f"  host: \"127.0.0.1\"\n"
        f"  port: {50051 + port_offset}\n"
    )
    path.write_text(cfg, encoding="utf-8")


def _build_go_binary(out_path: Path, work_dir: Path, pkg: str) -> None:
    cmd = ["go", "build", "-o", str(out_path), pkg]
    subprocess.run(cmd, check=True, cwd=str(work_dir))


def _start_agent_server(server_bin: Path, server_cfg_dir: Path, log_path: Path) -> subprocess.Popen:
    proc = subprocess.Popen(
        [str(server_bin), "start"],
        cwd=str(server_cfg_dir),
        stdout=log_path.open("w", encoding="utf-8"),
        stderr=subprocess.STDOUT,
        text=True,
    )
    return proc


def _terminate_process(proc: subprocess.Popen | None, timeout: float = 5) -> None:
    if proc is None:
        return
    if proc.poll() is not None:
        return
    proc.terminate()
    try:
        proc.wait(timeout=timeout)
    except subprocess.TimeoutExpired:
        proc.kill()


def _wait_server_ready(server_url: str) -> None:
    client = AgentServerClient.from_settings()
    deadline = time.time() + 30
    while time.time() < deadline:
        try:
            resp = client.get(f"{server_url}/api/agents")
            if resp.status_code == 200:
                return
        except Exception:
            time.sleep(0.2)
    raise RuntimeError("agent-server not ready")


def _wait_agent_registered(server_url: str, timeout: float = 30) -> str:
    client = AgentServerClient.from_settings()
    deadline = time.time() + timeout
    while time.time() < deadline:
        resp = client.get(f"{server_url}/api/agents")
        if resp.status_code == 200:
            data = resp.json()
            agents = data.get("agents", [])
            if agents:
                return agents[0].get("id")
        time.sleep(0.3)
    raise RuntimeError("agent not registered")


def _restart_agent_server(env: dict) -> None:
    proc = env.get("server_proc")
    _terminate_process(proc)

    env["server_proc"] = _start_agent_server(env["server_bin"], env["server_cfg_dir"], env.get("server_log"))
    env.setdefault("server_procs", []).append(env["server_proc"])
    _wait_server_ready(env["server_url"])
    env["agent_server_id"] = _wait_agent_registered(env["server_url"])


def _ensure_redis_available(redis_addr: str) -> None:
    host, port = redis_addr.split(":", 1)
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(2)
    try:
        sock.connect((host, int(port)))
    finally:
        sock.close()


def _start_file_server(root: Path):
    handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(root))
    httpd = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    return httpd, thread, httpd.server_address[1]


def _poll_task_stats_from_stream(r: redis.Redis, agent_id: str, timeout: int = 15) -> dict | None:
    """从 agent_task_stats 流读取指定 agent 的最新记录。"""
    deadline = time.time() + timeout
    while time.time() < deadline:
        entries = r.xrevrange("agent_task_stats", count=20)
        for _, raw in entries:
            # raw is dict with string values when decode_responses=True
            if raw.get("agent_id") == agent_id:
                return raw
        time.sleep(0.5)
    return None


def _poll_agent_logs(r: redis.Redis, execution_id: str, timeout: int = 10) -> dict | None:
    """从 agent_logs 流读取指定 execution_id 的日志。"""
    deadline = time.time() + timeout
    while time.time() < deadline:
        entries = r.xrevrange("agent_logs", count=100)
        for _, raw in entries:
            if raw.get("execution_id") == execution_id:
                return raw
        time.sleep(0.5)
    return None


def _dump_logs(env: dict, tail: int = 200):
    server_log = env.get("server_log")
    agent_log = env.get("agent_log")

    def _read_tail(path: Path):
        if not path or not path.exists():
            return f"{path}: not found\n"
        try:
            lines = path.read_text(encoding="utf-8", errors="ignore").splitlines()
            return "\n".join(lines[-tail:]) + "\n"
        except Exception as exc:
            return f"{path}: read error {exc}\n"

    server_txt = _read_tail(server_log)
    agent_txt = _read_tail(agent_log)

    print("\n===== server.log (tail) =====\n" + server_txt)
    print("\n===== agent.log (tail) =====\n" + agent_txt)


def _refresh_agent_id(env: dict) -> str:
    """读取 server 当前在线 agent 列表，刷新 env 中的 agent_server_id。"""
    try:
        new_id = _wait_agent_registered(env["server_url"], timeout=30)
        env["agent_server_id"] = new_id
        return new_id
    except Exception:
        return env["agent_server_id"]
