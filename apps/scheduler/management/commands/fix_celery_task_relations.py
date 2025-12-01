from django.core.management.base import BaseCommand
from apps.scheduler.models import ScheduledJob
from apps.scheduler.services import SchedulerService


class Command(BaseCommand):
    help = '修复定时作业与Celery Beat任务的关联关系'

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
            self.stdout.write('=== 开始修复定时作业与Celery任务关联关系 ===')

        # 查找没有Celery任务关联的定时作业
        jobs_without_celery = ScheduledJob.objects.filter(periodic_task__isnull=True)
        
        self.stdout.write(f'\n找到 {jobs_without_celery.count()} 个没有Celery任务关联的定时作业')
        
        fixed_count = 0
        
        for job in jobs_without_celery:
            self.stdout.write(f'\n检查定时作业: {job.name} (ID: {job.id})')
            self.stdout.write(f'  当前状态: {"启用" if job.is_active else "禁用"}')
            self.stdout.write(f'  Cron表达式: {job.cron_expression}')
            self.stdout.write(f'  时区: {job.timezone}')
            
            if not dry_run:
                try:
                    # 为这个定时作业创建Celery任务
                    SchedulerService._create_periodic_task(job)
                    
                    # 刷新对象以获取最新的关联
                    job.refresh_from_db()
                    
                    self.stdout.write(f'  ✅ 成功创建Celery任务: {job.periodic_task.name}')
                    self.stdout.write(f'  Celery任务启用状态: {job.periodic_task.enabled}')
                    self.stdout.write(f'  状态一致性: {"✅ 一致" if job.is_active == job.periodic_task.enabled else "❌ 不一致"}')
                    
                    fixed_count += 1
                    
                except Exception as e:
                    self.stdout.write(f'  ❌ 创建失败: {e}')
            else:
                self.stdout.write(f'  需要创建Celery任务')

        # 检查所有定时作业的状态一致性
        self.stdout.write(f'\n=== 检查状态一致性 ===')
        
        all_jobs = ScheduledJob.objects.filter(periodic_task__isnull=False)
        inconsistent_count = 0
        
        for job in all_jobs:
            if job.is_active != job.periodic_task.enabled:
                inconsistent_count += 1
                self.stdout.write(f'\n状态不一致: {job.name}')
                self.stdout.write(f'  定时作业状态: {"启用" if job.is_active else "禁用"}')
                self.stdout.write(f'  Celery任务状态: {"启用" if job.periodic_task.enabled else "禁用"}')
                
                if not dry_run:
                    try:
                        # 修复状态不一致
                        job.periodic_task.enabled = job.is_active
                        job.periodic_task.save()
                        self.stdout.write(f'  ✅ 已修复状态一致性')
                        
                    except Exception as e:
                        self.stdout.write(f'  ❌ 修复失败: {e}')

        # 最终统计
        self.stdout.write(f'\n=== 修复完成 ===')
        
        if not dry_run:
            # 重新统计
            total_jobs = ScheduledJob.objects.count()
            jobs_with_celery = ScheduledJob.objects.filter(periodic_task__isnull=False).count()
            
            self.stdout.write(f'总定时作业数量: {total_jobs}')
            self.stdout.write(f'有Celery任务关联的数量: {jobs_with_celery}')
            self.stdout.write(f'修复的关联数量: {fixed_count}')
            self.stdout.write(f'修复的状态不一致数量: {inconsistent_count}')
            
            if total_jobs == jobs_with_celery:
                self.stdout.write(self.style.SUCCESS('✅ 所有定时作业都有Celery任务关联'))
            else:
                self.stdout.write(self.style.ERROR('❌ 仍有定时作业缺少Celery任务关联'))
        else:
            self.stdout.write(f'需要修复的关联数量: {jobs_without_celery.count()}')
            self.stdout.write(f'需要修复的状态不一致数量: {inconsistent_count}')
            self.stdout.write('\n使用不带 --dry-run 参数来实际执行修复')
