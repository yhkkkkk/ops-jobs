"""
Agent 管理服务
"""
import hashlib
import secrets
import string
from typing import Any, Dict, Optional

from django.db import transaction
from django.utils import timezone
from django.contrib.contenttypes.models import ContentType

from utils.audit_service import AuditLogService
from apps.hosts.models import Host
from apps.hosts.fabric_ssh_manager import fabric_ssh_manager
from .models import Agent, AgentToken, AgentInstallRecord, AgentUninstallRecord
from utils.realtime_logs import realtime_log_service
import uuid


class AgentService:
    """Agent 相关服务"""

    @staticmethod
    def _hash_token(raw: str) -> str:
        return hashlib.sha256(raw.encode('utf-8')).hexdigest()


    @classmethod
    def issue_token(cls, agent: Agent, user, expired_at=None, note: str = '') -> Dict[str, Any]:
        """签发新 token，吊销旧 token，返回明文（仅此一次）"""
        raw = secrets.token_urlsafe(32)
        token_hash = cls._hash_token(raw)
        token_last4 = raw[-4:]
        now = timezone.now()
        with transaction.atomic():
            AgentToken.objects.filter(agent=agent, revoked_at__isnull=True).update(revoked_at=now)
            AgentToken.objects.create(
                agent=agent,
                token_hash=token_hash,
                token_last4=token_last4,
                issued_by=user,
                expired_at=expired_at,
                note=note,
            )
            agent.active_token_hash = token_hash
            if agent.status == 'disabled':
                agent.status = 'offline'
            agent.save(update_fields=['active_token_hash', 'status', 'updated_at'])
        return {'token': raw, 'expired_at': expired_at, 'token_last4': token_last4}

    @staticmethod
    def revoke_active_token(agent: Agent) -> bool:
        """吊销当前有效 token"""
        now = timezone.now()
        active = AgentToken.objects.filter(agent=agent, revoked_at__isnull=True)
        if not active.exists():
            return False
        active.update(revoked_at=now)
        agent.active_token_hash = ''
        agent.save(update_fields=['active_token_hash', 'updated_at'])
        return True

    @staticmethod
    def enable_agent(agent: Agent) -> None:
        if agent.status == 'disabled':
            agent.status = 'offline'
            agent.save(update_fields=['status', 'updated_at'])

    @staticmethod
    def disable_agent(agent: Agent) -> None:
        if agent.status != 'disabled':
            agent.status = 'disabled'
            agent.save(update_fields=['status', 'updated_at'])

    @staticmethod
    def audit(user, action: str, agent: Agent, request=None, success: bool = True, error_message: str = '', extra: Optional[Dict[str, Any]] = None):
        """写审计日志"""
        extra_data = extra or {}
        
        # 处理 agent 已被删除的情况（如批量删除场景）
        try:
            # 尝试访问 agent 的属性
            if agent and hasattr(agent, 'id') and agent.id:
                resource_id = agent.id
                host_id = getattr(agent, 'host_id', None) or extra_data.get('host_id')
                try:
                    resource_name = str(agent)
                except (AttributeError, ValueError):
                    resource_name = extra_data.get('host_name', 'Unknown')
            else:
                # agent 无效或已删除，从 extra 中获取信息
                resource_id = extra_data.get('agent_id') or extra_data.get('host_id')
                host_id = extra_data.get('host_id', 'Unknown')
                resource_name = extra_data.get('host_name', 'Unknown')
        except (AttributeError, ValueError, TypeError):
            # agent 对象无效，从 extra 中获取信息
            resource_id = extra_data.get('agent_id') or extra_data.get('host_id')
            host_id = extra_data.get('host_id', 'Unknown')
            resource_name = extra_data.get('host_name', 'Unknown')
        
        description = f"{action} agent {host_id}"
        
        AuditLogService.log_action(
            user=user,
            action=action,
            description=description,
            request=request,
            success=success,
            error_message=error_message,
            resource_type=ContentType.objects.get_for_model(Agent),
            resource_id=resource_id,
            resource_name=resource_name,
            extra_data=extra_data,
        )

    @staticmethod
    def get_download_url(host: Host, package_version: str = None, package_id: int = None,
                        raise_if_not_found: bool = False, package_type: str = 'agent') -> str:
        """
        获取 Agent 安装包下载地址
        Args:
            host: 主机对象
            package_version: 安装包版本号（可选，不指定则使用默认版本）
            package_id: 安装包ID（可选，优先级最高）
        Returns:
            str: 下载地址
        Raises:
            ValueError: 如果 raise_if_not_found=True 且找不到安装包
        """
        from .models import AgentPackage
        
        # 确定操作系统和架构
        os_type = host.os_type.lower() if host.os_type else 'linux'
        if 'windows' in os_type:
            os_type = 'windows'
        elif 'darwin' in os_type or 'macos' in os_type:
            os_type = 'darwin'
        else:
            os_type = 'linux'
        
        # 默认架构为 amd64
        arch = 'amd64'
        
        # 优先使用 package_id
        if package_id:
            try:
                package = AgentPackage.objects.get(id=package_id, is_active=True)
                if package.package_type != package_type:
                    raise AgentPackage.DoesNotExist
                return package.get_download_url()
            except AgentPackage.DoesNotExist:
                if raise_if_not_found:
                    raise ValueError(f"指定的安装包 ID {package_id} 不存在或未启用（type={package_type}）")

        # 其次使用 package_version
        if package_version:
            try:
                package = AgentPackage.objects.get(
                    package_type=package_type,
                    version=package_version,
                    os_type=os_type,
                    arch=arch,
                    is_active=True
                )
                return package.get_download_url()
            except AgentPackage.DoesNotExist:
                if raise_if_not_found:
                    raise ValueError(f"指定的安装包版本 {package_version} (OS: {os_type}, Arch: {arch}, type={package_type}) 不存在或未启用")

        # 使用默认版本
        package = AgentPackage.objects.filter(
            package_type=package_type,
            is_default=True,
            is_active=True,
            os_type=os_type,
            arch=arch
        ).first()
        if package:
            return package.get_download_url()

        # 如果默认版本不存在，尝试使用最新的可用包
        package = AgentPackage.objects.filter(
            package_type=package_type,
            is_active=True,
            os_type=os_type,
            arch=arch
        ).order_by('-created_at').first()
        if package:
            return package.get_download_url()
        
        # 如果都没有且要求验证，抛出异常
        if raise_if_not_found:
            raise ValueError(f"未找到可用的 Agent 安装包 (OS: {os_type}, Arch: {arch})，请先上传安装包")
        
        return ''

    @classmethod
    def generate_install_script(cls, host: Host, agent_token: str, install_type: str = 'agent',
                                install_mode: str = 'agent-server', agent_server_url: str = '',
                                agent_server_backup_url: str = '', download_url: str = '',
                                ws_backoff_initial_ms: int = 1000, ws_backoff_max_ms: int = 30000,
                                ws_max_retries: int = 6, agent_server_listen_addr: str = '0.0.0.0:8080',
                                max_connections: int = 1000, heartbeat_timeout: int = 60,
                                package_version: str = None, package_id: int = None) -> Dict[str, str]:
        """
        生成 Agent 或 Agent-Server 安装脚本
        Args:
            host: 主机对象
            agent_token: Agent Token（用于 Agent 认证）
            install_type: 安装类型 ('agent' 或 'agent-server')
            install_mode: 安装模式 ('agent-server')
            agent_server_url: Agent-Server 地址（agent 安装需要）
            agent_server_listen_addr: Agent-Server 监听地址（agent-server 安装需要）
            max_connections: 最大连接数（agent-server 安装需要）
            heartbeat_timeout: 心跳超时（agent-server 安装需要）
            download_url: Agent 二进制下载地址
        Returns:
            Dict[str, str]: 包含不同操作系统的安装脚本
        """
        scripts = {}
        agent_server_backup_url = ''  # 备地址暂不支持，强制清空

        if install_type == 'agent':
            # Agent 安装配置
            if not agent_server_url:
                raise ValueError("agent_server_url is required for agent installation")
            ws_backoff_initial_ms = max(100, min(ws_backoff_initial_ms or 1000, 60000))
            ws_backoff_max_ms = max(1000, min(ws_backoff_max_ms or 30000, 600000))
            ws_max_retries = max(1, min(ws_max_retries or 6, 20))
        elif install_type == 'agent-server':
            # Agent-Server 安装配置
            max_connections = max(100, min(max_connections or 1000, 10000))
            heartbeat_timeout = max(30, min(heartbeat_timeout or 60, 300))
        else:
            raise ValueError(f"Unsupported install_type: {install_type}")
        
        if not download_url:
            pkg_type = 'agent' if install_type == 'agent' else 'agent-server'
            # 使用版本管理获取下载地址（生成脚本时必须验证安装包存在）
            download_url = cls.get_download_url(
                host,
                package_version=package_version,
                package_id=package_id,
                raise_if_not_found=True,
                package_type=pkg_type
            )
        
        # 根据安装类型生成不同的配置
        if install_type == 'agent':
            config_content = f"""mode: "agent-server"
agent_server_url: "{agent_server_url}"
ws_backoff_initial_ms: {ws_backoff_initial_ms}
ws_backoff_max_ms: {ws_backoff_max_ms}
ws_max_retries: {ws_max_retries}
agent_token: "{agent_token}"
host_id: {host.id}
"""
            binary_name = "ops-job-agent"
            service_name = "ops-job-agent"
            install_dir = "/opt/ops-job-agent"
        else:  # agent-server
            config_content = f"""server:
  host: "{agent_server_listen_addr.split(':')[0]}"
  port: {agent_server_listen_addr.split(':')[1]}

control_plane:
  url: "{agent_server_url or 'http://localhost:8000'}"
  token: "{agent_token}"

agent:
  max_connections: {max_connections}
  heartbeat_timeout: {heartbeat_timeout}s
  cleanup_interval: 30s

logging:
  level: "info"
  file: "logs/agent-server.log"
"""
            binary_name = "ops-job-agent-server"
            service_name = "ops-job-agent-server"
            install_dir = "/opt/ops-job-agent-server"

        # Linux 安装脚本模板（使用 config.example.yaml 作为基线，内置 python 覆盖关键参数）
        linux_tpl = """#!/bin/bash
set -e

# 配置
AGENT_TOKEN="${AGENT_TOKEN}"
INSTALL_DIR="${INSTALL_DIR}"
BINARY_NAME="${BINARY_NAME}"
SERVICE_NAME="${SERVICE_NAME}"
DOWNLOAD_URL="${DOWNLOAD_URL}"
CONFIG_DIR="$INSTALL_DIR/config"
CONFIG_FILE="$CONFIG_DIR/config.yaml"
CONFIG_EXAMPLE_SRC=""
INSTALL_TYPE="${INSTALL_TYPE}"
HOST_ID=${HOST_ID}
AGENT_SERVER_URL="${AGENT_SERVER_URL}"
WS_BACKOFF_INITIAL_MS=${WS_BACKOFF_INITIAL_MS}
WS_BACKOFF_MAX_MS=${WS_BACKOFF_MAX_MS}
WS_MAX_RETRIES=${WS_MAX_RETRIES}
AGENT_SERVER_LISTEN_ADDR="${AGENT_SERVER_LISTEN_ADDR}"
MAX_CONNECTIONS=${MAX_CONNECTIONS}
HEARTBEAT_TIMEOUT=${HEARTBEAT_TIMEOUT}
# 检查是否已安装
if systemctl is-active --quiet $SERVICE_NAME 2>/dev/null; then
    echo "Agent 服务已在运行，请先停止服务"
    exit 1
fi

# 创建安装目录
mkdir -p "$INSTALL_DIR"
cd "$INSTALL_DIR"

# 下载并解压/放置二进制与示例配置
echo "正在下载 Agent 包..."
TMP_PKG=""
if echo "$DOWNLOAD_URL" | grep -Ei "\\.zip($|\\?)" >/dev/null; then
    TMP_PKG="$(mktemp /tmp/ops-agent-pkg.XXXXXX.zip)"
    (curl -fL "$DOWNLOAD_URL" -o "$TMP_PKG" || wget -O "$TMP_PKG" "$DOWNLOAD_URL")
    unzip -o "$TMP_PKG" -d "$INSTALL_DIR"
elif echo "$DOWNLOAD_URL" | grep -Ei "\\.(tar\\.gz|tgz)($|\\?)" >/dev/null; then
    TMP_PKG="$(mktemp /tmp/ops-agent-pkg.XXXXXX.tar.gz)"
    (curl -fL "$DOWNLOAD_URL" -o "$TMP_PKG" || wget -O "$TMP_PKG" "$DOWNLOAD_URL")
    tar -xzf "$TMP_PKG" -C "$INSTALL_DIR"
else
    curl -fL -o "$INSTALL_DIR/$BINARY_NAME" "$DOWNLOAD_URL" || wget -O "$INSTALL_DIR/$BINARY_NAME" "$DOWNLOAD_URL"
fi
[ -n "$TMP_PKG" ] && rm -f "$TMP_PKG"

# 归一化二进制命名
[ -f "$INSTALL_DIR/agent" ] && mv -f "$INSTALL_DIR/agent" "$INSTALL_DIR/$BINARY_NAME"
[ -f "$INSTALL_DIR/agent-server" ] && mv -f "$INSTALL_DIR/agent-server" "$INSTALL_DIR/$BINARY_NAME"
CONFIG_EXAMPLE_SRC="$INSTALL_DIR/config.example.yaml"

chmod +x "$BINARY_NAME"

# 准备配置目录（与二进制同级的 config 目录）
mkdir -p "$CONFIG_DIR"
if [ -f "$CONFIG_FILE" ]; then
    cp "$CONFIG_FILE" "$CONFIG_FILE.$(date +%Y%m%d%H%M%S).bak"
fi
# 复制 example 作为基线（如果存在）
if [ -f "$CONFIG_EXAMPLE_SRC" ]; then
    cp "$CONFIG_EXAMPLE_SRC" "$CONFIG_FILE"
else
    : > "$CONFIG_FILE"
fi

# 使用内置 python 覆盖关键字段（无外部依赖，若缺少 PyYAML 则写 JSON 语法，YAML 兼容）
export CONFIG_FILE INSTALL_TYPE AGENT_SERVER_URL WS_BACKOFF_INITIAL_MS WS_BACKOFF_MAX_MS WS_MAX_RETRIES AGENT_TOKEN HOST_ID AGENT_SERVER_LISTEN_ADDR MAX_CONNECTIONS HEARTBEAT_TIMEOUT
python3 - <<'PY'
import json
import os

CONFIG_FILE = os.environ.get("CONFIG_FILE")
install_type = os.environ.get("INSTALL_TYPE", "agent")

override = {}
if install_type == "agent":
    override = {
        "mode": "agent-server",
        "agent_server_url": os.environ.get("AGENT_SERVER_URL", ""),
        "ws_backoff_initial_ms": int(os.environ.get("WS_BACKOFF_INITIAL_MS", "1000") or 1000),
        "ws_backoff_max_ms": int(os.environ.get("WS_BACKOFF_MAX_MS", "30000") or 30000),
        "ws_max_retries": int(os.environ.get("WS_MAX_RETRIES", "6") or 6),
        "agent_token": os.environ.get("AGENT_TOKEN", ""),
        "host_id": int(os.environ.get("HOST_ID", "0") or 0),
        "log_level": "info",
    }
else:
    listen_addr = os.environ.get("AGENT_SERVER_LISTEN_ADDR", "0.0.0.0:8080")
    host, port = "0.0.0.0", "8080"
    if ":" in listen_addr:
        host, port = listen_addr.rsplit(":", 1)
    override = {
        "server": {
            "host": host,
            "port": int(port),
        },
        "control_plane": {
            "url": os.environ.get("AGENT_SERVER_URL", "http://localhost:8000"),
            "token": os.environ.get("AGENT_TOKEN", ""),
        },
        "agent": {
            "max_connections": int(os.environ.get("MAX_CONNECTIONS", "1000") or 1000),
            "heartbeat_timeout": f"{os.environ.get('HEARTBEAT_TIMEOUT', '60')}s",
            "cleanup_interval": "30s",
        },
        "logging": {
            "level": "info",
            "file": "logs/agent-server.log",
        },
    }

try:
    import yaml  # type: ignore
except Exception:
    yaml = None

data = {}
if yaml:
    try:
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            loaded = yaml.safe_load(f) or {}
            if isinstance(loaded, dict):
                data.update(loaded)
    except Exception:
        pass

def deep_update(dst, src):
    for k, v in src.items():
        if isinstance(v, dict) and isinstance(dst.get(k), dict):
            deep_update(dst[k], v)
        else:
            dst[k] = v

deep_update(data, override)

if yaml:
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        yaml.safe_dump(data, f, allow_unicode=False, default_flow_style=False, sort_keys=False)
else:
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        f.write(json.dumps(data, indent=2))
PY

# 创建 systemd 服务
cat > /etc/systemd/system/$SERVICE_NAME.service <<EOF
[Unit]
Description=Ops Job Agent
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=$INSTALL_DIR
ExecStart=$INSTALL_DIR/$BINARY_NAME
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

# 启动服务
systemctl daemon-reload
systemctl enable $SERVICE_NAME
systemctl start $SERVICE_NAME

echo "Agent 安装成功！"
echo "服务状态: systemctl status $SERVICE_NAME"
echo "查看日志: journalctl -u $SERVICE_NAME -f"
"""

        linux_script = string.Template(linux_tpl).safe_substitute(
            AGENT_TOKEN=agent_token,
            INSTALL_DIR=install_dir,
            BINARY_NAME=binary_name,
            SERVICE_NAME=service_name,
            DOWNLOAD_URL=download_url,
            INSTALL_TYPE=install_type,
            HOST_ID=host.id,
            AGENT_SERVER_URL=agent_server_url,
            WS_BACKOFF_INITIAL_MS=ws_backoff_initial_ms,
            WS_BACKOFF_MAX_MS=ws_backoff_max_ms,
            WS_MAX_RETRIES=ws_max_retries,
            AGENT_SERVER_LISTEN_ADDR=agent_server_listen_addr,
            MAX_CONNECTIONS=max_connections,
            HEARTBEAT_TIMEOUT=heartbeat_timeout,
        )
        scripts['linux'] = linux_script

        # 目前仅输出 Linux 安装脚本（暂不支持 Windows）
        return scripts

    @classmethod
    def batch_install_agents(cls, host_ids: list, user, account_id: int = None,
                             install_type: str = 'agent', install_mode: str = 'agent-server',
                             agent_server_url: str = '', agent_server_backup_url: str = '',
                             download_url: str = '', install_task_id: str = None,
                             package_version: str = None, package_id: int = None,
                             ws_backoff_initial_ms: int = 1000, ws_backoff_max_ms: int = 30000,
                             ws_max_retries: int = 6, agent_server_listen_addr: str = '0.0.0.0:8080',
                             max_connections: int = 1000, heartbeat_timeout: int = 60,
                             ssh_timeout: int = 300, allow_reinstall: bool = False) -> Dict[str, Any]:
        """
        批量安装 Agent（通过 SSH）
        
        Args:
            host_ids: 主机ID列表
            user: 执行用户
            account_id: 用于SSH的账号ID（可选）
            install_mode: 安装模式
            agent_server_url: Agent-Server 地址
            download_url: Agent 二进制下载地址
            install_task_id: 安装任务ID（用于SSE进度推送）
        
        Returns:
            Dict[str, Any]: 安装结果
        """
        if not install_task_id:
            install_task_id = str(uuid.uuid4())
        agent_server_backup_url = ''  # 备地址暂不支持，强制清空
        
        results = []
        total = len(host_ids)
        completed = 0
        success_count = 0
        failed_count = 0
        
        install_status_prefix = "agent_install_status:"
        install_log_stream = "agent_install_logs"

        # 推送初始状态
        realtime_log_service.push_status(install_task_id, {
            'status': 'running',
            'total': total,
            'completed': 0,
            'success_count': 0,
            'failed_count': 0,
            'message': '开始批量安装 Agent'
        }, stream_prefix=install_status_prefix)
        
        # 获取主机列表
        hosts = Host.objects.filter(id__in=host_ids)
        
        for host in hosts:
            try:
                # 为所有类型的Agent创建/检查记录（agent和agent-server都需要）
                agent = None
                # 检查是否已有相同类型的在线Agent
                if hasattr(host, 'agent') and host.agent:
                    if host.agent.agent_type == install_type and host.agent.status == 'online' and not allow_reinstall:
                        results.append({
                            'host_id': host.id,
                            'host_name': host.name,
                            'success': False,
                            'message': f'该主机已有在线 {host.agent.get_agent_type_display()}（allow_reinstall=false）'
                        })
                        continue

                    # 根据安装类型设置不同的endpoint
                    endpoint = agent_server_url or ''
                    if install_type == 'agent-server':
                        # agent-server的endpoint设置为其监听地址
                        endpoint = agent_server_listen_addr or '0.0.0.0:8080'

                    agent, agent_created = Agent.objects.get_or_create(
                        host=host,
                        defaults={
                            'agent_type': install_type,
                            'status': 'pending',
                            'endpoint': endpoint,
                        }
                    )

                    if not agent_created:
                        # 如果Agent类型不同，更新类型
                        if agent.agent_type != install_type:
                            agent.agent_type = install_type
                        agent.status = 'pending'
                        # 根据安装类型设置不同的endpoint
                        if install_type == 'agent-server':
                            agent.endpoint = agent_server_listen_addr or '0.0.0.0:8080'
                        else:
                            agent.endpoint = agent_server_url or ''
                        agent.save(update_fields=['agent_type', 'status', 'endpoint', 'updated_at'])
                
                # 签发 Agent Token
                token_data = cls.issue_token(agent, user, note="Agent 安装")
                agent_token = token_data['token']
                
                # 创建或更新安装记录
                from .models import AgentInstallRecord
                install_record, created = AgentInstallRecord.objects.get_or_create(
                    host=host,
                    agent=agent,
                    status='pending',
                    defaults={
                        'install_mode': install_mode,
                        'agent_server_url': agent_server_url,
                        'agent_server_backup_url': '',
                        'ws_backoff_initial_ms': ws_backoff_initial_ms,
                        'ws_backoff_max_ms': ws_backoff_max_ms,
                        'ws_max_retries': ws_max_retries,
                        'package_id': package_id,
                        'package_version': package_version,
                        'installed_by': user,
                        'install_task_id': install_task_id,
                    }
                )
                if not created:
                    # 更新现有安装记录的配置（允许重新安装）
                    install_record.agent = agent
                    install_record.install_mode = install_mode
                    install_record.agent_server_url = agent_server_url
                    install_record.agent_server_backup_url = ''
                    install_record.ws_backoff_initial_ms = ws_backoff_initial_ms
                    install_record.ws_backoff_max_ms = ws_backoff_max_ms
                    install_record.ws_max_retries = ws_max_retries
                    install_record.package_id = package_id
                    install_record.package_version = package_version
                    install_record.status = 'pending'
                    install_record.install_task_id = install_task_id
                    install_record.save()
                
                # 生成安装脚本（使用 Agent Token）
                scripts = cls.generate_install_script(
                    host=host,
                    agent_token=agent_token,
                    install_type=install_type,
                    install_mode=install_mode,
                    agent_server_url=agent_server_url,
                    download_url=download_url,
                    ws_backoff_initial_ms=ws_backoff_initial_ms,
                    ws_backoff_max_ms=ws_backoff_max_ms,
                    ws_max_retries=ws_max_retries,
                    agent_server_listen_addr=agent_server_listen_addr,
                    max_connections=max_connections,
                    heartbeat_timeout=heartbeat_timeout,
                    package_version=package_version,
                    package_id=package_id
                )
                
                # 根据操作系统选择脚本
                os_type = host.os_type.lower() if host.os_type else 'linux'
                if 'windows' in os_type:
                    script_content = scripts.get('windows', '')
                    script_type = 'powershell'
                else:
                    script_content = scripts.get('linux', '')
                    script_type = 'shell'
                
                # 推送开始安装日志
                realtime_log_service.push_log(install_task_id, str(host.id), {
                    'host_name': host.name,
                    'host_ip': host.ip_address,
                    'log_type': 'info',
                    'content': f'开始安装 Agent 到主机 {host.name} ({host.ip_address})',
                    'step_name': '安装 Agent',
                    'step_order': 1
                }, stream_key=install_log_stream)
                
                # 通过ssh执行安装脚本
                try:
                    timeout = max(60, min(ssh_timeout or 300, 900))
                    result = fabric_ssh_manager.execute_script(
                        host=host,
                        script_content=script_content,
                        script_type=script_type,
                        timeout=timeout,
                        account_id=account_id
                    )
                    
                    config_summary = f"primary={agent_server_url or 'n/a'}, backoff_initial={ws_backoff_initial_ms}ms, backoff_max={ws_backoff_max_ms}ms, retries={ws_max_retries}"
                    if result['success']:
                        if install_type == 'agent-server':
                            install_record.status = 'success'
                            install_record.message = f'Agent-Server 安装脚本执行成功 | {config_summary}'
                        else:
                            # Agent 安装等待首次上线
                            install_record.status = 'pending'
                            install_record.message = f'安装脚本执行成功，等待 Agent 首次上线 | {config_summary}'
                        install_record.error_message = ''
                        install_record.error_detail = ''
                        success_count += 1
                        results.append({
                            'host_id': host.id,
                            'host_name': host.name,
                            'success': True,
                            'message': install_record.message
                        })
                        # 推送成功日志
                        install_target = 'Agent-Server' if install_type == 'agent-server' else 'Agent'
                        realtime_log_service.push_log(install_task_id, str(host.id), {
                            'host_name': host.name,
                            'host_ip': host.ip_address,
                            'log_type': 'info',
                            'content': f'主机 {host.name} {install_target} 安装成功 | {config_summary}',
                            'step_name': f'安装 {install_target}',
                            'step_order': 1
                        }, stream_key=install_log_stream)
                    else:
                        install_record.status = 'failed'
                        stderr = (result.get('stderr') or '').strip()
                        error_msg = stderr.splitlines()[0] if stderr else (result.get('message') or '安装失败')
                        install_record.message = f'安装脚本执行失败：{error_msg} | {config_summary}'
                        install_record.error_message = error_msg
                        install_record.error_detail = stderr or error_msg
                        failed_count += 1
                        results.append({
                            'host_id': host.id,
                            'host_name': host.name,
                            'success': False,
                            'message': install_record.message
                        })
                        # 推送失败日志
                        realtime_log_service.push_log(install_task_id, str(host.id), {
                            'host_name': host.name,
                            'host_ip': host.ip_address,
                            'log_type': 'error',
                            'content': f'主机 {host.name} Agent 安装失败: {error_msg} | {config_summary}',
                            'step_name': '安装 Agent',
                            'step_order': 1
                        }, stream_key=install_log_stream)
                    
                    install_record.save()
                    completed += 1
                    
                    # 推送进度更新
                    realtime_log_service.push_status(install_task_id, {
                        'status': 'running',
                        'total': total,
                        'completed': completed,
                        'success_count': success_count,
                        'failed_count': failed_count,
                        'message': f'已完成 {completed}/{total} 个主机的安装'
                    }, stream_prefix=install_status_prefix)
                    
                except Exception as e:
                    error_msg = f'SSH 执行失败: {str(e)}'
                    install_record.status = 'failed'
                    install_record.message = f'{error_msg} | primary={agent_server_url or "n/a"}'
                    install_record.error_message = error_msg
                    install_record.error_detail = str(e)
                    install_record.save()
                    failed_count += 1
                    
                    results.append({
                        'host_id': host.id,
                        'host_name': host.name,
                        'success': False,
                        'message': error_msg
                    })
                    
                    # 推送失败日志
                    realtime_log_service.push_log(install_task_id, str(host.id), {
                        'host_name': host.name,
                        'host_ip': host.ip_address,
                        'log_type': 'error',
                        'content': f'主机 {host.name} SSH 执行失败: {str(e)}',
                        'step_name': '安装 Agent',
                        'step_order': 1
                    }, stream_key=install_log_stream)
                    
                    completed += 1
                    
                    # 推送进度更新
                    realtime_log_service.push_status(install_task_id, {
                        'status': 'running',
                        'total': total,
                        'completed': completed,
                        'success_count': success_count,
                        'failed_count': failed_count,
                        'message': f'已完成 {completed}/{total} 个主机的安装'
                    }, stream_prefix=install_status_prefix)
                
            except Exception as e:
                failed_count += 1
                host_name = host.name if hasattr(host, 'name') else 'Unknown'
                error_msg = f'安装失败: {str(e)}'
                results.append({
                    'host_id': host.id,
                    'host_name': host_name,
                    'success': False,
                    'message': f'{error_msg} | primary={agent_server_url or "n/a"}'
                })
                
                # 推送失败日志
                realtime_log_service.push_log(install_task_id, str(host.id), {
                    'host_name': host_name,
                    'host_ip': getattr(host, 'ip_address', ''),
                    'log_type': 'error',
                    'content': f'主机 {host_name} 安装失败: {error_msg}',
                    'step_name': '安装 Agent',
                    'step_order': 1
                }, stream_key=install_log_stream)
                
                completed += 1
                
                # 推送进度更新
                realtime_log_service.push_status(install_task_id, {
                    'status': 'running',
                    'total': total,
                    'completed': completed,
                    'success_count': success_count,
                    'failed_count': failed_count,
                    'message': f'已完成 {completed}/{total} 个主机的安装'
                }, stream_prefix=install_status_prefix)
        
        # 推送最终状态
        final_status = 'completed' if failed_count == 0 else 'completed_with_errors'
        realtime_log_service.push_status(install_task_id, {
            'status': final_status,
            'total': total,
            'completed': completed,
            'success_count': success_count,
            'failed_count': failed_count,
            'message': f'批量安装完成：成功 {success_count} 个，失败 {failed_count} 个'
        }, stream_prefix=install_status_prefix)
        
        return {
            'results': results,
            'total': len(results),
            'success_count': success_count,
            'failed_count': failed_count,
            'install_task_id': install_task_id
        }

    @classmethod
    def batch_uninstall_agents(
        cls,
        agent_ids: list,
        user,
        account_id: int = None,
        uninstall_task_id: str = None,
        ssh_timeout: int = 300,
    ) -> Dict[str, Any]:
        """
        批量卸载 Agent（通过 SSH）
        - 停止/禁用 systemd 服务
        - 删除安装目录 /opt/ops-job-agent
        - 写入 AgentUninstallRecord 并通过 SSE 推送进度
        """
        if not uninstall_task_id:
            uninstall_task_id = str(uuid.uuid4())

        results = []
        total = len(agent_ids)
        completed = 0
        success_count = 0
        failed_count = 0

        realtime_log_service.push_status(uninstall_task_id, {
            'status': 'running',
            'total': total,
            'completed': 0,
            'success_count': 0,
            'failed_count': 0,
            'message': '开始批量卸载 Agent'
        })

        agents = Agent.objects.select_related('host').filter(id__in=agent_ids)

        # 卸载脚本（尽量幂等）
        uninstall_script = """#!/bin/bash
set -e

SERVICE_NAME="ops-job-agent"
INSTALL_DIR="/opt/ops-job-agent"
UNIT_FILE_1="/etc/systemd/system/${SERVICE_NAME}.service"
UNIT_FILE_2="/lib/systemd/system/${SERVICE_NAME}.service"

echo "[1/3] 停止并禁用服务（如存在）..."
if systemctl list-unit-files 2>/dev/null | grep -q "^${SERVICE_NAME}\\.service"; then
  systemctl stop "${SERVICE_NAME}" || true
  systemctl disable "${SERVICE_NAME}" || true
fi

echo "[2/3] 删除 systemd unit（如存在）..."
rm -f "${UNIT_FILE_1}" "${UNIT_FILE_2}" || true
systemctl daemon-reload || true

echo "[3/3] 清理安装目录（如存在）..."
if [ -d "${INSTALL_DIR}" ]; then
  # 备份配置（可选）
  if [ -f "${INSTALL_DIR}/config/config.yaml" ]; then
    ts=$(date +%Y%m%d%H%M%S)
    mkdir -p "/opt/ops-job-agent-backup" || true
    cp "${INSTALL_DIR}/config/config.yaml" "/opt/ops-job-agent-backup/config.yaml.${ts}.bak" || true
  fi
  rm -rf "${INSTALL_DIR}"
fi

echo "Agent 卸载完成"
"""

        for agent in agents:
            host = agent.host
            try:
                # 创建卸载记录
                uninstall_record = AgentUninstallRecord.objects.create(
                    host=host,
                    agent=agent,
                    status='pending',
                    uninstalled_by=user,
                    uninstall_task_id=uninstall_task_id,
                    message='开始卸载'
                )

                realtime_log_service.push_log(uninstall_task_id, str(host.id), {
                    'host_name': host.name,
                    'host_ip': host.ip_address,
                    'log_type': 'info',
                    'content': f'开始卸载主机 {host.name} ({host.ip_address}) 的 Agent',
                    'step_name': '卸载 Agent',
                    'step_order': 1
                })

                timeout = max(60, min(ssh_timeout or 300, 900))
                exec_result = fabric_ssh_manager.execute_script(
                    host=host,
                    script_content=uninstall_script,
                    script_type='shell',
                    timeout=timeout,
                    account_id=account_id
                )

                if exec_result.get('success'):
                    uninstall_record.status = 'success'
                    uninstall_record.message = '卸载脚本执行成功'
                    success_count += 1

                    # 安全：吊销 token，标记离线
                    try:
                        cls.revoke_active_token(agent)
                    except Exception:
                        # 不影响卸载结果
                        pass
                    try:
                        agent.status = 'offline'
                        agent.save(update_fields=['status', 'updated_at'])
                    except Exception:
                        pass

                    results.append({
                        'agent_id': agent.id,
                        'host_id': host.id,
                        'host_name': host.name,
                        'success': True,
                        'message': uninstall_record.message
                    })

                    realtime_log_service.push_log(uninstall_task_id, str(host.id), {
                        'host_name': host.name,
                        'host_ip': host.ip_address,
                        'log_type': 'info',
                        'content': f'主机 {host.name} Agent 卸载成功',
                        'step_name': '卸载 Agent',
                        'step_order': 1
                    })
                else:
                    stderr = exec_result.get('stderr') or exec_result.get('message') or '卸载失败'
                    uninstall_record.status = 'failed'
                    uninstall_record.message = stderr
                    uninstall_record.error_message = stderr
                    uninstall_record.error_detail = exec_result.get('stderr', '')
                    failed_count += 1

                    results.append({
                        'agent_id': agent.id,
                        'host_id': host.id,
                        'host_name': host.name,
                        'success': False,
                        'message': uninstall_record.message
                    })

                    realtime_log_service.push_log(uninstall_task_id, str(host.id), {
                        'host_name': host.name,
                        'host_ip': host.ip_address,
                        'log_type': 'error',
                        'content': f'主机 {host.name} Agent 卸载失败: {stderr}',
                        'step_name': '卸载 Agent',
                        'step_order': 1
                    })

                uninstall_record.save()
                completed += 1

                realtime_log_service.push_status(uninstall_task_id, {
                    'status': 'running',
                    'total': total,
                    'completed': completed,
                    'success_count': success_count,
                    'failed_count': failed_count,
                    'message': f'已完成 {completed}/{total} 个 Agent 的卸载'
                })

            except Exception as e:
                failed_count += 1
                completed += 1
                err = f'卸载失败: {str(e)}'

                try:
                    AgentUninstallRecord.objects.create(
                        host=host,
                        agent=agent,
                        status='failed',
                        uninstalled_by=user,
                        uninstall_task_id=uninstall_task_id,
                        message=err,
                        error_message=err,
                        error_detail=str(e)
                    )
                except Exception:
                    pass

                results.append({
                    'agent_id': getattr(agent, 'id', None),
                    'host_id': getattr(host, 'id', None),
                    'host_name': getattr(host, 'name', 'Unknown'),
                    'success': False,
                    'message': err
                })

                realtime_log_service.push_log(uninstall_task_id, str(getattr(host, 'id', '0')), {
                    'host_name': getattr(host, 'name', 'Unknown'),
                    'host_ip': getattr(host, 'ip_address', ''),
                    'log_type': 'error',
                    'content': f'主机 {getattr(host, "name", "Unknown")} 卸载异常: {err}',
                    'step_name': '卸载 Agent',
                    'step_order': 1
                })

                realtime_log_service.push_status(uninstall_task_id, {
                    'status': 'running',
                    'total': total,
                    'completed': completed,
                    'success_count': success_count,
                    'failed_count': failed_count,
                    'message': f'已完成 {completed}/{total} 个 Agent 的卸载'
                })

        final_status = 'completed' if failed_count == 0 else 'completed_with_errors'
        realtime_log_service.push_status(uninstall_task_id, {
            'status': final_status,
            'total': total,
            'completed': completed,
            'success_count': success_count,
            'failed_count': failed_count,
            'message': f'批量卸载完成：成功 {success_count} 个，失败 {failed_count} 个'
        })

        return {
            'results': results,
            'total': len(results),
            'success_count': success_count,
            'failed_count': failed_count,
            'uninstall_task_id': uninstall_task_id
        }
