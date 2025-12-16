"""
Agent 管理服务
"""
import hashlib
import secrets
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
        AuditLogService.log_action(
            user=user,
            action=action,
            description=f"{action} agent {agent.host_id}",
            request=request,
            success=success,
            error_message=error_message,
            resource_type=ContentType.objects.get_for_model(agent),
            resource_id=agent.id,
            resource_name=str(agent),
            extra_data=extra or {},
        )

    @staticmethod
    def get_download_url(host: Host, package_version: str = None, package_id: int = None, raise_if_not_found: bool = False) -> str:
        """
        获取 Agent 安装包下载地址
        Args:
            host: 主机对象
            package_version: 安装包版本号（可选，不指定则使用默认版本）
            package_id: 安装包ID（可选，优先级最高）
            raise_if_not_found: 如果找不到安装包是否抛出异常（默认 False，返回默认 URL）
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
                return package.get_download_url()
            except AgentPackage.DoesNotExist:
                if raise_if_not_found:
                    raise ValueError(f"指定的安装包 ID {package_id} 不存在或未启用")
        
        # 其次使用 package_version
        if package_version:
            try:
                package = AgentPackage.objects.get(
                    version=package_version,
                    os_type=os_type,
                    arch=arch,
                    is_active=True
                )
                return package.get_download_url()
            except AgentPackage.DoesNotExist:
                if raise_if_not_found:
                    raise ValueError(f"指定的安装包版本 {package_version} (OS: {os_type}, Arch: {arch}) 不存在或未启用")
        
        # 使用默认版本
        package = AgentPackage.objects.filter(
            is_default=True,
            is_active=True,
            os_type=os_type,
            arch=arch
        ).first()
        if package:
            return package.get_download_url()
        
        # 如果都没有且要求验证，抛出异常
        if raise_if_not_found:
            raise ValueError(f"未找到可用的 Agent 安装包 (OS: {os_type}, Arch: {arch})，请先上传安装包")
        
        # 如果都没有，使用配置中的默认地址（向后兼容，但不推荐）
        from apps.system_config.models import ConfigManager
        base_url = ConfigManager.get('agent.download_url', 'http://localhost:8000/static/agent/')
        if os_type == 'windows':
            return f"{base_url}ops-job-agent-windows-amd64.exe"
        else:
            return f"{base_url}ops-job-agent-linux-amd64"

    @classmethod
    def generate_install_script(cls, host: Host, token: str, install_mode: str = 'agent-server',
                                agent_server_url: str = '', agent_server_backup_url: str = '',
                                download_url: str = '', ws_backoff_initial_ms: int = 1000,
                                ws_backoff_max_ms: int = 30000, ws_max_retries: int = 6,
                                package_version: str = None, package_id: int = None) -> Dict[str, str]:
        """
        生成 Agent 安装脚本
        Args:
            host: 主机对象
            token: Agent Token
            install_mode: 安装模式 ('direct' 或 'agent-server')
            agent_server_url: Agent-Server 地址（agent-server 模式需要）
            download_url: Agent 二进制下载地址
        Returns:
            Dict[str, str]: 包含不同操作系统的安装脚本
        """
        scripts = {}
        
        # agent-server 模式必须显式提供主地址
        if install_mode == 'agent-server' and not agent_server_url:
            raise ValueError("agent_server_url is required in agent-server mode")
        agent_server_backup_url = agent_server_backup_url or ''
        # clamp retry params to safe bounds
        ws_backoff_initial_ms = max(100, min(ws_backoff_initial_ms or 1000, 60000))
        ws_backoff_max_ms = max(1000, min(ws_backoff_max_ms or 30000, 600000))
        ws_max_retries = max(1, min(ws_max_retries or 6, 20))
        
        if not download_url:
            # 使用版本管理获取下载地址（生成脚本时必须验证安装包存在）
            download_url = cls.get_download_url(host, package_version=package_version, package_id=package_id, raise_if_not_found=True)
        
        # Linux 安装脚本
        linux_script = f"""#!/bin/bash
set -e

# 配置
AGENT_SERVER_URL="{agent_server_url}"
AGENT_SERVER_BACKUP_URL="{agent_server_backup_url}"
WS_BACKOFF_INITIAL_MS="{ws_backoff_initial_ms}"
WS_BACKOFF_MAX_MS="{ws_backoff_max_ms}"
WS_MAX_RETRIES="{ws_max_retries}"
TOKEN="{token}"
INSTALL_DIR="/opt/ops-job-agent"
BINARY_NAME="ops-job-agent"
SERVICE_NAME="ops-job-agent"
DOWNLOAD_URL="{download_url}"
CONFIG_DIR="$INSTALL_DIR/config"
CONFIG_FILE="$CONFIG_DIR/config.yaml"

# 检查是否已安装
if systemctl is-active --quiet $SERVICE_NAME 2>/dev/null; then
    echo "Agent 服务已在运行，请先停止服务"
    exit 1
fi

# 创建安装目录
mkdir -p "$INSTALL_DIR"
cd "$INSTALL_DIR"

# 下载二进制
echo "正在下载 Agent 二进制..."
curl -L -o "$BINARY_NAME" "$DOWNLOAD_URL" || wget -O "$BINARY_NAME" "$DOWNLOAD_URL"
chmod +x "$BINARY_NAME"

# 准备配置目录（与二进制同级的 config 目录）
mkdir -p "$CONFIG_DIR"
if [ -f "$CONFIG_FILE" ]; then
    cp "$CONFIG_FILE" "$CONFIG_FILE.$(date +%Y%m%d%H%M%S).bak"
fi

# 创建配置文件 ($INSTALL_DIR/config/config.yaml)
cat > "$CONFIG_FILE" <<EOF
mode: {install_mode}
"""
        if install_mode == 'agent-server':
            linux_script += """agent_server_url: $AGENT_SERVER_URL
agent_server_backup_url: $AGENT_SERVER_BACKUP_URL
ws_backoff_initial_ms: $WS_BACKOFF_INITIAL_MS
ws_backoff_max_ms: $WS_BACKOFF_MAX_MS
ws_max_retries: $WS_MAX_RETRIES
"""
        else:
            cp_url = agent_server_url.replace('ws://', 'http://').replace('wss://', 'https://')
            linux_script += f"""control_plane_url: {cp_url}
"""
        linux_script += """agent_token: "$TOKEN"
log_level: info
EOF

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
        scripts['linux'] = linux_script

        # 目前仅输出 Linux 安装脚本（暂不支持 Windows）
        return scripts

    @classmethod
    def batch_install_agents(cls, host_ids: list, user, account_id: int = None,
                             install_mode: str = 'agent-server', agent_server_url: str = '',
                             agent_server_backup_url: str = '', download_url: str = '', install_task_id: str = None,
                             package_version: str = None, package_id: int = None,
                             ws_backoff_initial_ms: int = 1000, ws_backoff_max_ms: int = 30000,
                             ws_max_retries: int = 6, ssh_timeout: int = 300, allow_reinstall: bool = False) -> Dict[str, Any]:
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
        
        results = []
        total = len(host_ids)
        completed = 0
        success_count = 0
        failed_count = 0
        
        # 推送初始状态
        realtime_log_service.push_status(install_task_id, {
            'status': 'running',
            'total': total,
            'completed': 0,
            'success_count': 0,
            'failed_count': 0,
            'message': '开始批量安装 Agent'
        })
        
        # 获取主机列表
        hosts = Host.objects.filter(id__in=host_ids)
        
        for host in hosts:
            try:
                # 检查是否已有 Agent
                if hasattr(host, 'agent') and host.agent and not allow_reinstall:
                    results.append({
                        'host_id': host.id,
                        'host_name': host.name,
                        'success': False,
                        'message': '该主机已安装 Agent（allow_reinstall=false）'
                    })
                    continue
                
                # 为每个主机签发 Token
                # 先创建 Agent 对象
                agent, created = Agent.objects.get_or_create(
                    host=host,
                    defaults={'status': 'pending'}
                )
                
                # 签发 Token
                token_data = cls.issue_token(agent, user, note='批量安装')
                token = token_data['token']
                
                # 保存 agent_id 用于后续审计日志
                agent_id = agent.id
                
                # 生成安装脚本
                scripts = cls.generate_install_script(
                    host=host,
                    token=token,
                    install_mode=install_mode,
                    agent_server_url=agent_server_url,
                    agent_server_backup_url=agent_server_backup_url,
                    download_url=download_url,
                    ws_backoff_initial_ms=ws_backoff_initial_ms,
                    ws_backoff_max_ms=ws_backoff_max_ms,
                    ws_max_retries=ws_max_retries,
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
                
                # 创建安装记录
                install_record = AgentInstallRecord.objects.create(
                    host=host,
                    agent=agent,
                    install_mode=install_mode,
                    status='pending',
                    agent_server_url=agent_server_url,
                    installed_by=user,
                    install_task_id=install_task_id
                )
                
                # 推送开始安装日志
                realtime_log_service.push_log(install_task_id, str(host.id), {
                    'host_name': host.name,
                    'host_ip': host.ip_address,
                    'log_type': 'info',
                    'content': f'开始安装 Agent 到主机 {host.name} ({host.ip_address})',
                    'step_name': '安装 Agent',
                    'step_order': 1
                })
                
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
                    
                    config_summary = f"primary={agent_server_url or 'n/a'}, backup={agent_server_backup_url or 'n/a'}, backoff_initial={ws_backoff_initial_ms}ms, backoff_max={ws_backoff_max_ms}ms, retries={ws_max_retries}"
                    if result['success']:
                        install_record.status = 'success'
                        install_record.message = f'安装成功 | {config_summary}'
                        success_count += 1
                        results.append({
                            'host_id': host.id,
                            'host_name': host.name,
                            'agent_id': agent.id,
                            'success': True,
                            'message': install_record.message
                        })
                        # 推送成功日志
                        realtime_log_service.push_log(install_task_id, str(host.id), {
                            'host_name': host.name,
                            'host_ip': host.ip_address,
                            'log_type': 'info',
                            'content': f'主机 {host.name} Agent 安装成功 | {config_summary}',
                            'step_name': '安装 Agent',
                            'step_order': 1
                        })
                    else:
                        install_record.status = 'failed'
                        error_msg = result.get('stderr', '安装失败')
                        install_record.message = f'{error_msg} | {config_summary}'
                        install_record.error_message = error_msg
                        install_record.error_detail = result.get('stderr', '')
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
                        })
                    
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
                    })
                    
                except Exception as e:
                    error_msg = f'SSH 执行失败: {str(e)}'
                    install_record.status = 'failed'
                    install_record.message = f'{error_msg} | primary={agent_server_url or "n/a"}, backup={agent_server_backup_url or "n/a"}'
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
                    })
                    
                    completed += 1
                    
                    # 推送进度更新
                    realtime_log_service.push_status(install_task_id, {
                        'status': 'running',
                        'total': total,
                        'completed': completed,
                        'success_count': success_count,
                        'failed_count': failed_count,
                        'message': f'已完成 {completed}/{total} 个主机的安装'
                    })
                
            except Exception as e:
                failed_count += 1
                host_name = host.name if hasattr(host, 'name') else 'Unknown'
                error_msg = f'安装失败: {str(e)}'
                results.append({
                    'host_id': host.id,
                    'host_name': host_name,
                    'success': False,
                    'message': f'{error_msg} | primary={agent_server_url or "n/a"}, backup={agent_server_backup_url or "n/a"}'
                })
                
                # 推送失败日志
                realtime_log_service.push_log(install_task_id, str(host.id), {
                    'host_name': host_name,
                    'host_ip': getattr(host, 'ip_address', ''),
                    'log_type': 'error',
                    'content': f'主机 {host_name} 安装失败: {error_msg}',
                    'step_name': '安装 Agent',
                    'step_order': 1
                })
                
                completed += 1
                
                # 推送进度更新
                realtime_log_service.push_status(install_task_id, {
                    'status': 'running',
                    'total': total,
                    'completed': completed,
                    'success_count': success_count,
                    'failed_count': failed_count,
                    'message': f'已完成 {completed}/{total} 个主机的安装'
                })
        
        # 推送最终状态
        final_status = 'completed' if failed_count == 0 else 'completed_with_errors'
        realtime_log_service.push_status(install_task_id, {
            'status': final_status,
            'total': total,
            'completed': completed,
            'success_count': success_count,
            'failed_count': failed_count,
            'message': f'批量安装完成：成功 {success_count} 个，失败 {failed_count} 个'
        })
        
        return {
            'results': results,
            'total': len(results),
            'success_count': success_count,
            'failed_count': failed_count,
            'install_task_id': install_task_id
        }

