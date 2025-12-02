from django.http.response import HttpResponse
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from django_filters.rest_framework import DjangoFilterBackend
from guardian.shortcuts import get_objects_for_user
from apps.permissions.permissions import HostManagementPermission, ServerAccountPermission

from utils.responses import SycResponse
from utils.pagination import HostPagination
from .models import Host, HostGroup, ServerAccount
from .services import HostService, HostGroupService
from .cloud_sync_service import CloudSyncService
from .serializers import (
    HostSerializer,
    HostGroupSerializer,
    HostGroupTreeSerializer,
    HostGroupSimpleSerializer,
    HostConnectionTestSerializer,
    HostCommandExecuteSerializer,
    HostGroupHostsSerializer,
    ServerAccountSerializer,
    CloudSyncSerializer,
    BatchMoveToGroupSerializer,
    HostExcelImportSerializer
)
from .filters import HostFilter, HostGroupFilter, ServerAccountFilter


class HostViewSet(viewsets.ModelViewSet):
    """主机管理API"""
    queryset = Host.objects.select_related('created_by').prefetch_related('groups')
    serializer_class = HostSerializer
    permission_classes = [HostManagementPermission]
    pagination_class = HostPagination
    filter_backends = [DjangoFilterBackend]
    filterset_class = HostFilter

    def get_queryset(self):
        """基于用户权限过滤查询集"""
        queryset = super().get_queryset()

        # 如果是超级用户，返回所有主机
        if self.request.user.is_superuser:
            return queryset
        else:
            # 其他用户只能看到有权限的主机
            queryset = get_objects_for_user(
                self.request.user,
                'view_host',
                klass=Host,
                accept_global_perms=False
            )

        return queryset.select_related('created_by').prefetch_related('groups').order_by('-created_at')

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

    def create(self, request, *args, **kwargs):
        """创建主机"""
        serializer = self.get_serializer(data=request.data)
        if not serializer.is_valid():
            return SycResponse.validation_error(serializer.errors)
        
        host = serializer.save(created_by=request.user)

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

        # 返回统一格式的响应
        response_serializer = self.get_serializer(host)
        return SycResponse.success(
            content=response_serializer.data,
            message="主机更新成功"
        )

    def destroy(self, request, *args, **kwargs):
        """删除主机"""
        instance = self.get_object()
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
            return SycResponse.success(content=content, message="连接测试成功")
        else:
            # 错误情况下返回错误详情
            content = {
                'error_details': result.get('error_details', ''),
                'connection_info': result.get('connection_info', {})
            }
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
            return SycResponse.success(content=content, message=result['message'])
        else:
            content = {
                'system_info': result.get('system_info', {})
            }
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
            return SycResponse.success(content=result, message="命令执行成功")
        else:
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
        return SycResponse.success(content=result, message="批量连接测试完成")

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
            return SycResponse.success(content=content, message=result['message'])
        else:
            # 错误情况下返回基本信息
            content = {
                'provider': provider,
                'region': region
            }
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

            return SycResponse.success(content=content, message=message)

        except Exception as e:
            return SycResponse.error(message=f"批量移动失败: {str(e)}", code=500)

    @action(detail=False, methods=['post'], url_path='import_excel')
    def import_excel(self, request):
        """通过Excel批量导入主机"""
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
            return SycResponse.success(content=result, message=result.get('message', '导入完成'))
        return SycResponse.error(content=result, message=result.get('message', '导入失败'))

    @action(detail=False, methods=['get'], url_path='import_excel_template')
    def download_import_template(self, request):
        """下载主机导入Excel模板"""
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
        local_path = request.data.get('local_path')
        remote_path = request.data.get('remote_path')
        overwrite_policy = request.data.get('overwrite_policy', 'overwrite')

        if not local_path or not remote_path:
            return SycResponse.error(message="本地路径和远程路径不能为空", code=400)

        # 验证覆盖策略
        valid_policies = ['overwrite', 'skip', 'backup', 'fail']
        if overwrite_policy not in valid_policies:
            return SycResponse.error(message=f"无效的覆盖策略，支持: {', '.join(valid_policies)}", code=400)

        host = self.get_object()
        result = HostService.upload_file_to_host(host, local_path, remote_path, overwrite_policy, request.user)

        if result['success']:
            return SycResponse.success(content=result, message="文件上传成功")
        else:
            return SycResponse.error(content=result, message="文件上传失败")

    @action(detail=True, methods=['post'])
    def download_file(self, request, pk=None):
        """从主机下载文件"""
        remote_path = request.data.get('remote_path')
        local_path = request.data.get('local_path')

        if not remote_path or not local_path:
            return SycResponse.error(message="远程路径和本地路径不能为空", code=400)

        host = self.get_object()
        result = HostService.download_file_from_host(host, remote_path, local_path, request.user)

        if result['success']:
            return SycResponse.success(content=result, message="文件下载成功")
        else:
            return SycResponse.error(content=result, message="文件下载失败")

    @action(detail=False, methods=['post'])
    def batch_upload(self, request):
        """批量上传文件到多个主机"""
        serializer = HostConnectionTestSerializer(data=request.data)  # 复用host_ids验证
        if not serializer.is_valid():
            return SycResponse.validation_error(errors=serializer.errors)

        local_path = request.data.get('local_path')
        remote_path = request.data.get('remote_path')
        overwrite_policy = request.data.get('overwrite_policy', 'overwrite')

        if not local_path or not remote_path:
            return SycResponse.error(message="本地路径和远程路径不能为空", code=400)

        # 验证覆盖策略
        valid_policies = ['overwrite', 'skip', 'backup']
        if overwrite_policy not in valid_policies:
            return SycResponse.error(message=f"无效的覆盖策略，支持: {', '.join(valid_policies)}", code=400)

        host_ids = serializer.validated_data['host_ids']
        hosts = Host.objects.filter(id__in=host_ids)
        result = HostService.batch_upload_file(list(hosts), local_path, remote_path, overwrite_policy, request.user)

        return SycResponse.success(content=result, message="批量文件上传完成")

    @action(detail=False, methods=['post'])
    def batch_download(self, request):
        """批量从多个主机下载文件"""
        serializer = HostConnectionTestSerializer(data=request.data)  # 复用host_ids验证
        if not serializer.is_valid():
            return SycResponse.validation_error(errors=serializer.errors)

        remote_path = request.data.get('remote_path')
        local_base_path = request.data.get('local_base_path')

        if not remote_path or not local_base_path:
            return SycResponse.error(message="远程路径和本地基础路径不能为空", code=400)

        host_ids = serializer.validated_data['host_ids']
        hosts = Host.objects.filter(id__in=host_ids)
        result = HostService.batch_download_file(list(hosts), remote_path, local_base_path, request.user)

        return SycResponse.success(content=result, message="批量文件下载完成")

    @action(detail=False, methods=['post'])
    def transfer_between_hosts(self, request):
        """主机间文件传输"""
        source_host_id = request.data.get('source_host_id')
        target_host_id = request.data.get('target_host_id')
        source_path = request.data.get('source_path')
        target_path = request.data.get('target_path')
        overwrite_policy = request.data.get('overwrite_policy', 'overwrite')

        if not all([source_host_id, target_host_id, source_path, target_path]):
            return SycResponse.error(message="源主机ID、目标主机ID、源路径和目标路径都不能为空", code=400)

        # 验证覆盖策略
        valid_policies = ['overwrite', 'skip', 'backup', 'fail']
        if overwrite_policy not in valid_policies:
            return SycResponse.error(message=f"无效的覆盖策略，支持: {', '.join(valid_policies)}", code=400)

        if source_host_id == target_host_id:
            return SycResponse.error(message="源主机和目标主机不能相同", code=400)

        try:
            source_host = Host.objects.get(id=source_host_id)
            target_host = Host.objects.get(id=target_host_id)
        except Host.DoesNotExist:
            return SycResponse.error(message="主机不存在", code=404)

        result = HostService.transfer_file_between_hosts(
            source_host, target_host, source_path, target_path, overwrite_policy, request.user
        )

        if result['success']:
            return SycResponse.success(content=result, message="主机间文件传输成功")
        else:
            return SycResponse.error(content=result, message="主机间文件传输失败")


class HostGroupViewSet(viewsets.ModelViewSet):
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

        # 返回统一格式的响应
        response_serializer = self.get_serializer(group)
        return SycResponse.success(
            content=response_serializer.data,
            message="主机分组更新成功"
        )

    def destroy(self, request, *args, **kwargs):
        """删除主机分组"""
        instance = self.get_object()
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


class ServerAccountViewSet(viewsets.ModelViewSet):
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
        instance.delete()

        # 返回统一格式的响应
        return SycResponse.success(
            content=None,
            message="账号删除成功"
        )
