from django.core.management.base import BaseCommand
from apps.job_templates.models import PlanStep
from apps.job_templates.sync_service import TemplateChangeDetector


class Command(BaseCommand):
    help = '更新所有执行方案步骤的哈希值'

    def handle(self, *args, **options):
        self.stdout.write('开始更新执行方案步骤哈希值...')
        
        updated_count = 0
        for plan_step in PlanStep.objects.select_related('step').all():
            if plan_step.step:
                # 重新计算哈希值
                new_hash = TemplateChangeDetector.calculate_step_hash(plan_step.step)
                if plan_step.step_hash != new_hash:
                    plan_step.step_hash = new_hash
                    plan_step.save(update_fields=['step_hash'])
                    updated_count += 1
                    self.stdout.write(
                        f'更新步骤 {plan_step.step.name} (ID: {plan_step.id}) 的哈希值'
                    )
        
        self.stdout.write(
            self.style.SUCCESS(f'成功更新了 {updated_count} 个步骤的哈希值')
        )
