"""
Agent 执行服务
用于通过 Agent 执行任务，支持与 ExecutionRecord 关联
"""
import logging
import uuid
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone as dt_timezone
from django.utils import timezone
from django.db import transaction

from apps.executor.models import ExecutionRecord, ExecutionStep
from apps.executor.services import ExecutionRecordService
from apps.hosts.models import Host
from apps.agents.models import Agent
from utils.realtime_logs import realtime_log_service
from apps.system_config.models import ConfigManager

logger = logging.getLogger(__name__)


class AgentExecutionService:
    """Agent 执行服务"""

    @staticmethod
    def create_task_spec(
        task_id: str,
        name: str,
        task_type: str,
        command: str = "",
        script_type: str = "shell",
        args: List[str] = None,
        env: Dict[str, str] = None,
        timeout_sec: int = 300,
        work_dir: str = "",
        execution_id: str = None,
        step_id: str = None,
        host_id: int = None,
        is_retry: bool = False,
        retry_count: int = 0,
        parent_task_id: str = None,
        run_as: str = None,  # 执行用户（用户名）
    ) -> Dict[str, Any]:
        """
        创建任务规范（TaskSpec）
        
        Args:
            task_id: 任务ID
            name: 任务名称
            task_type: 任务类型（script/file_transfer/command）
            command: 命令或脚本内容
            script_type: 脚本类型（shell/python/powershell）
            args: 命令参数
            env: 环境变量
            timeout_sec: 超时时间（秒）
            work_dir: 工作目录
            execution_id: ExecutionRecord的execution_id
            step_id: ExecutionStep的ID
            host_id: 目标主机ID
            is_retry: 是否为重试任务
            retry_count: 当前重试次数
            parent_task_id: 父任务ID
        
        Returns:
            Dict: TaskSpec字典
        """
        task_spec = {
            "id": task_id,
            "name": name,
            "type": task_type,
            "command": command,
            "script_type": script_type,
            "args": args or [],
            "env": env or {},
            "timeout_sec": timeout_sec,
            "work_dir": work_dir,
            "execution_id": execution_id,
            "step_id": step_id,
            "host_id": host_id,
            "is_retry": is_retry,
            "retry_count": retry_count,
            "parent_task_id": parent_task_id,
        }
        # 如果指定了执行用户，添加到task_spec
        if run_as:
            task_spec["run_as"] = run_as
        return task_spec

    @staticmethod
    def _get_agent_server_scope(agent: Agent) -> str:
        """
        根据 Agent 所在环境/业务生成调用 Agent-Server 时使用的 X-Scope。
        优先级：
          1) SystemConfig.agent.scope_by_env: {"prod": "prod-scope", "test": "test-scope", "default": "default-scope"}
          2) settings.AGENT_SERVER_SCOPE
          3) "default"
        """
        from django.conf import settings

        default_scope = getattr(settings, "AGENT_SERVER_SCOPE", "default") or "default"
        scope_by_env = ConfigManager.get("agent.scope_by_env", {}) or {}

        if isinstance(scope_by_env, dict):
            env = getattr(agent, "environment", None)
            if env and env in scope_by_env:
                val = scope_by_env.get(env)
                if isinstance(val, str) and val.strip():
                    return val.strip()
            # default 兜底
            default_val = scope_by_env.get("default")
            if isinstance(default_val, str) and default_val.strip():
                return default_val.strip()

        return default_scope

    @staticmethod
    def push_task_to_agent(
        agent: Agent,
        task_spec: Dict[str, Any],
        agent_server_url: str = None,
    ) -> Dict[str, Any]:
        """
        推送任务到Agent（通过Agent-Server或直接推送）
        
        Args:
            agent: Agent对象
            task_spec: 任务规范
            agent_server_url: Agent-Server地址（如果使用Agent-Server模式）
        
        Returns:
            Dict: 推送结果
        """
        try:
            import requests
            from django.conf import settings

            # 优先判断是否走 Agent-Server 模式（有显式 agent_server_url / endpoint / 全局配置）
            server_url = None
            if agent_server_url:
                server_url = agent_server_url
            elif agent.endpoint:
                server_url = agent.endpoint
            else:
                server_url = getattr(settings, 'AGENT_SERVER_URL', None)

            if server_url:
                # === Agent-Server 模式：调用 Agent-Server 的 /api/agents/{id}/tasks ===
                if server_url.startswith('ws://') or server_url.startswith('wss://'):
                    server_url = server_url.replace('ws://', 'http://').replace('wss://', 'https://')
            
                # 移除路径部分，只保留基础URL
                if '://' in server_url:
                    scheme_end = server_url.find('://') + 3
                    slash_idx = server_url.find('/', scheme_end)
                    if slash_idx != -1:
                        server_url = server_url[:slash_idx]

                api_url = f"{server_url}/api/agents/{agent.host_id}/tasks"
            
                # 构造带 HMAC 签名的请求
                from utils.agent_server_client import AgentServerClient

                client = AgentServerClient.from_settings()
                # 根据 Agent 环境设置 X-Scope，支持多租户/多环境的 Agent-Server 集群
                scope = AgentExecutionService._get_agent_server_scope(agent)
                headers = {"X-Scope": scope} if scope else {}
                response = client.post(api_url, json=task_spec, headers=headers)

                if response.status_code == 200:
                    result = response.json()
                    logger.info(f"任务已通过 Agent-Server 推送到Agent: {task_spec['id']}, Agent: {agent.host_id}")
                    return {
                        'success': True,
                        'task_id': task_spec['id'],
                        'agent_id': agent.host_id,
                        'status': result.get('status', 'dispatched')
                    }
                else:
                    error_msg = response.text or f"HTTP {response.status_code}"
                    logger.error(f"通过 Agent-Server 推送任务到Agent失败: {error_msg}")
                    return {
                        'success': False,
                        'error': f'推送任务失败: {error_msg}'
                    }

            # === 直连模式：控制面主动 POST 到 Agent 本地 HTTP 服务 ===
            host = agent.host  # OneToOne 关联
            if not host or not host.ip_address:
                return {
                    'success': False,
                    'error': '直连模式下需要主机 IP 地址'
                }

            direct_port = getattr(settings, 'AGENT_DIRECT_PORT', 8080)
            # 如果 endpoint 已经是 http(s):// 开头，可用作直连基础地址
            base_url = None
            if agent.endpoint and (agent.endpoint.startswith('http://') or agent.endpoint.startswith('https://')):
                base_url = agent.endpoint.rstrip('/')
            else:
                base_url = f"http://{host.ip_address}:{direct_port}"

            api_url = f"{base_url}/api/tasks"
            headers = {
                "Content-Type": "application/json",
            }
            direct_secret = getattr(settings, "AGENT_DIRECT_SHARED_SECRET", "") or ""
            if direct_secret:
                headers["Authorization"] = f"Bearer {direct_secret}"

            response = requests.post(
                api_url,
                json=task_spec,
                headers=headers,
                timeout=10,
            )

            if response.status_code == 200:
                result = response.json()
                logger.info(
                    f"任务已通过直连模式推送到Agent: {task_spec['id']}, Agent: {agent.host_id}, URL={api_url}"
                )
                return {
                    "success": True,
                    "task_id": task_spec["id"],
                    "agent_id": agent.host_id,
                    "status": result.get("status", "accepted"),
                }
            else:
                error_msg = response.text or f"HTTP {response.status_code}"
                logger.error(
                    f"直连模式推送任务到Agent失败: {error_msg}, URL={api_url}"
                )
                return {
                    "success": False,
                    "error": f"直连模式推送任务失败: {error_msg}",
                }

        except Exception as e:
            logger.error(f"推送任务到Agent异常: {str(e)}", exc_info=True)
            return {
                'success': False,
                'error': f'推送任务异常: {str(e)}'
            }

    @staticmethod
    def execute_script_via_agent(
        execution_record: ExecutionRecord,
        script_content: str,
        script_type: str,
        target_hosts: List[Host],
        timeout: int = 300,
        global_variables: Dict[str, Any] = None,
        step_id: str = None,
        agent_server_url: str = None,
        account_id: int = None,  # 执行账号ID
    ) -> Dict[str, Any]:
        """
        通过Agent执行脚本
        
        Args:
            execution_record: 执行记录
            script_content: 脚本内容
            script_type: 脚本类型
            target_hosts: 目标主机列表
            timeout: 超时时间
            global_variables: 全局变量
            step_id: 步骤ID（如果是工作流）
            agent_server_url: Agent-Server地址
        
        Returns:
            Dict: 执行结果
        """
        try:
            results = []
            success_count = 0
            failed_count = 0

            # 为每个主机创建任务
            for host in target_hosts:
                # 检查主机是否有Agent
                if not hasattr(host, 'agent') or not host.agent:
                    logger.warning(f"主机 {host.id} 没有Agent，跳过")
                    results.append({
                        'host_id': host.id,
                        'host_name': host.name,
                        'success': False,
                        'error': '主机没有Agent'
                    })
                    failed_count += 1
                    continue

                agent = host.agent
                if agent.status != 'online':
                    logger.warning(f"主机 {host.id} 的Agent状态为 {agent.status}，跳过")
                    results.append({
                        'host_id': host.id,
                        'host_name': host.name,
                        'success': False,
                        'error': f'Agent状态为 {agent.status}'
                    })
                    failed_count += 1
                    continue

                # 生成任务ID
                task_id = f"{execution_record.execution_id}_{step_id or 'main'}_{host.id}_{uuid.uuid4().hex[:8]}"

                # 获取执行用户名（如果有account_id）
                run_as = None
                if account_id:
                    try:
                        from apps.hosts.models import ServerAccount
                        account = ServerAccount.objects.get(id=account_id)
                        run_as = account.username
                    except ServerAccount.DoesNotExist:
                        logger.warning(f"执行账号不存在: account_id={account_id}，将使用Agent默认用户")
                    except Exception as e:
                        logger.warning(f"获取执行账号失败: account_id={account_id}, 错误: {str(e)}，将使用Agent默认用户")

                # 创建任务规范
                task_spec = AgentExecutionService.create_task_spec(
                    task_id=task_id,
                    name=f"{execution_record.name} - {host.name}",
                    task_type="script",
                    command=script_content,
                    script_type=script_type,
                    env=global_variables or {},
                    timeout_sec=timeout,
                    execution_id=str(execution_record.execution_id),
                    step_id=step_id,
                    host_id=host.id,
                    run_as=run_as,
                )

                # 推送任务到Agent
                push_result = AgentExecutionService.push_task_to_agent(
                    agent=agent,
                    task_spec=task_spec,
                    agent_server_url=agent_server_url,
                )

                if push_result['success']:
                    success_count += 1
                    results.append({
                        'host_id': host.id,
                        'host_name': host.name,
                        'task_id': task_id,
                        'success': True,
                    })
                else:
                    failed_count += 1
                    results.append({
                        'host_id': host.id,
                        'host_name': host.name,
                        'task_id': task_id,
                        'success': False,
                        'error': push_result.get('error', '推送任务失败')
                    })

            return {
                'success': success_count > 0,
                'success_count': success_count,
                'failed_count': failed_count,
                'results': results
            }

        except Exception as e:
            logger.error(f"通过Agent执行脚本异常: {str(e)}", exc_info=True)
            return {
                'success': False,
                'error': f'执行异常: {str(e)}'
            }

    @staticmethod
    def execute_file_transfer_via_agent(
        execution_record: ExecutionRecord,
        transfer_type: str,
        local_path: str,
        remote_path: str,
        target_hosts: List[Host],
        file_content: bytes = None,
        timeout: int = 300,
        bandwidth_limit: int = 0,
        download_url: str = None,
        checksum: str = None,
        size: int = None,
        auth_headers: Dict[str, str] = None,
        step_id: str = None,
        agent_server_url: str = None,
        account_id: int = None,  # 执行账号ID
    ) -> Dict[str, Any]:
        """
        通过Agent执行文件传输
        
        Args:
            execution_record: 执行记录
            transfer_type: 传输类型（upload/download）
            local_path: 本地路径
            remote_path: 远程路径
            target_hosts: 目标主机列表
            file_content: 文件内容（上传时使用）
            timeout: 超时时间
            bandwidth_limit: 带宽限制（KB/s）
            step_id: 步骤ID（如果是工作流）
            agent_server_url: Agent-Server地址
        
        Returns:
            Dict: 执行结果
        """
        try:
            results = []
            success_count = 0
            failed_count = 0

            # 为每个主机创建任务
            for host in target_hosts:
                # 检查主机是否有Agent
                if not hasattr(host, 'agent') or not host.agent:
                    logger.warning(f"主机 {host.id} 没有Agent，跳过")
                    results.append({
                        'host_id': host.id,
                        'host_name': host.name,
                        'success': False,
                        'error': '主机没有Agent'
                    })
                    failed_count += 1
                    continue

                agent = host.agent
                if agent.status != 'online':
                    logger.warning(f"主机 {host.id} 的Agent状态为 {agent.status}，跳过")
                    results.append({
                        'host_id': host.id,
                        'host_name': host.name,
                        'success': False,
                        'error': f'Agent状态为 {agent.status}'
                    })
                    failed_count += 1
                    continue

                # 生成任务ID
                task_id = f"{execution_record.execution_id}_{step_id or 'main'}_{host.id}_{uuid.uuid4().hex[:8]}"

                # 获取执行用户名（如果有account_id）
                run_as = None
                if account_id:
                    try:
                        from apps.hosts.models import ServerAccount
                        account = ServerAccount.objects.get(id=account_id)
                        run_as = account.username
                    except ServerAccount.DoesNotExist:
                        logger.warning(f"执行账号不存在: account_id={account_id}，将使用Agent默认用户")
                    except Exception as e:
                        logger.warning(f"获取执行账号失败: account_id={account_id}, 错误: {str(e)}，将使用Agent默认用户")

                # 创建文件传输规范
                # 对于大文件，如果文件太大，可以考虑只传递local_path，让Agent端自己读取
                import base64
                
                # 如果文件太大（>10MB），只传递路径，不传递内容
                MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB
                file_content_b64 = None
                if file_content:
                    if len(file_content) > MAX_FILE_SIZE:
                        logger.warning(f"文件太大 ({len(file_content)} bytes)，只传递路径，不传递内容")
                        # 大文件只传递路径，Agent端会从local_path读取
                        file_content_b64 = None
                    else:
                        file_content_b64 = base64.b64encode(file_content).decode('utf-8')
                
                file_transfer_spec = {
                    'type': transfer_type,
                    'local_path': local_path,
                    'remote_path': remote_path,
                    'content': file_content_b64,  # base64编码的字符串
                    'bandwidth_limit': bandwidth_limit,
                    'download_url': download_url,
                    'checksum': checksum,
                    'size': size,
                    'auth_headers': auth_headers or {},
                }

                # 创建任务规范
                task_spec = AgentExecutionService.create_task_spec(
                    task_id=task_id,
                    name=f"{execution_record.name} - {host.name} ({transfer_type})",
                    task_type="file_transfer",
                    timeout_sec=timeout,
                    execution_id=str(execution_record.execution_id),
                    step_id=step_id,
                    host_id=host.id,
                    run_as=run_as,
                )

                # 添加文件传输规范
                task_spec['file_transfer'] = file_transfer_spec

                # 推送任务到Agent
                push_result = AgentExecutionService.push_task_to_agent(
                    agent=agent,
                    task_spec=task_spec,
                    agent_server_url=agent_server_url,
                )

                if push_result['success']:
                    success_count += 1
                    results.append({
                        'host_id': host.id,
                        'host_name': host.name,
                        'task_id': task_id,
                        'success': True,
                    })
                else:
                    failed_count += 1
                    results.append({
                        'host_id': host.id,
                        'host_name': host.name,
                        'task_id': task_id,
                        'success': False,
                        'error': push_result.get('error', '推送任务失败')
                    })

            return {
                'success': success_count > 0,
                'success_count': success_count,
                'failed_count': failed_count,
                'results': results
            }

        except Exception as e:
            logger.error(f"通过Agent执行文件传输异常: {str(e)}", exc_info=True)
            return {
                'success': False,
                'error': f'执行异常: {str(e)}'
            }

    @staticmethod
    def execute_workflow_via_agent(
        execution_record: ExecutionRecord,
        plan_steps: List[Dict[str, Any]],
        target_hosts: List[Host],
        global_parameters: Dict[str, Any] = None,
        execution_mode: str = 'parallel',
        rolling_batch_size: int = 1,
        rolling_batch_delay: int = 0,
        start_step_order: int = 1,
        agent_server_url: str = None,
    ) -> Dict[str, Any]:
        """
        通过Agent执行工作流
        
        Args:
            execution_record: 执行记录
            plan_steps: 计划步骤列表
            target_hosts: 目标主机列表
            global_parameters: 全局参数
            execution_mode: 执行模式（parallel/serial/rolling）
            rolling_batch_size: 滚动批次大小
            rolling_batch_delay: 滚动批次延迟
            start_step_order: 起始步骤顺序
            agent_server_url: Agent-Server地址
        
        Returns:
            Dict: 执行结果
        """
        try:
            from apps.executor.services import ExecutionRecordService
            from apps.executor.models import ExecutionStep

            overall_success = True
            all_results = []

            # 按步骤顺序执行
            for step_index, step_data in enumerate(plan_steps):
                step_order = step_data.get('order', step_index + 1)
                
                # 跳过指定步骤之前的步骤
                if step_order < start_step_order:
                    continue

                step_name = step_data.get('step_name', f'步骤{step_order}')
                step_type = step_data.get('step_type', 'script')

                logger.info(f"执行工作流步骤: {step_name} (类型: {step_type}, 顺序: {step_order})")

                # 创建执行步骤记录
                step = ExecutionRecordService.create_execution_step(
                    execution_record=execution_record,
                    step_name=step_name,
                    step_type=step_type,
                    step_order=step_order,
                    step_parameters=step_data
                )

                # 更新步骤状态为运行中
                ExecutionRecordService.update_step_status(step, 'running')

                if step_type == 'script':
                    # 脚本执行步骤
                    # 获取步骤的目标主机
                    step_target_hosts = []
                    step_host_ids = []
                    
                    # 从步骤数据中获取目标主机
                    if step_data.get('target_hosts'):
                        step_host_ids = [h.get('id') for h in step_data['target_hosts']]
                    elif step_data.get('target_groups'):
                        # 从分组中获取主机
                        for group in step_data['target_groups']:
                            if group.get('hosts'):
                                step_host_ids.extend([h.get('id') for h in group['hosts']])
                    
                    # 如果没有指定步骤主机，使用所有目标主机
                    if not step_host_ids:
                        step_target_hosts = target_hosts
                    else:
                        step_target_hosts = [h for h in target_hosts if h.id in step_host_ids]

                    if not step_target_hosts:
                        logger.warning(f"步骤 {step_name} 没有目标主机，跳过")
                        ExecutionRecordService.update_step_status(
                            step, 'skipped',
                            error_message='没有目标主机'
                        )
                        continue

                    # 合并全局变量和步骤变量
                    step_global_variables = (global_parameters or {}).copy()
                    step_global_variables.update(step_data.get('execution_parameters', {}))

                    # 通过Agent执行脚本
                    result = AgentExecutionService.execute_script_via_agent(
                        execution_record=execution_record,
                        script_content=step_data.get('script_content', ''),
                        script_type=step_data.get('script_type', 'shell'),
                        target_hosts=step_target_hosts,
                        timeout=step_data.get('timeout', 300),
                        global_variables=step_global_variables,
                        step_id=str(step.id),
                        agent_server_url=agent_server_url,
                        account_id=step_data.get('account_id'),  # 传递执行账号ID
                    )

                    # 更新步骤结果
                    host_results = []
                    for r in result.get('results', []):
                        host_results.append({
                            'host_id': r.get('host_id'),
                            'host_name': r.get('host_name'),
                            'task_id': r.get('task_id'),  # 存储task_id用于取消任务
                            'status': 'success' if r.get('success') else 'failed',
                            'error': r.get('error'),
                        })

                    if result['success'] and result.get('failed_count', 0) == 0:
                        step_status = 'success'
                    else:
                        step_status = 'failed'
                        overall_success = False

                    ExecutionRecordService.update_step_status(
                        step, step_status,
                        host_results=host_results,
                        error_message=None if step_status == 'success' else '部分主机执行失败'
                    )

                    all_results.append({
                        'step_name': step_name,
                        'step_type': step_type,
                        'result': result
                    })

                    # 如果步骤失败且不允许忽略错误，停止执行
                    if step_status == 'failed' and not step_data.get('ignore_error', False):
                        logger.error(f"工作流步骤失败: {step_name}，停止执行")
                        break

                elif step_type == 'file_transfer':
                    # 文件传输步骤
                    # 获取步骤的目标主机
                    step_target_hosts = []
                    step_host_ids = []
                    
                    # 从步骤数据中获取目标主机
                    if step_data.get('target_hosts'):
                        step_host_ids = [h.get('id') for h in step_data['target_hosts']]
                    elif step_data.get('target_groups'):
                        # 从分组中获取主机
                        for group in step_data['target_groups']:
                            if group.get('hosts'):
                                step_host_ids.extend([h.get('id') for h in group['hosts']])
                    
                    # 如果没有指定步骤主机，使用所有目标主机
                    if not step_host_ids:
                        step_target_hosts = target_hosts
                    else:
                        step_target_hosts = [h for h in target_hosts if h.id in step_host_ids]

                    if not step_target_hosts:
                        logger.warning(f"步骤 {step_name} 没有目标主机，跳过")
                        ExecutionRecordService.update_step_status(
                            step, 'skipped',
                            error_message='没有目标主机'
                        )
                        continue

                    # 如果步骤包含 file_sources（多来源），支持 local/server 混合处理
                    file_sources = step_data.get('file_sources') or []
                    if file_sources:
                        overall_results = {'success_count': 0, 'failed_count': 0, 'results': []}
                        from apps.hosts.fabric_ssh_manager import fabric_ssh_manager
                        import base64, os
                        for src in file_sources:
                            stype = src.get('type')
                            remote_path_src = src.get('remote_path') or step_data.get('remote_path', '')
                            if stype == 'local':
                                # local 可以是模板中配置的 local_path（控制面可访问）
                                local_path = src.get('local_path') or src.get('path') or step_data.get('local_path', '')
                                file_content = None
                                if local_path and os.path.exists(local_path):
                                    try:
                                        with open(local_path, 'rb') as f:
                                            file_content = f.read()
                                    except Exception as e:
                                        logger.error(f"读取本地文件失败: {str(e)}")
                                        if not step_data.get('ignore_error', False):
                                            overall_success = False
                                            break
                                        else:
                                            continue
                                else:
                                    # 如果没有本地文件，尝试从content字段（base64）
                                    content_b64 = src.get('content') or src.get('file_content')
                                    if content_b64:
                                        try:
                                            file_content = base64.b64decode(content_b64)
                                        except Exception as e:
                                            logger.error(f"解码文件内容失败: {str(e)}")
                                            if not step_data.get('ignore_error', False):
                                                overall_success = False
                                                break
                                            else:
                                                continue

                                res = AgentExecutionService.execute_file_transfer_via_agent(
                                    execution_record=execution_record,
                                    transfer_type=step_data.get('transfer_type', 'upload'),
                                    local_path=os.path.basename(local_path) if local_path else '',
                                    remote_path=remote_path_src,
                                    target_hosts=step_target_hosts,
                                    file_content=file_content,
                                    timeout=step_data.get('timeout', 300),
                                    bandwidth_limit=step_data.get('bandwidth_limit', 0),
                                    step_id=str(step.id),
                                    agent_server_url=agent_server_url,
                                    account_id=step_data.get('account_id'),  # 传递执行账号ID
                                )
                            else:
                                # server 类型：使用 FabricSSHManager 三跳方式，从源服务器下载再上传到目标主机
                                # 该方式由控制面直接驱动，不通过 Agent
                                source_host = src.get('source_server_host') or src.get('host')
                                source_path = src.get('source_server_path') or src.get('path')
                                source_user = src.get('source_server_user') or src.get('user')
                                # 对每个目标主机调用 fabric_ssh_manager.transfer_file
                                for tgt in step_target_hosts:
                                    try:
                                        res_single = fabric_ssh_manager.transfer_file(
                                            host=tgt,
                                            transfer_type='server_upload',
                                            local_path='',
                                            remote_path=remote_path_src,
                                            timeout=step_data.get('timeout', 300),
                                            task_id=None,
                                            source_server_host=source_host,
                                            source_server_user=source_user,
                                            source_server_path=source_path,
                                            account_id=step_data.get('account_id'),
                                            max_target_matches=step_data.get('max_target_matches', 100)
                                        )
                                        # 合并结果格式，fabric 返回 success/message 等
                                        overall_results['results'].append({
                                            'host_id': tgt.id,
                                            'host_name': tgt.name,
                                            'success': res_single.get('success', False),
                                            'message': res_single.get('message', '')
                                        })
                                        if res_single.get('success'):
                                            overall_results['success_count'] += 1
                                        else:
                                            overall_results['failed_count'] += 1
                                    except Exception as e:
                                        overall_results['failed_count'] += 1
                                        overall_results['results'].append({
                                            'host_id': tgt.id,
                                            'host_name': tgt.name,
                                            'success': False,
                                            'message': str(e)
                                        })
                                # continue 到下一个 source
                                continue

                            # 合并 execute_file_transfer_via_agent 返回结果
                            overall_results['success_count'] += res.get('success_count', 0)
                            overall_results['failed_count'] += res.get('failed_count', 0)
                            overall_results['results'].extend(res.get('results', []))

                        # 将 overall_results 转换为统一 result
                        if overall_results['success_count'] > 0:
                            result = {
                                'success': True,
                                'success_count': overall_results['success_count'],
                                'failed_count': overall_results['failed_count'],
                                'results': overall_results['results']
                            }
                        else:
                            result = {
                                'success': False,
                                'success_count': overall_results['success_count'],
                                'failed_count': overall_results['failed_count'],
                                'results': overall_results['results']
                            }
                    else:
                        ExecutionRecordService.update_step_status(
                            step, 'failed',
                            error_message='file_sources required for file_transfer step'
                        )
                        overall_success = False
                        result = {'success': False, 'results': [], 'failed_count': len(step_target_hosts)}

                    # 更新步骤结果
                    host_results = []
                    for r in result.get('results', []):
                        host_results.append({
                            'host_id': r.get('host_id'),
                            'host_name': r.get('host_name'),
                            'task_id': r.get('task_id'),  # 存储task_id用于取消任务
                            'status': 'success' if r.get('success') else 'failed',
                            'error': r.get('error'),
                        })

                    if result['success'] and result.get('failed_count', 0) == 0:
                        step_status = 'success'
                    else:
                        step_status = 'failed'
                        overall_success = False

                    ExecutionRecordService.update_step_status(
                        step, step_status,
                        host_results=host_results,
                        error_message=None if step_status == 'success' else '部分主机执行失败'
                    )

                    all_results.append({
                        'step_name': step_name,
                        'step_type': step_type,
                        'result': result
                    })

                    # 如果步骤失败且不允许忽略错误，停止执行
                    if step_status == 'failed' and not step_data.get('ignore_error', False):
                        logger.error(f"工作流步骤失败: {step_name}，停止执行")
                        break

                else:
                    # 其他步骤类型暂未实现
                    logger.warning(f"步骤类型暂未实现: {step_type}")
                    ExecutionRecordService.update_step_status(
                        step, 'failed',
                        error_message=f'步骤类型 {step_type} 暂未实现'
                    )
                    if not step_data.get('ignore_error', False):
                        overall_success = False
                        break

            # 更新执行记录状态
            if overall_success:
                ExecutionRecordService.update_execution_status(
                    execution_record=execution_record,
                    status='success',
                    execution_results={'summary': {
                        'total_steps': len(plan_steps),
                        'success_steps': len([r for r in all_results if r.get('result', {}).get('success')]),
                        'failed_steps': len([r for r in all_results if not r.get('result', {}).get('success')]),
                    }}
                )
            else:
                ExecutionRecordService.update_execution_status(
                    execution_record=execution_record,
                    status='failed',
                    error_message='工作流执行失败'
                )

            return {
                'success': overall_success,
                'results': all_results,
                'message': '工作流执行完成' if overall_success else '工作流执行失败'
            }

        except Exception as e:
            logger.error(f"通过Agent执行工作流异常: {str(e)}", exc_info=True)
            ExecutionRecordService.update_execution_status(
                execution_record=execution_record,
                status='failed',
                error_message=f'工作流执行异常: {str(e)}'
            )
            return {
                'success': False,
                'error': f'执行异常: {str(e)}'
            }

    @staticmethod
    def handle_task_result(
        task_id: str,
        result: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        处理Agent任务执行结果
        
        Args:
            task_id: 任务ID
            result: 任务结果
        
        Returns:
            Dict: 处理结果
        """
        try:
            # 从task_id解析execution_id和step_id
            # task_id格式: {execution_id}_{step_id}_{host_id}_{random}
            parts = task_id.split('_')
            if len(parts) < 3:
                logger.warning(f"任务ID格式不正确: {task_id}")
                return {'success': False, 'error': '任务ID格式不正确'}

            execution_id = parts[0]
            step_id = parts[1] if len(parts) > 1 else None
            host_id = int(parts[2]) if len(parts) > 2 and parts[2].isdigit() else None

            # 查找ExecutionRecord
            try:
                execution_record = ExecutionRecord.objects.get(execution_id=execution_id)
            except ExecutionRecord.DoesNotExist:
                logger.warning(f"执行记录不存在: {execution_id}")
                return {'success': False, 'error': '执行记录不存在'}

            # 更新执行记录状态
            status = result.get('status', 'failed')
            if status == 'success':
                execution_record.status = 'success'
            elif status == 'failed':
                execution_record.status = 'failed'
                execution_record.error_message = result.get('error_msg', '任务执行失败')
            elif status == 'cancelled':
                execution_record.status = 'cancelled'

            # 使用传入的时间戳（Unix 秒），如果不存在则使用当前时间
            finished_at_ts = result.get('finished_at')
            if finished_at_ts:
                try:
                    execution_record.finished_at = datetime.fromtimestamp(
                        int(finished_at_ts), tz=dt_timezone.utc
                    )
                except (ValueError, TypeError, OSError):
                    execution_record.finished_at = timezone.now()
            else:
                execution_record.finished_at = timezone.now()
            
            execution_record.save()

            # 如果是工作流，更新步骤状态和主机结果
            if step_id and step_id != 'main':
                try:
                    step = ExecutionStep.objects.get(id=step_id, execution_record=execution_record)
                    step.status = status
                    if status == 'failed':
                        step.error_message = result.get('error_msg', '步骤执行失败')
                    
                    # 使用传入的时间戳（Unix 秒），如果不存在则使用当前时间
                    finished_at_ts = result.get('finished_at')
                    if finished_at_ts:
                        try:
                            step.finished_at = datetime.fromtimestamp(
                                int(finished_at_ts), tz=dt_timezone.utc
                            )
                        except (ValueError, TypeError, OSError):
                            step.finished_at = timezone.now()
                    else:
                        step.finished_at = timezone.now()
                    
                    # 更新主机结果
                    if host_id:
                        host_results = step.host_results or []
                        updated = False
                        for hr in host_results:
                            if hr.get('host_id') == host_id:
                                hr['status'] = status
                                hr['error'] = result.get('error_msg', '') if status == 'failed' else None
                                updated = True
                                break
                        if not updated:
                            # 添加新的主机结果
                            from apps.hosts.models import Host
                            try:
                                host = Host.objects.get(id=host_id)
                                host_results.append({
                                    'host_id': host_id,
                                    'host_name': host.name,
                                    'status': status,
                                    'error': result.get('error_msg', '') if status == 'failed' else None,
                                })
                            except Host.DoesNotExist:
                                pass
                        step.host_results = host_results
                    
                    step.save()
                except ExecutionStep.DoesNotExist:
                    logger.warning(f"执行步骤不存在: {step_id}")

            return {
                'success': True,
                'execution_record_id': execution_record.id,
                'status': status
            }

        except Exception as e:
            logger.error(f"处理任务结果异常: {str(e)}", exc_info=True)
            return {
                'success': False,
                'error': f'处理结果异常: {str(e)}'
            }

    @staticmethod
    def retry_execution_record(
        execution_record: ExecutionRecord,
        user,
        retry_type: str = 'full',  # full: 完整重试, step: 步骤重试
        step_id: str = None,
        failed_only: bool = True,
        agent_server_url: str = None,
    ) -> Dict[str, Any]:
        """
        重试ExecutionRecord（Agent方式）
        
        Args:
            execution_record: 要重试的执行记录
            user: 执行用户
            retry_type: 重试类型（full/step）
            step_id: 步骤ID（如果是步骤重试）
            failed_only: 是否只重试失败的主机
            agent_server_url: Agent-Server地址
        
        Returns:
            Dict: 重试结果
        """
        try:
            from apps.job_templates.services import ExecutionPlanService
            from django.db import transaction

            if retry_type == 'full':
                # 完整重试：创建新的ExecutionRecord
                # 获取根执行记录
                root_execution = execution_record.get_root_execution()

                # 检查重试次数
                if root_execution.retry_count >= root_execution.max_retries:
                    return {
                        'success': False,
                        'error': f'已达到最大重试次数 ({root_execution.max_retries})'
                    }

                # 根据执行类型进行重试
                execution_type = execution_record.execution_type

                if execution_type == 'job_workflow':
                    # 工作流重试
                    if not execution_record.related_object:
                        return {
                            'success': False,
                            'error': '执行记录没有关联对象，无法重试'
                        }

                    with transaction.atomic():
                        result = ExecutionPlanService.execute_plan(
                            execution_plan=execution_record.related_object,
                            user=user,
                            trigger_type='retry',
                            name=f"重试: {root_execution.name}",
                            description=f"重试执行记录 {root_execution.execution_id}",
                            execution_parameters=execution_record.execution_parameters,
                            execution_mode='agent',  # 使用Agent方式
                            agent_server_url=agent_server_url,
                        )

                        if result['success']:
                            # 获取新的执行记录
                            new_execution = ExecutionRecord.objects.get(id=result['execution_record_id'])

                            # 设置重试关系
                            new_execution.parent_execution = root_execution
                            new_execution.is_latest = True
                            new_execution.retry_reason = "手动重试（Agent方式）"
                            new_execution.save()

                            # 将之前的所有记录标记为非最新
                            from django.db.models import Q
                            ExecutionRecord.objects.filter(
                                Q(id=root_execution.id) |
                                Q(parent_execution=root_execution)
                            ).exclude(id=new_execution.id).update(is_latest=False)

                            # 更新根记录的重试次数
                            root_execution.retry_count = root_execution.total_retry_count
                            root_execution.save()

                            return {
                                'success': True,
                                'execution_record_id': new_execution.id,
                                'execution_id': new_execution.execution_id,
                                'message': '重试任务已启动'
                            }
                        else:
                            return result

                elif execution_type == 'quick_script':
                    # 快速脚本重试
                    from apps.quick_execute.services import QuickExecuteService

                    params = execution_record.execution_parameters
                    script_data = {
                        'script_content': params.get('script_content'),
                        'script_type': params.get('script_type', 'shell'),
                        'timeout': params.get('timeout', 300),
                        'execution_mode': params.get('execution_mode', 'parallel'),
                        'rolling_batch_size': params.get('rolling_batch_size', 1),
                        'rolling_batch_delay': params.get('rolling_batch_delay', 0),
                        'target_host_ids': params.get('target_host_ids', []),
                        'global_variables': params.get('global_variables', {}),
                        'positional_args': params.get('positional_args', []),
                        'agent_server_url': agent_server_url,
                    }

                    with transaction.atomic():
                        result = QuickExecuteService.execute_script(
                            user=user,
                            script_data=script_data,
                            client_ip=None,
                            user_agent=None
                        )

                        if result['success']:
                            # 获取新的执行记录
                            new_execution = ExecutionRecord.objects.get(id=result['execution_record_id'])

                            # 设置重试关系
                            new_execution.parent_execution = root_execution
                            new_execution.is_latest = True
                            new_execution.retry_reason = "手动重试（Agent方式）"
                            new_execution.save()

                            # 将之前的所有记录标记为非最新
                            from django.db.models import Q
                            ExecutionRecord.objects.filter(
                                Q(id=root_execution.id) |
                                Q(parent_execution=root_execution)
                            ).exclude(id=new_execution.id).update(is_latest=False)

                            # 更新根记录的重试次数
                            root_execution.retry_count = root_execution.total_retry_count
                            root_execution.save()

                            return {
                                'success': True,
                                'execution_record_id': new_execution.id,
                                'execution_id': new_execution.execution_id,
                                'message': '重试任务已启动'
                            }
                        else:
                            return result

                elif execution_type == 'quick_file_transfer':
                    # 快速文件传输重试
                    from apps.quick_execute.services import QuickExecuteService

                    params = execution_record.execution_parameters
                    transfer_data = {
                        'transfer_type': params.get('transfer_type'),
                        'local_path': params.get('local_path'),
                        'remote_path': params.get('remote_path'),
                        'source_server_host': params.get('source_server_host'),
                        'source_server_user': params.get('source_server_user'),
                        'source_server_path': params.get('source_server_path'),
                        'timeout': params.get('timeout', 300),
                        'execution_mode': params.get('execution_mode', 'parallel'),
                        'rolling_batch_size': params.get('rolling_batch_size', 20),
                        'rolling_batch_delay': params.get('rolling_batch_delay', 0),
                        'overwrite_policy': params.get('overwrite_policy', 'overwrite'),
                        'target_host_ids': params.get('target_host_ids', []),
                        'agent_server_url': agent_server_url,
                    }

                    with transaction.atomic():
                        result = QuickExecuteService.transfer_file(
                            user=user,
                            transfer_data=transfer_data,
                            client_ip=None,
                            user_agent=None
                        )

                        if result['success']:
                            # 获取新的执行记录
                            new_execution = ExecutionRecord.objects.get(id=result['execution_record_id'])

                            # 设置重试关系
                            new_execution.parent_execution = root_execution
                            new_execution.is_latest = True
                            new_execution.retry_reason = "手动重试（Agent方式）"
                            new_execution.save()

                            # 将之前的所有记录标记为非最新
                            from django.db.models import Q
                            ExecutionRecord.objects.filter(
                                Q(id=root_execution.id) |
                                Q(parent_execution=root_execution)
                            ).exclude(id=new_execution.id).update(is_latest=False)

                            # 更新根记录的重试次数
                            root_execution.retry_count = root_execution.total_retry_count
                            root_execution.save()

                            return {
                                'success': True,
                                'execution_record_id': new_execution.id,
                                'execution_id': new_execution.execution_id,
                                'message': '重试任务已启动'
                            }
                        else:
                            return result

                else:
                    return {
                        'success': False,
                        'error': f'不支持重试的执行类型: {execution_type}'
                    }

            elif retry_type == 'step':
                # 步骤重试：在原记录上重试失败的步骤
                if not step_id:
                    return {
                        'success': False,
                        'error': '步骤重试需要指定step_id'
                    }

                # 获取步骤
                try:
                    step = ExecutionStep.objects.get(
                        id=step_id,
                        execution_record=execution_record
                    )
                except ExecutionStep.DoesNotExist:
                    return {
                        'success': False,
                        'error': '步骤不存在'
                    }

                # 检查步骤状态
                if step.status not in ['failed', 'skipped', 'timeout']:
                    return {
                        'success': False,
                        'error': '只有失败、跳过或超时的步骤才能重试'
                    }

                # 根据重试类型确定要重试的主机
                if failed_only:
                    target_hosts = [
                        host for host in step.host_results
                        if host.get('status') in ['failed', 'timeout']
                    ]
                else:
                    target_hosts = step.host_results

                if not target_hosts:
                    return {
                        'success': False,
                        'error': '没有需要重试的主机'
                    }

                # 重置步骤状态
                step.status = 'pending'
                step.started_at = None
                step.finished_at = None
                step.error_message = None
                step.host_results = []
                step.save()

                # 更新执行记录状态
                execution_record.status = 'running'
                execution_record.retry_count += 1
                execution_record.last_retry_at = timezone.now()
                execution_record.save()

                # 重新执行步骤（通过Agent）
                from apps.hosts.models import Host
                from apps.executor.services import ExecutionRecordService

                # 获取主机对象
                host_ids = [h.get('host_id') for h in target_hosts if isinstance(h, dict) and h.get('host_id')]
                if not host_ids:
                    return {
                        'success': False,
                        'error': '没有有效的主机ID'
                    }

                target_host_objs = Host.objects.filter(id__in=host_ids)

                # 根据步骤类型执行
                step_type = step.step_type
                step_params = step.step_parameters or {}

                if step_type == 'script':
                    # 脚本步骤重试
                    result = AgentExecutionService.execute_script_via_agent(
                        execution_record=execution_record,
                        script_content=step_params.get('script_content', ''),
                        script_type=step_params.get('script_type', 'shell'),
                        target_hosts=list(target_host_objs),
                        timeout=step_params.get('timeout', 300),
                        global_variables=execution_record.execution_parameters.get('global_variables', {}),
                        step_id=str(step.id),
                        agent_server_url=agent_server_url,
                        account_id=step_params.get('account_id'),  # 传递执行账号ID
                    )
                elif step_type == 'file_transfer':
                    # 文件传输步骤重试
                    # 读取文件内容（如果是上传且需要）
                    file_content = None
                    transfer_type = step_params.get('transfer_type', 'upload')
                    if transfer_type == 'upload':
                        local_path = step_params.get('local_path', '')
                        if local_path:
                            try:
                                with open(local_path, 'rb') as f:
                                    file_content = f.read()
                            except Exception as e:
                                logger.error(f"读取文件失败: {str(e)}")
                                return {
                                    'success': False,
                                    'error': f'读取文件失败: {str(e)}'
                                }
                        # 如果step_params中有file_content（base64编码），也需要处理
                        elif step_params.get('file_content'):
                            import base64
                            try:
                                file_content = base64.b64decode(step_params['file_content'])
                            except Exception as e:
                                logger.error(f"解码文件内容失败: {str(e)}")
                                return {
                                    'success': False,
                                    'error': f'解码文件内容失败: {str(e)}'
                                }
                    
                    result = AgentExecutionService.execute_file_transfer_via_agent(
                        execution_record=execution_record,
                        transfer_type=transfer_type,
                        local_path=step_params.get('local_path', ''),
                        remote_path=step_params.get('remote_path', ''),
                        target_hosts=list(target_host_objs),
                        file_content=file_content,
                        timeout=step_params.get('timeout', 300),
                        bandwidth_limit=step_params.get('bandwidth_limit', 0),
                        step_id=str(step.id),
                        agent_server_url=agent_server_url,
                        account_id=step_params.get('account_id'),  # 传递执行账号ID
                    )
                else:
                    return {
                        'success': False,
                        'error': f'不支持的步骤类型: {step_type}'
                    }

                if result['success']:
                    return {
                        'success': True,
                        'execution_record_id': execution_record.id,
                        'message': '步骤重试已启动'
                    }
                else:
                    return result

            else:
                return {
                    'success': False,
                    'error': f'不支持的重试类型: {retry_type}'
                }

        except Exception as e:
            logger.error(f"重试执行记录异常: {str(e)}", exc_info=True)
            return {
                'success': False,
                'error': f'重试异常: {str(e)}'
            }

    @staticmethod
    def cancel_task_via_agent(
        execution_record: ExecutionRecord,
        agent_server_url: str = None,
    ) -> Dict[str, Any]:
        """
        通过Agent取消任务（支持直连和Agent-Server两种模式）
        
        Args:
            execution_record: 执行记录
            agent_server_url: Agent-Server地址（如果使用Agent-Server模式）
        
        Returns:
            Dict: 取消结果
        """
        try:
            # 收集所有需要取消的task_id
            task_ids = []
            agent_task_map = {}  # {agent_id: [task_ids]}
            
            # 从ExecutionStep的host_results中收集task_id
            steps = ExecutionStep.objects.filter(execution_record=execution_record)
            for step in steps:
                host_results = step.host_results or []
                for hr in host_results:
                    task_id = hr.get('task_id')
                    host_id = hr.get('host_id')
                    if task_id and host_id:
                        # 获取Agent
                        try:
                            host = Host.objects.get(id=host_id)
                            if hasattr(host, 'agent') and host.agent:
                                agent_id = host.agent.host_id
                                if agent_id not in agent_task_map:
                                    agent_task_map[agent_id] = {
                                        'agent': host.agent,
                                        'tasks': []
                                    }
                                agent_task_map[agent_id]['tasks'].append({
                                    'task_id': task_id,
                                    'host_id': host_id,
                                })
                                task_ids.append(task_id)
                        except Host.DoesNotExist:
                            logger.warning(f"主机不存在: {host_id}")
            
            if not task_ids:
                logger.warning(f"执行记录 {execution_record.execution_id} 没有找到需要取消的任务")
                return {
                    'success': True,
                    'message': '没有找到需要取消的任务',
                    'cancelled_count': 0
                }
            
            # 确定执行模式
            if agent_server_url or (execution_record.execution_parameters.get('agent_server_url')):
                # Agent-Server模式
                server_url = agent_server_url or execution_record.execution_parameters.get('agent_server_url')
                return AgentExecutionService._cancel_tasks_via_agent_server(
                    agent_task_map=agent_task_map,
                    server_url=server_url,
                )
            else:
                # Direct模式（直连控制面）
                return AgentExecutionService._cancel_tasks_via_direct(
                    agent_task_map=agent_task_map,
                )
        
        except Exception as e:
            logger.error(f"取消Agent任务异常: {str(e)}", exc_info=True)
            return {
                'success': False,
                'error': f'取消任务异常: {str(e)}'
            }

    @staticmethod
    def _cancel_tasks_via_agent_server(
        agent_task_map: Dict[int, Dict],
        server_url: str,
    ) -> Dict[str, Any]:
        """
        通过Agent-Server取消任务
        
        Args:
            agent_task_map: Agent和任务映射 {agent_id: {'agent': Agent, 'tasks': [{'task_id': str, 'host_id': int}]}}
            server_url: Agent-Server地址
        
        Returns:
            Dict: 取消结果
        """
        try:
            from django.conf import settings
            
            # 确保URL格式正确
            if server_url.startswith('ws://') or server_url.startswith('wss://'):
                server_url = server_url.replace('ws://', 'http://').replace('wss://', 'https://')
            
            # 移除路径部分，只保留基础URL
            if '/' in server_url[8:]:  # 跳过 http:// 或 https://
                server_url = server_url[:server_url.find('/', 8)]
            
            # 获取Agent-Server的认证Token（如果需要）
            agent_server_token = getattr(settings, 'AGENT_SERVER_TOKEN', None)
            
            headers_base = {
                'Content-Type': 'application/json',
            }
            if agent_server_token:
                headers_base['Authorization'] = f'Bearer {agent_server_token}'
            
            cancelled_count = 0
            failed_count = 0
            errors = []
            
            # 为每个Agent取消任务
            for agent_id, agent_info in agent_task_map.items():
                agent = agent_info['agent']
                tasks = agent_info['tasks']
                
                for task_info in tasks:
                    task_id = task_info['task_id']
                    host_id = task_info['host_id']
                    
                    # 调用Agent-Server的取消任务API
                    api_url = f"{server_url}/api/agents/{agent_id}/tasks/{task_id}/cancel"
                    
                    try:
                        # 使用 HMAC 客户端发起请求，并按 Agent 环境附加合适的 X-Scope
                        from utils.agent_server_client import AgentServerClient

                        client = AgentServerClient.from_settings()
                        scope = AgentExecutionService._get_agent_server_scope(agent)
                        headers = headers_base.copy()
                        if scope:
                            headers["X-Scope"] = scope
                        response = client.post(api_url, json=None, headers=headers)
                        
                        if response.status_code == 200:
                            cancelled_count += 1
                            logger.info(f"成功取消任务: task_id={task_id}, agent_id={agent_id}, host_id={host_id}")
                        else:
                            failed_count += 1
                            error_msg = response.text or f"HTTP {response.status_code}"
                            errors.append(f"取消任务失败 (task_id={task_id}, agent_id={agent_id}): {error_msg}")
                            logger.error(f"取消任务失败: task_id={task_id}, agent_id={agent_id}, 状态码={response.status_code}, 错误={error_msg}")
                    
                    except Exception as e:
                        failed_count += 1
                        error_msg = f"请求异常: {str(e)}"
                        errors.append(f"取消任务异常 (task_id={task_id}, agent_id={agent_id}): {error_msg}")
                        logger.error(f"取消任务异常: task_id={task_id}, agent_id={agent_id}, 错误={str(e)}", exc_info=True)
            
            return {
                'success': cancelled_count > 0,
                'cancelled_count': cancelled_count,
                'failed_count': failed_count,
                'total_count': cancelled_count + failed_count,
                'errors': errors if errors else None,
                'message': f'成功取消 {cancelled_count} 个任务，失败 {failed_count} 个'
            }
        
        except Exception as e:
            logger.error(f"通过Agent-Server取消任务异常: {str(e)}", exc_info=True)
            return {
                'success': False,
                'error': f'取消任务异常: {str(e)}'
            }

    @staticmethod
    def _cancel_tasks_via_direct(
        agent_task_map: Dict[int, Dict],
    ) -> Dict[str, Any]:
        """
        通过直连模式取消任务：直接调用 Agent 本地 HTTP 接口 /api/tasks/{id}/cancel
        Args:
            agent_task_map: Agent和任务映射 {agent_id: {'agent': Agent, 'tasks': [{'task_id': str, 'host_id': int}]}}
        Returns:
            Dict: 取消结果
        """
        try:
            import requests
            from django.conf import settings
            from apps.hosts.models import Host

            cancelled_count = 0
            failed_count = 0
            errors = []

            direct_port = getattr(settings, 'AGENT_DIRECT_PORT', 8080)
            direct_secret = getattr(settings, 'AGENT_DIRECT_SHARED_SECRET', '') or ''

            for agent_id, agent_info in agent_task_map.items():
                agent_obj = agent_info['agent']
                tasks = agent_info['tasks']

                # 获取主机 IP
                host: Host = getattr(agent_obj, 'host', None)
                host_ip = getattr(host, 'ip_address', '') if host else ''
                if not host_ip:
                    for task_info in tasks:
                        failed_count += 1
                        msg = f'直连模式取消任务失败: 找不到主机 IP (agent_id={agent_id})'
                        errors.append(msg)
                        logger.error(msg)
                    continue

                # 如果 endpoint 已是 http(s)，可作为直连基础 URL
                endpoint = getattr(agent_obj, 'endpoint', '') or ''
                if endpoint.startswith('http://') or endpoint.startswith('https://'):
                    base_url = endpoint.rstrip('/')
                else:
                    base_url = f"http://{host_ip}:{direct_port}"

                for task_info in tasks:
                    task_id = task_info['task_id']
                    host_id = task_info['host_id']

                    api_url = f"{base_url}/api/tasks/{task_id}/cancel"
                    try:
                        cancel_headers = {}
                        if direct_secret:
                            cancel_headers["Authorization"] = f"Bearer {direct_secret}"
                        resp = requests.post(api_url, timeout=10, headers=cancel_headers)
                        if resp.status_code == 200:
                            cancelled_count += 1
                            logger.info(
                                f"直连模式取消任务成功: task_id={task_id}, agent_id={agent_id}, host_id={host_id}, url={api_url}"
                            )
                        else:
                            failed_count += 1
                            error_msg = resp.text or f"HTTP {resp.status_code}"
                            errors.append(
                                f"直连模式取消任务失败 (task_id={task_id}, agent_id={agent_id}): {error_msg}"
                            )
                            logger.error(
                                f"直连模式取消任务失败: task_id={task_id}, agent_id={agent_id}, 状态码={resp.status_code}, 错误={error_msg}"
                            )
                    except Exception as e:
                        failed_count += 1
                        error_msg = f"请求异常: {str(e)}"
                        errors.append(
                            f"直连模式取消任务异常 (task_id={task_id}, agent_id={agent_id}): {error_msg}"
                        )
                        logger.error(
                            f"直连模式取消任务异常: task_id={task_id}, agent_id={agent_id}, 错误={str(e)}",
                            exc_info=True,
                        )

            return {
                'success': cancelled_count > 0,
                'cancelled_count': cancelled_count,
                'failed_count': failed_count,
                'total_count': cancelled_count + failed_count,
                'errors': errors if errors else None,
                'message': f'直连模式取消任务：成功 {cancelled_count} 个，失败 {failed_count} 个',
            }

        except Exception as e:
            logger.error(f"通过直连模式取消任务异常: {str(e)}", exc_info=True)
            return {
                'success': False,
                'error': f'取消任务异常: {str(e)}'
            }
