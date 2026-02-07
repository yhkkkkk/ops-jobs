"""
Management command to sync PlanStep snapshots from their template steps.
This fixes existing execution plans that were created before file_sources was added.
"""
from django.core.management.base import BaseCommand
from apps.job_templates.models import PlanStep


class Command(BaseCommand):
    help = 'Sync PlanStep snapshots from their template steps to populate missing file_sources data'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be updated without making changes',
        )
        parser.add_argument(
            '--force',
            action='store_true',
            help='Force sync all file_transfer steps, not just empty ones',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        force = options['force']

        # Find PlanSteps to update
        if force:
            # Force: update all file_transfer steps
            plan_steps = PlanStep.objects.filter(
                step__step_type='file_transfer'
            ).select_related('step')
            self.stdout.write(f'Force mode: Found {plan_steps.count()} file_transfer PlanStep records')
        else:
            # Normal: only update steps with empty file_sources
            plan_steps = PlanStep.objects.filter(
                step__step_type='file_transfer',
                step_file_sources=[]
            ).select_related('step')
            self.stdout.write(f'Found {plan_steps.count()} PlanStep records with empty step_file_sources')

        total_count = plan_steps.count()

        if total_count == 0:
            self.stdout.write(self.style.SUCCESS('No records need updating'))
            return
        
        updated_count = 0
        for plan_step in plan_steps:
            template_step = plan_step.step
            if template_step and template_step.file_sources:
                if dry_run:
                    self.stdout.write(
                        f'Would update PlanStep {plan_step.id} with {len(template_step.file_sources)} file sources'
                    )
                else:
                    # Call the copy method to sync snapshot data
                    plan_step.copy_from_template_step()
                    plan_step.save()
                    self.stdout.write(
                        self.style.SUCCESS(
                            f'Updated PlanStep {plan_step.id} with {len(template_step.file_sources)} file sources'
                        )
                    )
                updated_count += 1
            else:
                self.stdout.write(
                    self.style.WARNING(
                        f'PlanStep {plan_step.id} has no template step or template step has no file_sources'
                    )
                )
        
        if dry_run:
            self.stdout.write(self.style.WARNING(f'DRY RUN: Would have updated {updated_count} records'))
        else:
            self.stdout.write(self.style.SUCCESS(f'Successfully updated {updated_count} PlanStep records'))
