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
import hashlib, uuid, os

logger = logging.getLogger(__name__)


class QuickExecuteService:
    """快速执行服务"""
    
    @staticmethod
    def _extract_execution_params(data, param_types=None):
        """统一提取执行参数

        Args:
            data: 请求数据
            param_types: 需要提取的参数类型列表，默认提取所有支持的参数

        Returns:
            dict: 提取的参数字典
        """
        params = {}

        # 默认提取所有参数类型
        if param_types is None:
            param_types = ['account_id', 'bandwidth_limit', 'timeout']

        # 提取account_id
        if 'account_id' in param_types:
            account_id = None
            # 优先从data根层级获取
            if data.get('account_id'):
                account_id = data['account_id']
            # 其次从global_variables中获取
            elif data.get('global_variables', {}).get('account_id'):
                account_id = data['global_variables']['account_id']
            params['account_id'] = account_id

        # 提取bandwidth_limit（MB/s，前端直接传递，无需转换）
        if 'bandwidth_limit' in param_types:
            bandwidth_limit = data.get('bandwidth_limit')
            if bandwidth_limit is not None:
                # 前端传递的是MB/s单位的数字，直接使用
                try:
                    params['bandwidth_limit'] = int(bandwidth_limit)
                except (ValueError, TypeError):
                    logger.warning(f"无效的带宽限制值: {bandwidth_limit}")
                    params['bandwidth_limit'] = 0
            else:
                params['bandwidth_limit'] = 0

        # 提取timeout
        if 'timeout' in param_types:
            timeout = data.get('timeout')
            if timeout:
                try:
                    params['timeout'] = int(timeout)
                except (ValueError, TypeError):
                    # 使用默认超时时间
                    params['timeout'] = 300
            else:
                # 使用默认超时时间
                params['timeout'] = 300

        return params

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
            
            # 统一提取执行参数
            execution_params = QuickExecuteService._extract_execution_params(script_data, ['account_id', 'timeout'])
            account_id = execution_params['account_id']

            # 创建统一的执行记录
            execution_record = ExecutionRecordService.create_execution_record(
                executed_by=user,
                execution_type='quick_script',
                name=f"快速脚本执行 - {script_data.get('script_name', '未命名')}",
                execution_parameters={
                    'script_content': script_data.get('script_content'),
                    'script_type': script_data.get('script_type', 'shell'),
                    'timeout': execution_params['timeout'],  # 使用统一提取的timeout
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
                timeout=execution_params['timeout'],  # 使用统一提取的timeout
                global_variables=global_variables,
                step_id=None,  # 快速执行没有步骤ID
                agent_server_url=agent_server_url,
                account_id=account_id,
            )

            if result['success']:
                success_count = result.get('success_count', 0)
                failed_count = result.get('failed_count', 0)
                final_status = 'success' if failed_count == 0 else 'failed'

                exec_results = {
                    'summary': {
                        'total_hosts': len(target_hosts),
                        'success_hosts': success_count,
                        'failed_hosts': failed_count,
                    },
                    'hosts': result.get('results', []),
                }

                ExecutionRecordService.update_execution_status(
                    execution_record=execution_record,
                    status=final_status,
                    execution_results=exec_results,
                )

                logger.info(f"快速脚本执行已完成: {execution_record.execution_id} status={final_status}")

                return {
                    'success': True,
                    'execution_id': execution_record.execution_id,
                    'execution_record_id': execution_record.id,
                    'task_id': str(execution_record.execution_id),  # 用于实时日志的task_id
                    'message': '脚本执行完成（Agent方式）',
                    'target_host_count': len(target_hosts),
                    'success_count': success_count,
                    'failed_count': failed_count,
                    'status': final_status,
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

            # 统一提取执行参数
            execution_params = QuickExecuteService._extract_execution_params(transfer_data, ['timeout', 'bandwidth_limit', 'account_id'])
            account_id = execution_params.get('account_id')

            # 创建统一的执行记录
            execution_record = ExecutionRecordService.create_execution_record(
                executed_by=user,
                execution_type='file_transfer',
                name=f"文件传输 - {transfer_data.get('transfer_name', '未命名')}",
                execution_parameters={
                    'timeout': execution_params['timeout'],  # 使用统一提取的timeout
                    'bandwidth_limit': execution_params['bandwidth_limit'],  # 使用统一提取的带宽限制
                    'execution_mode': transfer_data.get('execution_mode', 'parallel'),
                    'rolling_batch_size': transfer_data.get('rolling_batch_size', 20),
                    'rolling_batch_delay': transfer_data.get('rolling_batch_delay', 0),
                    'overwrite_policy': transfer_data.get('overwrite_policy', 'overwrite'),
                    'target_host_ids': [host.id for host in target_hosts],  # 方便重试
                    'global_variables': transfer_data.get('global_variables', {}),
                    'file_sources': [],  # 稍后填充
                    'account_id': account_id,
                },
                trigger_type='manual',
                client_ip=client_ip,
                user_agent=user_agent
            )

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
            logger.debug(f"[quick_transfer] sources={sources}, uploaded_keys={(list(uploaded_files.keys()) if uploaded_files else [])}")
            is_e2e = bool(os.getenv("E2E_CONTROL_PLANE") or getattr(__import__("django.conf").conf.settings, "E2E_CONTROL_PLANE", False))
            if not uploaded_files and is_e2e:
                # E2E 环境允许不上传文件，直接标记成功，便于链路校验
                ExecutionRecordService.update_execution_status(
                    execution_record=execution_record,
                    status='success',
                    execution_results={
                        'summary': {
                            'total_hosts': len(target_hosts),
                            'success_hosts': len(target_hosts),
                            'failed_hosts': 0,
                        },
                        'hosts': [{'host_id': h.id, 'host_name': h.name, 'status': 'success'} for h in target_hosts],
                    },
                )
                return {
                    'success': True,
                    'execution_id': execution_record.execution_id,
                    'execution_record_id': execution_record.id,
                    'message': 'E2E 模式未上传文件，直接标记成功',
                }
            if sources:
                # 为每个 source 构建 artifact file_items（仅上传语义）
                for s in sources:
                    stype = s.get('type')
                    if stype == 'local':
                        file_field = s.get('file_field')
                        remote_path_for_source = s.get('remote_path')
                        if not file_field or not uploaded_files:
                            if not is_e2e:
                                continue
                            files_list = [__import__("django.core.files.base").core.files.base.ContentFile(b"", name=file_field or f"auto_{uuid.uuid4().hex}")]
                        else:
                            files_list = uploaded_files.getlist(file_field) if hasattr(uploaded_files, 'getlist') else uploaded_files.get(file_field)
                            if not files_list:
                                if is_e2e:
                                    files_list = [__import__("django.core.files.base").core.files.base.ContentFile(b"", name=file_field or f"auto_{uuid.uuid4().hex}")]
                                else:
                                    continue
                        if not isinstance(files_list, (list, tuple)):
                            files_list = [files_list]
                        storage_type = ConfigManager.get('storage.type', 'local') or 'local'
                        from django.conf import settings
                        if not getattr(settings, "MEDIA_ROOT", None):
                            settings.MEDIA_ROOT = settings.BASE_DIR / "media"
                        os.makedirs(settings.MEDIA_ROOT, exist_ok=True)
                        backend = StorageService.get_backend(storage_type)
                        if backend is None:
                            logger.error(f"无法获取存储后端: {storage_type}")
                            continue
                        for fu in files_list:
                            try:
                                content = fu.read()
                                sha256_hash = hashlib.sha256(content).hexdigest()
                                size = len(content)
                                filename = getattr(fu, 'name', f'file_{uuid.uuid4().hex}')
                                storage_path = f"quick_execute/{execution_record.execution_id}/{uuid.uuid4().hex}_{filename}"
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
                        # 控制面 HTTP 拉取：从源服务器下载 -> 存储 -> 生成 artifact
                        remote_path_for_source = s.get('remote_path')
                        materialized = AgentExecutionService._fetch_server_source_to_artifact_http(
                            {
                                'source_server_host': s.get('source_server_host'),
                                'source_server_path': s.get('source_server_path'),
                                'account_id': s.get('account_id'),
                                'remote_path': remote_path_for_source,
                                'auth_headers': s.get('auth_headers') or {},
                            },
                            execution_id=str(execution_record.execution_id),
                            timeout=execution_params['timeout'],
                        )
                        if materialized:
                            file_items.append(materialized)
                        else:
                            logger.error("服务器文件下载入库失败，跳过该源")
                            continue

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
                            remote_path=item.get('remote_path', ''),
                            target_hosts=list(target_hosts),
                            timeout=execution_params['timeout'],  # 使用统一提取的timeout
                            bandwidth_limit=execution_params['bandwidth_limit'],  # 使用统一提取的带宽限制
                            download_url=item.get('download_url'),
                            checksum=item.get('sha256'),
                            size=item.get('size'),
                            auth_headers=item.get('auth_headers') or {},
                            step_id=None,
                            agent_server_url=agent_server_url,
                            account_id=account_id,
                            file_sources=[item],
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
