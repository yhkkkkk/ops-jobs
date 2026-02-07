"""
批量操作相关的 Mixin 和工具函数
用于统一处理批量操作的二次确认、限流等逻辑
"""
import logging
from typing import List, Tuple, Optional
from django.db.models import QuerySet
from apps.hosts.models import Host
from apps.agents.models import Agent

logger = logging.getLogger(__name__)


class BatchOperationMixin:
    """批量操作 Mixin，提供统一的二次确认和限流逻辑"""

    # 默认批量操作限制
    DEFAULT_MAX_BATCH_SIZE = 50
    DEFAULT_PROD_MAX_BATCH_SIZE = 10

    def validate_batch_operation(
        self,
        request,
        item_ids: List[int],
        confirmed: bool,
        max_batch_size: Optional[int] = None,
        prod_max_batch_size: Optional[int] = None,
        check_prod_env: bool = True,
        item_type: str = "item",  # "host", "agent", "item"
    ) -> Tuple[bool, Optional[str], Optional[QuerySet]]:
        """
        验证批量操作
        
        Args:
            request: Django request 对象
            item_ids: 要操作的项目ID列表
            confirmed: 是否已确认
            max_batch_size: 最大批量大小（默认 50）
            prod_max_batch_size: 生产环境最大批量大小（默认 10）
            check_prod_env: 是否检查生产环境
            item_type: 项目类型（"host", "agent", "item"）
        
        Returns:
            Tuple[bool, Optional[str], Optional[QuerySet]]:
                (is_valid, error_message, queryset)
                is_valid: 是否通过验证
                error_message: 错误消息（如果验证失败）
                queryset: 过滤后的查询集（如果验证通过）
        """
        # 1. 检查二次确认
        if not confirmed:
            return False, f"请勾选确认框以执行批量操作", None

        # 2. 检查批量大小
        max_size = max_batch_size or self.DEFAULT_MAX_BATCH_SIZE
        prod_max_size = prod_max_batch_size or self.DEFAULT_PROD_MAX_BATCH_SIZE

        if len(item_ids) > max_size:
            return False, f"批量操作数量超过限制，最多允许操作 {max_size} 个{item_type}", None

        # 3. 根据项目类型获取查询集
        if item_type == "host":
            queryset = Host.objects.filter(id__in=item_ids)
        elif item_type == "agent":
            queryset = Agent.objects.filter(id__in=item_ids).select_related('host')
        else:
            # 默认使用 self.get_queryset()（如果 ViewSet 有的话）
            if hasattr(self, 'get_queryset'):
                queryset = self.get_queryset().filter(id__in=item_ids)
            else:
                return False, f"无法获取查询集（item_type={item_type}）", None

        # 4. 检查生产环境限制
        if check_prod_env:
            if item_type == "host":
                prod_items = queryset.filter(tags__icontains='prod')
            elif item_type == "agent":
                prod_items = queryset.filter(host__tags__icontains='prod')
            else:
                prod_items = queryset.none()

            if prod_items.exists():
                current_max_size = prod_max_size
                if len(item_ids) > current_max_size:
                    return (
                        False,
                        f"批量操作数量超过限制，包含生产环境时最多允许操作 {current_max_size} 个{item_type}",
                        None,
                    )

        return True, None, queryset

    def validate_batch_operation_with_hosts(
        self,
        request,
        host_ids: List[int],
        confirmed: bool,
        max_batch_size: Optional[int] = None,
        prod_max_batch_size: Optional[int] = None,
    ) -> Tuple[bool, Optional[str], Optional[QuerySet]]:
        """
        验证基于主机的批量操作（便捷方法）
        
        Args:
            request: Django request 对象
            host_ids: 主机ID列表
            confirmed: 是否已确认
            max_batch_size: 最大批量大小
            prod_max_batch_size: 生产环境最大批量大小
        
        Returns:
            Tuple[bool, Optional[str], Optional[QuerySet]]:
                (is_valid, error_message, queryset)
        """
        return self.validate_batch_operation(
            request=request,
            item_ids=host_ids,
            confirmed=confirmed,
            max_batch_size=max_batch_size,
            prod_max_batch_size=prod_max_batch_size,
            check_prod_env=True,
            item_type="host",
        )

    def validate_batch_operation_with_agents(
        self,
        request,
        agent_ids: List[int],
        confirmed: bool,
        max_batch_size: Optional[int] = None,
        prod_max_batch_size: Optional[int] = None,
    ) -> Tuple[bool, Optional[str], Optional[QuerySet]]:
        """
        验证基于 Agent 的批量操作（便捷方法）
        
        Args:
            request: Django request 对象
            agent_ids: Agent ID列表
            confirmed: 是否已确认
            max_batch_size: 最大批量大小
            prod_max_batch_size: 生产环境最大批量大小
        
        Returns:
            Tuple[bool, Optional[str], Optional[QuerySet]]:
                (is_valid, error_message, queryset)
        """
        return self.validate_batch_operation(
            request=request,
            item_ids=agent_ids,
            confirmed=confirmed,
            max_batch_size=max_batch_size,
            prod_max_batch_size=prod_max_batch_size,
            check_prod_env=True,
            item_type="agent",
        )

