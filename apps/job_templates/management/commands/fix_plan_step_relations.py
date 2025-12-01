from django.core.management.base import BaseCommand
from apps.job_templates.models import ExecutionPlan, PlanStep, JobStep
from apps.job_templates.sync_service import TemplateChangeDetector


class Command(BaseCommand):
    help = '修复执行方案步骤与模板步骤的关联关系'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='只显示需要修复的数据，不实际修改',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        
        if dry_run:
            self.stdout.write('=== 干运行模式，只显示需要修复的数据 ===')
        else:
            self.stdout.write('=== 开始修复执行方案步骤关联关系 ===')

        total_plans = 0
        fixed_plans = 0
        total_steps = 0
        fixed_steps = 0

        for plan in ExecutionPlan.objects.all():
            total_plans += 1
            plan_fixed = False
            
            self.stdout.write(f'\n检查执行方案: {plan.name} (ID: {plan.id})')
            
            # 获取模板步骤
            template_steps = list(plan.template.steps.all().order_by('order'))
            plan_steps = list(plan.planstep_set.all().order_by('order'))
            
            self.stdout.write(f'  模板步骤数量: {len(template_steps)}')
            self.stdout.write(f'  执行方案步骤数量: {len(plan_steps)}')
            
            # 检查关联问题
            broken_steps = [ps for ps in plan_steps if ps.step is None]
            if broken_steps:
                self.stdout.write(f'  发现 {len(broken_steps)} 个断开关联的步骤')
                plan_fixed = True
                
                # 尝试根据顺序和名称匹配步骤
                for i, plan_step in enumerate(plan_steps):
                    total_steps += 1
                    
                    if plan_step.step is None and i < len(template_steps):
                        template_step = template_steps[i]
                        
                        # 检查名称是否匹配
                        if plan_step.step_name == template_step.name:
                            self.stdout.write(f'    匹配步骤 {i+1}: {plan_step.step_name} -> {template_step.name}')
                            
                            if not dry_run:
                                # 更新关联
                                plan_step.step = template_step
                                plan_step.save(update_fields=['step'])
                                
                                # 重新计算哈希值
                                new_hash = TemplateChangeDetector.calculate_step_hash(template_step)
                                if plan_step.step_hash != new_hash:
                                    # 基于快照数据计算哈希值
                                    from apps.job_templates.sync_service import TemplateChangeDetector
                                    
                                    # 创建虚拟步骤对象来计算快照哈希
                                    class MockStep:
                                        def __init__(self, plan_step):
                                            self.name = plan_step.step_name
                                            self.description = plan_step.step_description
                                            self.step_type = plan_step.step_type
                                            self.script_content = plan_step.step_script_content
                                            self.script_type = plan_step.step_script_type
                                            self.order = plan_step.order
                                            self.step_parameters = plan_step.step_parameters
                                            self.timeout = plan_step.step_timeout
                                            self.ignore_error = plan_step.step_ignore_error
                                            self.condition = plan_step.step_condition
                                            # 模拟空的关联查询
                                            self.target_hosts = type('MockQuerySet', (), {'values_list': lambda *args, **kwargs: []})()
                                            self.target_groups = type('MockQuerySet', (), {'values_list': lambda *args, **kwargs: []})()
                                    
                                    mock_step = MockStep(plan_step)
                                    snapshot_hash = TemplateChangeDetector.calculate_step_hash(mock_step)
                                    plan_step.step_hash = snapshot_hash
                                    plan_step.save(update_fields=['step_hash'])
                                    
                                    self.stdout.write(f'      更新哈希值: {snapshot_hash}')

                            fixed_steps += 1
                        else:
                            self.stdout.write(f'    步骤 {i+1} 名称不匹配: {plan_step.step_name} != {template_step.name}')
                    elif plan_step.step is None:
                        self.stdout.write(f'    步骤 {i+1} 没有对应的模板步骤')
            else:
                self.stdout.write('  所有步骤关联正常')

                # 即使关联正常，也检查哈希值是否需要更新
                for plan_step in plan_steps:
                    if plan_step.step:
                        from apps.job_templates.sync_service import TemplateChangeDetector
                        template_hash = TemplateChangeDetector.calculate_step_hash(plan_step.step)
                        if plan_step.step_hash != template_hash:
                            if not dry_run:
                                # 基于快照数据重新计算哈希值

                                class MockStep:
                                    def __init__(self, plan_step):
                                        self.name = plan_step.step_name
                                        self.description = plan_step.step_description
                                        self.step_type = plan_step.step_type
                                        self.script_content = plan_step.step_script_content
                                        self.script_type = plan_step.step_script_type
                                        self.order = plan_step.order
                                        self.step_parameters = plan_step.step_parameters
                                        self.timeout = plan_step.step_timeout
                                        self.ignore_error = plan_step.step_ignore_error
                                        self.condition = plan_step.step_condition
                                        self.target_hosts = type('MockQuerySet', (), {'values_list': lambda *args, **kwargs: []})()
                                        self.target_groups = type('MockQuerySet', (), {'values_list': lambda *args, **kwargs: []})()

                                mock_step = MockStep(plan_step)
                                snapshot_hash = TemplateChangeDetector.calculate_step_hash(mock_step)
                                plan_step.step_hash = snapshot_hash
                                plan_step.save(update_fields=['step_hash'])
                                self.stdout.write(f'    更新步骤 {plan_step.step_name} 的哈希值')
                                plan_fixed = True

            if plan_fixed:
                fixed_plans += 1

        self.stdout.write(f'\n=== 修复完成 ===')
        self.stdout.write(f'检查的执行方案数量: {total_plans}')
        self.stdout.write(f'需要修复的执行方案数量: {fixed_plans}')
        self.stdout.write(f'检查的步骤数量: {total_steps}')
        self.stdout.write(f'修复的步骤数量: {fixed_steps}')
        
        if dry_run:
            self.stdout.write('\n使用 --no-dry-run 参数来实际执行修复')
        else:
            self.stdout.write(self.style.SUCCESS('\n修复完成！'))
