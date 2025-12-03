"""
作业模板同步服务
基于内容变更检测的同步机制，而非简单的版本号控制
"""
import hashlib
import json
from typing import Dict, List, Any
from django.utils import timezone
from django.db import transaction
from .models import JobTemplate, JobStep, ExecutionPlan, PlanStep
import logging

logger = logging.getLogger(__name__)


class TemplateChangeDetector:
    """模板变更检测器"""
    
    @staticmethod
    def calculate_step_hash(step: JobStep) -> str:
        """计算步骤的内容哈希值（根据步骤类型）"""
        # 通用字段
        step_data = {
            'name': step.name,
            'description': step.description,
            'step_type': step.step_type,
            'order': step.order,
            'step_parameters': step.step_parameters,
            'timeout': step.timeout,
            'ignore_error': step.ignore_error,
            'target_host_ids': sorted(list(step.target_hosts.values_list('id', flat=True))),
            'target_group_ids': sorted(list(step.target_groups.values_list('id', flat=True))),
        }

        # 根据步骤类型添加特定字段
        if step.step_type == 'script':
            step_data['script_content'] = step.script_content
            step_data['script_type'] = step.script_type
            step_data['account_id'] = step.account_id
        elif step.step_type == 'file_transfer':
            step_data['transfer_type'] = step.transfer_type
            step_data['local_path'] = step.local_path
            step_data['remote_path'] = step.remote_path

        # 将数据序列化为json字符串，然后计算md5哈希
        step_json = json.dumps(step_data, sort_keys=True, ensure_ascii=False)
        return hashlib.md5(step_json.encode('utf-8')).hexdigest()
    
    @staticmethod
    def calculate_template_hash(template: JobTemplate) -> str:
        """计算模板的内容哈希值"""
        template_data = {
            'name': template.name,
            'description': template.description,
            'category': template.category,
            'tags': template.tag_list,
            'steps': []
        }
        
        # 按顺序添加所有步骤的哈希值
        for step in template.steps.all().order_by('order'):
            template_data['steps'].append({
                'id': step.id,
                'hash': TemplateChangeDetector.calculate_step_hash(step)
            })
        
        template_json = json.dumps(template_data, sort_keys=True, ensure_ascii=False)
        return hashlib.md5(template_json.encode('utf-8')).hexdigest()
    
    @staticmethod
    def detect_changes(plan: ExecutionPlan) -> Dict[str, Any]:
        """检测执行方案与模板之间的变更"""
        changes = {
            'has_changes': False,
            'modified_steps': [],
            'summary': ''
        }

        try:
            template = plan.template

            # 获取模板当前的步骤
            current_template_steps = {
                step.id: step for step in template.steps.all()
            }

            # 获取执行方案中的步骤快照
            plan_steps = {}
            for plan_step in plan.planstep_set.all():
                step_id = plan_step.step.id if plan_step.step else None
                plan_steps[step_id] = {
                    'plan_step': plan_step,
                    'original_hash': getattr(plan_step, 'step_hash', None),
                    # 快照数据
                    'snapshot': {
                        'name': plan_step.step_name,
                        'description': plan_step.step_description,
                        'step_type': plan_step.step_type,
                        'script_content': plan_step.step_script_content,
                        'script_type': plan_step.step_script_type,
                        'step_parameters': plan_step.step_parameters,
                        'timeout': plan_step.step_timeout,
                        'ignore_error': plan_step.step_ignore_error,
                        'target_host_ids': plan_step.step_target_host_ids,
                        'target_group_ids': plan_step.step_target_group_ids,
                    }
                }

            # 1. 检测全局变量变更
            if template.global_parameters != plan.global_parameters_snapshot:
                changes['global_parameters_changed'] = True
                changes['old_global_parameters'] = plan.global_parameters_snapshot
                changes['new_global_parameters'] = template.global_parameters

            # 2. 检测步骤增删
            template_step_ids = set(current_template_steps.keys())
            plan_step_ids = set(plan_steps.keys())

            added_step_ids = template_step_ids - plan_step_ids
            deleted_step_ids = plan_step_ids - template_step_ids

            changes['added_steps'] = [
                {'step_id': step_id, 'name': current_template_steps[step_id].name, 'order': current_template_steps[step_id].order}
                for step_id in added_step_ids
            ]
            changes['deleted_steps'] = [
                {'step_id': step_id, 'name': plan_steps[step_id]['snapshot']['name'], 'order': plan_steps[step_id]['plan_step'].order}
                for step_id in deleted_step_ids
            ]

            # 3. 检测步骤内容变更 (仅对共同存在的步骤)
            common_step_ids = template_step_ids & plan_step_ids
            for step_id in common_step_ids:
                step = current_template_steps[step_id]
                current_hash = TemplateChangeDetector.calculate_step_hash(step)
                original_hash = plan_steps[step_id]['original_hash']

                if current_hash != original_hash:
                    snapshot = plan_steps[step_id]['snapshot']
                    step_changes = TemplateChangeDetector._analyze_step_changes_from_snapshot(snapshot, step)
                    simple_changes = TemplateChangeDetector._get_simple_change_descriptions(step_changes)
                    changes['modified_steps'].append({
                        'step_id': step_id,
                        'name': step.name,
                        'order': step.order,
                        'changes': simple_changes,
                        'detailed_changes': step_changes
                    })

            # 4. 判断最终是否有变更
            changes['has_changes'] = bool(
                changes.get('global_parameters_changed') or
                changes['added_steps'] or
                changes['deleted_steps'] or
                changes['modified_steps']
            )

            # 5. 生成变更摘要
            changes['summary'] = TemplateChangeDetector._generate_change_summary(changes)
            if not changes['has_changes']:
                changes['summary'] = '执行方案与模板内容一致，无需同步'
            
            return changes
            
        except Exception as e:
            logger.error(f'检测模板变更失败: {str(e)}')
            return {
                'has_changes': False,
                'error': str(e),
                'summary': f'变更检测失败: {str(e)}'
            }
    
    @staticmethod
    def _analyze_step_changes(old_step: JobStep, new_step: JobStep) -> List[str]:
        """分析步骤的具体变更内容"""
        changes = []
        
        if old_step.name != new_step.name:
            changes.append(f'步骤名称: "{old_step.name}" → "{new_step.name}"')
        
        if old_step.description != new_step.description:
            changes.append('步骤描述已修改')
        
        if old_step.step_type != new_step.step_type:
            changes.append(f'步骤类型: {old_step.step_type} → {new_step.step_type}')
        
        if old_step.order != new_step.order:
            changes.append(f'执行顺序: {old_step.order} → {new_step.order}')
        
        if old_step.step_parameters != new_step.step_parameters:
            changes.append('步骤参数已修改')
        
        if old_step.timeout != new_step.timeout:
            changes.append(f'超时时间: {old_step.timeout}s → {new_step.timeout}s')
        
        if old_step.ignore_error != new_step.ignore_error:
            changes.append(f'忽略错误: {old_step.ignore_error} → {new_step.ignore_error}')
        
        # 检查目标主机变更
        old_hosts = set(old_step.target_hosts.values_list('id', flat=True))
        new_hosts = set(new_step.target_hosts.values_list('id', flat=True))
        if old_hosts != new_hosts:
            changes.append('目标主机已修改')
        
        # 检查目标分组变更
        old_groups = set(old_step.target_groups.values_list('id', flat=True))
        new_groups = set(new_step.target_groups.values_list('id', flat=True))
        if old_groups != new_groups:
            changes.append('目标分组已修改')
        
        return changes

    @staticmethod
    def _analyze_step_changes_from_snapshot(snapshot: Dict[str, Any], new_step: JobStep) -> List[Dict[str, Any]]:
        """基于快照数据分析步骤的具体变更内容"""
        changes = []

        if snapshot['name'] != new_step.name:
            changes.append({
                'field': 'name',
                'field_name': '步骤名称',
                'old_value': snapshot['name'],
                'new_value': new_step.name,
                'change_type': 'text'
            })

        if snapshot['description'] != new_step.description:
            changes.append({
                'field': 'description',
                'field_name': '步骤描述',
                'old_value': snapshot['description'],
                'new_value': new_step.description,
                'change_type': 'text'
            })

        if snapshot['step_type'] != new_step.step_type:
            changes.append({
                'field': 'step_type',
                'field_name': '步骤类型',
                'old_value': snapshot['step_type'],
                'new_value': new_step.step_type,
                'change_type': 'text'
            })

        if snapshot['script_content'] != new_step.script_content:
            changes.append({
                'field': 'script_content',
                'field_name': '脚本内容',
                'old_value': snapshot['script_content'],
                'new_value': new_step.script_content,
                'change_type': 'code'
            })

        if snapshot['script_type'] != new_step.script_type:
            changes.append({
                'field': 'script_type',
                'field_name': '脚本类型',
                'old_value': snapshot['script_type'],
                'new_value': new_step.script_type,
                'change_type': 'text'
            })

        if snapshot['step_parameters'] != new_step.step_parameters:
            changes.append({
                'field': 'step_parameters',
                'field_name': '步骤参数',
                'old_value': snapshot['step_parameters'],
                'new_value': new_step.step_parameters,
                'change_type': 'json'
            })

        if snapshot['timeout'] != new_step.timeout:
            changes.append({
                'field': 'timeout',
                'field_name': '超时时间',
                'old_value': f"{snapshot['timeout']}秒",
                'new_value': f"{new_step.timeout}秒",
                'change_type': 'text'
            })

        if snapshot['ignore_error'] != new_step.ignore_error:
            changes.append({
                'field': 'ignore_error',
                'field_name': '忽略错误',
                'old_value': '是' if snapshot['ignore_error'] else '否',
                'new_value': '是' if new_step.ignore_error else '否',
                'change_type': 'text'
            })

        # 检查目标主机变化
        current_host_ids = sorted(list(new_step.target_hosts.values_list('id', flat=True)))
        if snapshot['target_host_ids'] != current_host_ids:
            # 获取主机名称用于显示
            from apps.hosts.models import Host
            old_hosts = Host.objects.filter(id__in=snapshot['target_host_ids']).values_list('name', flat=True)
            new_hosts = Host.objects.filter(id__in=current_host_ids).values_list('name', flat=True)

            changes.append({
                'field': 'target_hosts',
                'field_name': '目标主机',
                'old_value': list(old_hosts),
                'new_value': list(new_hosts),
                'change_type': 'list'
            })

        # 检查目标分组变化
        current_group_ids = sorted(list(new_step.target_groups.values_list('id', flat=True)))
        if snapshot['target_group_ids'] != current_group_ids:
            # 获取分组名称用于显示
            from apps.hosts.models import HostGroup
            old_groups = HostGroup.objects.filter(id__in=snapshot['target_group_ids']).values_list('name', flat=True)
            new_groups = HostGroup.objects.filter(id__in=current_group_ids).values_list('name', flat=True)

            changes.append({
                'field': 'target_groups',
                'field_name': '目标分组',
                'old_value': list(old_groups),
                'new_value': list(new_groups),
                'change_type': 'list'
            })

        # 根据步骤类型检查特定字段的变更
        if new_step.step_type == 'script':
            if snapshot.get('account_id') != new_step.account_id:
                changes.append({
                    'field': 'account_id',
                    'field_name': '执行账号ID',
                    'old_value': snapshot.get('account_id'),
                    'new_value': new_step.account_id,
                    'change_type': 'text'
                })
        elif new_step.step_type == 'file_transfer':
            if snapshot.get('transfer_type') != new_step.transfer_type:
                changes.append({
                    'field': 'transfer_type',
                    'field_name': '传输类型',
                    'old_value': snapshot.get('transfer_type'),
                    'new_value': new_step.transfer_type,
                    'change_type': 'text'
                })
            if snapshot.get('local_path') != new_step.local_path:
                changes.append({
                    'field': 'local_path',
                    'field_name': '本地路径',
                    'old_value': snapshot.get('local_path'),
                    'new_value': new_step.local_path,
                    'change_type': 'text'
                })
            if snapshot.get('remote_path') != new_step.remote_path:
                changes.append({
                    'field': 'remote_path',
                    'field_name': '远程路径',
                    'old_value': snapshot.get('remote_path'),
                    'new_value': new_step.remote_path,
                    'change_type': 'text'
                })

        return changes

    @staticmethod
    def _generate_change_summary(changes: Dict[str, Any]) -> str:
        """生成更全面的变更摘要"""
        summary_parts = []
        if changes.get('global_parameters_changed'):
            summary_parts.append('全局变量已更新')
        if changes.get('added_steps'):
            summary_parts.append(f"{len(changes['added_steps'])}个步骤已新增")
        if changes.get('deleted_steps'):
            summary_parts.append(f"{len(changes['deleted_steps'])}个步骤已删除")
        if changes.get('modified_steps'):
            summary_parts.append(f"{len(changes['modified_steps'])}个步骤已修改")

        if not summary_parts:
            return "执行方案与模板内容一致，无需同步"

        return f"模板已更新：{', '.join(summary_parts)}"

    @staticmethod
    def _get_simple_change_descriptions(detailed_changes: List[Dict[str, Any]]) -> List[str]:
        """将详细变更转换为简单描述（向后兼容）"""
        simple_descriptions = []
        for change in detailed_changes:
            field_name = change['field_name']
            if change['change_type'] == 'code':
                simple_descriptions.append(f'{field_name}已修改')
            elif change['change_type'] == 'json':
                simple_descriptions.append(f'{field_name}已修改')
            elif change['change_type'] == 'list':
                simple_descriptions.append(f'{field_name}已修改')
            else:
                old_val = change['old_value']
                new_val = change['new_value']
                simple_descriptions.append(f'{field_name}: {old_val} → {new_val}')
        return simple_descriptions


class TemplateSyncService:
    """模板同步服务"""
    
    @staticmethod
    def sync_plan_from_template(plan: ExecutionPlan, force: bool = False) -> Dict[str, Any]:
        """将执行方案同步到模板的最新状态"""
        try:
            # 检测变更
            if not force:
                changes = TemplateChangeDetector.detect_changes(plan)
                if not changes['has_changes']:
                    return {
                        'success': True,
                        'message': '执行方案已是最新状态，无需同步',
                        'changes': changes
                    }
            
            with transaction.atomic():
                # 检测变更
                changes = TemplateChangeDetector.detect_changes(plan)

                updated_steps = 0

                # 1. 同步全局变量
                if changes.get('global_parameters_changed'):
                    plan.global_parameters_snapshot = plan.template.global_parameters

                # 2. 删除步骤
                deleted_step_ids = [step['step_id'] for step in changes.get('deleted_steps', [])]
                if deleted_step_ids:
                    plan.planstep_set.filter(step_id__in=deleted_step_ids).delete()

                # 3. 新增步骤
                added_step_ids = [step['step_id'] for step in changes.get('added_steps', [])]
                for step_id in added_step_ids:
                    template_step = plan.template.steps.get(id=step_id)
                    plan_step = PlanStep.objects.create(
                        plan=plan,
                        step=template_step,
                        order=template_step.order,
                        step_hash=TemplateChangeDetector.calculate_step_hash(template_step)
                    )
                    plan_step.copy_from_template_step()
                    plan_step.save()

                # 4. 更新修改的步骤
                modified_step_ids = [step['step_id'] for step in changes.get('modified_steps', [])]
                for step_id in modified_step_ids:
                    template_step = plan.template.steps.get(id=step_id)
                    plan_step = plan.planstep_set.get(step_id=step_id)
                    plan_step.copy_from_template_step()
                    plan_step.step_hash = TemplateChangeDetector.calculate_step_hash(template_step)
                    plan_step.save()

                # 5. 更新同步状态
                plan.is_synced = True
                plan.last_sync_at = timezone.now()
                plan.save()

                # 记录同步日志
                logger.info(f'执行方案 {plan.name} 同步完成，更新了 {updated_steps} 个步骤的内容')

                if updated_steps > 0:
                    message = f'同步完成，更新了 {updated_steps} 个步骤的内容'
                else:
                    message = '同步完成，所有步骤内容已是最新'

                return {
                    'success': True,
                    'message': message,
                    'updated_steps': updated_steps,
                    'synced_at': plan.last_sync_at.isoformat()
                }
                
        except Exception as e:
            logger.error(f'同步执行方案失败: {str(e)}')
            return {
                'success': False,
                'message': f'同步失败: {str(e)}'
            }
    
    @staticmethod
    def check_all_plans_sync_status(template: JobTemplate) -> Dict[str, Any]:
        """检查模板下所有执行方案的同步状态"""
        plans = template.plans.all()
        sync_status = {
            'total_plans': plans.count(),
            'synced_plans': 0,
            'unsynced_plans': 0,
            'plan_details': []
        }
        
        for plan in plans:
            changes = TemplateChangeDetector.detect_changes(plan)
            is_synced = not changes['has_changes']
            
            if is_synced:
                sync_status['synced_plans'] += 1
            else:
                sync_status['unsynced_plans'] += 1
            
            sync_status['plan_details'].append({
                'plan_id': plan.id,
                'plan_name': plan.name,
                'is_synced': is_synced,
                'last_sync_at': plan.last_sync_at.isoformat() if plan.last_sync_at else None,
                'changes_summary': changes['summary']
            })
        
        return sync_status
