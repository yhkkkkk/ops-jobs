from django.core.management.base import BaseCommand
from apps.job_templates.models import PlanStep
from apps.job_templates.sync_service import TemplateChangeDetector


class Command(BaseCommand):
    help = '重新计算所有 PlanStep 的哈希值'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='只显示将要更新的记录，不实际更新',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        
        if dry_run:
            self.stdout.write(self.style.WARNING('DRY RUN 模式 - 不会实际更新数据'))
        
        plan_steps = PlanStep.objects.filter(step__isnull=False).select_related('step')
        total_count = plan_steps.count()
        
        self.stdout.write(f'找到 {total_count} 个需要处理的 PlanStep 记录')
        
        updated_count = 0
        
        for plan_step in plan_steps:
            try:
                # 计算新的哈希值
                new_hash = TemplateChangeDetector.calculate_step_hash(plan_step.step)
                old_hash = plan_step.step_hash
                
                if old_hash != new_hash:
                    if not dry_run:
                        plan_step.step_hash = new_hash
                        plan_step.save(update_fields=['step_hash'])
                    
                    updated_count += 1
                    self.stdout.write(
                        f'更新 PlanStep {plan_step.id}: {old_hash[:8]}... -> {new_hash[:8]}...'
                    )
                
            except Exception as e:
                self.stdout.write(
                    self.style.ERROR(f'处理 PlanStep {plan_step.id} 时出错: {e}')
                )
        
        if dry_run:
            self.stdout.write(
                self.style.SUCCESS(f'DRY RUN 完成: 将更新 {updated_count}/{total_count} 个记录')
            )
        else:
            self.stdout.write(
                self.style.SUCCESS(f'成功更新 {updated_count}/{total_count} 个记录的哈希值')
            )
