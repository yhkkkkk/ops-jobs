"""
Agent 执行服务
用于通过 Agent 执行任务，支持与 ExecutionRecord 关联
"""
import logging
import uuid
from typing import Dict, Any, List, Optional
from django.utils import timezone
from django.db import transaction

from apps.executor.models import ExecutionRecord, ExecutionStep
from apps.executor.services import ExecutionRecordService
from apps.hosts.models import Host
from apps.agents.models import Agent
from utils.realtime_logs import realtime_log_service

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
        return task_spec

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

            # 确定Agent-Server地址
            if agent_server_url:
                server_url = agent_server_url
            elif agent.endpoint:
                # 从Agent的endpoint提取Agent-Server地址
                server_url = agent.endpoint
            else:
                # 从配置获取默认Agent-Server地址
                server_url = getattr(settings, 'AGENT_SERVER_URL', None)
                if not server_url:
                    return {
                        'success': False,
                        'error': 'Agent-Server地址未配置'
                    }

            # 确保URL格式正确
            if server_url.startswith('ws://') or server_url.startswith('wss://'):
                server_url = server_url.replace('ws://', 'http://').replace('wss://', 'https://')
            
            # 移除路径部分，只保留基础URL
            if '/' in server_url[8:]:  # 跳过 http:// 或 https://
                server_url = server_url[:server_url.find('/', 8)]

            # 构建API URL
            api_url = f"{server_url}/api/agents/{agent.host_id}/tasks"
            
            # 获取Agent-Server的认证Token（如果需要）
            agent_server_token = getattr(settings, 'AGENT_SERVER_TOKEN', None)
            
            headers = {
                'Content-Type': 'application/json',
            }
            if agent_server_token:
                headers['Authorization'] = f'Bearer {agent_server_token}'

            # 发送任务
            response = requests.post(
                api_url,
                json=task_spec,
                headers=headers,
                timeout=10
            )

            if response.status_code == 200:
                result = response.json()
                logger.info(f"任务已推送到Agent: {task_spec['id']}, Agent: {agent.host_id}")
                return {
                    'success': True,
                    'task_id': task_spec['id'],
                    'agent_id': agent.host_id,
                    'status': result.get('status', 'dispatched')
                }
            else:
                error_msg = response.text or f"HTTP {response.status_code}"
                logger.error(f"推送任务到Agent失败: {error_msg}")
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
        step_id: str = None,
        agent_server_url: str = None,
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

                # 创建文件传输规范
                # 注意：Go的JSON库会自动将base64字符串解码为[]byte
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
                    'content': file_content_b64,  # base64编码的字符串，Go JSON库会自动解码为[]byte
                    'bandwidth_limit': bandwidth_limit,
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
                    )

                    # 更新步骤结果
                    host_results = []
                    for r in result.get('results', []):
                        host_results.append({
                            'host_id': r.get('host_id'),
                            'host_name': r.get('host_name'),
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

                    # 读取文件内容（如果是上传）
                    file_content = None
                    if step_data.get('transfer_type') == 'upload':
                        local_path = step_data.get('local_path', '')
                        if local_path:
                            try:
                                with open(local_path, 'rb') as f:
                                    file_content = f.read()
                            except Exception as e:
                                logger.error(f"读取文件失败: {str(e)}")
                                ExecutionRecordService.update_step_status(
                                    step, 'failed',
                                    error_message=f'读取文件失败: {str(e)}'
                                )
                                if not step_data.get('ignore_error', False):
                                    overall_success = False
                                    break
                                continue

                    # 通过Agent执行文件传输
                    result = AgentExecutionService.execute_file_transfer_via_agent(
                        execution_record=execution_record,
                        transfer_type=step_data.get('transfer_type', 'upload'),
                        local_path=step_data.get('local_path', ''),
                        remote_path=step_data.get('remote_path', ''),
                        target_hosts=step_target_hosts,
                        file_content=file_content,
                        timeout=step_data.get('timeout', 300),
                        bandwidth_limit=step_data.get('bandwidth_limit', 0),
                        step_id=str(step.id),
                        agent_server_url=agent_server_url,
                    )

                    # 更新步骤结果
                    host_results = []
                    for r in result.get('results', []):
                        host_results.append({
                            'host_id': r.get('host_id'),
                            'host_name': r.get('host_name'),
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

            execution_record.finished_at = timezone.now()
            execution_record.save()

            # 如果是工作流，更新步骤状态和主机结果
            if step_id and step_id != 'main':
                try:
                    step = ExecutionStep.objects.get(id=step_id, execution_record=execution_record)
                    step.status = status
                    if status == 'failed':
                        step.error_message = result.get('error_msg', '步骤执行失败')
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


