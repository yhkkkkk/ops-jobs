"""
执行策略模块

定义执行模式策略，包括并行、串行和滚动执行。
"""
import logging
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional
from concurrent.futures import Future, as_completed

from apps.hosts.models import Host
from apps.agents.models import Agent

logger = logging.getLogger(__name__)


@dataclass
class HostResult:
    """单个主机的执行结果"""
    host_id: int
    host_name: str
    task_id: str
    success: bool
    exit_code: Optional[int] = None
    error: Optional[str] = None
    started_at: Optional[str] = None
    finished_at: Optional[str] = None


@dataclass
class ExecutionResult:
    """执行策略的整体结果"""
    success: bool
    total: int
    success_count: int
    failed_count: int
    results: List[HostResult] = field(default_factory=list)
    stopped_early: bool = False  # 是否因错误提前终止


class ExecutionStrategy(ABC):
    """
    执行策略基类

    定义执行多主机任务的策略接口。
    """

    @abstractmethod
    def execute(
        self,
        hosts: List[Host],
        task_creator: Callable[[Host], Dict[str, Any]],
        task_pusher: Callable[[Agent, Dict[str, Any]], Dict[str, Any]],
        on_result: Optional[Callable[[Host, Dict[str, Any]], None]] = None,
        timeout: int = 300,
        ignore_error: bool = False,
    ) -> ExecutionResult:
        """
        执行任务

        Args:
            hosts: 目标主机列表
            task_creator: 为每个主机创建任务规范的函数，参数为 Host，返回任务规范字典
            task_pusher: 推送任务到 Agent 的函数，参数为 (Agent, task_spec)，返回推送结果
            on_result: 收到结果时的回调函数，参数为 (Host, result_dict)
            timeout: 任务超时时间（秒）
            ignore_error: 是否忽略错误继续执行

        Returns:
            ExecutionResult: 执行结果
        """
        pass


class ParallelExecutionStrategy(ExecutionStrategy):
    """
    并行执行策略

    同时向所有主机推送任务，并行等待所有结果。
    """

    def execute(
        self,
        hosts: List[Host],
        task_creator: Callable[[Host], Dict[str, Any]],
        task_pusher: Callable[[Agent, Dict[str, Any]], Dict[str, Any]],
        on_result: Optional[Callable[[Host, Dict[str, Any]], None]] = None,
        timeout: int = 300,
        ignore_error: bool = False,
    ) -> ExecutionResult:
        if not hosts:
            return ExecutionResult(
                success=True,
                total=0,
                success_count=0,
                failed_count=0,
                results=[]
            )

        from utils.thread_pool import get_global_thread_pool
        from utils.task_result_waiter import get_task_result_waiter

        pool = get_global_thread_pool()
        waiter = get_task_result_waiter()

        results: List[HostResult] = []
        task_id_to_host: Dict[str, Host] = {}
        push_futures: Dict[Future, Host] = {}

        # 并发推送任务
        for host in hosts:
            if not hasattr(host, 'agent') or not host.agent:
                results.append(HostResult(
                    host_id=host.id,
                    host_name=host.name,
                    task_id='',
                    success=False,
                    error='主机没有 Agent'
                ))
                continue

            agent = host.agent
            if agent.status != 'online':
                results.append(HostResult(
                    host_id=host.id,
                    host_name=host.name,
                    task_id='',
                    success=False,
                    error=f'Agent 状态为 {agent.status}'
                ))
                continue

            try:
                task_spec = task_creator(host)
                future = pool.submit(task_pusher, agent, task_spec)
                push_futures[future] = host
                task_id_to_host[task_spec['id']] = host
            except Exception as e:
                logger.error(f"创建任务规范失败: host={host.name}, error={e}")
                results.append(HostResult(
                    host_id=host.id,
                    host_name=host.name,
                    task_id='',
                    success=False,
                    error=f'创建任务失败: {str(e)}'
                ))

        # 等待所有推送完成
        pushed_task_ids: List[str] = []
        for future in as_completed(push_futures.keys()):
            host = push_futures[future]
            try:
                push_result = future.result()
                if push_result.get('success'):
                    task_id = push_result.get('task_id')
                    pushed_task_ids.append(task_id)
                    logger.debug(f"任务推送成功: host={host.name}, task_id={task_id}")
                else:
                    results.append(HostResult(
                        host_id=host.id,
                        host_name=host.name,
                        task_id=push_result.get('task_id', ''),
                        success=False,
                        error=push_result.get('error', '推送失败')
                    ))
            except Exception as e:
                logger.error(f"任务推送异常: host={host.name}, error={e}")
                results.append(HostResult(
                    host_id=host.id,
                    host_name=host.name,
                    task_id='',
                    success=False,
                    error=f'推送异常: {str(e)}'
                ))

        # 等待所有任务结果
        if pushed_task_ids:
            task_results = waiter.wait_for_results(pushed_task_ids, timeout=timeout)

            for task_id, result in task_results.items():
                host = task_id_to_host.get(task_id)
                if host:
                    host_result = HostResult(
                        host_id=host.id,
                        host_name=host.name,
                        task_id=task_id,
                        success=result.get('success', False),
                        exit_code=result.get('exit_code'),
                        error=result.get('error_msg'),
                        started_at=result.get('started_at'),
                        finished_at=result.get('finished_at')
                    )
                    results.append(host_result)

                    if on_result:
                        try:
                            on_result(host, result)
                        except Exception as e:
                            logger.error(f"结果回调执行失败: host={host.name}, error={e}")

        success_count = sum(1 for r in results if r.success)
        failed_count = len(results) - success_count

        return ExecutionResult(
            success=failed_count == 0 or ignore_error,
            total=len(hosts),
            success_count=success_count,
            failed_count=failed_count,
            results=results,
            stopped_early=False
        )


class SerialExecutionStrategy(ExecutionStrategy):
    """
    串行执行策略

    逐个主机执行任务，等待当前主机完成后再执行下一个。
    """

    def execute(
        self,
        hosts: List[Host],
        task_creator: Callable[[Host], Dict[str, Any]],
        task_pusher: Callable[[Agent, Dict[str, Any]], Dict[str, Any]],
        on_result: Optional[Callable[[Host, Dict[str, Any]], None]] = None,
        timeout: int = 300,
        ignore_error: bool = False,
    ) -> ExecutionResult:
        if not hosts:
            return ExecutionResult(
                success=True,
                total=0,
                success_count=0,
                failed_count=0,
                results=[]
            )

        from utils.task_result_waiter import get_task_result_waiter

        waiter = get_task_result_waiter()
        results: List[HostResult] = []
        stopped_early = False

        for host in hosts:
            # 检查主机是否有可用的 Agent
            if not hasattr(host, 'agent') or not host.agent:
                host_result = HostResult(
                    host_id=host.id,
                    host_name=host.name,
                    task_id='',
                    success=False,
                    error='主机没有 Agent'
                )
                results.append(host_result)

                if not ignore_error:
                    stopped_early = True
                    break
                continue

            agent = host.agent
            if agent.status != 'online':
                host_result = HostResult(
                    host_id=host.id,
                    host_name=host.name,
                    task_id='',
                    success=False,
                    error=f'Agent 状态为 {agent.status}'
                )
                results.append(host_result)

                if not ignore_error:
                    stopped_early = True
                    break
                continue

            # 创建并推送任务
            try:
                task_spec = task_creator(host)
                push_result = task_pusher(agent, task_spec)

                if not push_result.get('success'):
                    host_result = HostResult(
                        host_id=host.id,
                        host_name=host.name,
                        task_id=push_result.get('task_id', ''),
                        success=False,
                        error=push_result.get('error', '推送失败')
                    )
                    results.append(host_result)

                    if not ignore_error:
                        stopped_early = True
                        break
                    continue

                task_id = push_result.get('task_id')

                # 等待任务完成
                result = waiter.wait_for_result(task_id, timeout=timeout)

                host_result = HostResult(
                    host_id=host.id,
                    host_name=host.name,
                    task_id=task_id,
                    success=result.get('success', False),
                    exit_code=result.get('exit_code'),
                    error=result.get('error_msg'),
                    started_at=result.get('started_at'),
                    finished_at=result.get('finished_at')
                )
                results.append(host_result)

                if on_result:
                    try:
                        on_result(host, result)
                    except Exception as e:
                        logger.error(f"结果回调执行失败: host={host.name}, error={e}")

                # 检查是否应该停止
                if not host_result.success and not ignore_error:
                    stopped_early = True
                    break

            except Exception as e:
                logger.error(f"串行执行失败: host={host.name}, error={e}")
                host_result = HostResult(
                    host_id=host.id,
                    host_name=host.name,
                    task_id='',
                    success=False,
                    error=f'执行异常: {str(e)}'
                )
                results.append(host_result)

                if not ignore_error:
                    stopped_early = True
                    break

        success_count = sum(1 for r in results if r.success)
        failed_count = len(results) - success_count

        return ExecutionResult(
            success=(failed_count == 0 or ignore_error) and not stopped_early,
            total=len(hosts),
            success_count=success_count,
            failed_count=failed_count,
            results=results,
            stopped_early=stopped_early
        )


class RollingExecutionStrategy(ExecutionStrategy):
    """
    滚动执行策略

    分批执行任务，每批完成后再执行下一批。
    """

    def __init__(self, batch_size: int = 1, batch_delay: int = 0):
        """
        初始化滚动执行策略

        Args:
            batch_size: 每批主机数量，默认为 1
            batch_delay: 批次间延迟（秒），默认为 0
        """
        self.batch_size = max(1, batch_size)  # 至少为 1
        self.batch_delay = max(0, batch_delay)

    def execute(
        self,
        hosts: List[Host],
        task_creator: Callable[[Host], Dict[str, Any]],
        task_pusher: Callable[[Agent, Dict[str, Any]], Dict[str, Any]],
        on_result: Optional[Callable[[Host, Dict[str, Any]], None]] = None,
        timeout: int = 300,
        ignore_error: bool = False,
    ) -> ExecutionResult:
        if not hosts:
            return ExecutionResult(
                success=True,
                total=0,
                success_count=0,
                failed_count=0,
                results=[]
            )

        from utils.thread_pool import get_global_thread_pool
        from utils.task_result_waiter import get_task_result_waiter

        pool = get_global_thread_pool()
        waiter = get_task_result_waiter()

        results: List[HostResult] = []
        stopped_early = False

        # 将主机分成批次
        batches = [
            hosts[i:i + self.batch_size]
            for i in range(0, len(hosts), self.batch_size)
        ]
        total_batches = len(batches)

        logger.info(f"滚动执行: 共 {len(hosts)} 个主机，分 {total_batches} 批，每批 {self.batch_size} 个")

        for batch_index, batch_hosts in enumerate(batches):
            batch_num = batch_index + 1
            logger.info(f"开始执行第 {batch_num}/{total_batches} 批 ({len(batch_hosts)} 个主机)")

            batch_results: List[HostResult] = []
            task_id_to_host: Dict[str, Host] = {}
            push_futures: Dict[Future, Host] = {}

            # 并发推送当前批次的任务
            for host in batch_hosts:
                if not hasattr(host, 'agent') or not host.agent:
                    batch_results.append(HostResult(
                        host_id=host.id,
                        host_name=host.name,
                        task_id='',
                        success=False,
                        error='主机没有 Agent'
                    ))
                    continue

                agent = host.agent
                if agent.status != 'online':
                    batch_results.append(HostResult(
                        host_id=host.id,
                        host_name=host.name,
                        task_id='',
                        success=False,
                        error=f'Agent 状态为 {agent.status}'
                    ))
                    continue

                try:
                    task_spec = task_creator(host)
                    future = pool.submit(task_pusher, agent, task_spec)
                    push_futures[future] = host
                    task_id_to_host[task_spec['id']] = host
                except Exception as e:
                    logger.error(f"创建任务规范失败: host={host.name}, error={e}")
                    batch_results.append(HostResult(
                        host_id=host.id,
                        host_name=host.name,
                        task_id='',
                        success=False,
                        error=f'创建任务失败: {str(e)}'
                    ))

            # 等待推送完成
            pushed_task_ids: List[str] = []
            for future in as_completed(push_futures.keys()):
                host = push_futures[future]
                try:
                    push_result = future.result()
                    if push_result.get('success'):
                        task_id = push_result.get('task_id')
                        pushed_task_ids.append(task_id)
                    else:
                        batch_results.append(HostResult(
                            host_id=host.id,
                            host_name=host.name,
                            task_id=push_result.get('task_id', ''),
                            success=False,
                            error=push_result.get('error', '推送失败')
                        ))
                except Exception as e:
                    batch_results.append(HostResult(
                        host_id=host.id,
                        host_name=host.name,
                        task_id='',
                        success=False,
                        error=f'推送异常: {str(e)}'
                    ))

            # 等待当前批次的所有任务结果
            if pushed_task_ids:
                task_results = waiter.wait_for_results(pushed_task_ids, timeout=timeout)

                for task_id, result in task_results.items():
                    host = task_id_to_host.get(task_id)
                    if host:
                        host_result = HostResult(
                            host_id=host.id,
                            host_name=host.name,
                            task_id=task_id,
                            success=result.get('success', False),
                            exit_code=result.get('exit_code'),
                            error=result.get('error_msg'),
                            started_at=result.get('started_at'),
                            finished_at=result.get('finished_at')
                        )
                        batch_results.append(host_result)

                        if on_result:
                            try:
                                on_result(host, result)
                            except Exception as e:
                                logger.error(f"结果回调执行失败: host={host.name}, error={e}")

            results.extend(batch_results)

            # 检查当前批次是否有失败
            batch_failed = any(not r.success for r in batch_results)
            if batch_failed and not ignore_error:
                logger.warning(f"第 {batch_num}/{total_batches} 批有失败，停止后续批次执行")
                stopped_early = True
                break

            # 如果还有下一批，等待延迟
            if batch_index < total_batches - 1 and self.batch_delay > 0:
                logger.info(f"等待 {self.batch_delay} 秒后执行下一批")
                time.sleep(self.batch_delay)

        success_count = sum(1 for r in results if r.success)
        failed_count = len(results) - success_count

        return ExecutionResult(
            success=(failed_count == 0 or ignore_error) and not stopped_early,
            total=len(hosts),
            success_count=success_count,
            failed_count=failed_count,
            results=results,
            stopped_early=stopped_early
        )


def get_execution_strategy(
    mode: str,
    batch_size: int = 1,
    batch_delay: int = 0
) -> ExecutionStrategy:
    """
    根据执行模式获取对应的策略实例

    Args:
        mode: 执行模式 ('parallel', 'serial', 'rolling')
        batch_size: 滚动模式的批次大小
        batch_delay: 滚动模式的批次延迟

    Returns:
        ExecutionStrategy: 策略实例
    """
    if mode == 'serial':
        return SerialExecutionStrategy()
    elif mode == 'rolling':
        return RollingExecutionStrategy(batch_size=batch_size, batch_delay=batch_delay)
    else:
        # 默认并行
        return ParallelExecutionStrategy()
