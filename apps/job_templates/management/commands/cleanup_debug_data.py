"""
清理调试数据管理命令
"""
from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta
from apps.executor.models import ExecutionRecord
from apps.job_templates.models import ExecutionPlan


class Command(BaseCommand):
    help = '清理旧的调试数据'

    def add_arguments(self, parser):
        parser.add_argument(
            '--days',
            type=int,
            default=1,
            help='清理多少天前的调试数据（默认1天）',
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='只显示要清理的数据，不实际删除',
        )
        parser.add_argument(
            '--cleanup-plans',
            action='store_true',
            help='同时清理旧的调试执行方案',
        )

    def handle(self, *args, **options):
        days = options['days']
        dry_run = options['dry_run']
        cleanup_plans = options['cleanup_plans']
        
        cutoff_date = timezone.now() - timedelta(days=days)
        
        if dry_run:
            self.stdout.write(f'=== 干运行模式，只显示要清理的数据（{days}天前） ===')
        else:
            self.stdout.write(f'=== 开始清理调试数据（{days}天前） ===')

        # 1. 清理调试执行记录
        debug_records = ExecutionRecord.objects.filter(
            trigger_type='debug',
            created_at__lt=cutoff_date
        )
        
        self.stdout.write(f'\n找到 {debug_records.count()} 条调试执行记录需要清理:')
        for record in debug_records:
            self.stdout.write(f'  - {record.name} (ID: {record.execution_id}, 创建时间: {record.created_at})')
        
        if not dry_run:
            deleted_records = debug_records.delete()[0]
            self.stdout.write(f'✅ 已删除 {deleted_records} 条调试执行记录')

        # 2. 清理调试执行方案（可选）
        if cleanup_plans:
            debug_plans = ExecutionPlan.objects.filter(
                name__startswith='[调试]',
                created_at__lt=cutoff_date
            )
            
            self.stdout.write(f'\n找到 {debug_plans.count()} 个调试执行方案需要清理:')
            for plan in debug_plans:
                self.stdout.write(f'  - {plan.name} (ID: {plan.id}, 创建时间: {plan.created_at})')
            
            if not dry_run:
                deleted_plans = debug_plans.delete()[0]
                self.stdout.write(f'✅ 已删除 {deleted_plans} 个调试执行方案')

        if dry_run:
            self.stdout.write('\n=== 干运行完成，未实际删除任何数据 ===')
        else:
            self.stdout.write('\n=== 调试数据清理完成 ===')
