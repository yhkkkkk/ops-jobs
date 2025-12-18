import logging
from datetime import timedelta
from typing import Dict, Any

from django.core.management.base import BaseCommand
from django.utils import timezone

from apps.agents.models import Agent
from apps.system_config.models import ConfigManager

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = (
        "Scan Agent.last_heartbeat_at and mark long-time inactive agents as offline.\n"
        "支持通过 SystemConfig 配置阈值：\n"
        "  - agent.offline_threshold_seconds: 全局离线判定阈值（秒，默认 600）\n"
        "  - agent.offline_threshold_by_env: 按环境的阈值映射，例如 {\"prod\": 300, \"test\": 900}\n"
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="仅打印将要更新的 Agent 数量，不实际写入数据库",
        )
        parser.add_argument(
            "--threshold",
            type=int,
            default=None,
            help="覆盖全局阈值（秒），优先级高于 SystemConfig.agent.offline_threshold_seconds",
        )

    def handle(self, *args, **options):
        dry_run: bool = options["dry_run"]
        override_threshold: int | None = options["threshold"]

        # 1. 读取全局阈值和按环境阈值
        global_threshold = self._get_global_threshold(override_threshold)
        env_thresholds = self._get_env_thresholds()

        if global_threshold <= 0:
            self.stderr.write(
                self.style.ERROR("全局离线阈值必须为正整数，请检查配置或命令行参数")
            )
            return

        now = timezone.now()

        # 2. 只扫描当前标记为 online 的 Agent，pending/offline/disabled 不参与
        queryset = Agent.objects.select_related("host").filter(status="online")
        total_online = queryset.count()

        if total_online == 0:
            self.stdout.write(self.style.WARNING("当前没有状态为 online 的 Agent，可忽略本次扫描"))
            return

        to_update: list[Agent] = []

        for agent in queryset:
            # 根据 Host.environment 选择阈值
            env = agent.environment or "default"
            threshold = int(env_thresholds.get(env, global_threshold))

            # 如果没有心跳时间，视作已超时（防御性处理）
            last_hb = agent.last_heartbeat_at
            if not last_hb:
                to_update.append(agent)
                continue

            deadline = now - timedelta(seconds=threshold)
            if last_hb < deadline:
                to_update.append(agent)

        if not to_update:
            self.stdout.write(
                self.style.SUCCESS(
                    f"扫描完成：共 {total_online} 个 online Agent，未发现需要标记为 offline 的实例"
                )
            )
            return

        if dry_run:
            self.stdout.write(
                self.style.WARNING(
                    f"[dry-run] 共有 {len(to_update)}/{total_online} 个 online Agent 将被标记为 offline"
                )
            )
            ids_preview = [a.id for a in to_update[:20]]
            self.stdout.write(f"[dry-run] 样例 Agent IDs: {ids_preview}")
            return

        # 3. 实际更新数据库
        updated = 0
        for agent in to_update:
            agent.status = "offline"
            agent.updated_at = now
            agent.save(update_fields=["status", "updated_at"])
            updated += 1

        msg = (
            f"离线扫描完成：共 {total_online} 个 online Agent，其中 {updated} 个被标记为 offline "
            f"(global_threshold={global_threshold}s, env_overrides={self._format_env_thresholds(env_thresholds)})"
        )
        logger.info(msg)
        self.stdout.write(self.style.SUCCESS(msg))

    def _get_global_threshold(self, override_threshold: int | None) -> int:
        """
        读取全局离线阈值，优先级：
          1) 命令行 --threshold
          2) SystemConfig.agent.offline_threshold_seconds
          3) 默认 600 秒
        """
        if override_threshold is not None:
            return max(1, int(override_threshold))

        cfg_value = ConfigManager.get("agent.offline_threshold_seconds", 600)
        try:
            # 支持直接存储 int 或类似 {"value": 600} 的结构
            if isinstance(cfg_value, dict) and "value" in cfg_value:
                return max(1, int(cfg_value["value"]))
            return max(1, int(cfg_value))
        except (TypeError, ValueError):
            logger.warning(
                "invalid agent.offline_threshold_seconds config, fallback to 600",
                extra={"value": cfg_value},
            )
            return 600

    def _get_env_thresholds(self) -> Dict[str, int]:
        """
        读取按环境的离线阈值映射，来自 SystemConfig.agent.offline_threshold_by_env。
        例如: {\"prod\": 300, \"staging\": 600}
        """
        raw = ConfigManager.get("agent.offline_threshold_by_env", {}) or {}
        env_thresholds: Dict[str, int] = {}
        if not isinstance(raw, dict):
            return env_thresholds

        for env, seconds in raw.items():
            try:
                env_thresholds[str(env)] = max(1, int(seconds))
            except (TypeError, ValueError):
                logger.warning(
                    "invalid env threshold for agent offline",
                    extra={"env": env, "value": seconds},
                )
        return env_thresholds

    def _format_env_thresholds(self, env_thresholds: Dict[str, int]) -> Dict[str, Any]:
        """格式化环境阈值用于日志输出。"""
        return {env: int(sec) for env, sec in env_thresholds.items()}


