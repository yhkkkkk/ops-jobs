"""
将执行记录从旧格式迁移到step_results格式的管理命令
"""
import json
from django.core.management.base import BaseCommand
from django.db import transaction
from apps.executor.models import ExecutionRecord


class Command(BaseCommand):
    help = '将执行记录从旧格式迁移到step_results格式'

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
            help='限制处理的记录数量（默认100）',
        )
        parser.add_argument(
            '--execution-id',
            type=str,
            help='只处理指定的execution_id',
        )
        parser.add_argument(
            '--fix-summary',
            action='store_true',
            help='修复log_summary统计数据',
        )
        parser.add_argument(
            '--clean-results',
            action='store_true',
            help='清理冗余的results字段',
        )
        parser.add_argument(
            '--auto-fix',
            action='store_true',
            help='自动扫描并修复所有问题（迁移、清理、修复摘要）',
        )
        parser.add_argument(
            '--fix-time-info',
            action='store_true',
            help='修复step_results中的时间信息并删除step_logs',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        limit = options['limit']
        execution_id = options['execution_id']
        fix_summary = options['fix_summary']

        if fix_summary:
            self.fix_log_summary(dry_run, limit, execution_id)
            return

        if options['clean_results']:
            self.clean_results_field(dry_run, limit, execution_id)
            return

        if options['auto_fix']:
            self.auto_fix_all(dry_run, limit, execution_id)
            return

        if options['fix_time_info']:
            self.fix_time_info(dry_run, limit, execution_id)
            return

        self.stdout.write(
            self.style.SUCCESS(f'开始迁移执行记录到step_results格式 (dry_run={dry_run}, limit={limit})')
        )
        
        # 构建查询条件
        queryset = ExecutionRecord.objects.all()
        
        if execution_id:
            queryset = queryset.filter(execution_id=execution_id)
        
        # 查找需要迁移的记录（没有step_results但有results或step_logs的记录）
        records_to_migrate = []
        
        for record in queryset.order_by('-created_at')[:limit]:
            execution_results = record.execution_results or {}
            
            # 如果已经有step_results，跳过
            if execution_results.get('step_results'):
                continue
                
            # 如果有results或step_logs，需要迁移
            if execution_results.get('results') or execution_results.get('step_logs'):
                records_to_migrate.append(record)
        
        total_count = len(records_to_migrate)
        
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
                        self.stdout.write(f'✓ 迁移成功: {record.execution_id}')
                    else:
                        failed_count += 1
                        self.stdout.write(f'✗ 迁移跳过: {record.execution_id}')
            except Exception as e:
                failed_count += 1
                self.stdout.write(
                    self.style.ERROR(f'✗ 迁移失败: {record.execution_id} - {e}')
                )
        
        self.stdout.write(
            self.style.SUCCESS(f'迁移完成: 成功 {migrated_count}, 失败 {failed_count}')
        )

    def migrate_record(self, record):
        """迁移单个执行记录"""
        execution_results = record.execution_results or {}
        
        # 如果已经有step_results，跳过
        if execution_results.get('step_results'):
            return False
        
        step_results = {}
        
        # 方案1：从results构建step_results
        results = execution_results.get('results', [])
        if results:
            step_results = self.convert_results_to_step_results(results, record)
        
        # 方案2：从step_logs构建step_results
        elif execution_results.get('step_logs'):
            step_results = self.convert_step_logs_to_step_results(execution_results['step_logs'], record)
        
        if not step_results:
            return False
        
        # 更新执行记录，删除旧的results字段
        execution_results['step_results'] = step_results
        if 'results' in execution_results:
            del execution_results['results']  # 删除冗余的results字段
        record.execution_results = execution_results
        record.save(update_fields=['execution_results'])
        
        return True

    def convert_results_to_step_results(self, results, record):
        """从results格式转换为step_results格式"""
        if not results or not isinstance(results, list):
            return {}
        
        step_results = {
            '脚本执行': {
                'step_order': 1,
                'step_type': 'script',
                'step_status': 'success',  # 默认成功，后面会根据主机结果调整
                'hosts': {}
            }
        }
        
        has_failed = False
        
        for result in results:
            if not isinstance(result, dict):
                continue
                
            host_id = str(result.get('host_id', 'unknown'))
            success = result.get('success', True)
            
            if not success:
                has_failed = True
            
            step_results['脚本执行']['hosts'][host_id] = {
                'host_id': result.get('host_id'),
                'host_name': result.get('host_name', f'Host-{host_id}'),
                'host_ip': result.get('host_ip', ''),
                'success': success,
                'stdout': result.get('stdout', ''),
                'stderr': result.get('stderr', ''),
                'exit_code': result.get('exit_code', 0),
                'execution_time': result.get('execution_time', 0),
                'message': result.get('message', ''),
                'log_lines': len(result.get('stdout', '').split('\n')) + len(result.get('stderr', '').split('\n'))
            }
        
        # 根据主机结果设置步骤状态
        if has_failed:
            step_results['脚本执行']['step_status'] = 'failed'
        
        return step_results

    def convert_step_logs_to_step_results(self, step_logs, record):
        """从step_logs格式转换为step_results格式"""
        if not step_logs or not isinstance(step_logs, dict):
            return {}
        
        step_results = {}
        
        for step_name, hosts_data in step_logs.items():
            if not isinstance(hosts_data, dict):
                continue
            
            step_results[step_name] = {
                'step_order': 1,  # 默认步骤顺序
                'step_type': 'script',
                'step_status': 'success',
                'hosts': {}
            }
            
            has_failed = False
            
            for host_id, host_data in hosts_data.items():
                if host_id == 'duration':  # 跳过duration字段
                    continue
                    
                if not isinstance(host_data, dict):
                    continue
                
                # 从logs数组重建stdout/stderr
                logs = host_data.get('logs', [])
                stdout_lines = []
                stderr_lines = []
                
                for log in logs:
                    if isinstance(log, dict):
                        content = log.get('content', '')
                        log_type = log.get('log_type', 'stdout')
                        
                        if log_type == 'stderr':
                            stderr_lines.append(content)
                        else:
                            stdout_lines.append(content)
                
                success = host_data.get('status') == 'success'
                if not success:
                    has_failed = True
                
                step_results[step_name]['hosts'][str(host_id)] = {
                    'host_id': host_data.get('host_id'),
                    'host_name': host_data.get('host_name', f'Host-{host_id}'),
                    'host_ip': host_data.get('host_ip', ''),
                    'success': success,
                    'stdout': '\n'.join(stdout_lines),
                    'stderr': '\n'.join(stderr_lines),
                    'exit_code': 0 if success else 1,
                    'execution_time': host_data.get('execution_time', 0),
                    'message': '执行成功' if success else '执行失败',
                    'log_lines': len(logs)
                }
            
            # 根据主机结果设置步骤状态
            if has_failed:
                step_results[step_name]['step_status'] = 'failed'
        
        return step_results

    def fix_log_summary(self, dry_run, limit, execution_id):
        """修复log_summary统计数据"""
        self.stdout.write(
            self.style.SUCCESS(f'开始修复log_summary统计数据 (dry_run={dry_run}, limit={limit})')
        )

        # 构建查询条件
        queryset = ExecutionRecord.objects.all()

        if execution_id:
            queryset = queryset.filter(execution_id=execution_id)

        # 查找有step_logs的记录
        records_to_fix = []

        for record in queryset.order_by('-created_at')[:limit]:
            execution_results = record.execution_results or {}

            # 如果有step_logs，需要修复摘要
            if execution_results.get('step_logs'):
                records_to_fix.append(record)

        total_count = len(records_to_fix)

        if total_count == 0:
            self.stdout.write(
                self.style.SUCCESS('没有找到需要修复摘要的记录')
            )
            return

        self.stdout.write(
            self.style.WARNING(f'找到 {total_count} 条需要修复摘要的记录')
        )

        if dry_run:
            for record in records_to_fix:
                self.stdout.write(f'  - ID: {record.id}, 执行ID: {record.execution_id}, 名称: {record.name}')
            return

        # 执行修复
        fixed_count = 0
        failed_count = 0

        for record in records_to_fix:
            try:
                with transaction.atomic():
                    if self.fix_record_summary(record):
                        fixed_count += 1
                        self.stdout.write(f'✓ 修复成功: {record.execution_id}')
                    else:
                        failed_count += 1
                        self.stdout.write(f'✗ 修复跳过: {record.execution_id}')
            except Exception as e:
                failed_count += 1
                self.stdout.write(
                    self.style.ERROR(f'✗ 修复失败: {record.execution_id} - {e}')
                )

        self.stdout.write(
            self.style.SUCCESS(f'修复完成: 成功 {fixed_count}, 失败 {failed_count}')
        )

    def fix_record_summary(self, record):
        """修复单个记录的摘要"""
        execution_results = record.execution_results or {}
        step_logs = execution_results.get('step_logs', {})
        step_results = execution_results.get('step_results', {})

        # 如果没有step_logs但有step_results，从step_results重新生成step_logs
        if not step_logs and step_results:
            step_logs = self.generate_step_logs_from_step_results(step_results, record)
            execution_results['step_logs'] = step_logs

        if not step_logs:
            return False

        # 重新计算摘要
        log_summary = self.calculate_log_summary(step_logs)

        # 更新执行记录
        execution_results['log_summary'] = log_summary
        record.execution_results = execution_results
        record.save(update_fields=['execution_results'])

        return True

    def calculate_log_summary(self, step_logs):
        """计算日志摘要"""
        total_steps = len(step_logs)
        success_steps = 0
        failed_steps = 0

        all_hosts = set()
        success_hosts = set()
        failed_hosts = set()

        for step_log in step_logs.values():
            step_has_failed = False
            step_has_success = False

            for key, value in step_log.items():
                if key in ['duration', 'status', 'step_name', 'step_order']:
                    continue

                if isinstance(value, dict) and ('host_id' in value or 'status' in value):
                    host_id = key
                    host_status = value.get('status')

                    all_hosts.add(host_id)

                    if host_status == 'success':
                        success_hosts.add(host_id)
                        step_has_success = True
                    elif host_status == 'failed':
                        failed_hosts.add(host_id)
                        step_has_failed = True

            # 根据主机状态确定步骤状态
            if step_has_failed:
                failed_steps += 1
            elif step_has_success:
                success_steps += 1

        return {
            'total_steps': total_steps,
            'success_steps': success_steps,
            'failed_steps': failed_steps,
            'total_hosts': len(all_hosts),
            'success_hosts': len(success_hosts),
            'failed_hosts': len(failed_hosts)
        }

    def clean_results_field(self, dry_run, limit, execution_id):
        """清理冗余的results字段"""
        self.stdout.write(
            self.style.SUCCESS(f'开始清理冗余的results字段 (dry_run={dry_run}, limit={limit})')
        )

        # 构建查询条件
        queryset = ExecutionRecord.objects.all()

        if execution_id:
            queryset = queryset.filter(execution_id=execution_id)

        # 查找有results字段的记录
        records_to_clean = []

        for record in queryset.order_by('-created_at')[:limit]:
            execution_results = record.execution_results or {}

            # 如果有results字段，需要清理
            if execution_results.get('results'):
                records_to_clean.append(record)

        total_count = len(records_to_clean)

        if total_count == 0:
            self.stdout.write(
                self.style.SUCCESS('没有找到需要清理results字段的记录')
            )
            return

        self.stdout.write(
            self.style.WARNING(f'找到 {total_count} 条需要清理results字段的记录')
        )

        if dry_run:
            for record in records_to_clean:
                self.stdout.write(f'  - ID: {record.id}, 执行ID: {record.execution_id}, 名称: {record.name}')
            return

        # 执行清理
        cleaned_count = 0
        failed_count = 0

        for record in records_to_clean:
            try:
                with transaction.atomic():
                    execution_results = record.execution_results or {}
                    if 'results' in execution_results:
                        del execution_results['results']
                        record.execution_results = execution_results
                        record.save(update_fields=['execution_results'])
                        cleaned_count += 1
                        self.stdout.write(f'✓ 清理成功: {record.execution_id}')
                    else:
                        failed_count += 1
                        self.stdout.write(f'✗ 清理跳过: {record.execution_id}')
            except Exception as e:
                failed_count += 1
                self.stdout.write(
                    self.style.ERROR(f'✗ 清理失败: {record.execution_id} - {e}')
                )

        self.stdout.write(
            self.style.SUCCESS(f'清理完成: 成功 {cleaned_count}, 失败 {failed_count}')
        )

    def auto_fix_all(self, dry_run, limit, execution_id):
        """自动扫描并修复所有问题"""
        self.stdout.write(
            self.style.SUCCESS('🚀 开始自动扫描和修复所有执行记录...')
        )

        # 构建查询条件
        queryset = ExecutionRecord.objects.all()

        if execution_id:
            queryset = queryset.filter(execution_id=execution_id)

        # 扫描所有记录，分类问题
        records_need_migration = []
        records_need_cleanup = []
        records_need_summary_fix = []

        self.stdout.write('📊 正在扫描执行记录...')

        for record in queryset.order_by('-created_at')[:limit]:
            execution_results = record.execution_results or {}

            # 检查是否需要迁移到step_results
            if not execution_results.get('step_results') and (execution_results.get('results') or execution_results.get('step_logs')):
                records_need_migration.append(record)

            # 检查是否需要清理results字段
            if execution_results.get('results') and execution_results.get('step_results'):
                records_need_cleanup.append(record)

            # 检查是否需要修复摘要或缺少step_logs
            if execution_results.get('step_results'):
                # 如果有step_results但没有step_logs，需要修复
                if not execution_results.get('step_logs'):
                    records_need_summary_fix.append(record)
                else:
                    # 如果有step_logs但摘要统计有问题，也需要修复
                    log_summary = execution_results.get('log_summary', {})
                    if (log_summary.get('total_hosts', 0) == 0 or
                        log_summary.get('success_hosts', 0) == 0 or
                        log_summary.get('total_steps', 0) == 0):
                        records_need_summary_fix.append(record)

        # 显示扫描结果
        self.stdout.write(f'📋 扫描完成:')
        self.stdout.write(f'  - 需要迁移到step_results: {len(records_need_migration)} 条')
        self.stdout.write(f'  - 需要清理results字段: {len(records_need_cleanup)} 条')
        self.stdout.write(f'  - 需要修复摘要统计: {len(records_need_summary_fix)} 条')

        if dry_run:
            self.stdout.write(self.style.WARNING('🔍 预览模式，不执行实际修复'))

            if records_need_migration:
                self.stdout.write('\n需要迁移的记录:')
                for record in records_need_migration[:10]:  # 只显示前10条
                    self.stdout.write(f'  - ID: {record.id}, 执行ID: {record.execution_id}')

            if records_need_cleanup:
                self.stdout.write('\n需要清理的记录:')
                for record in records_need_cleanup[:10]:
                    self.stdout.write(f'  - ID: {record.id}, 执行ID: {record.execution_id}')

            if records_need_summary_fix:
                self.stdout.write('\n需要修复摘要的记录:')
                for record in records_need_summary_fix[:10]:
                    self.stdout.write(f'  - ID: {record.id}, 执行ID: {record.execution_id}')

            return

        # 执行修复
        total_fixed = 0
        total_failed = 0

        # 1. 执行迁移
        if records_need_migration:
            self.stdout.write(f'\n🔄 开始迁移 {len(records_need_migration)} 条记录...')
            migrated, failed = self._batch_migrate_records(records_need_migration)
            total_fixed += migrated
            total_failed += failed
            self.stdout.write(f'✅ 迁移完成: 成功 {migrated}, 失败 {failed}')

        # 2. 清理results字段
        if records_need_cleanup:
            self.stdout.write(f'\n🧹 开始清理 {len(records_need_cleanup)} 条记录的results字段...')
            cleaned, failed = self._batch_clean_results(records_need_cleanup)
            total_fixed += cleaned
            total_failed += failed
            self.stdout.write(f'✅ 清理完成: 成功 {cleaned}, 失败 {failed}')

        # 3. 修复摘要统计
        if records_need_summary_fix:
            self.stdout.write(f'\n📊 开始修复 {len(records_need_summary_fix)} 条记录的摘要统计...')
            fixed, failed = self._batch_fix_summary(records_need_summary_fix)
            total_fixed += fixed
            total_failed += failed
            self.stdout.write(f'✅ 摘要修复完成: 成功 {fixed}, 失败 {failed}')

        # 显示总结
        self.stdout.write(f'\n🎉 自动修复完成!')
        self.stdout.write(f'📈 总计: 成功修复 {total_fixed} 项, 失败 {total_failed} 项')

        if total_failed == 0:
            self.stdout.write(self.style.SUCCESS('✨ 所有问题已成功修复!'))
        else:
            self.stdout.write(self.style.WARNING(f'⚠️  有 {total_failed} 项修复失败，请检查日志'))

    def _batch_migrate_records(self, records):
        """批量迁移记录"""
        success_count = 0
        failed_count = 0

        for record in records:
            try:
                with transaction.atomic():
                    if self.migrate_record(record):
                        success_count += 1
                    else:
                        failed_count += 1
            except Exception as e:
                failed_count += 1
                self.stdout.write(f'❌ 迁移失败: {record.execution_id} - {e}')

        return success_count, failed_count

    def _batch_clean_results(self, records):
        """批量清理results字段"""
        success_count = 0
        failed_count = 0

        for record in records:
            try:
                with transaction.atomic():
                    execution_results = record.execution_results or {}
                    if 'results' in execution_results:
                        del execution_results['results']
                        record.execution_results = execution_results
                        record.save(update_fields=['execution_results'])
                        success_count += 1
                    else:
                        failed_count += 1
            except Exception as e:
                failed_count += 1
                self.stdout.write(f'❌ 清理失败: {record.execution_id} - {e}')

        return success_count, failed_count

    def _batch_fix_summary(self, records):
        """批量修复摘要统计"""
        success_count = 0
        failed_count = 0

        for record in records:
            try:
                with transaction.atomic():
                    if self.fix_record_summary(record):
                        success_count += 1
                    else:
                        failed_count += 1
            except Exception as e:
                failed_count += 1
                self.stdout.write(f'❌ 摘要修复失败: {record.execution_id} - {e}')

        return success_count, failed_count

    def fix_time_info(self, dry_run, limit, execution_id):
        """修复step_results中的时间信息并删除step_logs"""
        self.stdout.write(
            self.style.SUCCESS('🔧 开始修复执行记录的时间信息...')
        )

        # 构建查询条件
        queryset = ExecutionRecord.objects.all()

        if execution_id:
            queryset = queryset.filter(execution_id=execution_id)

        # 查找需要修复的记录
        records_to_fix = []

        for record in queryset.order_by('-created_at')[:limit]:
            execution_results = record.execution_results or {}
            step_results = execution_results.get('step_results', {})

            # 检查是否需要修复
            needs_fix = False

            # 如果有step_logs字段，需要删除
            if 'step_logs' in execution_results:
                needs_fix = True

            # 如果step_results中缺少时间信息，需要修复
            if step_results:
                for step_name, step_data in step_results.items():
                    if not step_data.get('started_at') or not step_data.get('duration'):
                        needs_fix = True
                        break

                    # 检查主机是否缺少时间信息
                    hosts = step_data.get('hosts', {})
                    for host_id, host_data in hosts.items():
                        if not host_data.get('start_time') or not host_data.get('end_time'):
                            needs_fix = True
                            break

                    if needs_fix:
                        break

            if needs_fix:
                records_to_fix.append(record)

        total_count = len(records_to_fix)

        if total_count == 0:
            self.stdout.write(
                self.style.SUCCESS('✅ 没有找到需要修复时间信息的记录')
            )
            return

        self.stdout.write(
            self.style.WARNING(f'📋 找到 {total_count} 条需要修复时间信息的记录')
        )

        if dry_run:
            for record in records_to_fix:
                self.stdout.write(f'  - ID: {record.id}, 执行ID: {record.execution_id}, 名称: {record.name}')
            return

        # 执行修复
        fixed_count = 0
        failed_count = 0

        for record in records_to_fix:
            try:
                with transaction.atomic():
                    if self.fix_record_time_info(record):
                        fixed_count += 1
                        self.stdout.write(f'✅ 修复成功: {record.execution_id}')
                    else:
                        failed_count += 1
                        self.stdout.write(f'❌ 修复跳过: {record.execution_id}')
            except Exception as e:
                failed_count += 1
                self.stdout.write(
                    self.style.ERROR(f'❌ 修复失败: {record.execution_id} - {e}')
                )

        self.stdout.write(
            self.style.SUCCESS(f'🎉 时间信息修复完成: 成功 {fixed_count}, 失败 {failed_count}')
        )

    def fix_record_time_info(self, record):
        """修复单个记录的时间信息"""
        execution_results = record.execution_results or {}
        step_results = execution_results.get('step_results', {})

        if not step_results:
            return False

        # 删除step_logs字段
        if 'step_logs' in execution_results:
            del execution_results['step_logs']

        # 修复每个步骤的时间信息
        for step_name, step_data in step_results.items():
            hosts = step_data.get('hosts', {})

            # 收集主机时间信息
            host_start_times = []
            host_end_times = []
            host_execution_times = []

            # 为每个主机添加时间信息
            for host_id, host_data in hosts.items():
                # 如果主机没有时间信息，使用执行记录的时间
                if not host_data.get('start_time'):
                    host_data['start_time'] = record.started_at.isoformat() if record.started_at else record.created_at.isoformat()

                if not host_data.get('end_time'):
                    host_data['end_time'] = record.finished_at.isoformat() if record.finished_at else record.created_at.isoformat()

                if not host_data.get('execution_time'):
                    host_data['execution_time'] = record.duration or 0

                # 收集时间信息
                if host_data.get('start_time'):
                    host_start_times.append(host_data['start_time'])
                if host_data.get('end_time'):
                    host_end_times.append(host_data['end_time'])
                if host_data.get('execution_time'):
                    host_execution_times.append(host_data['execution_time'])

            # 计算步骤级别的时间信息
            if host_start_times and host_end_times:
                step_started_at = min(host_start_times)
                step_finished_at = max(host_end_times)

                # 计算步骤持续时间
                try:
                    from datetime import datetime
                    start_dt = datetime.fromisoformat(step_started_at.replace('Z', '+00:00'))
                    end_dt = datetime.fromisoformat(step_finished_at.replace('Z', '+00:00'))
                    step_duration = (end_dt - start_dt).total_seconds()
                except Exception:
                    # 如果时间计算失败，使用最长的主机执行时间
                    step_duration = max(host_execution_times) if host_execution_times else record.duration or 0

                # 更新步骤时间信息
                step_data['started_at'] = step_started_at
                step_data['finished_at'] = step_finished_at
                step_data['duration'] = step_duration

        # 保存更新后的数据
        record.execution_results = execution_results
        record.save(update_fields=['execution_results'])

        return True
