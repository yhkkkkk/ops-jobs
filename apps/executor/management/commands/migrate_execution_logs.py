"""
迁移旧格式的执行记录日志到新格式
"""

from django.core.management.base import BaseCommand
from django.db import transaction
from apps.executor.models import ExecutionRecord
import logging

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = '将旧格式的执行记录日志迁移到新的主机聚合格式'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='只显示需要迁移的记录，不实际执行迁移',
        )
        parser.add_argument(
            '--limit',
            type=int,
            default=100,
            help='每次处理的记录数量（默认100）',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        limit = options['limit']
        
        self.stdout.write(
            self.style.SUCCESS(f'开始迁移执行记录日志格式 (dry_run={dry_run}, limit={limit})')
        )
        
        # 查找需要迁移的记录（有旧格式logs但没有新格式host_logs的记录）
        records_to_migrate = ExecutionRecord.objects.filter(
            execution_results__logs__isnull=False
        ).exclude(
            execution_results__host_logs__isnull=False
        )[:limit]
        
        total_count = records_to_migrate.count()
        
        if total_count == 0:
            self.stdout.write(
                self.style.SUCCESS('没有找到需要迁移的记录')
            )
            return
        
        self.stdout.write(
            self.style.WARNING(f'找到 {total_count} 条需要迁移的记录')
        )
        
        if dry_run:
            for record in records_to_migrate:
                self.stdout.write(f'  - ID: {record.id}, 执行ID: {record.execution_id}, 名称: {record.name}')
            return
        
        # 执行迁移
        migrated_count = 0
        failed_count = 0
        
        for record in records_to_migrate:
            try:
                with transaction.atomic():
                    if self.migrate_record(record):
                        migrated_count += 1
                        self.stdout.write(f'✅ 迁移成功: {record.execution_id}')
                    else:
                        failed_count += 1
                        self.stdout.write(f'⚠️  跳过记录: {record.execution_id} (无有效日志)')
            except Exception as e:
                failed_count += 1
                self.stdout.write(
                    self.style.ERROR(f'❌ 迁移失败: {record.execution_id} - {str(e)}')
                )
                logger.error(f'迁移执行记录失败: {record.execution_id}', exc_info=True)
        
        self.stdout.write(
            self.style.SUCCESS(
                f'迁移完成: 成功 {migrated_count} 条, 失败 {failed_count} 条'
            )
        )

    def migrate_record(self, record):
        """迁移单个执行记录"""
        execution_results = record.execution_results or {}
        legacy_logs = execution_results.get('logs', [])
        
        if not legacy_logs or not isinstance(legacy_logs, list):
            return False
        
        # 转换为新格式
        host_logs = self.convert_legacy_logs_to_host_logs(legacy_logs)
        
        if not host_logs:
            return False
        
        # 生成日志摘要
        log_summary = self.create_log_summary(host_logs)
        
        # 更新执行记录
        execution_results.update({
            'host_logs': host_logs,
            'log_summary': log_summary,
            'migrated_at': '2025-01-18T12:00:00Z',  # 迁移时间标记
            # 保留原始logs用于备份
            'legacy_logs_backup': legacy_logs
        })
        
        record.execution_results = execution_results
        record.save(update_fields=['execution_results'])
        
        return True

    def convert_legacy_logs_to_host_logs(self, legacy_logs):
        """将旧格式日志转换为新格式"""
        host_logs = {}
        
        for log_entry in legacy_logs:
            host_id = log_entry.get('host_id', 'unknown')
            host_name = log_entry.get('host_name', '')
            host_ip = log_entry.get('host_ip', '')
            content = log_entry.get('content', '')
            log_type = log_entry.get('log_type', 'stdout')
            timestamp = log_entry.get('timestamp', '')
            
            # 初始化主机日志结构
            if host_id not in host_logs:
                host_logs[host_id] = {
                    'host_id': host_id,
                    'host_name': host_name,
                    'host_ip': host_ip,
                    'status': 'unknown',
                    'logs': '',
                    'error_logs': '',
                    'start_time': timestamp,
                    'end_time': timestamp,
                    'log_count': 0
                }
            
            # 更新时间范围
            if timestamp and timestamp < host_logs[host_id]['start_time']:
                host_logs[host_id]['start_time'] = timestamp
            if timestamp and timestamp > host_logs[host_id]['end_time']:
                host_logs[host_id]['end_time'] = timestamp
            
            # 合并日志内容
            if content.strip():
                formatted_log = f"[{timestamp}] {content}\n"
                if log_type in ['stderr', 'error']:
                    host_logs[host_id]['error_logs'] += formatted_log
                else:
                    host_logs[host_id]['logs'] += formatted_log
                
                host_logs[host_id]['log_count'] += 1
        
        # 推断主机状态
        for host_id in host_logs:
            if host_logs[host_id]['error_logs'].strip():
                host_logs[host_id]['status'] = 'failed'
            else:
                host_logs[host_id]['status'] = 'success'
        
        return host_logs

    def create_log_summary(self, host_logs):
        """创建日志摘要"""
        total_hosts = len(host_logs)
        success_hosts = len([h for h in host_logs.values() if h['status'] == 'success'])
        failed_hosts = total_hosts - success_hosts
        total_size = sum(len(h['logs']) + len(h['error_logs']) for h in host_logs.values())
        
        return {
            'total_hosts': total_hosts,
            'success_hosts': success_hosts,
            'failed_hosts': failed_hosts,
            'total_size': total_size
        }
