"""
状态同步服务 - 检测和解决任务状态不一致问题
"""
import logging
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime, timedelta

from django.db import transaction
from django.utils import timezone
from django.db.models import Q, Count

from apps.agents.models import Agent
from apps.executor.models import ExecutionRecord, ExecutionStep
from apps.agents.execution_service import AgentExecutionService

logger = logging.getLogger(__name__)


class StatusReconciliationService:
    """状态同步服务 - 检测和解决任务状态不一致问题"""

    def __init__(self):
        self.max_conflicts_per_run = 100  # 每次运行最多处理的状态冲突数量
        self.conflict_detection_window_hours = 24  # 冲突检测时间窗口（小时）

    def reconcile_agent_status(self, agent_id: int) -> Dict[str, Any]:
        """
        检查并修复指定Agent的状态冲突

        Args:
            agent_id: Agent ID

        Returns:
            Dict: 同步结果
        """
        try:
            # 获取Agent
            agent = Agent.objects.get(id=agent_id)

            logger.info(f"开始状态同步: Agent {agent_id} ({agent.host.name})")

            conflicts_found = []
            conflicts_resolved = []

            # 1. 检查执行记录状态冲突
            execution_conflicts = self._check_execution_status_conflicts(agent)
            conflicts_found.extend(execution_conflicts)

            # 2. 检查步骤状态冲突
            step_conflicts = self._check_step_status_conflicts(agent)
            conflicts_found.extend(step_conflicts)

            # 3. 解决检测到的冲突
            for conflict in conflicts_found[:self.max_conflicts_per_run]:
                resolved = self._resolve_single_conflict(conflict)
                if resolved:
                    conflicts_resolved.append(conflict)

            return {
                'success': True,
                'agent_id': agent_id,
                'conflicts_found': len(conflicts_found),
                'conflicts_resolved': len(conflicts_resolved),
                'details': {
                    'execution_conflicts': len(execution_conflicts),
                    'step_conflicts': len(step_conflicts),
                    'resolved_execution_conflicts': len([c for c in conflicts_resolved if c['type'] == 'execution']),
                    'resolved_step_conflicts': len([c for c in conflicts_resolved if c['type'] == 'step']),
                }
            }

        except Agent.DoesNotExist:
            return {
                'success': False,
                'error': f'Agent不存在: {agent_id}'
            }
        except Exception as e:
            logger.error(f"状态同步失败: Agent {agent_id}, 错误: {e}")
            return {
                'success': False,
                'error': str(e)
            }

    def detect_status_anomalies(self, hours_back: int = 24) -> List[Dict[str, Any]]:
        """
        识别潜在的状态异常

        Args:
            hours_back: 回溯时间（小时）

        Returns:
            List[Dict]: 检测到的异常列表
        """
        anomalies = []
        cutoff_time = timezone.now() - timedelta(hours=hours_back)

        try:
            # 1. 检测长时间运行的任务
            long_running_executions = ExecutionRecord.objects.filter(
                status='running',
                started_at__lt=cutoff_time
            ).select_related('related_object')

            for execution in long_running_executions:
                anomalies.append({
                    'type': 'long_running_execution',
                    'severity': 'medium',
                    'execution_id': execution.execution_id,
                    'started_at': execution.started_at,
                    'duration_hours': (timezone.now() - execution.started_at).total_seconds() / 3600,
                    'description': f'执行任务已运行超过{hours_back}小时'
                })

            # 2. 检测状态不一致的步骤
            inconsistent_steps = ExecutionStep.objects.filter(
                Q(status='running') & Q(started_at__lt=cutoff_time) |
                Q(status='pending') & Q(created_at__lt=cutoff_time)
            )

            for step in inconsistent_steps:
                anomalies.append({
                    'type': 'inconsistent_step_status',
                    'severity': 'high',
                    'step_id': step.id,
                    'execution_id': step.execution_record.execution_id,
                    'status': step.status,
                    'created_at': step.created_at,
                    'description': f'步骤状态异常：{step.status}状态已持续过久'
                })

            # 3. 检测Agent离线但任务仍运行的情况
            offline_agents = Agent.objects.filter(
                status='offline',
                last_heartbeat_at__lt=cutoff_time
            )

            for agent in offline_agents:
                # 检查是否有该Agent相关的运行中任务
                running_tasks = ExecutionStep.objects.filter(
                    execution_record__execution_parameters__contains={'target_host_ids': [agent.host_id]},
                    status__in=['running', 'pending']
                ).exists()

                if running_tasks:
                    anomalies.append({
                        'type': 'offline_agent_with_running_tasks',
                        'severity': 'critical',
                        'agent_id': agent.id,
                        'agent_name': agent.host.name,
                        'last_heartbeat': agent.last_heartbeat_at,
                        'description': f'Agent离线但仍有运行中的任务'
                    })

            logger.info(f"检测到 {len(anomalies)} 个状态异常")

        except Exception as e:
            logger.error(f"检测状态异常失败: {e}")

        return anomalies

    def resolve_conflicts(self, conflicts: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        应用冲突解决规则

        Args:
            conflicts: 冲突列表

        Returns:
            Dict: 解决结果
        """
        resolved_count = 0
        failed_count = 0

        for conflict in conflicts[:self.max_conflicts_per_run]:
            try:
                if self._resolve_single_conflict(conflict):
                    resolved_count += 1
                else:
                    failed_count += 1
            except Exception as e:
                logger.error(f"解决冲突失败: {conflict}, 错误: {e}")
                failed_count += 1

        return {
            'total_conflicts': len(conflicts),
            'resolved_count': resolved_count,
            'failed_count': failed_count,
            'success_rate': resolved_count / len(conflicts) if conflicts else 0
        }

    def _check_execution_status_conflicts(self, agent: Agent) -> List[Dict[str, Any]]:
        """检查执行记录状态冲突"""
        conflicts = []

        # 获取最近24小时该Agent相关的执行记录
        cutoff_time = timezone.now() - timedelta(hours=self.conflict_detection_window_hours)

        # 通过execution_parameters中的target_host_ids查找相关的执行
        executions = ExecutionRecord.objects.filter(
            Q(created_at__gte=cutoff_time) &
            (
                Q(execution_parameters__target_host_ids__contains=[agent.host_id]) |
                Q(execution_parameters__contains={'target_host_ids': [agent.host_id]})
            )
        )

        for execution in executions:
            # 检查是否有明显的状态不一致
            if execution.status == 'running' and execution.started_at:
                # 检查是否所有步骤都已完成
                total_steps = execution.steps.count()
                completed_steps = execution.steps.filter(status__in=['success', 'failed', 'skipped']).count()

                if total_steps > 0 and completed_steps == total_steps and execution.status == 'running':
                    conflicts.append({
                        'type': 'execution',
                        'conflict_type': 'execution_stuck_running',
                        'execution_id': execution.execution_id,
                        'current_status': execution.status,
                        'expected_status': 'success',  # 所有步骤完成时应该成功
                        'reason': '所有步骤已完成但执行状态仍为运行中',
                        'agent_id': agent.id,
                        'resolution': 'update_execution_status'
                    })

            # 检查超时的执行
            if execution.status == 'running' and execution.started_at:
                timeout_hours = execution.execution_parameters.get('timeout', 2)  # 默认2小时
                if (timezone.now() - execution.started_at).total_seconds() / 3600 > timeout_hours:
                    conflicts.append({
                        'type': 'execution',
                        'conflict_type': 'execution_timeout',
                        'execution_id': execution.execution_id,
                        'current_status': execution.status,
                        'timeout_hours': timeout_hours,
                        'running_hours': (timezone.now() - execution.started_at).total_seconds() / 3600,
                        'reason': f'执行已运行超过{timeout_hours}小时',
                        'agent_id': agent.id,
                        'resolution': 'mark_execution_timeout'
                    })

        return conflicts

    def _check_step_status_conflicts(self, agent: Agent) -> List[Dict[str, Any]]:
        """检查步骤状态冲突"""
        conflicts = []

        # 获取最近24小时该Agent相关的步骤
        cutoff_time = timezone.now() - timedelta(hours=self.conflict_detection_window_hours)

        steps = ExecutionStep.objects.filter(
            Q(execution_record__created_at__gte=cutoff_time) &
            Q(host_results__contains=[{'host_id': agent.host_id}])
        ).select_related('execution_record')

        for step in steps:
            # 检查步骤超时
            if step.status == 'running' and step.started_at:
                # 从步骤参数或执行参数中获取超时时间
                timeout_sec = step.step_parameters.get('timeout', 300)  # 默认5分钟
                if (timezone.now() - step.started_at).total_seconds() > timeout_sec:
                    conflicts.append({
                        'type': 'step',
                        'conflict_type': 'step_timeout',
                        'step_id': step.id,
                        'execution_id': step.execution_record.execution_id,
                        'current_status': step.status,
                        'timeout_seconds': timeout_sec,
                        'running_seconds': (timezone.now() - step.started_at).total_seconds(),
                        'reason': f'步骤已运行超过{timeout_sec}秒',
                        'agent_id': agent.id,
                        'resolution': 'mark_step_timeout'
                    })

            # 检查Agent离线但步骤仍在运行
            if step.status == 'running' and agent.status == 'offline':
                conflicts.append({
                    'type': 'step',
                    'conflict_type': 'step_running_on_offline_agent',
                    'step_id': step.id,
                    'execution_id': step.execution_record.execution_id,
                    'current_status': step.status,
                    'agent_status': agent.status,
                    'last_heartbeat': agent.last_heartbeat_at,
                    'reason': 'Agent已离线但步骤仍在运行',
                    'agent_id': agent.id,
                    'resolution': 'mark_step_failed'
                })

        return conflicts

    def _resolve_single_conflict(self, conflict: Dict[str, Any]) -> bool:
        """
        解决单个冲突

        Args:
            conflict: 冲突信息

        Returns:
            bool: 是否解决成功
        """
        try:
            conflict_type = conflict['conflict_type']

            if conflict['type'] == 'execution':
                if conflict_type == 'execution_stuck_running':
                    return self._resolve_execution_stuck_running(conflict)
                elif conflict_type == 'execution_timeout':
                    return self._resolve_execution_timeout(conflict)

            elif conflict['type'] == 'step':
                if conflict_type == 'step_timeout':
                    return self._resolve_step_timeout(conflict)
                elif conflict_type == 'step_running_on_offline_agent':
                    return self._resolve_step_on_offline_agent(conflict)

            logger.warning(f"未知的冲突类型: {conflict_type}")
            return False

        except Exception as e:
            logger.error(f"解决冲突失败: {conflict}, 错误: {e}")
            return False

    def _resolve_execution_stuck_running(self, conflict: Dict[str, Any]) -> bool:
        """解决执行卡在运行状态的问题"""
        try:
            execution = ExecutionRecord.objects.get(execution_id=conflict['execution_id'])

            # 检查是否所有步骤都已完成
            total_steps = execution.steps.count()
            failed_steps = execution.steps.filter(status='failed').count()
            success_steps = execution.steps.filter(status='success').count()

            with transaction.atomic():
                if failed_steps > 0:
                    # 有失败步骤，标记执行为失败
                    execution.status = 'failed'
                    execution.error_message = '部分步骤执行失败'
                elif success_steps == total_steps:
                    # 所有步骤成功，标记执行为成功
                    execution.status = 'success'
                else:
                    # 还有未完成的步骤，继续运行
                    return False

                execution.finished_at = timezone.now()
                execution.save()

            logger.info(f"解决执行状态冲突: {conflict['execution_id']} -> {execution.status}")
            return True

        except Exception as e:
            logger.error(f"解决执行状态冲突失败: {conflict}, 错误: {e}")
            return False

    def _resolve_execution_timeout(self, conflict: Dict[str, Any]) -> bool:
        """解决执行超时问题"""
        try:
            execution = ExecutionRecord.objects.get(execution_id=conflict['execution_id'])

            with transaction.atomic():
                execution.status = 'failed'
                execution.error_message = f'执行超时 ({conflict["timeout_hours"]}小时)'
                execution.finished_at = timezone.now()
                execution.save()

            logger.info(f"解决执行超时: {conflict['execution_id']}")
            return True

        except Exception as e:
            logger.error(f"解决执行超时失败: {conflict}, 错误: {e}")
            return False

    def _resolve_step_timeout(self, conflict: Dict[str, Any]) -> bool:
        """解决步骤超时问题"""
        try:
            step = ExecutionStep.objects.get(id=conflict['step_id'])

            with transaction.atomic():
                step.status = 'failed'
                step.error_message = f'步骤超时 ({conflict["timeout_seconds"]}秒)'
                step.finished_at = timezone.now()
                step.save()

            logger.info(f"解决步骤超时: step {conflict['step_id']}")
            return True

        except Exception as e:
            logger.error(f"解决步骤超时失败: {conflict}, 错误: {e}")
            return False

    def _resolve_step_on_offline_agent(self, conflict: Dict[str, Any]) -> bool:
        """解决Agent离线但步骤仍在运行的问题"""
        try:
            step = ExecutionStep.objects.get(id=conflict['step_id'])

            with transaction.atomic():
                step.status = 'failed'
                step.error_message = 'Agent离线导致步骤失败'
                step.finished_at = timezone.now()
                step.save()

            logger.info(f"解决Agent离线步骤冲突: step {conflict['step_id']}, agent离线时间: {conflict['last_heartbeat']}")
            return True

        except Exception as e:
            logger.error(f"解决Agent离线步骤冲突失败: {conflict}, 错误: {e}")
            return False


# 全局实例
status_reconciliation_service = StatusReconciliationService()
