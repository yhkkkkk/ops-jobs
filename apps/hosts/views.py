from django.http.response import HttpResponse
from django.db.models.deletion import ProtectedError
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from django_filters.rest_framework import DjangoFilterBackend
from guardian.shortcuts import get_objects_for_user
from apps.permissions.permissions import HostManagementPermission, ServerAccountPermission

from utils.responses import SycResponse
from utils.pagination import HostPagination
from utils.audit_mixin import AuditLogMixin
from .models import Host, HostGroup, ServerAccount
from .services import HostService, HostGroupService
from .cloud_sync_service import CloudSyncService
from .serializers import (
    HostSerializer,
    HostListSerializer,
    HostGroupSerializer,
    HostGroupTreeSerializer,
    HostGroupSimpleSerializer,
    HostConnectionTestSerializer,
    HostCommandExecuteSerializer,
    HostGroupHostsSerializer,
    ServerAccountSerializer,
    CloudSyncSerializer,
    BatchMoveToGroupSerializer,
    HostExcelImportSerializer,
    HostBatchUpdateSerializer,
    HostToHostTransferSerializer,
)
from .filters import HostFilter, HostGroupFilter, ServerAccountFilter


class HostViewSet(AuditLogMixin, viewsets.ModelViewSet):
    """主机管理API"""
    queryset = Host.objects.all()
    serializer_class = HostSerializer
    permission_classes = [HostManagementPermission]

    def get_serializer_class(self):
        if self.action == 'list':
            return HostListSerializer
        return HostSerializer
    pagination_class = HostPagination
    filter_backends = [DjangoFilterBackend]
    filterset_class = HostFilter

    def get_queryset(self):
        """基于用户权限过滤查询集"""
        base_qs = Host.objects.select_related('created_by', 'agent').prefetch_related('groups')

        # 如果是超级用户，返回所有主机
        if self.request.user.is_superuser:
            return base_qs.order_by('-created_at')

        # 检查用户是否有模型级别的 view_host 权限
        # 如果有模型级别权限，返回所有主机
        if self.request.user.has_perm('hosts.view_host'):
            return base_qs.order_by('-created_at')

        # 否则，只返回有对象级别权限的主机
        queryset = get_objects_for_user(
            self.request.user,
            'view_host',
            klass=Host,
            accept_global_perms=False
        )

        return queryset.select_related('created_by', 'agent').prefetch_related('groups').order_by('-created_at')

    def list(self, request, *args, **kwargs):
        """获取主机列表"""
        queryset = self.filter_queryset(self.get_queryset())

        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            paginator = self.paginator

            # 返回统一格式的响应
            return SycResponse.success(
                content={
                    'results': serializer.data,
                    'total': paginator.page.paginator.count,
                    'page': paginator.page.number,
                    'page_size': paginator.page_size,
                },
                message="获取主机列表成功"
            )

        serializer = self.get_serializer(queryset, many=True)
        return SycResponse.success(
            content={
                'results': serializer.data,
                'total': len(serializer.data),
                'page': 1,
                'page_size': len(serializer.data),
            },
            message="获取主机列表成功"
        )

    @action(detail=False, methods=['get'])
    def tags(self, request):
        """获取可用标签列表"""
        queryset = self.get_queryset()
        tags = set()

        for tag_list in queryset.values_list('tags', flat=True):
            if not tag_list:
                continue
            if isinstance(tag_list, dict):
                for key, value in tag_list.items():
                    key = str(key or '').strip()
                    if not key:
                        continue
                    val = '' if value is None else str(value).strip()
                    tags.add(f"{key}={val}" if val else key)
                continue
            if isinstance(tag_list, (list, tuple)):
                for item in tag_list:
                    if isinstance(item, dict):
                        key = str(item.get('key', '') or '').strip()
                        if not key:
                            continue
                        val_raw = item.get('value', '')
                        val = '' if val_raw is None else str(val_raw).strip()
                        tags.add(f"{key}={val}" if val else key)
                    else:
                        text = str(item or '').strip()
                        if text:
                            tags.add(text)
                continue
            text = str(tag_list or '').strip()
            if text:
                tags.add(text)

        return SycResponse.success(
            content={'tags': sorted(tags)},
            message="获取标签列表成功"
        )

    def create(self, request, *args, **kwargs):
        """创建主机"""
        serializer = self.get_serializer(data=request.data)
        if not serializer.is_valid():
            return SycResponse.validation_error(serializer.errors)
        
        host = serializer.save(created_by=request.user)
        self.audit_log_create(host)

        # 返回统一格式的响应
        response_serializer = self.get_serializer(host)
        return SycResponse.success(
            content=response_serializer.data,
            message="主机创建成功"
        )

    def retrieve(self, request, *args, **kwargs):
        """获取主机详情"""
        instance = self.get_object()
        serializer = self.get_serializer(instance)

        # 返回统一格式的响应
        return SycResponse.success(
            content=serializer.data,
            message="获取主机详情成功"
        )

    def update(self, request, *args, **kwargs):
        """更新主机"""
        partial = kwargs.pop('partial', False)
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        if not serializer.is_valid():
            return SycResponse.validation_error(serializer.errors)
        
        host = serializer.save()
        self.audit_log_update(host)

        # 返回统一格式的响应
        response_serializer = self.get_serializer(host)
        return SycResponse.success(
            content=response_serializer.data,
            message="主机更新成功"
        )

    def destroy(self, request, *args, **kwargs):
        """删除主机"""
        instance = self.get_object()
        self.audit_log_delete(instance)
        instance.delete()

        # 返回统一格式的响应
        return SycResponse.success(
            content=None,
            message="主机删除成功"
        )

    @action(detail=True, methods=['post'])
    def test_connection(self, request, pk=None):
        """测试主机连接"""
        host = self.get_object()
        result = HostService.test_host_connection(host, request.user)

        if result['success']:
            # 只返回有用的连接信息，避免重复success和message
            content = {
                'connection_info': result.get('connection_info', {}),
                'test_time': result.get('test_time')
            }
            self.audit_log_action(
                action='test_connection',
                description=f"测试主机连接: {host.name}",
                resource_obj=host,
                extra_data={'test_time': result.get('test_time')}
            )
            return SycResponse.success(content=content, message="连接测试成功")
        else:
            # 错误情况下返回错误详情
            content = {
                'error_details': result.get('error_details', ''),
                'connection_info': result.get('connection_info', {})
            }
            self.audit_log_action(
                action='test_connection',
                description=f"测试主机连接失败: {host.name}",
                resource_obj=host,
                success=False,
                error_message=result.get('message') or result.get('error_details')
            )
            return SycResponse.error(content=content, message="连接测试失败")

    @action(detail=True, methods=['post'])
    def collect_system_info(self, request, pk=None):
        """收集主机系统信息"""
        host = self.get_object()
        result = HostService.collect_system_info(host, request.user)

        if result['success']:
            # 只返回有用的数据，避免重复success和message
            content = {
                'system_info': result.get('system_info', {}),
                'updated_fields': result.get('updated_fields', [])
            }
            self.audit_log_action(
                action='collect_system_info',
                description=f"收集主机系统信息: {host.name}",
                resource_obj=host,
                extra_data={'updated_fields': result.get('updated_fields', [])}
            )
            return SycResponse.success(content=content, message=result['message'])
        else:
            content = {
                'system_info': result.get('system_info', {})
            }
            self.audit_log_action(
                action='collect_system_info',
                description=f"收集主机系统信息失败: {host.name}",
                resource_obj=host,
                success=False,
                error_message=result.get('message')
            )
            return SycResponse.error(content=content, message=result['message'])

    @action(detail=True, methods=['post'])
    def execute_command(self, request, pk=None):
        """在主机上执行命令"""
        serializer = HostCommandExecuteSerializer(data=request.data)
        if not serializer.is_valid():
            return SycResponse.validation_error(errors=serializer.errors)

        host = self.get_object()
        command = serializer.validated_data['command']
        timeout = serializer.validated_data['timeout']

        result = HostService.execute_command_on_host(host, command, timeout, request.user)

        if result['success']:
            self.audit_log_action(
                action='execute',
                description=f"主机命令执行: {host.name}",
                resource_obj=host,
                extra_data={'command_preview': (command or '')[:200]}
            )
            return SycResponse.success(content=result, message="命令执行成功")
        else:
            self.audit_log_action(
                action='execute',
                description=f"主机命令执行失败: {host.name}",
                resource_obj=host,
                success=False,
                error_message=result.get('message') or result.get('error'),
                extra_data={'command_preview': (command or '')[:200]}
            )
            return SycResponse.error(content=result, message="命令执行失败")

    @action(detail=True, methods=['get'])
    def system_info(self, request, pk=None):
        """获取主机系统信息"""
        host = self.get_object()
        system_info = HostService.get_host_system_info(host)
        return SycResponse.success(content=system_info, message="获取系统信息成功")

    @action(detail=False, methods=['post'])
    def batch_test(self, request):
        """批量测试主机连接"""
        serializer = HostConnectionTestSerializer(data=request.data)
        if not serializer.is_valid():
            return SycResponse.validation_error(errors=serializer.errors)

        host_ids = serializer.validated_data['host_ids']
        hosts = Host.objects.filter(id__in=host_ids)
        result = HostService.batch_test_connections(list(hosts), request.user)
        self.audit_log_action(
            action='test_connection',
            description="批量测试主机连接",
            extra_data={'host_count': len(host_ids)}
        )
        return SycResponse.success(content=result, message="批量连接测试完成")

    @action(detail=False, methods=['post'], url_path='batch_update')
    def batch_update(self, request):
        """批量更新主机信息"""
        serializer = HostBatchUpdateSerializer(data=request.data)
        if not serializer.is_valid():
            return SycResponse.validation_error(errors=serializer.errors)

        host_ids = serializer.validated_data['host_ids']
        update_data = serializer.validated_data['data']

        hosts = Host.objects.filter(id__in=host_ids)
        if not hosts.exists():
            return SycResponse.error(message="未找到指定的主机", code=404)

        # 按权限过滤可编辑的主机
        user = request.user
        editable_hosts = []
        no_permission_ids = []

        for host in hosts:
            if user.is_superuser or user.has_perm('hosts.change_host', host):
                editable_hosts.append(host)
            else:
                no_permission_ids.append(host.id)

        if not editable_hosts:
            return SycResponse.error(
                message="没有可编辑的主机，缺少 hosts.change_host 权限",
                content={"no_permission_ids": no_permission_ids},
                code=403,
            )

        updated_count = 0
        for host in editable_hosts:
            update_fields = []

            for field, value in update_data.items():
                if field == 'tags':
                    # 标签替换模式：完全替换标签
                    clean_list = []
                    if isinstance(value, list):
                        for item in value:
                            if isinstance(item, str):
                                # 前端发送的是字符串列表，转换为键值对格式
                                clean_list.append({'key': item, 'value': ''})
                            elif isinstance(item, dict):
                                key = str(item.get('key', '')).strip()
                                if not key:
                                    continue
                                val = '' if item.get('value') is None else str(item.get('value')).strip()
                                clean_list.append({'key': key, 'value': val})
                    host.tags = clean_list
                    update_fields.append('tags')
                else:
                    setattr(host, field, value)
                    update_fields.append(field)
            if update_fields:
                if 'updated_at' not in update_fields:
                    update_fields.append('updated_at')
                host.save(update_fields=update_fields)
            updated_count += 1

        content = {
            "requested_count": len(host_ids),
            "updated_count": updated_count,
            "no_permission_ids": no_permission_ids,
        }
        self.audit_log_action(
            action='manage_host',
            description="批量更新主机",
            extra_data=content
        )
        return SycResponse.success(content=content, message="批量更新主机成功")

    @action(detail=False, methods=['post'])
    def sync_cloud_hosts(self, request):
        """从云厂商同步主机"""
        serializer = CloudSyncSerializer(data=request.data)
        if not serializer.is_valid():
            return SycResponse.validation_error(errors=serializer.errors)

        provider = serializer.validated_data['provider']
        region = serializer.validated_data.get('region')

        result = CloudSyncService.sync_cloud_hosts(provider, region, request.user)

        if result['success']:
            # 只返回同步统计信息，避免重复success和message
            content = {
                'synced_hosts': result.get('synced_hosts', 0),
                'updated_hosts': result.get('updated_hosts', 0),
                'total_hosts': result.get('total_hosts', 0),
                'provider': provider,
                'region': region
            }
            self.audit_log_action(
                action='sync_cloud_hosts',
                description=f"同步云主机: {provider}",
                extra_data=content
            )
            return SycResponse.success(content=content, message=result['message'])
        else:
            # 错误情况下返回基本信息
            content = {
                'provider': provider,
                'region': region
            }
            self.audit_log_action(
                action='sync_cloud_hosts',
                description=f"同步云主机失败: {provider}",
                success=False,
                error_message=result.get('message'),
                extra_data=content
            )
            return SycResponse.error(content=content, message=result['message'])

    @action(detail=False, methods=['post'])
    def batch_move_to_group(self, request):
        """批量移动主机到分组"""
        serializer = BatchMoveToGroupSerializer(data=request.data)
        if not serializer.is_valid():
            return SycResponse.validation_error(errors=serializer.errors)

        host_ids = serializer.validated_data['host_ids']
        group_id = serializer.validated_data.get('group_id')

        # 获取要移动的主机
        hosts = Host.objects.filter(id__in=host_ids)
        if not hosts.exists():
            return SycResponse.error(message="未找到指定的主机", code=404)

        target_group = None
        if group_id:
            try:
                target_group = HostGroup.objects.get(id=group_id)
            except HostGroup.DoesNotExist:
                return SycResponse.error(message="目标分组不存在", code=404)

        try:
            moved_count = 0
            for host in hosts:
                # 清除现有分组关联
                host.groups.clear()

                # 如果指定了目标分组，添加到目标分组
                if target_group:
                    host.groups.add(target_group)

                moved_count += 1

            if target_group:
                message = f"成功将 {moved_count} 台主机移动到分组 {target_group.name}"
            else:
                message = f"成功将 {moved_count} 台主机移出所有分组"

            content = {
                'moved_count': moved_count,
                'target_group_id': group_id,
                'target_group_name': target_group.name if target_group else None
            }

            self.audit_log_action(
                action='manage_host',
                description=message,
                extra_data=content
            )
            return SycResponse.success(content=content, message=message)

        except Exception as e:
            self.audit_log_action(
                action='manage_host',
                description="批量移动主机失败",
                success=False,
                error_message=str(e),
                extra_data={'target_group_id': group_id}
            )
            return SycResponse.error(message=f"批量移动失败: {str(e)}", code=500)

    @action(detail=False, methods=['post'], url_path='import_excel')
    def import_excel(self, request):
        """通过excel批量导入主机"""
        serializer = HostExcelImportSerializer(data=request.data)
        if not serializer.is_valid():
            return SycResponse.validation_error(errors=serializer.errors)

        default_group = None
        group_id = serializer.validated_data.get('default_group_id')
        if group_id:
            try:
                default_group = HostGroup.objects.get(id=group_id)
            except HostGroup.DoesNotExist:
                return SycResponse.error(message="默认分组不存在", code=404)

        result = HostService.import_hosts_from_excel(
            uploaded_file=serializer.validated_data['file'],
            user=request.user,
            default_group=default_group,
            overwrite_existing=serializer.validated_data.get('overwrite_existing', False)
        )

        if result.get('success', True):
            self.audit_log_action(
                action='manage_host',
                description="导入主机",
                extra_data={'synced_hosts': result.get('synced_hosts'), 'updated_hosts': result.get('updated_hosts')}
            )
            return SycResponse.success(content=result, message=result.get('message', '导入完成'))
        self.audit_log_action(
            action='manage_host',
            description="导入主机失败",
            success=False,
            error_message=result.get('message')
        )
        return SycResponse.error(content=result, message=result.get('message', '导入失败'))

    @action(detail=False, methods=['get'], url_path='import_excel_template')
    def download_import_template(self, request):
        """下载主机导入excel模板"""
        excel_bytes = HostService.generate_excel_template()
        response = HttpResponse(
            excel_bytes,
            content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )
        response['Content-Disposition'] = 'attachment; filename="hosts_import_template.xlsx"'
        return response

    @action(detail=True, methods=['post'])
    def upload_file(self, request, pk=None):
        """上传文件到主机"""
        return SycResponse.error(message="已禁用 SSH 文件上传，请使用 Agent 文件传输", code=400)

    @action(detail=True, methods=['post'])
    def download_file(self, request, pk=None):
        """从主机下载文件"""
        return SycResponse.error(message="已禁用 SSH 文件下载，请使用 Agent 文件传输", code=400)

    @action(detail=False, methods=['post'])
    def batch_upload(self, request):
        """批量上传文件到多个主机"""
        return SycResponse.error(message="已禁用 SSH 批量上传，请使用 Agent 文件传输", code=400)

    @action(detail=False, methods=['post'])
    def batch_download(self, request):
        """批量从多个主机下载文件"""
        return SycResponse.error(message="已禁用 SSH 批量下载，请使用 Agent 文件传输", code=400)

    @action(detail=False, methods=['post'])
    def transfer_between_hosts(self, request):
        """主机间文件传输"""
        return SycResponse.error(message="已禁用 SSH 主机间文件传输，请使用 Agent 文件传输", code=400)


class HostGroupViewSet(AuditLogMixin, viewsets.ModelViewSet):
    """主机分组管理API"""
    queryset = HostGroup.objects.select_related('created_by', 'parent').prefetch_related('children')
    serializer_class = HostGroupSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend]
    filterset_class = HostGroupFilter

    def get_queryset(self):
        return super().get_queryset().order_by('sort_order', 'name')

    def list(self, request, *args, **kwargs):
        """获取主机分组列表"""
        queryset = self.filter_queryset(self.get_queryset())

        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            paginator = self.paginator

            # 返回统一格式的响应
            return SycResponse.success(
                content={
                    'results': serializer.data,
                    'total': paginator.page.paginator.count,
                    'page': paginator.page.number,
                    'page_size': paginator.page_size,
                },
                message="获取主机分组列表成功"
            )

        serializer = self.get_serializer(queryset, many=True)
        return SycResponse.success(
            content={
                'results': serializer.data,
                'total': len(serializer.data),
                'page': 1,
                'page_size': len(serializer.data),
            },
            message="获取主机分组列表成功"
        )

    def create(self, request, *args, **kwargs):
        """创建主机分组"""
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        group = serializer.save(created_by=request.user)
        self.audit_log_create(group)

        # 返回统一格式的响应
        response_serializer = self.get_serializer(group)
        return SycResponse.success(
            content=response_serializer.data,
            message="主机分组创建成功"
        )

    def retrieve(self, request, *args, **kwargs):
        """获取主机分组详情"""
        instance = self.get_object()
        serializer = self.get_serializer(instance)

        # 返回统一格式的响应
        return SycResponse.success(
            content=serializer.data,
            message="获取主机分组详情成功"
        )

    def update(self, request, *args, **kwargs):
        """更新主机分组"""
        partial = kwargs.pop('partial', False)
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        group = serializer.save()
        self.audit_log_update(group)

        # 返回统一格式的响应
        response_serializer = self.get_serializer(group)
        return SycResponse.success(
            content=response_serializer.data,
            message="主机分组更新成功"
        )

    def destroy(self, request, *args, **kwargs):
        """删除主机分组"""
        instance = self.get_object()
        self.audit_log_delete(instance)
        instance.delete()

        # 返回统一格式的响应
        return SycResponse.success(
            content=None,
            message="主机分组删除成功"
        )

    @action(detail=False, methods=['get'])
    def tree(self, request):
        """获取主机分组树形结构"""
        # 只获取根节点（没有父分组的分组）
        root_groups = self.get_queryset().filter(parent=None)
        serializer = HostGroupTreeSerializer(root_groups, many=True)

        return SycResponse.success(
            content=serializer.data,
            message="获取主机分组树形结构成功"
        )

    @action(detail=False, methods=['get'])
    def simple_list(self, request):
        """获取主机分组简单列表（用于下拉选择）"""
        # 按层级和排序字段排序，确保父分组在子分组前面
        queryset = self.get_queryset().order_by('parent__id', 'sort_order', 'name')
        serializer = HostGroupSimpleSerializer(queryset, many=True)

        return SycResponse.success(
            content=serializer.data,
            message="获取主机分组简单列表成功"
        )

    @action(detail=True, methods=['post'])
    def move(self, request, pk=None):
        """移动分组到新的父分组"""
        group = self.get_object()
        new_parent_id = request.data.get('parent_id')
        new_sort_order = request.data.get('sort_order', 0)

        # 验证新父分组
        new_parent = None
        if new_parent_id:
            try:
                new_parent = HostGroup.objects.get(id=new_parent_id)
            except HostGroup.DoesNotExist:
                return SycResponse.error(message="目标父分组不存在", code=404)

        # 检查是否可以移动
        if not group.can_move_to(new_parent):
            return SycResponse.error(message="不能移动到自己或自己的子分组", code=400)

        # 执行移动
        group.parent = new_parent
        group.sort_order = new_sort_order
        group.save()

        self.audit_log_action(
            action='manage_host',
            description=f"移动主机分组: {group.name}",
            resource_obj=group,
            extra_data={'parent_id': new_parent_id, 'sort_order': new_sort_order}
        )

        # 返回更新后的分组信息
        serializer = self.get_serializer(group)
        return SycResponse.success(
            content=serializer.data,
            message="分组移动成功"
        )

    @action(detail=True, methods=['post'])
    def add_hosts(self, request, pk=None):
        """添加主机到分组"""
        serializer = HostGroupHostsSerializer(data=request.data)
        if not serializer.is_valid():
            return SycResponse.validation_error(errors=serializer.errors)

        group = self.get_object()
        host_ids = serializer.validated_data['host_ids']
        hosts = Host.objects.filter(id__in=host_ids)

        HostGroupService.add_hosts_to_group(group, list(hosts), request.user)
        self.audit_log_action(
            action='manage_host',
            description=f"主机添加到分组: {group.name}",
            resource_obj=group,
            extra_data={'host_ids': host_ids}
        )
        return SycResponse.success(message="主机添加成功")

    @action(detail=True, methods=['post'])
    def remove_hosts(self, request, pk=None):
        """从分组移除主机"""
        serializer = HostGroupHostsSerializer(data=request.data)
        if not serializer.is_valid():
            return SycResponse.validation_error(errors=serializer.errors)

        group = self.get_object()
        host_ids = serializer.validated_data['host_ids']
        hosts = Host.objects.filter(id__in=host_ids)

        HostGroupService.remove_hosts_from_group(group, list(hosts), request.user)
        self.audit_log_action(
            action='manage_host',
            description=f"主机从分组移除: {group.name}",
            resource_obj=group,
            extra_data={'host_ids': host_ids}
        )
        return SycResponse.success(message="主机移除成功")

    @action(detail=True, methods=['get'])
    def hosts_status(self, request, pk=None):
        """获取分组主机状态统计"""
        group = self.get_object()
        status_info = HostGroupService.get_group_hosts_status(group)
        return SycResponse.success(content=status_info, message="获取分组状态成功")

    @action(detail=True, methods=['post'])
    def batch_test(self, request, pk=None):
        """批量测试分组内主机连接"""
        group = self.get_object()
        result = HostGroupService.batch_test_group_connections(group, request.user)
        return SycResponse.success(content=result, message="批量连接测试完成")


class ServerAccountViewSet(AuditLogMixin, viewsets.ModelViewSet):
    """服务器账号管理API"""
    queryset = ServerAccount.objects.all()
    serializer_class = ServerAccountSerializer
    permission_classes = [ServerAccountPermission]
    filter_backends = [DjangoFilterBackend]
    filterset_class = ServerAccountFilter

    def get_queryset(self):
        return super().get_queryset().order_by('-id')

    def list(self, request, *args, **kwargs):
        """获取账号列表"""
        queryset = self.filter_queryset(self.get_queryset())

        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            paginator = self.paginator

            return SycResponse.success(
                content={
                    'results': serializer.data,
                    'total': paginator.page.paginator.count,
                    'page': paginator.page.number,
                    'page_size': paginator.page_size,
                },
                message="获取账号列表成功"
            )

        serializer = self.get_serializer(queryset, many=True)
        return SycResponse.success(
            content={
                'results': serializer.data,
                'total': len(serializer.data),
                'page': 1,
                'page_size': len(serializer.data),
            },
            message="获取账号列表成功"
        )

    def create(self, request, *args, **kwargs):
        """创建账号"""
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        account = serializer.save()
        self.audit_log_create(account)

        response_serializer = self.get_serializer(account)
        return SycResponse.success(
            content=response_serializer.data,
            message="账号创建成功"
        )

    def update(self, request, *args, **kwargs):
        """更新账号"""
        partial = kwargs.pop('partial', False)
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        account = serializer.save()
        self.audit_log_update(account)

        response_serializer = self.get_serializer(account)
        return SycResponse.success(
            content=response_serializer.data,
            message="账号更新成功"
        )

    def retrieve(self, request, *args, **kwargs):
        """获取账号详情"""
        instance = self.get_object()
        serializer = self.get_serializer(instance)

        # 返回统一格式的响应
        return SycResponse.success(
            content=serializer.data,
            message="获取账号详情成功"
        )

    def destroy(self, request, *args, **kwargs):
        """删除账号"""
        instance = self.get_object()

        try:
            self.audit_log_delete(instance)
            instance.delete()
        except ProtectedError as e:
            # 获取被保护的外键引用信息
            protected_objects = e.protected_objects
            host_names = [str(host) for host in protected_objects]

            return SycResponse.error(
                message=f"该账号正在被以下主机使用，无法删除：{', '.join(host_names)}",
                code=400
            )

        # 返回统一格式的响应
        return SycResponse.success(
            content=None,
            message="账号删除成功"
        )
