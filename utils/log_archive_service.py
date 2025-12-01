"""
日志归档服务 - 将Redis Stream中的实时日志保存到文件系统
"""
import json
import logging
import os
from datetime import datetime
from typing import List, Dict, Any
from django.conf import settings
from django.utils import timezone
from .realtime_logs import realtime_log_service

logger = logging.getLogger(__name__)


class LogArchiveService:
    """日志归档服务"""
    
    @staticmethod
    def get_logs_directory():
        """获取日志存储目录"""
        logs_dir = getattr(settings, 'EXECUTION_LOGS_DIR', os.path.join(settings.BASE_DIR, 'logs', 'executions'))
        os.makedirs(logs_dir, exist_ok=True)
        return logs_dir

    @staticmethod
    def archive_execution_logs(execution_id: int, task_id: str):
        """归档执行日志 - 从Redis Stream保存到ExecutionRecord"""
        try:
            from apps.executor.models import ExecutionRecord

            logger.info(f"开始归档执行日志: execution_id={execution_id}, task_id={task_id}")

            # 从Redis Stream获取所有日志
            logs_data = LogArchiveService._get_all_logs_from_redis(task_id)
            status_data = LogArchiveService._get_all_status_from_redis(task_id)

            # 即使没有日志数据，也要创建基本的执行记录
            if not logs_data and not status_data:
                logger.warning(f"没有找到日志数据，但仍创建基本执行记录: task_id={task_id}")
                # 创建一个基本的日志条目表示任务已执行
                logs_data = [{
                    'timestamp': datetime.now().isoformat(),
                    'host_id': '0',
                    'host_name': '系统',
                    'host_ip': '',
                    'log_type': 'info',
                    'content': '任务已执行，但未获取到详细日志（可能由于Redis连接问题）',
                    'step_name': '任务执行',
                    'step_order': 1
                }]

            # 获取执行记录
            try:
                execution_record = ExecutionRecord.objects.get(execution_id=execution_id)
            except ExecutionRecord.DoesNotExist:
                logger.error(f"执行记录不存在: execution_id={execution_id}")
                return False

            # 按步骤和主机聚合日志数据
            step_logs = LogArchiveService._aggregate_logs_by_step_and_host(logs_data)

            # 根据状态更新推断主机状态
            LogArchiveService._update_step_host_status_from_status_data(step_logs, status_data)

            log_summary = LogArchiveService._create_step_log_summary(execution_id, task_id, step_logs, status_data)

            # 将step_logs转换为logs格式，保持向后兼容
            logs_list = LogArchiveService._convert_step_logs_to_logs_list(step_logs, logs_data)
            
            # 更新执行记录的结果字段
            execution_record.execution_results.update({
                'logs': logs_list,  # 向后兼容的日志格式
                'step_logs': step_logs,  # 按步骤和主机聚合的日志
                'status_updates': status_data,
                'log_summary': log_summary,
                'archived_at': timezone.now().isoformat()
            })
            execution_record.save(update_fields=['execution_results'])

            logger.info(f"归档完成: execution_id={execution_id}, 日志条数={len(logs_data)}")

            # 清理Redis Stream（可选，保留一段时间用于调试）
            # LogArchiveService._cleanup_redis_streams(task_id)

            return True
                
        except Exception as e:
            logger.error(f"归档执行日志失败: execution_id={execution_id}, task_id={task_id} - {e}")
            return False
    
    @staticmethod
    def _aggregate_logs_by_host(logs_data: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
        """按主机聚合日志数据"""
        host_logs = {}

        for log_entry in logs_data:
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
                    'status': 'unknown',  # 将在后续步骤中更新
                    'logs': '',  # 合并后的日志内容
                    'error_logs': '',  # 错误日志
                    'start_time': timestamp,
                    'end_time': timestamp,
                    'log_count': 0
                }

            # 更新时间范围
            if timestamp < host_logs[host_id]['start_time']:
                host_logs[host_id]['start_time'] = timestamp
            if timestamp > host_logs[host_id]['end_time']:
                host_logs[host_id]['end_time'] = timestamp

            # 合并日志内容
            if content.strip():  # 只添加非空内容
                formatted_log = f"[{timestamp}] {content}\n"
                if log_type in ['stderr', 'error']:
                    host_logs[host_id]['error_logs'] += formatted_log
                else:
                    host_logs[host_id]['logs'] += formatted_log

                host_logs[host_id]['log_count'] += 1

        return host_logs

    @staticmethod
    def _aggregate_logs_by_step_and_host(logs_data: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
        """按步骤和主机聚合日志数据"""
        step_logs = {}

        for log_entry in logs_data:
            step_name = log_entry.get('step_name', '执行任务')
            step_order = log_entry.get('step_order', 1)
            host_id = log_entry.get('host_id', 'unknown')
            host_name = log_entry.get('host_name', '')
            host_ip = log_entry.get('host_ip', '')
            content = log_entry.get('content', '')
            log_type = log_entry.get('log_type', 'stdout')
            timestamp = log_entry.get('timestamp', '')

            # 生成步骤ID
            step_id = f"step_{step_order}_{step_name.replace(' ', '_')}"

            # 初始化步骤结构
            if step_id not in step_logs:
                step_logs[step_id] = {
                    'step_name': step_name,
                    'step_order': step_order,
                    'status': 'unknown',
                    'host_logs': {}
                }

            # 初始化主机日志结构
            if host_id not in step_logs[step_id]['host_logs']:
                step_logs[step_id]['host_logs'][host_id] = {
                    'host_id': host_id,
                    'host_name': host_name or 'unknown',
                    'host_ip': host_ip,
                    'status': 'unknown',
                    'logs': '',  # 合并后的日志内容
                    'error_logs': '',  # 错误日志
                    'start_time': timestamp,
                    'end_time': timestamp,
                    'log_count': 0
                }

            host_log = step_logs[step_id]['host_logs'][host_id]

            # 更新时间范围
            if timestamp and timestamp < host_log['start_time']:
                host_log['start_time'] = timestamp
            if timestamp and timestamp > host_log['end_time']:
                host_log['end_time'] = timestamp

            # 合并日志内容
            if content.strip():  # 只添加非空内容
                formatted_log = f"[{timestamp}] {content}\n"
                if log_type in ['stderr', 'error']:
                    host_log['error_logs'] += formatted_log
                else:
                    host_log['logs'] += formatted_log

                host_log['log_count'] += 1

        # 推断步骤和主机状态
        for step_id, step_log in step_logs.items():
            step_has_failed = False
            for host_id, host_log in step_log['host_logs'].items():
                # 如果有错误日志，标记为失败
                if host_log['error_logs'].strip():
                    host_log['status'] = 'failed'
                    step_has_failed = True
                elif host_log['status'] == 'unknown':
                    # 如果有日志内容，认为执行成功
                    if host_log['logs'].strip():
                        host_log['status'] = 'success'
                    else:
                        # 没有日志内容，保持unknown状态
                        host_log['status'] = 'unknown'

            # 设置步骤状态
            step_log['status'] = 'failed' if step_has_failed else 'success'

        return step_logs

    @staticmethod
    def _update_step_host_status_from_status_data(step_logs: Dict[str, Dict[str, Any]], status_data: List[Dict[str, Any]]):
        """根据状态数据更新步骤和主机状态"""
        # 从状态数据中提取主机状态信息
        for status_entry in status_data:
            status = status_entry.get('status', '')
            step_name = status_entry.get('step_name', '')

            # 如果状态数据中包含主机信息，更新对应主机的状态
            if 'host_results' in status_entry:
                host_results = status_entry.get('host_results', {})

                # 查找对应的步骤
                target_step = None
                for step_id, step_log in step_logs.items():
                    if step_log['step_name'] == step_name or not step_name:
                        target_step = step_log
                        break

                if target_step:
                    for host_id, host_result in host_results.items():
                        if host_id in target_step['host_logs']:
                            # 根据主机执行结果推断状态
                            if host_result.get('exit_code') == 0:
                                target_step['host_logs'][host_id]['status'] = 'success'
                            else:
                                target_step['host_logs'][host_id]['status'] = 'failed'

            # 如果没有具体的主机结果，根据整体状态推断
            elif status in ['success', 'failed']:
                for step_id, step_log in step_logs.items():
                    if step_log['step_name'] == step_name or not step_name:
                        for host_id, host_log in step_log['host_logs'].items():
                            if host_log['status'] == 'unknown':
                                # 如果有错误日志，标记为失败
                                if host_log['error_logs'].strip():
                                    host_log['status'] = 'failed'
                                else:
                                    host_log['status'] = status

        # 重新计算步骤状态
        for step_id, step_log in step_logs.items():
            step_has_failed = any(
                host_log['status'] == 'failed'
                for host_log in step_log['host_logs'].values()
            )
            step_log['status'] = 'failed' if step_has_failed else 'success'

    @staticmethod
    def _update_host_status_from_status_data(host_logs: Dict[str, Dict[str, Any]], status_data: List[Dict[str, Any]]):
        """根据状态数据更新主机状态（兼容性保留）"""
        # 从状态数据中提取主机状态信息
        for status_entry in status_data:
            status = status_entry.get('status', '')

            # 如果状态数据中包含主机信息，更新对应主机的状态
            if 'host_results' in status_entry:
                host_results = status_entry.get('host_results', {})
                for host_id, host_result in host_results.items():
                    if host_id in host_logs:
                        # 根据主机执行结果推断状态
                        if host_result.get('exit_code') == 0:
                            host_logs[host_id]['status'] = 'success'
                        else:
                            host_logs[host_id]['status'] = 'failed'

            # 如果没有具体的主机结果，根据整体状态推断
            elif status in ['success', 'failed']:
                for host_id in host_logs:
                    if host_logs[host_id]['status'] == 'unknown':
                        # 如果有错误日志，标记为失败
                        if host_logs[host_id]['error_logs'].strip():
                            host_logs[host_id]['status'] = 'failed'
                        else:
                            host_logs[host_id]['status'] = status

    @staticmethod
    def _get_all_logs_from_redis(task_id: str) -> List[Dict[str, Any]]:
        """从Redis Stream获取所有日志"""
        max_retries = 5  # 增加重试次数
        for attempt in range(max_retries):
            try:
                # 确保Redis连接可用
                if not realtime_log_service._ensure_connection():
                    logger.warning(f"Redis连接不可用，尝试 {attempt + 1}/{max_retries}: task_id={task_id}")
                    if attempt < max_retries - 1:
                        import time
                        time.sleep(2)  # 等待更长时间
                        continue
                    else:
                        logger.error(f"Redis连接最终失败，无法获取日志: task_id={task_id}")
                        return []

                stream_key = f"{realtime_log_service.log_stream_prefix}{task_id}"

                # 获取所有消息
                messages = realtime_log_service.redis_client.xrange(stream_key)

                logs = []
                for msg_id, fields in messages:
                    logs.append(fields)

                logger.info(f"从Redis获取到 {len(logs)} 条日志: task_id={task_id}")
                return logs

            except Exception as e:
                logger.error(f"从Redis获取日志失败 (尝试 {attempt + 1}/{max_retries}): task_id={task_id} - {e}")
                if attempt == max_retries - 1:
                    logger.error(f"从Redis获取日志最终失败: task_id={task_id}")
                    return []
                else:
                    import time
                    time.sleep(1)  # 重试前等待
    
    @staticmethod
    def _get_all_status_from_redis(task_id: str) -> List[Dict[str, Any]]:
        """从Redis Stream获取所有状态"""
        max_retries = 5  # 增加重试次数
        for attempt in range(max_retries):
            try:
                # 确保Redis连接可用
                if not realtime_log_service._ensure_connection():
                    logger.warning(f"Redis连接不可用，尝试 {attempt + 1}/{max_retries}: task_id={task_id}")
                    if attempt < max_retries - 1:
                        import time
                        time.sleep(2)  # 等待更长时间
                        continue
                    else:
                        logger.error(f"Redis连接最终失败，无法获取状态: task_id={task_id}")
                        return []

                stream_key = f"{realtime_log_service.status_stream_prefix}{task_id}"

                # 获取所有消息
                messages = realtime_log_service.redis_client.xrange(stream_key)

                status_list = []
                for msg_id, fields in messages:
                    status_list.append(fields)

                logger.info(f"从Redis获取到 {len(status_list)} 条状态: task_id={task_id}")
                return status_list

            except Exception as e:
                logger.error(f"从Redis获取状态失败 (尝试 {attempt + 1}/{max_retries}): task_id={task_id} - {e}")
                if attempt == max_retries - 1:
                    logger.error(f"从Redis获取状态最终失败: task_id={task_id}")
                    return []
                else:
                    import time
                    time.sleep(1)  # 重试前等待
    
    @staticmethod
    def _create_step_log_summary(execution_id: int, task_id: str, step_logs: Dict[str, Dict[str, Any]], status_data: List) -> Dict[str, Any]:
        """创建步骤日志摘要"""
        # 统计步骤信息
        total_steps = len(step_logs)
        success_steps = 0
        failed_steps = 0

        # 根据主机状态推断步骤状态
        for step_log in step_logs.values():
            step_has_failed = False
            step_has_success = False

            for key, value in step_log.items():
                if key in ['duration', 'status', 'step_name', 'step_order']:
                    continue

                if isinstance(value, dict) and ('host_id' in value or 'status' in value):
                    host_status = value.get('status')
                    if host_status == 'success':
                        step_has_success = True
                    elif host_status == 'failed':
                        step_has_failed = True

            # 如果有任何主机失败，步骤就是失败的
            if step_has_failed:
                failed_steps += 1
            elif step_has_success:
                success_steps += 1

        # 统计主机信息
        all_hosts = set()
        success_hosts = set()
        failed_hosts = set()

        for step_log in step_logs.values():
            # 新格式：主机数据直接在步骤下面，不在host_logs字段中
            # 需要排除duration等非主机字段
            for key, value in step_log.items():
                if key in ['duration', 'status', 'step_name', 'step_order']:
                    continue

                # 如果value是字典且包含host_id，则认为是主机数据
                if isinstance(value, dict) and ('host_id' in value or 'status' in value):
                    host_id = key
                    host_log = value

                    all_hosts.add(host_id)
                    if host_log.get('status') == 'success':
                        success_hosts.add(host_id)
                    elif host_log.get('status') == 'failed':
                        failed_hosts.add(host_id)

        # 计算日志大小
        total_size = 0
        total_log_count = 0
        for step_log in step_logs.values():
            for key, value in step_log.items():
                if key in ['duration', 'status', 'step_name', 'step_order']:
                    continue

                if isinstance(value, dict) and ('host_id' in value or 'status' in value):
                    host_log = value
                    # 计算日志大小
                    if isinstance(host_log.get('logs'), list):
                        # 新格式：logs是数组
                        for log_entry in host_log.get('logs', []):
                            if isinstance(log_entry, dict):
                                total_size += len(log_entry.get('content', '').encode('utf-8'))
                        total_log_count += len(host_log.get('logs', []))
                    else:
                        # 旧格式：logs是字符串
                        total_size += len(host_log.get('logs', '').encode('utf-8'))
                        total_size += len(host_log.get('error_logs', '').encode('utf-8'))
                        total_log_count += host_log.get('log_count', 0)

        # 时间范围
        start_time = None
        end_time = None
        for step_log in step_logs.values():
            for host_log in step_log.get('host_logs', {}).values():
                host_start = host_log.get('start_time')
                host_end = host_log.get('end_time')
                if host_start:
                    if not start_time or host_start < start_time:
                        start_time = host_start
                if host_end:
                    if not end_time or host_end > end_time:
                        end_time = host_end

        return {
            'total_steps': total_steps,
            'success_steps': success_steps,
            'failed_steps': failed_steps,
            'total_hosts': len(all_hosts),
            'success_hosts': len(success_hosts),
            'failed_hosts': len(failed_hosts),
            'started_at': start_time,
            'finished_at': end_time
        }

    @staticmethod
    def _create_log_summary(execution_id: int, task_id: str, logs_data: List, status_data: List) -> Dict[str, Any]:
        """创建日志摘要"""
        # 统计日志信息
        total_lines = len(logs_data)
        error_lines = sum(1 for log in logs_data if log.get('log_type') in ['error', 'stderr'])
        warning_lines = sum(1 for log in logs_data if log.get('log_type') == 'warning')

        # 统计主机信息
        hosts = set()
        success_hosts = set()
        failed_hosts = set()

        for log in logs_data:
            host_id = log.get('host_id')
            if host_id:
                hosts.add(host_id)

        # 从状态数据中统计成功/失败主机
        for status in status_data:
            host_id = status.get('host_id')
            status_type = status.get('status')
            if host_id and status_type:
                if status_type == 'success':
                    success_hosts.add(host_id)
                elif status_type in ['failed', 'error']:
                    failed_hosts.add(host_id)

        # 时间范围
        start_time = None
        end_time = None
        if logs_data:
            timestamps = [datetime.fromisoformat(log.get('timestamp', '')) for log in logs_data if log.get('timestamp')]
            if timestamps:
                start_time = min(timestamps).isoformat()
                end_time = max(timestamps).isoformat()

        # 计算日志大小
        total_size = sum(len(log.get('content', '').encode('utf-8')) for log in logs_data)

        return {
            'total_lines': total_lines,
            'error_lines': error_lines,
            'warning_lines': warning_lines,
            'total_hosts': len(hosts),
            'success_hosts': len(success_hosts),
            'failed_hosts': len(failed_hosts),
            'total_size': total_size,
            'start_time': start_time,
            'end_time': end_time
        }
    
    @staticmethod
    def _cleanup_redis_streams(task_id: str):
        """清理Redis Stream（可选）"""
        try:
            log_stream_key = f"{realtime_log_service.log_stream_prefix}{task_id}"
            status_stream_key = f"{realtime_log_service.status_stream_prefix}{task_id}"
            
            # 删除Stream
            realtime_log_service.redis_client.delete(log_stream_key)
            realtime_log_service.redis_client.delete(status_stream_key)
            
            logger.info(f"清理Redis Stream完成: task_id={task_id}")
            
        except Exception as e:
            logger.error(f"清理Redis Stream失败: task_id={task_id} - {e}")
    
    @staticmethod
    def _convert_step_logs_to_logs_list(step_logs: Dict[str, Any], original_logs: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """将step_logs格式转换为logs格式，保持向后兼容"""
        logs_list = []
        
        # 按时间顺序处理原始日志
        for log_data in original_logs:
            log_entry = {
                'id': log_data.get('id', ''),
                'timestamp': log_data.get('timestamp', ''),
                'level': log_data.get('level', 'info'),
                'message': log_data.get('message', ''),
                'host': log_data.get('host', ''),
                'step': log_data.get('step', ''),
                'step_order': log_data.get('step_order', 0),
                'host_status': log_data.get('host_status', 'unknown')
            }
            logs_list.append(log_entry)
        
        # 按时间戳排序
        logs_list.sort(key=lambda x: x.get('timestamp', ''))
        
        return logs_list

    @staticmethod
    def _process_step_logs_with_timing(step_logs: Dict[str, Any]) -> Dict[str, Any]:
        """处理步骤日志，添加步骤级别的时间信息"""
        processed_step_logs = {}
        
        for step_id, step_data in step_logs.items():
            # 分离主机数据和步骤元数据
            hosts_data = {}
            step_metadata = {}

            # 计算步骤级别的时间信息
            step_start_times = []
            step_end_times = []
            step_execution_times = []

            # 遍历步骤中的所有字段，分离主机数据和元数据
            for key, value in step_data.items():
                # 步骤元数据字段
                if key in ['duration', 'status', 'step_name', 'step_order', 'started_at', 'finished_at', 'start_time', 'end_time']:
                    step_metadata[key] = value
                # 主机数据（数字键或包含host_id的字典）
                elif isinstance(value, dict) and ('host_id' in value or 'status' in value or 'logs' in value):
                    hosts_data[key] = value
                    # 收集主机时间信息
                    if value.get('start_time'):
                        step_start_times.append(value['start_time'])
                    if value.get('end_time'):
                        step_end_times.append(value['end_time'])
                    if value.get('execution_time'):
                        step_execution_times.append(value['execution_time'])

            # 计算步骤级别的时间信息
            step_start_time = min(step_start_times) if step_start_times else None
            step_end_time = max(step_end_times) if step_end_times else None
            step_duration = None

            # 计算步骤持续时间 - 使用步骤的实际时间跨度
            if step_start_time and step_end_time:
                try:
                    from datetime import datetime
                    start_dt = datetime.fromisoformat(step_start_time.replace('Z', '+00:00'))
                    end_dt = datetime.fromisoformat(step_end_time.replace('Z', '+00:00'))
                    step_duration = (end_dt - start_dt).total_seconds()
                except Exception as e:
                    logger.warning(f"计算步骤持续时间失败: {e}")
                    # 如果时间计算失败，使用最长的主机执行时间作为备选
                    if step_execution_times:
                        step_duration = max(step_execution_times)

            # 构建正确的步骤结构
            processed_step_logs[step_id] = {
                'step_name': step_id,
                'step_order': step_metadata.get('step_order', 1),
                'status': step_metadata.get('status', 'unknown'),
                'started_at': step_start_time,
                'finished_at': step_end_time,
                'duration': step_duration,
                'hosts': hosts_data  # 主机数据放在hosts字段中
            }
        
        return processed_step_logs

    @staticmethod
    def _create_summary_from_step_results(step_results, execution_record):
        """从step_results创建摘要统计"""
        if not step_results:
            return {
                'total_steps': 0,
                'success_steps': 0,
                'failed_steps': 0,
                'total_hosts': 0,
                'success_hosts': 0,
                'failed_hosts': 0
            }

        total_steps = len(step_results)
        success_steps = 0
        failed_steps = 0
        all_hosts = set()
        success_hosts = set()
        failed_hosts = set()

        for step_name, step_data in step_results.items():
            step_status = step_data.get('step_status', 'unknown')
            if step_status == 'success':
                success_steps += 1
            else:
                failed_steps += 1

            # 统计主机
            hosts = step_data.get('hosts', {})
            for host_id, host_data in hosts.items():
                all_hosts.add(host_id)
                if host_data.get('success', False):
                    success_hosts.add(host_id)
                else:
                    failed_hosts.add(host_id)

        return {
            'total_steps': total_steps,
            'success_steps': success_steps,
            'failed_steps': failed_steps,
            'total_hosts': len(all_hosts),
            'success_hosts': len(success_hosts),
            'failed_hosts': len(failed_hosts)
        }

    @staticmethod
    def _extract_logs_from_step_logs(step_logs: Dict[str, Any]) -> List[Dict[str, Any]]:
        """从步骤日志中提取所有日志"""
        all_logs = []
        
        for step_id, step_data in step_logs.items():
            host_logs = step_data.get('host_logs', {})
            
            for host_id, host_log in host_logs.items():
                # 提取主机日志
                logs_text = host_log.get('logs', '')
                error_logs_text = host_log.get('error_logs', '')
                
                # 解析日志文本
                if logs_text:
                    log_lines = logs_text.strip().split('\n')
                    for line in log_lines:
                        if line.strip():
                            all_logs.append({
                                'timestamp': LogArchiveService._extract_timestamp_from_log_line(line),
                                'level': 'info',
                                'message': line,
                                'host': host_log.get('host_name', ''),
                                'step': step_data.get('step_name', ''),
                                'step_order': step_data.get('step_order', 0)
                            })
                
                if error_logs_text:
                    error_lines = error_logs_text.strip().split('\n')
                    for line in error_lines:
                        if line.strip():
                            all_logs.append({
                                'timestamp': LogArchiveService._extract_timestamp_from_log_line(line),
                                'level': 'error',
                                'message': line,
                                'host': host_log.get('host_name', ''),
                                'step': step_data.get('step_name', ''),
                                'step_order': step_data.get('step_order', 0)
                            })
        
        # 按时间戳排序
        all_logs.sort(key=lambda x: x.get('timestamp', ''))
        return all_logs

    @staticmethod
    def _extract_timestamp_from_log_line(log_line: str) -> str:
        """从日志行中提取时间戳"""
        import re
        # 匹配 [2025-09-06T23:47:05.296020] 格式的时间戳
        timestamp_match = re.match(r'\[([^\]]+)\]', log_line)
        if timestamp_match:
            return timestamp_match.group(1)
        return ''

    @staticmethod
    def get_execution_logs(execution_id: int, page: int = 1, page_size: int = 100) -> Dict[str, Any]:
        """获取执行的历史日志"""
        try:
            from apps.executor.models import ExecutionRecord

            # 获取执行记录
            try:
                execution_record = ExecutionRecord.objects.get(execution_id=execution_id)
            except ExecutionRecord.DoesNotExist:
                return {
                    'success': False,
                    'message': '执行记录不存在'
                }

            # 从execution_results中获取日志数据
            execution_results = execution_record.execution_results or {}
            
            # 先获取日志数据
            logs_data = execution_results.get('logs', [])
            step_logs = execution_results.get('step_logs', {})
            
            # 然后移除execution_results中的日志字段，避免重复
            if 'logs' in execution_results:
                del execution_results['logs']
            if 'step_logs' in execution_results:
                del execution_results['step_logs']
            if 'log_summary' in execution_results:
                del execution_results['log_summary']

            # 如果没有日志数据，检查是否有步骤日志
            if not logs_data and not step_logs:
                # 检查是否有状态更新信息，如果有则返回基本信息
                status_updates = execution_results.get('status_updates', [])

                # 尝试从execution_results中提取日志数据作为备用方案
                # 优先使用step_results，其次使用results
                step_results_data = execution_results.get('step_results', {})
                results_data = execution_results.get('results', [])

                if step_results_data:
                    # 从step_results中构建step_logs
                    step_logs = {}
                    logs_list = []

                    for step_name, step_data in step_results_data.items():
                        step_logs[step_name] = {}
                        hosts_data = step_data.get('hosts', {})

                        for host_id, host_data in hosts_data.items():
                            host_logs = []

                            # 处理stdout
                            stdout = host_data.get('stdout', '').strip()
                            if stdout:
                                for line in stdout.split('\n'):
                                    if line.strip():
                                        log_entry = {
                                            'timestamp': execution_record.finished_at.isoformat() if execution_record.finished_at else execution_record.created_at.isoformat(),
                                            'host_id': str(host_id),
                                            'host_name': host_data.get('host_name', f'Host-{host_id}'),
                                            'host_ip': host_data.get('host_ip', ''),
                                            'log_type': 'stdout',
                                            'content': line.strip(),
                                            'step_name': step_name,
                                            'step_order': step_data.get('step_order', 1)
                                        }
                                        host_logs.append(log_entry)
                                        logs_list.append(log_entry)

                            # 处理stderr
                            stderr = host_data.get('stderr', '').strip()
                            if stderr:
                                for line in stderr.split('\n'):
                                    if line.strip():
                                        log_entry = {
                                            'timestamp': execution_record.finished_at.isoformat() if execution_record.finished_at else execution_record.created_at.isoformat(),
                                            'host_id': str(host_id),
                                            'host_name': host_data.get('host_name', f'Host-{host_id}'),
                                            'host_ip': host_data.get('host_ip', ''),
                                            'log_type': 'stderr',
                                            'content': line.strip(),
                                            'step_name': step_name,
                                            'step_order': step_data.get('step_order', 1)
                                        }
                                        host_logs.append(log_entry)
                                        logs_list.append(log_entry)

                            # 添加到step_logs
                            step_logs[step_name][str(host_id)] = {
                                'host_id': str(host_id),
                                'host_name': host_data.get('host_name', f'Host-{host_id}'),
                                'host_ip': host_data.get('host_ip', ''),
                                'status': 'success' if host_data.get('success', False) else 'failed',
                                'logs': host_logs,
                                'log_count': len(host_logs),
                                'start_time': execution_record.started_at.isoformat() if execution_record.started_at else execution_record.created_at.isoformat(),
                                'end_time': execution_record.finished_at.isoformat() if execution_record.finished_at else execution_record.created_at.isoformat(),
                                'execution_time': host_data.get('execution_time', 0)
                            }

                    # 使用从step_results构建的日志数据
                    logs_data = logs_list

                elif results_data:
                    # 从results中构建step_logs（注意：这里重新赋值外层变量）
                    step_logs = {'脚本执行': {}}
                    logs_list = []

                    for result in results_data:
                        host_id = str(result.get('host_id', 'unknown'))
                        host_name = result.get('host_name', f'Host-{host_id}')
                        host_ip = result.get('host_ip', '')

                        # 构建主机日志
                        host_logs = []

                        # 处理stdout
                        stdout = result.get('stdout', '').strip()
                        if stdout:
                            for line in stdout.split('\n'):
                                if line.strip():
                                    log_entry = {
                                        'timestamp': execution_record.finished_at.isoformat() if execution_record.finished_at else execution_record.created_at.isoformat(),
                                        'host_id': host_id,
                                        'host_name': host_name,
                                        'host_ip': host_ip,
                                        'log_type': 'stdout',
                                        'content': line.strip(),
                                        'step_name': '脚本执行',
                                        'step_order': 1
                                    }
                                    host_logs.append(log_entry)
                                    logs_list.append(log_entry)

                        # 处理stderr
                        stderr = result.get('stderr', '').strip()
                        if stderr:
                            for line in stderr.split('\n'):
                                if line.strip():
                                    log_entry = {
                                        'timestamp': execution_record.finished_at.isoformat() if execution_record.finished_at else execution_record.created_at.isoformat(),
                                        'host_id': host_id,
                                        'host_name': host_name,
                                        'host_ip': host_ip,
                                        'log_type': 'stderr',
                                        'content': line.strip(),
                                        'step_name': '脚本执行',
                                        'step_order': 1
                                    }
                                    host_logs.append(log_entry)
                                    logs_list.append(log_entry)

                        # 添加到step_logs
                        step_logs['脚本执行'][host_id] = {
                            'host_id': host_id,
                            'host_name': host_name,
                            'host_ip': host_ip,
                            'status': 'success' if result.get('success', False) else 'failed',
                            'logs': host_logs,
                            'log_count': len(host_logs),
                            'start_time': execution_record.started_at.isoformat() if execution_record.started_at else execution_record.created_at.isoformat(),
                            'end_time': execution_record.finished_at.isoformat() if execution_record.finished_at else execution_record.created_at.isoformat(),
                            'execution_time': result.get('execution_time', 0)
                        }

                    # 使用从results构建的日志数据，并继续后续处理
                    logs_data = logs_list
                    # 注意：这里的step_logs是局部变量，需要让它继续被处理

                elif status_updates:
                    # 有状态更新但没有具体日志，返回基本信息
                    return {
                        'success': True,
                        'data': {
                            'execution_id': execution_record.execution_id,
                            'name': execution_record.name,
                            'execution_type': execution_record.execution_type,
                            'status': execution_record.status,
                            'created_at': execution_record.created_at,
                            'started_at': execution_record.started_at,
                            'finished_at': execution_record.finished_at,
                            'executed_by_name': execution_record.executed_by.username if execution_record.executed_by else None,
                            'is_running': execution_record.is_running,
                            'is_completed': execution_record.is_completed,
                            'execution_results': execution_results,
                            'step_logs': {},
                            'summary': execution_results.get('log_summary', {})
                        }
                    }
                else:
                    return {
                        'success': False,
                        'message': '未找到执行日志'
                    }

            # 不再生成step_logs
            
            # 从step_results生成摘要
            step_results = execution_record.execution_results.get('step_results', {}) if execution_record.execution_results else {}
            log_summary = LogArchiveService._create_summary_from_step_results(step_results, execution_record)

            # 不再从step_logs提取日志
            all_logs = []
            
            # 如果没有从步骤日志中提取到日志，使用原始日志数据
            if not all_logs and logs_data:
                all_logs = logs_data

            # 分页处理
            total_logs = len(all_logs)
            start_index = (page - 1) * page_size
            end_index = start_index + page_size
            paginated_logs = all_logs[start_index:end_index]

            # 转换日志格式为字符串列表（前端期望的格式）
            formatted_logs = []
            for log in paginated_logs:
                # 格式化日志行 - 兼容新旧格式
                timestamp = log.get('timestamp', '')
                host_name = log.get('host', log.get('host_name', ''))
                content = log.get('message', log.get('content', ''))
                log_type = log.get('level', log.get('log_type', 'info'))
                step = log.get('step', '')

                # 构建日志行格式
                if host_name and step:
                    log_line = f"[{timestamp}] [{step}] [{host_name}] [{log_type}] {content}"
                elif host_name:
                    log_line = f"[{timestamp}] [{host_name}] [{log_type}] {content}"
                elif step:
                    log_line = f"[{timestamp}] [{step}] [{log_type}] {content}"
                else:
                    log_line = f"[{timestamp}] [{log_type}] {content}"

                formatted_logs.append(log_line)

            # 计算分页信息
            total_pages = (total_logs + page_size - 1) // page_size

            return {
                'success': True,
                'data': {
                    # 执行记录基本信息
                    'execution_id': execution_record.execution_id,
                    'name': execution_record.name,
                    'execution_type': execution_record.execution_type,
                    'status': execution_record.status,
                    'created_at': execution_record.created_at,
                    'started_at': execution_record.started_at,
                    'finished_at': execution_record.finished_at,
                    'executed_by_name': execution_record.executed_by.username if execution_record.executed_by else None,
                    'is_running': execution_record.is_running,
                    'is_completed': execution_record.is_completed,
                    # 日志相关数据
                    'execution_results': execution_results,
                    'summary': log_summary
                }
            }
            
        except Exception as e:
            logger.error(f"获取执行日志失败: execution_id={execution_id} - {e}")
            return {
                'success': False,
                'message': str(e)
            }


# 全局实例
log_archive_service = LogArchiveService()
