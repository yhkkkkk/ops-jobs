"""
快速执行服务层
"""
import logging
from django.db.models import Q
from django.utils import timezone
from apps.hosts.models import Host, HostGroup
from apps.agents.execution_service import AgentExecutionService
from apps.executor.services import ExecutionRecordService
from apps.agents.storage_service import StorageService
from apps.system_config.models import ConfigManager
import hashlib, uuid

logger = logging.getLogger(__name__)


class QuickExecuteService:
    """快速执行服务"""
    
    @staticmethod
    def execute_script(user, script_data, client_ip=None, user_agent=None):
        """快速执行脚本"""
        try:
            # 获取目标主机
            target_hosts = QuickExecuteService._get_target_hosts_from_data(script_data)

            if not target_hosts:
                return {
                    'success': False,
                    'message': '没有找到目标主机'
                }

            # 构建主机信息列表
            host_info_list = [
                {
                    'id': host.id,
                    'name': host.name,
                    'ip_address': host.ip_address
                }
                for host in target_hosts
            ]

            # 获取全局变量和位置参数
            global_variables = script_data.get('global_variables', {})
            positional_args = script_data.get('positional_args', [])
            
            # 从global_variables中提取account_id（前端传递的）
            account_id = global_variables.get('account_id') if global_variables else None

            # 创建统一的执行记录
            execution_record = ExecutionRecordService.create_execution_record(
                executed_by=user,
                execution_type='quick_script',
                name=f"快速脚本执行 - {script_data.get('script_name', '未命名')}",
                execution_parameters={
                    'script_content': script_data.get('script_content'),
                    'script_type': script_data.get('script_type', 'shell'),
                    'timeout': script_data.get('timeout'),
                    'execution_mode': script_data.get('execution_mode', 'parallel'),
                    'rolling_strategy': script_data.get('rolling_strategy', 'fail_pause'),
                    'rolling_batch_size': script_data.get('rolling_batch_size', 20),
                    'rolling_batch_delay': script_data.get('rolling_batch_delay', 0),
                    'global_variables': global_variables,
                    'positional_args': positional_args,
                    'account_id': account_id,  # 保存account_id到执行参数中
                    'target_host_ids': [host.id for host in target_hosts],
                },
                trigger_type='manual',
                client_ip=client_ip,
                user_agent=user_agent
            )

            # 如果没有指定超时时间，使用系统配置的默认值
            if not script_data.get('timeout'):
                from apps.system_config.models import ConfigManager
                script_data['timeout'] = ConfigManager.get('task.job_timeout', 300)

            # 只支持Agent方式执行
            agent_server_url = script_data.get('agent_server_url')

            # 更新执行参数，添加执行方式标识
            execution_record.execution_parameters.update({
                'execution_mode': 'agent',
                'agent_server_url': agent_server_url,
            })
            execution_record.save()

            # 通过Agent执行脚本
            result = AgentExecutionService.execute_script_via_agent(
                execution_record=execution_record,
                    script_content=script_data.get('script_content'),
                script_type=script_data.get('script_type', 'shell'),
                target_hosts=target_hosts,
                    timeout=script_data['timeout'],
                    global_variables=global_variables,
                step_id=None,  # 快速执行没有步骤ID
                agent_server_url=agent_server_url,
            )

            if result['success']:
                # 更新执行记录状态
                ExecutionRecordService.update_execution_status(
                    execution_record=execution_record,
                    status='running',
                )

                logger.info(f"快速脚本执行已启动: {execution_record.execution_id}")

                return {
                    'success': True,
                    'execution_id': execution_record.execution_id,
                    'execution_record_id': execution_record.id,
                        'task_id': str(execution_record.execution_id),  # 用于实时日志的task_id
                        'message': '脚本执行已启动（Agent方式）',
                        'target_host_count': len(target_hosts),
                        'success_count': result.get('success_count', 0),
                        'failed_count': result.get('failed_count', 0)
                    }
            else:
                # 执行失败
                ExecutionRecordService.update_execution_status(
                    execution_record=execution_record,
                    status='failed',
                    error_message=result.get('error', '脚本执行启动失败')
                )

                return {
                    'success': False,
                    'error': result.get('error', '脚本执行启动失败')
            }

        except Exception as e:
            logger.error(f"快速脚本执行启动失败: {e}")
            return {
                'success': False,
                'message': f'启动失败: {str(e)}'
            }
    
    @staticmethod
    def transfer_file(user, transfer_data, client_ip=None, user_agent=None):
        """快速文件传输"""
        try:
            # 获取目标主机 - 使用统一的_get_target_hosts_from_data方法
            target_hosts = QuickExecuteService._get_target_hosts_from_data(transfer_data)
            
            if not target_hosts:
                return {
                    'success': False,
                    'message': '没有找到目标主机'
                }

            # 构建主机信息列表
            host_info_list = [
                {
                    'id': host.id,
                    'name': host.name,
                    'ip_address': host.ip_address
                }
                for host in target_hosts
            ]

            # 创建统一的执行记录
            execution_record = ExecutionRecordService.create_execution_record(
                executed_by=user,
                execution_type='file_transfer',
                name=f"文件传输 - {transfer_data.get('transfer_name', '未命名')}",
                execution_parameters={
                    'transfer_type': transfer_data.get('transfer_type'),
                    'local_path': transfer_data.get('local_path'),
                    'remote_path': transfer_data.get('remote_path'),
                    'source_server_host': transfer_data.get('source_server_host'),
                    'source_server_path': transfer_data.get('source_server_path'),
                    'timeout': transfer_data.get('timeout'),
                    'execution_mode': transfer_data.get('execution_mode', 'parallel'),
                    'rolling_batch_size': transfer_data.get('rolling_batch_size', 20),
                    'rolling_batch_delay': transfer_data.get('rolling_batch_delay', 0),
                    'overwrite_policy': transfer_data.get('overwrite_policy', 'overwrite'),
                    'target_host_ids': [host.id for host in target_hosts],
                    'global_variables': transfer_data.get('global_variables', {}),
                },
                trigger_type='manual',
                client_ip=client_ip,
                user_agent=user_agent
            )

            # 如果没有指定超时时间，使用系统配置的默认值
            if not transfer_data.get('timeout'):
                from apps.system_config.models import ConfigManager
                transfer_data['timeout'] = ConfigManager.get('task.job_timeout', 300)

            # 只支持Agent方式执行
            agent_server_url = transfer_data.get('agent_server_url')

            # 更新执行参数，添加执行方式标识
            execution_record.execution_parameters.update({
                'execution_mode': 'agent',
                'agent_server_url': agent_server_url,
            })
            execution_record.save()

            # 处理上传的多个 sources（必须存在，且不兼容旧字段）
            file_items = []
            sources = transfer_data.get('sources') or []
            uploaded_files = transfer_data.get('uploaded_files')  # request.FILES
            if sources:
                # 为每个 source 构建 file_items（local 或 server）
                for s in sources:
                    stype = s.get('type')
                    if stype == 'local':
                        # local: upload uploaded_files[file_field] into storage backend, generate download_url + checksum
                        file_field = s.get('file_field')
                        remote_path_for_source = s.get('remote_path') or transfer_data.get('remote_path')
                        if not file_field:
                            continue
                        if not uploaded_files:
                            continue
                        files_list = uploaded_files.getlist(file_field) if hasattr(uploaded_files, 'getlist') else uploaded_files.get(file_field)
                        if not files_list:
                            continue
                        if not isinstance(files_list, (list, tuple)):
                            files_list = [files_list]
                        # choose storage backend from system config
                        storage_type = ConfigManager.get('storage.type', 'local')
                        backend = StorageService.get_backend(storage_type)
                        if backend is None:
                            logger.error(f"无法获取存储后端: {storage_type}")
                            continue
                        for fu in files_list:
                            try:
                                # compute sha256
                                content = fu.read()
                                sha256_hash = hashlib.sha256(content).hexdigest()
                                size = len(content)
                                # generate storage path
                                filename = getattr(fu, 'name', f'file_{uuid.uuid4().hex}')
                                storage_path = f"quick_execute/{execution_record.execution_id}/{uuid.uuid4().hex}_{filename}"
                                # seek back if possible by writing to temp file-like for backend; use UploadedFile interface: create BytesIO
                                from django.core.files.uploadedfile import InMemoryUploadedFile, TemporaryUploadedFile
                                # create a new InMemoryUploadedFile-like wrapper if needed
                                try:
                                    fu.seek(0)
                                except Exception:
                                    pass
                                success, err_msg = backend.upload_file(fu, storage_path)
                                if not success:
                                    logger.error(f"上传到存储失败: {err_msg}")
                                    continue
                                download_url = backend.generate_url(storage_path, expires_in=3600)
                                file_items.append({
                                    'type': 'artifact',
                                    'storage_path': storage_path,
                                    'download_url': download_url,
                                    'sha256': sha256_hash,
                                    'size': size,
                                    'filename': filename,
                                    'remote_path': remote_path_for_source,
                                    'auth_headers': {},
                                })
                            except Exception as e:
                                logger.exception(f"处理上传文件失败: {e}")
                                continue
                    elif stype == 'server':
                        # server: require storage_path or download_url (artifact must be prepared front-end or other process)
                        remote_path_for_source = s.get('remote_path') or transfer_data.get('remote_path')
                        storage_path = s.get('storage_path')
                        download_url = s.get('download_url')
                        if storage_path and not download_url:
                            storage_type = ConfigManager.get('storage.type', 'local')
                            backend = StorageService.get_backend(storage_type)
                            download_url = backend.generate_url(storage_path, expires_in=3600) if backend else None
                        if not download_url:
                            logger.error("server source missing download_url/storage_path, skipping")
                            continue
                        file_items.append({
                            'type': 'artifact',
                            'storage_path': storage_path,
                            'download_url': download_url,
                            'sha256': s.get('sha256'),
                            'size': s.get('size'),
                            'filename': s.get('filename'),
                            'remote_path': remote_path_for_source,
                            'auth_headers': {},
                        })
            else:
                # 兼容旧逻辑：单文件从本地路径读取（用于 backward compatibility）
                if transfer_data.get('transfer_type') in ('local_upload', 'upload'):
                    local_path = transfer_data.get('local_path', '')
                    if local_path:
                        try:
                            with open(local_path, 'rb') as f:
                                content = f.read()
                            file_items.append({
                                'type': 'local',
                                'filename': local_path.split('/')[-1],
                                'content': content,
                                'remote_path': transfer_data.get('remote_path'),
                            })
                        except Exception as e:
                            logger.error(f"读取文件失败: {str(e)}")
                            ExecutionRecordService.update_execution_status(
                                execution_record=execution_record,
                                status='failed',
                                error_message=f'读取文件失败: {str(e)}'
                            )
                            return {
                                'success': False,
                                'message': f'读取文件失败: {str(e)}'
                            }

            # 通过Agent执行文件传输
            # 如果有多个 file_items，则逐个创建任务（每个 file_item 会在每台主机上创建一个任务）
            if file_items:
                # 把 file_items 写入 execution_parameters，便于审计/重试
                execution_record.execution_parameters.update({
                    'file_sources': file_items
                })
                execution_record.save()

                overall_results = {'success': True, 'success_count': 0, 'failed_count': 0, 'results': []}
                for item in file_items:
                    # artifact: use download_url + checksum + size; Agent will download from URL
                    if item.get('type') == 'artifact':
                        res = AgentExecutionService.execute_file_transfer_via_agent(
                            execution_record=execution_record,
                            transfer_type=transfer_data.get('transfer_type', 'upload'),
                            local_path=item.get('filename') or '',
                            remote_path=item.get('remote_path') or transfer_data.get('remote_path', ''),
                            target_hosts=list(target_hosts),
                            file_content=None,
                            timeout=transfer_data.get('timeout', 300),
                            bandwidth_limit=transfer_data.get('bandwidth_limit', 0),
                            download_url=item.get('download_url'),
                            checksum=item.get('sha256'),
                            size=item.get('size'),
                            auth_headers=item.get('auth_headers') or {},
                            step_id=None,
                            agent_server_url=agent_server_url,
                        )
                    else:
                        # unknown type: skip
                        logger.warning(f"未知的 file_item 类型: {item.get('type')}, 跳过")
                        continue
                    # aggregate results
                    overall_results['success_count'] += res.get('success_count', 0)
                    overall_results['failed_count'] += res.get('failed_count', 0)
                    overall_results['results'].extend(res.get('results', []))

                result = {
                    'success': overall_results['success_count'] > 0,
                    'success_count': overall_results['success_count'],
                    'failed_count': overall_results['failed_count'],
                    'results': overall_results['results'],
                }
            else:
                # 不再兼容旧字段，必须通过 sources 上传/描述文件
                ExecutionRecordService.update_execution_status(
                    execution_record=execution_record,
                    status='failed',
                    error_message='file_sources required for file transfer'
                )
                return {
                    'success': False,
                    'error': 'file_sources required for file transfer'
                }

            if result['success']:
                # 更新执行记录状态
                ExecutionRecordService.update_execution_status(
                    execution_record=execution_record,
                    status='running',
                )

                logger.info(f"快速文件传输已启动: {execution_record.execution_id}")

                return {
                    'success': True,
                    'execution_id': execution_record.execution_id,
                    'execution_record_id': execution_record.id,
                    'task_id': str(execution_record.execution_id),  # 用于实时日志的task_id
                    'message': '文件传输已启动（Agent方式）',
                    'target_host_count': len(target_hosts),
                    'success_count': result.get('success_count', 0),
                    'failed_count': result.get('failed_count', 0)
                }
            else:
                # 执行失败
                ExecutionRecordService.update_execution_status(
                    execution_record=execution_record,
                    status='failed',
                    error_message=result.get('error', '文件传输启动失败')
                )

                return {
                    'success': False,
                    'error': result.get('error', '文件传输启动失败')
                }

            # 从transfer_data中提取account_id（如果前端传递了）
            account_id = transfer_data.get('account_id')
            
        except Exception as e:
            logger.error(f"快速文件传输启动失败: {e}")
            return {
                'success': False,
                'message': f'启动失败: {str(e)}'
            }
    
    @staticmethod
    def _get_target_hosts_from_data(script_data):
        """从脚本数据中获取目标主机列表，支持target_host_ids（静态）和target_group_ids（动态）两种格式"""
        target_hosts = []
        existing_host_ids = set()
        
        # 1. 处理静态选择：直接指定的主机ID
        target_host_ids = script_data.get('target_host_ids', []) or []
        if target_host_ids:
            try:
                static_hosts = Host.objects.filter(id__in=target_host_ids)
                for host in static_hosts:
                    if host.id not in existing_host_ids:
                        target_hosts.append(host)
                        existing_host_ids.add(host.id)
            except Exception as e:
                logger.error(f"获取静态主机列表失败: {e}")
        
        # 2. 处理动态选择：分组ID，执行时动态获取分组内的所有主机
        target_group_ids = script_data.get('target_group_ids', []) or []
        if target_group_ids:
            try:
                from apps.hosts.models import HostGroup
                # 获取分组对象
                groups = HostGroup.objects.filter(id__in=target_group_ids)
                
                # 遍历每个分组，获取分组内的所有主机（动态获取，包括执行时新增的主机）
                for group in groups:
                    # 使用ManyToMany关系的host_set获取分组内的所有主机
                    group_hosts = group.host_set.all()
                    for host in group_hosts:
                        if host.id not in existing_host_ids:
                            target_hosts.append(host)
                            existing_host_ids.add(host.id)
                    
                    logger.info(f"动态选择分组 '{group.name}' (ID: {group.id})，获取到 {group_hosts.count()} 台主机")
                
            except Exception as e:
                logger.error(f"处理动态分组列表失败: {e}")
        
        return target_hosts
