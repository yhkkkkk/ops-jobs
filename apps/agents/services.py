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
from django.conf import settings

from utils.audit_service import AuditLogService
from apps.hosts.models import Host
from apps.hosts.fabric_ssh_manager import fabric_ssh_manager
from .models import Agent, AgentToken, AgentInstallRecord, AgentUninstallRecord
from utils.realtime_logs import realtime_log_service
import uuid
import base64
from pathlib import Path

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
                                package_version: str = None, package_id: int = None,
                                # 最大并发任务数
                                max_concurrent_tasks: int = None,
                                # agent-server WebSocket 配置
                                ws_handshake_timeout: str = None,
                                ws_read_buffer_size: int = None,
                                ws_write_buffer_size: int = None,
                                ws_enable_compression: bool = True,
                                ws_allowed_origins: list = None) -> Dict[str, str]:
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
            binary_name = "ops-job-agent"
            service_name = "ops-job-agent"
            install_dir = "/opt/ops-job-agent"
        else:  # agent-server
            control_plane_url = getattr(settings, "CONTROL_PLANE_URL", "") or ""
            if not control_plane_url:
                raise ValueError("CONTROL_PLANE_URL is not configured on control plane; cannot generate agent-server config")
            binary_name = "ops-job-agent-server"
            service_name = "ops-job-agent-server"
            install_dir = "/opt/ops-job-agent-server"

        # 从模板文件加载 Linux 安装脚本（模板文件位于 apps/agents/templates/linux_install.sh）
        import os as __os
        tpl_path = __os.path.join(__os.path.dirname(__file__), "templates", "linux_install.sh")
        try:
            with open(tpl_path, "r", encoding="utf-8") as tpl_f:
                linux_tpl = tpl_f.read()
        except Exception:
            # 如果模板缺失，回退为内联最小脚本（保证不会中断生成）
            linux_tpl = """#!/bin/bash
set -e
echo "安装脚本模板缺失，请检查完整性"
exit 1
"""

        # 在 control-plane 上渲染 config.yaml 并将结果 base64 编码，嵌入到安装脚本中
        # 直接调用渲染函数，避免 subprocess 在 Windows 上的兼容性问题
        config_b64 = ""
        try:
            from .tools.render_config import render_config_yaml

            # 选择对应的示例配置作为基础模板，保证完整字段
            repo_root = Path(__file__).resolve().parents[2]
            if install_type == 'agent':
                base_config_path = repo_root / "agent" / "agent-go" / "bin" / "config.example.yaml"
            else:
                base_config_path = repo_root / "agent" / "agent-server-go" / "bin" / "config.example.yaml"

            rendered_yaml = render_config_yaml(
                install_type=install_type,
                agent_token=agent_token,
                host_id=host.id,
                agent_name=host.name,
                agent_server_url=agent_server_url or "",
                control_plane_url=control_plane_url or "",
                ws_backoff_initial=ws_backoff_initial_ms,
                ws_backoff_max=ws_backoff_max_ms,
                ws_max_retries=ws_max_retries,
                agent_server_listen_addr=agent_server_listen_addr or "",
                max_connections=max_connections,
                heartbeat_timeout=heartbeat_timeout,
                # 最大并发任务数
                max_concurrent_tasks=max_concurrent_tasks,
                # agent-server WebSocket 配置
                ws_handshake_timeout=ws_handshake_timeout,
                ws_read_buffer_size=ws_read_buffer_size,
                ws_write_buffer_size=ws_write_buffer_size,
                ws_enable_compression=ws_enable_compression,
                ws_allowed_origins=ws_allowed_origins,
                base_config_path=str(base_config_path),
            )
            # base64 encode for safe insertion into shell script
            config_b64 = base64.b64encode(rendered_yaml.encode("utf-8")).decode("ascii")
        except Exception as e:
            # 让上层调用负责处理错误（例如在批量安装中会捕获并记录）
            raise RuntimeError(f"Failed to render agent config on control-plane: {e}")

        linux_script = string.Template(linux_tpl).safe_substitute(
            AGENT_TOKEN=agent_token,
            INSTALL_DIR=install_dir,
            BINARY_NAME=binary_name,
            SERVICE_NAME=service_name,
            DOWNLOAD_URL=download_url,
            INSTALL_TYPE=install_type,
            HOST_ID=host.id,
            AGENT_SERVER_URL=agent_server_url,
            CONTROL_PLANE_URL=control_plane_url if install_type == 'agent-server' else '',
            WS_BACKOFF_INITIAL_MS=ws_backoff_initial_ms,
            WS_BACKOFF_MAX_MS=ws_backoff_max_ms,
            WS_MAX_RETRIES=ws_max_retries,
            AGENT_SERVER_LISTEN_ADDR=agent_server_listen_addr,
            MAX_CONNECTIONS=max_connections,
            HEARTBEAT_TIMEOUT=heartbeat_timeout,
            CONFIG_B64=config_b64,
        )
        scripts['linux'] = linux_script

        # 目前仅输出 Linux 安装脚本（暂不支持 Windows）
        return scripts

    @classmethod
    def generate_uninstall_script(cls, agent_type: str = 'agent') -> Dict[str, str]:
        """
        生成 Agent 或 Agent-Server 卸载脚本
        Args:
            agent_type: Agent 类型 ('agent' 或 'agent-server')
        Returns:
            Dict[str, str]: 包含不同操作系统的卸载脚本
        """
        scripts = {}

        # 根据agent类型生成不同的配置
        if agent_type == 'agent':
            service_name = "ops-job-agent"
            install_dir = "/opt/ops-job-agent"
            backup_dir = "/opt/ops-job-agent-backup"
        elif agent_type == 'agent-server':
            service_name = "ops-job-agent-server"
            install_dir = "/opt/ops-job-agent-server"
            backup_dir = "/opt/ops-job-agent-server-backup"
        else:
            raise ValueError(f"Unsupported agent_type: {agent_type}")

        # 从模板文件加载 Linux 卸载脚本（模板文件位于 apps/agents/templates/linux_uninstall.sh）
        import os as __os
        tpl_path = __os.path.join(__os.path.dirname(__file__), "templates", "linux_uninstall.sh")
        try:
            with open(tpl_path, "r", encoding="utf-8") as tpl_f:
                linux_tpl = tpl_f.read()
        except Exception:
            # 如果模板缺失，回退为内联最小脚本（保证不会中断生成）
            linux_tpl = """#!/bin/bash
set -e
echo "卸载脚本模板缺失，请检查完整性"
exit 1
"""

        linux_script = string.Template(linux_tpl).safe_substitute(
            SERVICE_NAME=service_name,
            INSTALL_DIR=install_dir,
            BACKUP_DIR=backup_dir,
        )
        scripts['linux'] = linux_script

        # 目前仅输出 Linux 卸载脚本（暂不支持 Windows）
        return scripts

    @staticmethod
    def _should_fallback_to_public(result: Dict[str, Any]) -> bool:
        """判断是否应从内网IP回退到外网IP"""
        if not result or result.get('success'):
            return False

        msg_blob = f"{result.get('message', '')} {result.get('stderr', '')}".lower()
        return (
            result.get('exit_code') == -1
            or 'ssh连接失败' in msg_blob
            or 'ssh 连接失败' in msg_blob
            or 'authentication' in msg_blob
            or 'timed out' in msg_blob
            or '超时' in msg_blob
        )

    @classmethod
    def _execute_install_with_ip_fallback(
        cls,
        *,
        host: Host,
        script_content: str,
        script_type: str,
        timeout: int,
        account_id: Optional[int],
        install_task_id: str,
        log_stream_key: str,
        connection_timeout_internal: int = 5,
        connection_timeout_public: int = 10,
    ) -> Dict[str, Any]:
        """先尝试内网IP短连，失败时自动回退到外网IP执行脚本。"""
        original_internal = host.internal_ip
        original_public = host.public_ip
        candidates = []
        if original_internal:
            candidates.append(("internal", original_internal, connection_timeout_internal))
        if original_public and original_public != original_internal:
            candidates.append(("public", original_public, connection_timeout_public))

        if not candidates:
            return {
                "success": False,
                "host_id": getattr(host, "id", None),
                "host_name": getattr(host, "name", None),
                "host_ip": None,
                "stdout": "",
                "stderr": "缺少可用的SSH IP（内网/外网）",
                "exit_code": -1,
                "message": "缺少可用的SSH IP（内网/外网）",
            }

        last_result: Dict[str, Any] = {}
        try:
            for ip_type, ip, conn_timeout in candidates:
                # 设置当前尝试的IP
                if ip_type == "internal":
                    host.internal_ip = ip
                    host.public_ip = original_public
                else:
                    host.internal_ip = None
                    host.public_ip = ip

                result = fabric_ssh_manager.execute_script(
                    host=host,
                    script_content=script_content,
                    script_type=script_type,
                    timeout=timeout,
                    account_id=account_id,
                    task_id=install_task_id,
                    log_stream_key=log_stream_key,
                    connection_timeout=conn_timeout,
                )

                result["used_ip"] = ip
                result["used_ip_type"] = ip_type
                connection_info = result.get("connection_info", {}) or {}
                connection_info.update({"ssh_ip": ip, "ssh_ip_type": ip_type})
                result["connection_info"] = connection_info
                last_result = result

                if result.get("success"):
                    return result

                # 内网失败且具备外网时，记录日志并尝试外网
                if (
                    ip_type == "internal"
                    and len(candidates) > 1
                    and cls._should_fallback_to_public(result)
                ):
                    error_msg = result.get("stderr") or result.get("message") or "SSH连接失败"
                    realtime_log_service.push_log(
                        install_task_id,
                        str(host.id),
                        {
                            "host_name": host.name,
                            "host_ip": ip,
                            "log_type": "warning",
                            "content": f"内网IP {ip} SSH 连接失败，将尝试外网IP {original_public}: {error_msg}",
                            "step_name": "安装 Agent",
                            "step_order": 1,
                        },
                        stream_key=log_stream_key,
                    )
                    continue

                # 其他失败直接返回，不再尝试后续IP
                break
        finally:
            # 恢复原始IP数据，避免副作用
            host.internal_ip = original_internal
            host.public_ip = original_public

        return last_result

    @classmethod
    def batch_install_agents(cls, host_ids: list, user, account_id: int = None,
                             install_type: str = 'agent', install_mode: str = 'agent-server',
                             agent_server_url: str = '', agent_server_backup_url: str = '',
                             download_url: str = '', install_task_id: str = None,
                             package_version: str = None, package_id: int = None,
                             ws_backoff_initial_ms: int = 1000, ws_backoff_max_ms: int = 30000,
                             ws_max_retries: int = 6, agent_server_listen_addr: str = '0.0.0.0:8080',
                             max_connections: int = 1000, heartbeat_timeout: int = 60,
                             ssh_timeout: int = 300, allow_reinstall: bool = False,
                             # 最大并发任务数
                             max_concurrent_tasks: int = None,
                             # agent-server WebSocket 配置
                             ws_handshake_timeout: str = None,
                             ws_read_buffer_size: int = None,
                             ws_write_buffer_size: int = None,
                             ws_enable_compression: bool = True,
                             ws_allowed_origins: list = None) -> Dict[str, Any]:
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
        
        control_plane_url = getattr(settings, "CONTROL_PLANE_URL", "") or ""

        for host in hosts:
            try:
                # 为所有类型的Agent创建/检查记录（agent和agent-server都需要）
                agent = None
                reinstall_required = False

                # 检查是否已有Agent
                if hasattr(host, 'agent') and host.agent:
                    if host.agent.agent_type == install_type and host.agent.status == 'online':
                        if not allow_reinstall:
                            results.append({
                                'host_id': host.id,
                                'host_name': host.name,
                                'success': False,
                                'message': f'该主机已有在线 {host.agent.get_agent_type_display()}，需要允许覆盖安装才能重新安装'
                            })
                            continue
                        else:
                            reinstall_required = True

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
                
                if install_type == 'agent-server' and not control_plane_url:
                    raise ValueError("CONTROL_PLANE_URL 未配置，无法生成 Agent-Server 安装脚本")

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
                        'control_plane_url': control_plane_url if install_type == 'agent-server' else '',
                        'installed_by': user,
                        'install_task_id': install_task_id,
                        # agent-server WebSocket 配置
                        'ws_handshake_timeout': ws_handshake_timeout or '10s',
                        'ws_read_buffer_size': ws_read_buffer_size or 4096,
                        'ws_write_buffer_size': ws_write_buffer_size or 4096,
                        'ws_enable_compression': ws_enable_compression if ws_enable_compression is not None else True,
                        'ws_allowed_origins': ws_allowed_origins or [],
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
                    install_record.control_plane_url = control_plane_url if install_type == 'agent-server' else ''
                    install_record.status = 'pending'
                    install_record.install_task_id = install_task_id
                    # agent-server WebSocket 配置
                    install_record.ws_handshake_timeout = ws_handshake_timeout or '10s'
                    install_record.ws_read_buffer_size = ws_read_buffer_size or 4096
                    install_record.ws_write_buffer_size = ws_write_buffer_size or 4096
                    install_record.ws_enable_compression = ws_enable_compression if ws_enable_compression is not None else True
                    install_record.ws_allowed_origins = ws_allowed_origins or []
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
                    package_id=package_id,
                    # 最大并发任务数
                    max_concurrent_tasks=max_concurrent_tasks,
                    # agent-server WebSocket 配置
                    ws_handshake_timeout=ws_handshake_timeout,
                    ws_read_buffer_size=ws_read_buffer_size,
                    ws_write_buffer_size=ws_write_buffer_size,
                    ws_enable_compression=ws_enable_compression,
                    ws_allowed_origins=ws_allowed_origins,
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
                if install_type == 'agent-server':
                    config_summary = f"control_plane={control_plane_url or 'n/a'}, listen={agent_server_listen_addr}"
                else:
                    config_summary = f"primary={agent_server_url or 'n/a'}, backoff_initial={ws_backoff_initial_ms}ms, backoff_max={ws_backoff_max_ms}ms, retries={ws_max_retries}"
                try:
                    timeout = max(60, min(ssh_timeout or 300, 900))
                    result = cls._execute_install_with_ip_fallback(
                        host=host,
                        script_content=script_content,
                        script_type=script_type,
                        timeout=timeout,
                        account_id=account_id,
                        install_task_id=install_task_id,
                        log_stream_key=install_log_stream,
                    )
                    used_ip = result.get('used_ip') or host.ip_address
                    used_ip_type = result.get('used_ip_type') or ('internal' if host.internal_ip else 'public')
                    ip_note = f"ssh_ip={used_ip} ({used_ip_type})" if used_ip else ""
                    config_summary_with_ip = f"{config_summary} | {ip_note}" if ip_note else config_summary
                    if result['success']:
                        if install_type == 'agent-server':
                            install_record.status = 'success'
                            install_record.message = f'Agent-Server 安装脚本执行成功 | {config_summary_with_ip}'
                        else:
                            # Agent 安装等待首次上线
                            install_record.status = 'pending'
                            install_record.message = f'安装脚本执行成功，等待 Agent 首次上线 | {config_summary_with_ip}'
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
                            'host_ip': used_ip or host.ip_address,
                            'log_type': 'info',
                            'content': f'主机 {host.name} {install_target} 安装成功 | {config_summary_with_ip}',
                            'step_name': f'安装 {install_target}',
                            'step_order': 1
                        }, stream_key=install_log_stream)
                    else:
                        install_record.status = 'failed'
                        stderr = (result.get('stderr') or '').strip()
                        error_msg = stderr.splitlines()[0] if stderr else (result.get('message') or '安装失败')
                        install_record.message = f'安装脚本执行失败：{error_msg} | {config_summary_with_ip}'
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
                            'host_ip': used_ip or host.ip_address,
                            'log_type': 'error',
                            'content': f'主机 {host.name} Agent 安装失败: {error_msg} | {config_summary_with_ip}',
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
                    ip_note = f"ssh_ip={host.ip_address}" if getattr(host, 'ip_address', None) else ''
                    config_summary_with_ip = f"{config_summary} | {ip_note}" if ip_note else config_summary
                    install_record.status = 'failed'
                    install_record.message = f'{error_msg} | {config_summary_with_ip}'
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
                        'content': f'主机 {host.name} SSH 执行失败: {str(e)} | {config_summary_with_ip}',
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
                if install_type == 'agent-server':
                    config_summary = f"control_plane={control_plane_url or 'n/a'}, listen={agent_server_listen_addr}"
                else:
                    config_summary = f"primary={agent_server_url or 'n/a'}, backoff_initial={ws_backoff_initial_ms}ms, backoff_max={ws_backoff_max_ms}ms, retries={ws_max_retries}"
                ip_note = f"ssh_ip={getattr(host, 'ip_address', '')}" if getattr(host, 'ip_address', None) else ''
                config_summary_with_ip = f"{config_summary} | {ip_note}" if ip_note else config_summary
                results.append({
                    'host_id': host.id,
                    'host_name': host_name,
                    'success': False,
                    'message': f'{error_msg} | {config_summary_with_ip}'
                })
                
                # 推送失败日志
                realtime_log_service.push_log(install_task_id, str(host.id), {
                    'host_name': host_name,
                    'host_ip': getattr(host, 'ip_address', ''),
                    'log_type': 'error',
                    'content': f'主机 {host_name} 安装失败: {error_msg} | {config_summary_with_ip}',
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

        install_status_prefix = "agent_install_status:"
        install_log_stream = "agent_install_logs"

        realtime_log_service.push_status(uninstall_task_id, {
            'status': 'running',
            'total': total,
            'completed': 0,
            'success_count': 0,
            'failed_count': 0,
            'message': '开始批量卸载 Agent'
        }, stream_prefix=install_status_prefix)

        agents = Agent.objects.select_related('host').filter(id__in=agent_ids)

        for agent in agents:
            host = agent.host
            try:
                # 根据agent类型生成对应的卸载脚本
                uninstall_scripts = cls.generate_uninstall_script(agent.agent_type)
                # 根据操作系统选择脚本
                os_type = host.os_type.lower() if host.os_type else 'linux'
                if 'windows' in os_type:
                    uninstall_script = uninstall_scripts.get('windows', '')
                    script_type = 'powershell'
                else:
                    uninstall_script = uninstall_scripts.get('linux', '')
                    script_type = 'shell'

                # 创建卸载记录
                uninstall_record = AgentUninstallRecord.objects.create(
                    host=host,
                    agent=agent,
                    status='pending',
                    uninstalled_by=user,
                    uninstall_task_id=uninstall_task_id,
                    message='开始卸载'
                )

                agent_display_name = 'Agent-Server' if agent.agent_type == 'agent-server' else 'Agent'
                realtime_log_service.push_log(uninstall_task_id, str(host.id), {
                    'host_name': host.name,
                    'host_ip': host.ip_address,
                    'log_type': 'info',
                    'content': f'开始卸载主机 {host.name} ({host.ip_address}) 的 {agent_display_name}',
                    'step_name': f'卸载 {agent_display_name}',
                    'step_order': 1
                }, stream_key=install_log_stream)

                timeout = max(60, min(ssh_timeout or 300, 900))
                exec_result = fabric_ssh_manager.execute_script(
                    host=host,
                    script_content=uninstall_script,
                    script_type=script_type,
                    timeout=timeout,
                    account_id=account_id,
                    task_id=uninstall_task_id,
                    log_stream_key=install_log_stream,
                    connection_timeout=5,
                )

                if exec_result.get('success'):
                    # 保存agent信息以备后用
                    agent_id = agent.id

                    # 吊销 token，删除 agent 记录
                    try:
                        cls.revoke_active_token(agent)
                    except Exception:
                        # 不影响卸载结果
                        pass
                    try:
                        agent.delete()  # 完全删除 agent 记录
                    except Exception:
                        # 如果删除失败，至少标记为离线
                        try:
                            agent.status = 'offline'
                            agent.save(update_fields=['status', 'updated_at'])
                        except Exception:
                            pass

                    # 在删除agent后更新uninstall_record状态
                    uninstall_record.status = 'success'
                    uninstall_record.message = f'{agent_display_name} 卸载脚本执行成功'
                    success_count += 1

                    # 在删除agent之前保存uninstall_record
                    uninstall_record.save()

                    results.append({
                        'agent_id': agent_id,
                        'host_id': host.id,
                        'host_name': host.name,
                        'success': True,
                        'message': uninstall_record.message
                    })

                    realtime_log_service.push_log(uninstall_task_id, str(host.id), {
                        'host_name': host.name,
                        'host_ip': host.ip_address,
                        'log_type': 'info',
                        'content': f'主机 {host.name} {agent_display_name} 卸载成功',
                        'step_name': f'卸载 {agent_display_name}',
                        'step_order': 1
                    }, stream_key=install_log_stream)
                else:
                    stderr = exec_result.get('stderr') or exec_result.get('message') or f'{agent_display_name} 卸载失败'
                    uninstall_record.status = 'failed'
                    uninstall_record.message = stderr
                    uninstall_record.error_message = stderr
                    uninstall_record.error_detail = exec_result.get('stderr', '')
                    failed_count += 1

                    results.append({
                        'agent_id': agent.id,  # 失败情况下agent还未删除，所以可以直接使用
                        'host_id': host.id,
                        'host_name': host.name,
                        'success': False,
                        'message': uninstall_record.message
                    })

                    realtime_log_service.push_log(uninstall_task_id, str(host.id), {
                        'host_name': host.name,
                        'host_ip': host.ip_address,
                        'log_type': 'error',
                        'content': f'主机 {host.name} {agent_display_name} 卸载失败: {stderr}',
                        'step_name': f'卸载 {agent_display_name}',
                        'step_order': 1
                    }, stream_key=install_log_stream)

                    uninstall_record.save()
                    completed += 1

                realtime_log_service.push_status(uninstall_task_id, {
                    'status': 'running',
                    'total': total,
                    'completed': completed,
                    'success_count': success_count,
                    'failed_count': failed_count,
                    'message': f'已完成 {completed}/{total} 个 Agent 的卸载'
                }, stream_prefix=install_status_prefix)

            except Exception as e:
                failed_count += 1
                completed += 1
                agent_display_name = 'Agent-Server' if getattr(agent, 'agent_type', None) == 'agent-server' else 'Agent'
                err = f'{agent_display_name} 卸载失败: {str(e)}'

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
                    'content': f'主机 {getattr(host, "name", "Unknown")} {agent_display_name} 卸载异常: {err}',
                    'step_name': f'卸载 {agent_display_name}',
                    'step_order': 1
                }, stream_key=install_log_stream)

                realtime_log_service.push_status(uninstall_task_id, {
                    'status': 'running',
                    'total': total,
                    'completed': completed,
                    'success_count': success_count,
                    'failed_count': failed_count,
                    'message': f'已完成 {completed}/{total} 个 Agent 的卸载'
                }, stream_prefix=install_status_prefix)

                final_status = 'completed' if failed_count == 0 else 'completed_with_errors'
        realtime_log_service.push_status(uninstall_task_id, {
            'status': final_status,
            'total': total,
            'completed': completed,
            'success_count': success_count,
            'failed_count': failed_count,
            'message': f'批量卸载完成：成功 {success_count} 个，失败 {failed_count} 个'
        }, stream_prefix=install_status_prefix)

        return {
            'results': results,
            'total': len(results),
            'success_count': success_count,
            'failed_count': failed_count,
            'uninstall_task_id': uninstall_task_id
        }

    @classmethod
    def batch_restart_agents(cls, agent_ids: list, user, batch_task_id: str = None) -> Dict[str, Any]:
        """
        批量重启 Agent

        Args:
            agent_ids: Agent ID列表
            user: 执行用户
            batch_task_id: 批量操作任务ID（用于SSE进度推送）

        Returns:
            Dict[str, Any]: 操作结果
        """
        if not batch_task_id:
            batch_task_id = str(uuid.uuid4())

        results = []
        total = len(agent_ids)
        completed = 0
        success_count = 0
        failed_count = 0

        batch_status_prefix = "agent_batch_status:"
        batch_log_stream = "agent_batch_logs"

        # 推送初始状态
        realtime_log_service.push_status(batch_task_id, {
            'status': 'running',
            'total': total,
            'completed': 0,
            'success_count': 0,
            'failed_count': 0,
            'message': '开始批量重启 Agent'
        }, stream_prefix=batch_status_prefix)

        # 获取Agent列表
        agents = Agent.objects.filter(id__in=agent_ids).select_related('host')

        for agent in agents:
            completed += 1

            # 推送开始操作日志
            realtime_log_service.push_log(batch_task_id, str(agent.id), {
                'host_name': agent.host.name,
                'host_ip': agent.host.ip_address,
                'log_type': 'info',
                'content': f'开始重启 Agent ({agent.host.name})',
                'step_name': '重启 Agent',
                'step_order': 1
            }, stream_key=batch_log_stream)

            try:
                # 执行重启操作
                cls.control_agent(agent, 'restart', user)

                success_count += 1
                results.append({
                    'agent_id': agent.id,
                    'host_id': agent.host.id,
                    'host_name': agent.host.name,
                    'success': True,
                    'message': '重启指令已下发'
                })

                # 推送成功日志
                realtime_log_service.push_log(batch_task_id, str(agent.id), {
                    'host_name': agent.host.name,
                    'host_ip': agent.host.ip_address,
                    'log_type': 'info',
                    'content': f'Agent 重启指令下发成功 ({agent.host.name})',
                    'step_name': '重启 Agent',
                    'step_order': 1
                }, stream_key=batch_log_stream)

            except Exception as e:
                failed_count += 1
                error_msg = str(e)
                results.append({
                    'agent_id': agent.id,
                    'host_id': agent.host.id,
                    'host_name': agent.host.name,
                    'success': False,
                    'message': error_msg
                })

                # 推送失败日志
                realtime_log_service.push_log(batch_task_id, str(agent.id), {
                    'host_name': agent.host.name,
                    'host_ip': agent.host.ip_address,
                    'log_type': 'error',
                    'content': f'Agent 重启失败: {error_msg}',
                    'step_name': '重启 Agent',
                    'step_order': 1
                }, stream_key=batch_log_stream)

            # 更新进度
            realtime_log_service.push_status(batch_task_id, {
                'status': 'running',
                'total': total,
                'completed': completed,
                'success_count': success_count,
                'failed_count': failed_count,
                'message': f'已完成 {completed}/{total} 个 Agent 的重启'
            }, stream_prefix=batch_status_prefix)

        # 推送完成状态
        if failed_count == 0:
            final_status = 'completed'
            final_message = f'批量重启完成：成功 {success_count} 个'
        else:
            final_status = 'completed_with_errors'
            final_message = f'批量重启完成：成功 {success_count} 个，失败 {failed_count} 个'

        realtime_log_service.push_status(batch_task_id, {
            'status': final_status,
            'total': total,
            'completed': completed,
            'success_count': success_count,
            'failed_count': failed_count,
            'message': final_message
        }, stream_prefix=batch_status_prefix)

        return {
            'results': results,
            'total': total,
            'completed': completed,
            'success_count': success_count,
            'failed_count': failed_count,
            'batch_task_id': batch_task_id
        }

    @classmethod
    def batch_disable_agents(cls, agent_ids: list, user, batch_task_id: str = None) -> Dict[str, Any]:
        """
        批量禁用 Agent

        Args:
            agent_ids: Agent ID列表
            user: 执行用户
            batch_task_id: 批量操作任务ID（用于SSE进度推送）

        Returns:
            Dict[str, Any]: 操作结果
        """
        if not batch_task_id:
            batch_task_id = str(uuid.uuid4())

        results = []
        total = len(agent_ids)
        completed = 0
        success_count = 0
        failed_count = 0

        batch_status_prefix = "agent_batch_status:"
        batch_log_stream = "agent_batch_logs"

        # 推送初始状态
        realtime_log_service.push_status(batch_task_id, {
            'status': 'running',
            'total': total,
            'completed': 0,
            'success_count': 0,
            'failed_count': 0,
            'message': '开始批量禁用 Agent'
        }, stream_prefix=batch_status_prefix)

        # 获取Agent列表
        agents = Agent.objects.filter(id__in=agent_ids).select_related('host')

        for agent in agents:
            completed += 1

            # 推送开始操作日志
            realtime_log_service.push_log(batch_task_id, str(agent.id), {
                'host_name': agent.host.name,
                'host_ip': agent.host.ip_address,
                'log_type': 'info',
                'content': f'开始禁用 Agent ({agent.host.name})',
                'step_name': '禁用 Agent',
                'step_order': 1
            }, stream_key=batch_log_stream)

            try:
                # 执行禁用操作
                cls.disable_agent(agent)
                cls.audit(user, 'disable_agent', agent, success=True)

                success_count += 1
                results.append({
                    'agent_id': agent.id,
                    'host_id': agent.host.id,
                    'host_name': agent.host.name,
                    'success': True,
                    'message': 'Agent 已禁用'
                })

                # 推送成功日志
                realtime_log_service.push_log(batch_task_id, str(agent.id), {
                    'host_name': agent.host.name,
                    'host_ip': agent.host.ip_address,
                    'log_type': 'info',
                    'content': f'Agent 禁用成功 ({agent.host.name})',
                    'step_name': '禁用 Agent',
                    'step_order': 1
                }, stream_key=batch_log_stream)

            except Exception as e:
                failed_count += 1
                error_msg = str(e)
                results.append({
                    'agent_id': agent.id,
                    'host_id': agent.host.id,
                    'host_name': agent.host.name,
                    'success': False,
                    'message': error_msg
                })

                # 推送失败日志
                realtime_log_service.push_log(batch_task_id, str(agent.id), {
                    'host_name': agent.host.name,
                    'host_ip': agent.host.ip_address,
                    'log_type': 'error',
                    'content': f'Agent 禁用失败: {error_msg}',
                    'step_name': '禁用 Agent',
                    'step_order': 1
                }, stream_key=batch_log_stream)

            # 更新进度
            realtime_log_service.push_status(batch_task_id, {
                'status': 'running',
                'total': total,
                'completed': completed,
                'success_count': success_count,
                'failed_count': failed_count,
                'message': f'已完成 {completed}/{total} 个 Agent 的禁用'
            }, stream_prefix=batch_status_prefix)

        # 推送完成状态
        if failed_count == 0:
            final_status = 'completed'
            final_message = f'批量禁用完成：成功 {success_count} 个'
        else:
            final_status = 'completed_with_errors'
            final_message = f'批量禁用完成：成功 {success_count} 个，失败 {failed_count} 个'

        realtime_log_service.push_status(batch_task_id, {
            'status': final_status,
            'total': total,
            'completed': completed,
            'success_count': success_count,
            'failed_count': failed_count,
            'message': final_message
        }, stream_prefix=batch_status_prefix)

        return {
            'results': results,
            'total': total,
            'completed': completed,
            'success_count': success_count,
            'failed_count': failed_count,
            'batch_task_id': batch_task_id
        }

    @classmethod
    def batch_enable_agents(cls, agent_ids: list, user, batch_task_id: str = None) -> Dict[str, Any]:
        """
        批量启用 Agent

        Args:
            agent_ids: Agent ID列表
            user: 执行用户
            batch_task_id: 批量操作任务ID（用于SSE进度推送）

        Returns:
            Dict[str, Any]: 操作结果
        """
        if not batch_task_id:
            batch_task_id = str(uuid.uuid4())

        results = []
        total = len(agent_ids)
        completed = 0
        success_count = 0
        failed_count = 0

        batch_status_prefix = "agent_batch_status:"
        batch_log_stream = "agent_batch_logs"

        # 推送初始状态
        realtime_log_service.push_status(batch_task_id, {
            'status': 'running',
            'total': total,
            'completed': 0,
            'success_count': 0,
            'failed_count': 0,
            'message': '开始批量启用 Agent'
        }, stream_prefix=batch_status_prefix)

        # 获取Agent列表
        agents = Agent.objects.filter(id__in=agent_ids).select_related('host')

        for agent in agents:
            completed += 1

            # 推送开始操作日志
            realtime_log_service.push_log(batch_task_id, str(agent.id), {
                'host_name': agent.host.name,
                'host_ip': agent.host.ip_address,
                'log_type': 'info',
                'content': f'开始启用 Agent ({agent.host.name})',
                'step_name': '启用 Agent',
                'step_order': 1
            }, stream_key=batch_log_stream)

            try:
                # 执行启用操作
                cls.enable_agent(agent)
                cls.audit(user, 'enable_agent', agent, success=True)

                success_count += 1
                results.append({
                    'agent_id': agent.id,
                    'host_id': agent.host.id,
                    'host_name': agent.host.name,
                    'success': True,
                    'message': 'Agent 已启用'
                })

                # 推送成功日志
                realtime_log_service.push_log(batch_task_id, str(agent.id), {
                    'host_name': agent.host.name,
                    'host_ip': agent.host.ip_address,
                    'log_type': 'info',
                    'content': f'Agent 启用成功 ({agent.host.name})',
                    'step_name': '启用 Agent',
                    'step_order': 1
                }, stream_key=batch_log_stream)

            except Exception as e:
                failed_count += 1
                error_msg = str(e)
                results.append({
                    'agent_id': agent.id,
                    'host_id': agent.host.id,
                    'host_name': agent.host.name,
                    'success': False,
                    'message': error_msg
                })

                # 推送失败日志
                realtime_log_service.push_log(batch_task_id, str(agent.id), {
                    'host_name': agent.host.name,
                    'host_ip': agent.host.ip_address,
                    'log_type': 'error',
                    'content': f'Agent 启用失败: {error_msg}',
                    'step_name': '启用 Agent',
                    'step_order': 1
                }, stream_key=batch_log_stream)

            # 更新进度
            realtime_log_service.push_status(batch_task_id, {
                'status': 'running',
                'total': total,
                'completed': completed,
                'success_count': success_count,
                'failed_count': failed_count,
                'message': f'已完成 {completed}/{total} 个 Agent 的启用'
            }, stream_prefix=batch_status_prefix)

        # 推送完成状态
        if failed_count == 0:
            final_status = 'completed'
            final_message = f'批量启用完成：成功 {success_count} 个'
        else:
            final_status = 'completed_with_errors'
            final_message = f'批量启用完成：成功 {success_count} 个，失败 {failed_count} 个'

        realtime_log_service.push_status(batch_task_id, {
            'status': final_status,
            'total': total,
            'completed': completed,
            'success_count': success_count,
            'failed_count': failed_count,
            'message': final_message
        }, stream_prefix=batch_status_prefix)

        return {
            'results': results,
            'total': total,
            'completed': completed,
            'success_count': success_count,
            'failed_count': failed_count,
            'batch_task_id': batch_task_id
        }

    @staticmethod
    def control_agent(agent: Agent, action: str, user) -> None:
        """
        控制单个 Agent（重启等）

        Args:
            agent: Agent实例
            action: 控制动作 ('restart')
            user: 执行用户
        """
        from utils.agent_server_client import AgentServerClient
        from .execution_service import AgentExecutionService

        agent_type = agent.agent_type or 'agent'

        if agent_type == 'agent':
            # Agent 控制：通过 agent-server 下发控制指令
            server_base = agent.endpoint
            if not server_base:
                raise ValueError(f"Agent {agent.id} 未配置 agent-server 地址")

            # 如果 endpoint 只是地址，需要构建完整 URL
            if not server_base.startswith('http'):
                server_base = f"http://{server_base}"

            api_url = f"{server_base}/api/agents/{agent.host_id}/control"
            client = AgentServerClient.from_settings()

            payload = {
                "action": action,
                "reason": f"用户 {user.username} 手动{action}"
            }

            resp = client.post(api_url, json=payload, timeout=5)
            if resp.status_code != 200:
                raise ValueError(f"Agent控制失败: HTTP {resp.status_code}")

        elif agent_type == 'agent-server':
            # Agent-Server 控制：调用 agent-server 自身的控制接口
            agent_server_url = agent.endpoint
            if not agent_server_url:
                raise ValueError(f"Agent-Server {agent.id} 未配置 endpoint")

            # 如果 endpoint 只是地址，需要构建完整 URL
            if not agent_server_url.startswith('http'):
                agent_server_url = f"http://{agent_server_url}"

            api_url = f"{agent_server_url}/api/self/control"
            client = AgentServerClient.from_settings()

            payload = {
                "action": action,
                "reason": f"用户 {user.username} 手动{action}"
            }

            resp = client.post(api_url, json=payload, headers={}, timeout=5)
            if resp.status_code != 200:
                raise ValueError(f"Agent-Server控制失败: HTTP {resp.status_code}")

        else:
            raise ValueError(f"不支持的 agent_type: {agent_type}")
