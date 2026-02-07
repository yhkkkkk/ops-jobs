"""
Agent 执行服务
用于通过 Agent 执行任务，支持与 ExecutionRecord 关联
"""
import logging
import uuid
import time
import redis
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone as dt_timezone
from functools import wraps
from django.utils import timezone
from django.db import transaction, DatabaseError

from apps.executor.models import ExecutionRecord, ExecutionStep
from apps.executor.services import ExecutionRecordService
from apps.hosts.models import Host
from apps.agents.models import Agent
from utils.realtime_logs import realtime_log_service
from apps.system_config.models import ConfigManager
from apps.agents.storage_service import StorageService
from apps.hosts.models import ServerAccount
import requests
import tempfile, os, hashlib

logger = logging.getLogger(__name__)


def retry_on_db_error(max_retries=3, delay=0.1, backoff=2):
    """
    数据库错误重试装饰器
    处理死锁、连接超时等数据库临时错误
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            last_exception = None
            current_delay = delay

            for attempt in range(max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except (DatabaseError, transaction.TransactionManagementError) as e:
                    last_exception = e

                    # 检查是否是可重试的错误
                    error_msg = str(e).lower()
                    if any(keyword in error_msg for keyword in [
                        'deadlock', 'lock wait timeout', 'connection timeout',
                        'serialization failure', 'could not serialize'
                    ]):
                        if attempt < max_retries:
                            logger.warning(
                                f"Database error (attempt {attempt + 1}/{max_retries + 1}): {e}. "
                                f"Retrying in {current_delay}s..."
                            )
                            time.sleep(current_delay)
                            current_delay *= backoff
                            continue

                    # 不可重试的错误或已达到最大重试次数
                    logger.error(f"Database operation failed after {max_retries + 1} attempts: {e}")
                    raise e
                except Exception as e:
                    # 非数据库错误，直接抛出
                    raise e

            # 这行代码理论上不会到达，因为上面的循环会在最后一次尝试后抛出异常
            raise last_exception

        return wrapper
    return decorator


class AgentExecutionService:
    """Agent 执行服务"""

    @staticmethod
    def _fetch_server_source_to_artifact_http(source: Dict[str, Any], execution_id: str, timeout: int = 30) -> Optional[Dict[str, Any]]:
        """
        通过 HTTP 从源服务器下载文件到存储，生成 artifact 记录。
        source: {source_server_host, source_server_path, account_id, remote_path, auth_headers?}
        """
        host = source.get('source_server_host')
        path = source.get('source_server_path')
        account_id = source.get('account_id')
        remote_path = source.get('remote_path')
        if not (host and path and isinstance(account_id, int)):
            logger.error("server source 参数缺失")
            return None

        # 拼接 URL（如果 path 已含 schema 则直接用）
        if path.startswith('http://') or path.startswith('https://'):
            url = path
        else:
            scheme = 'https' if str(host).startswith(('https://', '443')) else 'http'
            url = f"{scheme}://{host}{path if path.startswith('/') else '/' + path}"

        auth = None
        headers = source.get('auth_headers') or {}
        try:
            account = ServerAccount.objects.get(id=account_id)
            if account.username and account.password:
                auth = (account.username, account.password)
        except ServerAccount.DoesNotExist:
            logger.error(f"account_id 无效: {account_id}")
            return None
        except Exception as e:
            logger.error(f"获取账号失败: {e}")
            return None

        try:
            resp = requests.get(url, headers=headers, auth=auth, timeout=timeout, stream=True)
            resp.raise_for_status()
            with tempfile.NamedTemporaryFile(delete=False) as tmp:
                sha = hashlib.sha256()
                size = 0
                for chunk in resp.iter_content(chunk_size=8192):
                    if not chunk:
                        continue
                    sha.update(chunk)
                    size += len(chunk)
                    tmp.write(chunk)
                tmp_path = tmp.name
        except Exception as e:
            logger.error(f"下载源服务器文件失败: {e}")
            return None

        try:
            storage_type = ConfigManager.get('storage.type', 'local')
            backend = StorageService.get_backend(storage_type)
            if backend is None:
                logger.error(f"无法获取存储后端: {storage_type}")
                return None
            filename = os.path.basename(path) or f"artifact_{uuid.uuid4().hex[:8]}"
            storage_path = f"server_fetch/{execution_id}/{uuid.uuid4().hex}_{filename}"
            with open(tmp_path, 'rb') as fobj:
                success, err = backend.upload_file(fobj, storage_path)
            if not success:
                logger.error(f"上传存储失败: {err}")
                return None
            download_url = backend.generate_url(storage_path, expires_in=3600)
            return {
                'type': 'artifact',
                'storage_path': storage_path,
                'download_url': download_url,
                'sha256': sha.hexdigest(),
                'size': size,
                'filename': filename,
                'remote_path': remote_path,
                'auth_headers': {},
            }
        finally:
            try:
                os.remove(tmp_path)
            except Exception:
                pass

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
        file_transfer: Dict[str, Any] = None,
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
        if file_transfer:
            task_spec["file_transfer"] = file_transfer
        return task_spec

    @staticmethod
    def push_task_to_agent(
        agent: Agent,
        task_spec: Dict[str, Any],
        agent_server_url: str = None,
    ) -> Dict[str, Any]:
        """
        推送任务到Agent（通过Agent-Server WebSocket模式）

        Args:
            agent: Agent对象
            task_spec: 任务规范
            agent_server_url: Agent-Server地址（可选，优先级最高）

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

            if not server_url:
                # Agent-Server URL 未配置，无法推送任务
                logger.error(f"Agent-Server URL 未配置，无法推送任务到 Agent {agent.host_id}")
                return {
                    'success': False,
                    'error': 'Agent-Server URL 未配置，请在 Agent 配置或全局设置中指定 AGENT_SERVER_URL'
                }

            # === Agent-Server 模式：调用 Agent-Server 的 /api/agents/{id}/tasks ===
            if server_url.startswith('ws://') or server_url.startswith('wss://'):
                server_url = server_url.replace('ws://', 'http://').replace('wss://', 'https://')

            # 移除路径部分，只保留基础URL
            if '://' in server_url:
                scheme_end = server_url.find('://') + 3
                slash_idx = server_url.find('/', scheme_end)
                if slash_idx != -1:
                    server_url = server_url[:slash_idx]

            # 支持在设置中提供覆盖的 agent_server_id（测试/单实例场景）
            override_agent_id = getattr(settings, "AGENT_ID_OVERRIDE", None)
            agent_identifier = override_agent_id or agent.host_id

            api_url = f"{server_url}/api/agents/{agent_identifier}/tasks"

            # 构造带 HMAC 签名的请求
            from utils.agent_server_client import AgentServerClient

            client = AgentServerClient.from_settings()
            response = client.post(api_url, json=task_spec)

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
        file_sources: List[Dict[str, Any]] = None,  # server 源需先 HTTP 拉取入库
        execution_mode: str = 'parallel',  # 执行模式: parallel/serial/rolling
        rolling_batch_size: int = 1,  # 滚动执行批次大小
        rolling_batch_delay: int = 0,  # 滚动执行批次延迟（秒）
        ignore_error: bool = False,  # 是否忽略错误继续执行
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
            account_id: 执行账号ID
            file_sources: 文件源列表
            execution_mode: 执行模式 (parallel/serial/rolling)
            rolling_batch_size: 滚动执行批次大小
            rolling_batch_delay: 滚动执行批次延迟（秒）
            ignore_error: 是否忽略错误继续执行

        Returns:
            Dict: 执行结果
        """
        try:
            from apps.agents.execution_strategies import get_execution_strategy

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

            # 创建任务规范的函数
            def task_creator(host: Host) -> Dict[str, Any]:
                task_id = f"{execution_record.execution_id}_{step_id or 'main'}_{host.id}_{uuid.uuid4().hex[:8]}"
                return AgentExecutionService.create_task_spec(
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

            # 推送任务到Agent的函数
            def task_pusher(agent: Agent, task_spec: Dict[str, Any]) -> Dict[str, Any]:
                return AgentExecutionService.push_task_to_agent(
                    agent=agent,
                    task_spec=task_spec,
                    agent_server_url=agent_server_url,
                )

            # 获取执行策略
            strategy = get_execution_strategy(
                mode=execution_mode,
                batch_size=rolling_batch_size,
                batch_delay=rolling_batch_delay,
            )

            logger.info(f"使用执行策略: {execution_mode}, 目标主机数: {len(target_hosts)}")

            # 执行任务
            exec_result = strategy.execute(
                hosts=target_hosts,
                task_creator=task_creator,
                task_pusher=task_pusher,
                timeout=timeout,
                ignore_error=ignore_error,
            )

            # 转换结果格式
            results = []
            for hr in exec_result.results:
                results.append({
                    'host_id': hr.host_id,
                    'host_name': hr.host_name,
                    'task_id': hr.task_id,
                    'success': hr.success,
                    'error': hr.error,
                    'exit_code': hr.exit_code,
                    'started_at': hr.started_at,
                    'finished_at': hr.finished_at,
                })

            return {
                'success': exec_result.success,
                'success_count': exec_result.success_count,
                'failed_count': exec_result.failed_count,
                'results': results,
                'stopped_early': exec_result.stopped_early,
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
        remote_path: str,
        target_hosts: List[Host],
        timeout: int = 300,
        bandwidth_limit: int = 0,
        download_url: str = None,
        checksum: str = None,
        size: int = None,
        auth_headers: Dict[str, str] = None,
        step_id: str = None,
        agent_server_url: str = None,
        account_id: int = None,  # 执行账号ID
        file_sources: List[Dict[str, Any]] = None,  # server 源需先 HTTP 拉取入库
        execution_mode: str = 'parallel',  # 执行模式: parallel/serial/rolling
        rolling_batch_size: int = 1,  # 滚动执行批次大小
        rolling_batch_delay: int = 0,  # 滚动执行批次延迟（秒）
        ignore_error: bool = False,  # 是否忽略错误继续执行
    ) -> Dict[str, Any]:
        """
        通过Agent执行文件传输

        Args:
            execution_record: 执行记录
            remote_path: 远程路径
            target_hosts: 目标主机列表
            timeout: 超时时间
            bandwidth_limit: 带宽限制（MB/s）
            download_url: 控制面已入库生成的文件 URL
            checksum: 校验值（可选）
            size: 文件大小（可选）
            auth_headers: 下载需要的认证头（可选）
            step_id: 步骤ID（如果是工作流）
            agent_server_url: Agent-Server地址
            file_sources: 可选，包含 server 源，需先 HTTP 拉取入库后再下发
            execution_mode: 执行模式 (parallel/serial/rolling)
            rolling_batch_size: 滚动执行批次大小
            rolling_batch_delay: 滚动执行批次延迟（秒）
            ignore_error: 是否忽略错误继续执行

        Returns:
            Dict: 执行结果
        """
        try:
            from apps.agents.execution_strategies import get_execution_strategy

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
            file_transfer_spec = {
                'remote_path': remote_path,
                'bandwidth_limit': bandwidth_limit,
                'download_url': download_url,
                'checksum': checksum,
                'size': size,
                'auth_headers': auth_headers or {},
            }

            # 创建任务规范的函数
            def task_creator(host: Host) -> Dict[str, Any]:
                task_id = f"{execution_record.execution_id}_{step_id or 'main'}_{host.id}_{uuid.uuid4().hex[:8]}"
                return AgentExecutionService.create_task_spec(
                    task_id=task_id,
                    name=f"{execution_record.name} - {host.name} (file_transfer)",
                    task_type="file_transfer",
                    timeout_sec=timeout,
                    execution_id=str(execution_record.execution_id),
                    step_id=step_id,
                    host_id=host.id,
                    run_as=run_as,
                    file_transfer=file_transfer_spec,
                )

            # 推送任务到Agent的函数
            def task_pusher(agent: Agent, task_spec: Dict[str, Any]) -> Dict[str, Any]:
                return AgentExecutionService.push_task_to_agent(
                    agent=agent,
                    task_spec=task_spec,
                    agent_server_url=agent_server_url,
                )

            # 获取执行策略
            strategy = get_execution_strategy(
                mode=execution_mode,
                batch_size=rolling_batch_size,
                batch_delay=rolling_batch_delay,
            )

            logger.info(f"文件传输使用执行策略: {execution_mode}, 目标主机数: {len(target_hosts)}")

            # 执行任务
            exec_result = strategy.execute(
                hosts=target_hosts,
                task_creator=task_creator,
                task_pusher=task_pusher,
                timeout=timeout,
                ignore_error=ignore_error,
            )

            # 转换结果格式
            results = []
            for hr in exec_result.results:
                results.append({
                    'host_id': hr.host_id,
                    'host_name': hr.host_name,
                    'task_id': hr.task_id,
                    'success': hr.success,
                    'error': hr.error,
                    'exit_code': hr.exit_code,
                    'started_at': hr.started_at,
                    'finished_at': hr.finished_at,
                })

            return {
                'success': exec_result.success,
                'success_count': exec_result.success_count,
                'failed_count': exec_result.failed_count,
                'results': results,
                'stopped_early': exec_result.stopped_early,
            }

        except Exception as e:
            logger.error(f"通过Agent执行文件传输异常: {str(e)}", exc_info=True)
            return {
                'success': False,
                'error': f'执行异常: {str(e)}'
            }

    @staticmethod
    def wait_task_result_from_stream(
        task_id: str,
        timeout: int = 10,
        stream_key: str = "agent_results",
    ) -> Optional[Dict[str, Any]]:
        """
        从 Redis Stream 阻塞等待指定 task_id 的结果（非消费组读取，不影响消费）。
        """
        try:
            if not task_id:
                return None
            from django.conf import settings

            client = redis.Redis(
                host=getattr(settings, "REDIS_HOST", "localhost"),
                port=getattr(settings, "REDIS_PORT", 6379),
                password=getattr(settings, "REDIS_PASSWORD", None),
                db=getattr(settings, "REDIS_DB_REALTIME", 3),
                decode_responses=True,
                socket_connect_timeout=3,
                socket_timeout=3,
                retry_on_timeout=True,
            )

            deadline = time.time() + max(timeout, 1)
            last_id = "$"  # 只关注调用后的新消息

            while time.time() < deadline:
                block_ms = int(max(1, min(1000, (deadline - time.time()) * 1000)))
                resp = client.xread(
                    {stream_key: last_id},
                    count=20,
                    block=block_ms,
                )
                if not resp:
                    continue
                for _, messages in resp:
                    for msg_id, fields in messages:
                        last_id = msg_id
                        if fields.get("task_id") == task_id:
                            return fields
            return None
        except Exception as exc:
            logger.warning(f"等待任务结果失败: {exc}")
            return None

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
                        execution_mode=execution_mode,  # 传递执行模式
                        rolling_batch_size=rolling_batch_size,  # 传递滚动批次大小
                        rolling_batch_delay=rolling_batch_delay,  # 传递滚动批次延迟
                        ignore_error=step_data.get('ignore_error', False),  # 传递忽略错误标志
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

                    # 如果步骤包含 file_sources（多来源），仅支持 server/artifact，server 会先 HTTP 拉取入库
                    file_sources = step_data.get('file_sources') or []
                    if file_sources:
                        overall_results = {'success_count': 0, 'failed_count': 0, 'results': []}
                        for src in file_sources:
                            remote_path_src = src.get('remote_path') or step_data.get('remote_path', '')
                            res = AgentExecutionService.execute_file_transfer_via_agent(
                                execution_record=execution_record,
                                remote_path=remote_path_src,
                                target_hosts=step_target_hosts,
                                timeout=step_data.get('timeout', 300),
                                bandwidth_limit=step_data.get('bandwidth_limit', 0),
                                download_url=src.get('download_url'),
                                checksum=src.get('sha256'),
                                size=src.get('size'),
                                auth_headers=src.get('auth_headers') or {},
                                step_id=str(step.id),
                                agent_server_url=agent_server_url,
                                account_id=step_data.get('account_id'),  # 传递执行账号ID
                                file_sources=[src],  # server 源将先落库
                            )

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
        progress: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        处理Agent任务执行结果

        Args:
            task_id: 任务ID
            result: 任务结果
            progress: 进度信息（可选，从 agent_results stream 聚合计算得出）

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

            # 保存日志指针/大小到 execution_results，供历史页回源
            log_pointer = result.get('log_pointer')
            log_size = result.get('log_size')
            if log_pointer or log_size is not None:
                results_meta = execution_record.execution_results or {}
                meta_logs = results_meta.get('logs_meta', {})
                meta_logs.update({
                    'log_pointer': log_pointer,
                    'log_size': log_size,
                })

                results_meta['logs_meta'] = meta_logs
                execution_record.execution_results = results_meta

            # 处理进度信息（从 agent_results stream 聚合计算）
            if progress:
                exec_results = execution_record.execution_results or {}
                exec_results['progress'] = {
                    'progress': progress.get('progress'),
                    'total_hosts': progress.get('total_hosts'),
                    'success_hosts': progress.get('success_hosts'),
                    'failed_hosts': progress.get('failed_hosts'),
                    'running_hosts': progress.get('running_hosts'),
                    'pending_hosts': progress.get('pending_hosts'),
                    'updated_at': datetime.now(tz=timezone.utc).isoformat(),
                }
                execution_record.execution_results = exec_results

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
    def _fetch_log_excerpt(log_pointer: str, tail: int = 50) -> Optional[str]:
        """根据 storage_uri 风格的 log_pointer 获取末尾摘录，默认取最后 tail 条记录内容拼接。"""
        try:
            if not log_pointer:
                return None
            # 仅支持 redis:job_logs/<task_id>@<id> 形式的指针
            if log_pointer.startswith("redis:"):
                logs = realtime_log_service.get_logs_by_pointer(log_pointer, limit=tail) or []
                if not logs:
                    return None
                excerpt_lines = [entry.get('content', '') for entry in logs[-tail:] if entry.get('content')]
                if excerpt_lines:
                    return "\n".join(excerpt_lines)
            # 其他协议暂不在此处回源，留给归档/查看接口处理
            return None
        except Exception as e:
            logger.warning(f"获取日志摘录失败: pointer={log_pointer}, err={e}")
            return None

    @staticmethod
    @retry_on_db_error(max_retries=3, delay=0.2, backoff=1.5)
    def retry_execution_record(
        execution_record: ExecutionRecord,
        user,
        retry_type: str = 'full',  # full: 完整重试, step: 步骤重试
        step_id: str = None,
        failed_only: bool = True,
        agent_server_url: str = None,
        ip_list: List[str] = None,  # 基于IP的重试支持
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
            ip_list: 指定IP列表进行重试（可选）
        
        Returns:
            Dict: 重试结果
        """
        try:
            from apps.job_templates.services import ExecutionPlanService
            from django.db import transaction
            from apps.system_config.models import ConfigManager

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

                    # 在事务中进行并发检查
                    max_concurrent_retries = ConfigManager.get('execution.max_concurrent_retries', 10)
                    with transaction.atomic():
                        # 使用悲观锁检查当前并发数量
                        current_retries = ExecutionRecord.objects.filter(
                            status__in=['running', 'pending'],
                            execution_type__in=['job_workflow', 'quick_script', 'quick_file_transfer']
                        ).select_for_update().count()

                        if current_retries >= max_concurrent_retries:
                            return {
                                'success': False,
                                'error': f'并发重试数量已达上限 ({max_concurrent_retries})，请稍后再试'
                            }

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

                    # 在事务中进行并发检查
                    max_concurrent_retries = ConfigManager.get('execution.max_concurrent_retries', 10)
                    with transaction.atomic():
                        # 使用悲观锁检查当前并发数量
                        current_retries = ExecutionRecord.objects.filter(
                            status__in=['running', 'pending'],
                            execution_type__in=['job_workflow', 'quick_script', 'quick_file_transfer']
                        ).select_for_update().count()

                        if current_retries >= max_concurrent_retries:
                            return {
                                'success': False,
                                'error': f'并发重试数量已达上限 ({max_concurrent_retries})，请稍后再试'
                            }

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
                        'file_sources': params.get('file_sources', []),
                        'remote_path': params.get('remote_path'),
                        'timeout': params.get('timeout', 300),
                        'execution_mode': params.get('execution_mode', 'parallel'),
                        'rolling_batch_size': params.get('rolling_batch_size', 20),
                        'rolling_batch_delay': params.get('rolling_batch_delay', 0),
                        'overwrite_policy': params.get('overwrite_policy', 'overwrite'),
                        'target_host_ids': params.get('target_host_ids', []),
                        'agent_server_url': agent_server_url,
                        'bandwidth_limit': params.get('bandwidth_limit', 0),
                        'account_id': params.get('account_id'),
                    }

                    # 在事务中进行并发检查
                    max_concurrent_retries = ConfigManager.get('execution.max_concurrent_retries', 10)
                    with transaction.atomic():
                        # 使用悲观锁检查当前并发数量
                        current_retries = ExecutionRecord.objects.filter(
                            status__in=['running', 'pending'],
                            execution_type__in=['job_workflow', 'quick_script', 'quick_file_transfer']
                        ).select_for_update().count()

                        if current_retries >= max_concurrent_retries:
                            return {
                                'success': False,
                                'error': f'并发重试数量已达上限 ({max_concurrent_retries})，请稍后再试'
                            }

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
                if ip_list:
                    # 基于IP列表的重试
                    target_hosts = [
                        host for host in step.host_results
                        if host.get('host_ip') in ip_list
                    ]
                    if not target_hosts:
                        return {
                            'success': False,
                            'error': f'指定的IP列表 {ip_list} 中没有找到对应的主机'
                        }
                elif failed_only:
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

                # 检查Agent状态，只对在线的Agent执行重试
                online_hosts = []
                for host in target_host_objs:
                    if hasattr(host, 'agent') and host.agent and host.agent.status == 'online':
                        online_hosts.append(host)
                    else:
                        logger.warning(f"主机 {host.id} 的Agent不在线，跳过重试")

                if not online_hosts:
                    return {
                        'success': False,
                        'error': '没有在线的Agent主机，无法重试'
                    }

                # 根据步骤类型执行
                step_type = step.step_type
                step_params = step.step_parameters or {}

                if step_type == 'script':
                    # 脚本步骤重试
                    result = AgentExecutionService.execute_script_via_agent(
                        execution_record=execution_record,
                        script_content=step_params.get('script_content', ''),
                        script_type=step_params.get('script_type', 'shell'),
                        target_hosts=online_hosts,
                        timeout=step_params.get('timeout', 300),
                        global_variables=execution_record.execution_parameters.get('global_variables', {}),
                        step_id=str(step.id),
                        agent_server_url=agent_server_url,
                        account_id=step_params.get('account_id'),  # 传递执行账号ID
                    )
                elif step_type == 'file_transfer':
                    file_sources = step_params.get('file_sources') or []
                    if not file_sources:
                        return {'success': False, 'error': 'file_sources required for file_transfer step'}
                    src = file_sources[0]
                    remote_path = src.get('remote_path') or step_params.get('remote_path', '')

                    result = AgentExecutionService.execute_file_transfer_via_agent(
                        execution_record=execution_record,
                        remote_path=remote_path,
                        target_hosts=online_hosts,
                        timeout=step_params.get('timeout', 300),
                        bandwidth_limit=step_params.get('bandwidth_limit', 0),
                        download_url=src.get('download_url'),
                        checksum=src.get('sha256'),
                        size=src.get('size'),
                        auth_headers=src.get('auth_headers') or {},
                        step_id=str(step.id),
                        agent_server_url=agent_server_url,
                        account_id=step_params.get('account_id'),  # 传递执行账号ID
                        file_sources=file_sources,
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
            
            # Agent-Server模式（唯一支持的模式）
            server_url = agent_server_url or execution_record.execution_parameters.get('agent_server_url')
            if not server_url:
                return {
                    'success': False,
                    'error': 'Agent-Server URL 未配置'
                }
            return AgentExecutionService._cancel_tasks_via_agent_server(
                agent_task_map=agent_task_map,
                server_url=server_url,
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
                        # 使用 HMAC 客户端发起请求
                        from utils.agent_server_client import AgentServerClient

                        client = AgentServerClient.from_settings()
                        response = client.post(api_url, json=None, headers=headers_base)
                        
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
