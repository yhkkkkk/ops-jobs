"""
状态同步定时任务 - 检测和修复任务状态不一致
可通过 crontab 或 APScheduler 定时执行
"""
import logging

from django.core.management.base import BaseCommand
from django.conf import settings

from apps.agents.status_reconciliation_service import status_reconciliation_service
from apps.agents.models import Agent

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "检测并修复任务状态不一致问题（可选兜底机制）"

    def add_arguments(self, parser):
        parser.add_argument(
            "--agent-id",
            type=int,
            default=None,
            help="指定要同步的 Agent ID，不指定则同步所有在线 Agent",
        )
        parser.add_argument(
            "--hours-back",
            type=int,
            default=24,
            help="检测多少小时内的状态异常，默认 24 小时",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            default=False,
            help="仅检测不修复，用于查看当前状态异常情况",
        )
        parser.add_argument(
            "--detect-only",
            action="store_true",
            default=False,
            help="仅检测全局异常，不执行单个 Agent 的状态同步",
        )

    def handle(self, *args, **options):
        agent_id = options["agent_id"]
        hours_back = options["hours_back"]
        dry_run = options["dry_run"]
        detect_only = options["detect_only"]

        # 检查是否启用状态同步（可通过配置关闭）
        enabled = getattr(settings, "STATUS_RECONCILIATION_ENABLED", True)
        if not enabled:
            self.stdout.write(
                self.style.WARNING("状态同步已禁用 (STATUS_RECONCILIATION_ENABLED=False)")
            )
            return

        self.stdout.write(
            self.style.SUCCESS(
                f"开始状态同步检查: hours_back={hours_back}, dry_run={dry_run}"
            )
        )

        # 1. 检测全局状态异常
        self.stdout.write("检测全局状态异常...")
        anomalies = status_reconciliation_service.detect_status_anomalies(
            hours_back=hours_back
        )

        if anomalies:
            self.stdout.write(
                self.style.WARNING(f"检测到 {len(anomalies)} 个状态异常:")
            )
            for anomaly in anomalies:
                severity_color = {
                    "critical": self.style.ERROR,
                    "high": self.style.WARNING,
                    "medium": self.style.NOTICE,
                }.get(anomaly.get("severity", "medium"), self.style.NOTICE)

                self.stdout.write(
                    severity_color(
                        f"  [{anomaly['severity']}] {anomaly['type']}: {anomaly['description']}"
                    )
                )
        else:
            self.stdout.write(self.style.SUCCESS("未检测到全局状态异常"))

        if detect_only:
            self.stdout.write("仅检测模式，跳过单个 Agent 状态同步")
            return

        # 2. 执行单个 Agent 状态同步
        if agent_id:
            agents = Agent.objects.filter(id=agent_id)
            if not agents.exists():
                self.stdout.write(self.style.ERROR(f"Agent 不存在: {agent_id}"))
                return
        else:
            # 同步所有非禁用的 Agent
            agents = Agent.objects.exclude(status="disabled")

        self.stdout.write(f"开始同步 {agents.count()} 个 Agent 的状态...")

        total_conflicts_found = 0
        total_conflicts_resolved = 0

        for agent in agents:
            if dry_run:
                # 仅检测，不修复
                result = self._detect_agent_conflicts(agent)
            else:
                result = status_reconciliation_service.reconcile_agent_status(agent.id)

            if result.get("success"):
                conflicts_found = result.get("conflicts_found", 0)
                conflicts_resolved = result.get("conflicts_resolved", 0)
                total_conflicts_found += conflicts_found
                total_conflicts_resolved += conflicts_resolved

                if conflicts_found > 0:
                    self.stdout.write(
                        f"  Agent {agent.id} ({agent.host.name}): "
                        f"发现 {conflicts_found} 个冲突, "
                        f"{'检测模式' if dry_run else f'已解决 {conflicts_resolved} 个'}"
                    )
            else:
                self.stdout.write(
                    self.style.ERROR(
                        f"  Agent {agent.id}: 同步失败 - {result.get('error', '未知错误')}"
                    )
                )

        # 3. 输出汇总
        self.stdout.write("")
        self.stdout.write(
            self.style.SUCCESS(
                f"状态同步完成: 共检测 {agents.count()} 个 Agent, "
                f"发现 {total_conflicts_found} 个冲突"
                + (f", 已解决 {total_conflicts_resolved} 个" if not dry_run else "")
            )
        )

    def _detect_agent_conflicts(self, agent):
        """仅检测 Agent 冲突，不修复"""
        try:
            from apps.agents.status_reconciliation_service import StatusReconciliationService

            service = StatusReconciliationService()
            execution_conflicts = service._check_execution_status_conflicts(agent)
            step_conflicts = service._check_step_status_conflicts(agent)

            return {
                "success": True,
                "agent_id": agent.id,
                "conflicts_found": len(execution_conflicts) + len(step_conflicts),
                "conflicts_resolved": 0,
                "details": {
                    "execution_conflicts": len(execution_conflicts),
                    "step_conflicts": len(step_conflicts),
                },
            }
        except Exception as e:
            return {"success": False, "error": str(e)}
