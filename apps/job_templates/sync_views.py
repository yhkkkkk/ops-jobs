"""
作业模板同步相关视图
"""
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from drf_spectacular.utils import extend_schema
from utils.responses import SycResponse
from .models import JobTemplate, ExecutionPlan
from .sync_service import TemplateChangeDetector, TemplateSyncService
import logging


logger = logging.getLogger(__name__)


class TemplateSyncMixin:
    """模板同步功能混入类"""

    @extend_schema(
        summary="检查模板同步状态",
        description="检查模板下所有执行方案的同步状态",
        tags=["作业模板"]
    )
    @action(detail=True, methods=['get'], permission_classes=[IsAuthenticated])
    def sync_status(self, request, pk=None):
        """检查模板同步状态"""
        try:
            template = self.get_object()
            sync_status = template.get_sync_status()

            return SycResponse.success(
                content=sync_status,
                message="获取同步状态成功"
            )

        except Exception as e:
            logger.error(f'获取模板同步状态失败: {str(e)}')
            return SycResponse.error(message=f"获取同步状态失败: {str(e)}")

    @extend_schema(
        summary="获取同步预览",
        description="获取模板与执行方案的差异对比信息",
        tags=["作业模板"]
    )
    @action(detail=True, methods=['get'], permission_classes=[IsAuthenticated])
    def sync_preview(self, request, pk=None):
        """获取同步预览"""
        try:
            template = self.get_object()

            # 获取所有关联的执行方案
            plans = template.plans.all()
            if not plans.exists():
                return SycResponse.success(
                    content={'plans': [], 'total': 0},
                    message="没有关联的执行方案"
                )

            preview_data = []
            for plan in plans:
                changes = plan.get_sync_changes()
                preview_data.append({
                    'plan_id': plan.id,
                    'plan_name': plan.name,
                    'plan_description': plan.description,
                    'is_synced': plan.is_synced,
                    'needs_sync': plan.needs_sync,
                    'last_sync_at': plan.last_sync_at.isoformat() if plan.last_sync_at else None,
                    'changes': changes
                })

            return SycResponse.success(
                content={
                    'template_name': template.name,
                    'template_updated_at': template.updated_at.isoformat(),
                    'plans': preview_data,
                    'total': len(preview_data)
                },
                message="获取同步预览成功"
            )

        except Exception as e:
            logger.error(f'获取同步预览失败: {str(e)}')
            return SycResponse.error(message=f"获取同步预览失败: {str(e)}")

    @extend_schema(
        summary="同步执行方案",
        description="将模板的最新配置同步到所有关联的执行方案",
        tags=["作业模板"]
    )
    @action(detail=True, methods=['post'], permission_classes=[IsAuthenticated])
    def sync_plans(self, request, pk=None):
        """同步执行方案"""
        try:
            template = self.get_object()
            force = request.data.get('force', False)

            # 检查权限
            if not request.user.has_perm('job_templates.change_executionplan'):
                return SycResponse.forbidden(message="没有权限同步执行方案")

            # 获取所有关联的执行方案
            plans = template.plans.all()
            if not plans.exists():
                return SycResponse.success(
                    content={'total': 0, 'success_count': 0, 'failed_count': 0, 'results': []},
                    message="没有关联的执行方案需要同步"
                )

            # 批量同步
            results = []
            success_count = 0
            failed_count = 0

            for plan in plans:
                result = plan.sync_from_template(force=force)
                results.append({
                    'plan_id': plan.id,
                    'plan_name': plan.name,
                    'success': result['success'],
                    'message': result['message']
                })

                if result['success']:
                    success_count += 1
                else:
                    failed_count += 1

            logger.info(f'用户 {request.user.username} 同步模板 {template.name} 的执行方案，成功: {success_count}，失败: {failed_count}')

            return SycResponse.success(
                content={
                    'total': plans.count(),
                    'success_count': success_count,
                    'failed_count': failed_count,
                    'results': results
                },
                message=f"同步完成，成功: {success_count}，失败: {failed_count}"
            )

        except Exception as e:
            logger.error(f'同步模板执行方案失败: {str(e)}')
            return SycResponse.error(message=f"同步失败: {str(e)}")


class ExecutionPlanSyncMixin:
    """执行方案同步功能混入类"""
    
    @extend_schema(
        summary="检查执行方案变更",
        description="检查执行方案与模板之间的变更详情",
        tags=["执行方案"]
    )
    @action(detail=True, methods=['get'], permission_classes=[IsAuthenticated])
    def check_changes(self, request, pk=None):
        """检查执行方案变更"""
        try:
            plan = self.get_object()
            changes = plan.get_sync_changes()

            return SycResponse.success(
                content=changes,
                message="检查变更成功"
            )

        except Exception as e:
            logger.error(f'检查执行方案变更失败: {str(e)}')
            return SycResponse.error(message=f"检查变更失败: {str(e)}")
    
    @extend_schema(
        summary="同步执行方案",
        description="将执行方案同步到模板的最新状态",
        tags=["执行方案"]
    )
    @action(detail=True, methods=['post'], permission_classes=[IsAuthenticated])
    def sync_from_template(self, request, pk=None):
        """同步执行方案"""
        try:
            plan = self.get_object()
            force = request.data.get('force', False)

            # 检查权限
            if not request.user.has_perm('job_templates.change_executionplan'):
                return SycResponse.forbidden(message="没有权限同步执行方案")

            # 执行同步
            result = plan.sync_from_template(force=force)

            if result['success']:
                logger.info(f'用户 {request.user.username} 同步执行方案 {plan.name} 成功')
                return SycResponse.success(
                    content=result,
                    message=result['message']
                )
            else:
                return SycResponse.error(
                    content=result,
                    message=result['message']
                )

        except Exception as e:
            logger.error(f'同步执行方案失败: {str(e)}')
            return SycResponse.error(message=f"同步失败: {str(e)}")
    
    @extend_schema(
        summary="批量同步执行方案",
        description="批量同步多个执行方案到模板的最新状态",
        tags=["执行方案"]
    )
    @action(detail=False, methods=['post'], permission_classes=[IsAuthenticated])
    def batch_sync(self, request):
        """批量同步执行方案"""
        try:
            plan_ids = request.data.get('plan_ids', [])
            force = request.data.get('force', False)
            
            if not plan_ids:
                return SycResponse.validation_error(message="请选择要同步的执行方案")
            
            # 检查权限
            if not request.user.has_perm('job_templates.change_executionplan'):
                return SycResponse.forbidden(message="没有权限同步执行方案")
            
            # 获取执行方案
            plans = ExecutionPlan.objects.filter(id__in=plan_ids)
            if plans.count() != len(plan_ids):
                return SycResponse.validation_error(message="部分执行方案不存在")
            
            # 批量同步
            results = []
            success_count = 0
            failed_count = 0
            
            for plan in plans:
                result = plan.sync_from_template(force=force)
                results.append({
                    'plan_id': plan.id,
                    'plan_name': plan.name,
                    'success': result['success'],
                    'message': result['message']
                })
                
                if result['success']:
                    success_count += 1
                else:
                    failed_count += 1
            
            logger.info(f'用户 {request.user.username} 批量同步执行方案，成功: {success_count}，失败: {failed_count}')
            
            return SycResponse.success(
                content={
                    'total': len(plan_ids),
                    'success_count': success_count,
                    'failed_count': failed_count,
                    'results': results
                },
                message=f"批量同步完成，成功: {success_count}，失败: {failed_count}"
            )
            
        except Exception as e:
            logger.error(f'批量同步执行方案失败: {str(e)}')
            return SycResponse.error(message=f"批量同步失败: {str(e)}")


class TemplateChangeAnalyzer:
    """模板变更分析器"""
    
    @staticmethod
    def analyze_template_changes(template_id: int, plan_ids: list = None):
        """分析模板变更对执行方案的影响"""
        try:
            template = JobTemplate.objects.get(id=template_id)
            
            # 如果指定了执行方案id，只分析这些方案
            if plan_ids:
                plans = template.plans.filter(id__in=plan_ids)
            else:
                plans = template.plans.all()
            
            analysis_result = {
                'template_id': template_id,
                'template_name': template.name,
                'total_plans': plans.count(),
                'plan_analysis': []
            }
            
            for plan in plans:
                changes = TemplateChangeDetector.detect_changes(plan)
                analysis_result['plan_analysis'].append({
                    'plan_id': plan.id,
                    'plan_name': plan.name,
                    'has_changes': changes['has_changes'],
                    'changes_summary': changes['summary'],
                    'new_steps_count': len(changes.get('new_steps', [])),
                    'deleted_steps_count': len(changes.get('deleted_steps', [])),
                    'modified_steps_count': len(changes.get('modified_steps', [])),
                    'last_sync_at': plan.last_sync_at.isoformat() if plan.last_sync_at else None
                })
            
            return analysis_result
            
        except Exception as e:
            logger.error(f'分析模板变更失败: {str(e)}')
            raise
