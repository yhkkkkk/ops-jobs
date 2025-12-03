"""
权限检查视图 - 专门用于前端权限判断
不包含权限分配功能，所有分配都在 Django Admin 后台完成
"""
from datetime import datetime, timedelta
import io
import pandas as pd
import logging
from django.http import FileResponse
from django.utils import timezone
from rest_framework import viewsets
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.decorators import action
from django.contrib.auth.models import User
from django.contrib.contenttypes.models import ContentType
from guardian.models import UserObjectPermission, GroupObjectPermission
from .models import AuditLog
from .serializers import AuditLogSerializer
from rest_framework.permissions import IsAuthenticated
from .permissions import IsSuperUser
from utils.pagination import CustomPagination
from utils.responses import SycResponse
from django.db.models import Q
from django_filters.rest_framework import DjangoFilterBackend
from .filters import AuditLogFilter

logger = logging.getLogger(__name__)


# 资源类型到真实 app_label / model 的映射
RESOURCE_MAP = {
    # 资源类型   (app_label,      model_name)
    'host':          ('hosts',          'host'),
    'jobtemplate':   ('job_templates',  'jobtemplate'),
    'executionplan': ('job_templates',  'executionplan'),
    'scripttemplate':('script_templates', 'scripttemplate'),
    'job':           ('scheduler',      'scheduledjob'),
    'serveraccount': ('hosts',          'serveraccount'),
    # 'script' 可以根据后续业务再单独映射
}


def build_codename(model: str, perm: str) -> str:
    """
    将前端的权限级别（view/add/change/delete/...）
    转换为后端真实的 codename（如 view_host、change_jobtemplate）
    """
    if perm in ('view', 'add', 'change', 'delete'):
        return f'{perm}_{model}'
    # 其他自定义权限（如 execute_* 等）可按需求扩展
    return perm


class PermissionCheckView(APIView):
    """权限检查视图 - 前端用于检查用户权限"""
    
    permission_classes = [IsAuthenticated]
    
    def post(self, request):
        """检查用户对特定资源的权限"""
        try:
            # 获取要检查的资源信息
            resource_type = request.data.get('resource_type')  # 如 'host', 'job', 'script'
            resource_id = request.data.get('resource_id')      # 具体资源ID，可选
            permissions_to_check = request.data.get('permissions', [])  # 要检查的权限列表
            
            if not resource_type:
                return SycResponse.error('必须提供资源类型', code=400)
            
            user = request.user
            result = {}
            
            if resource_type not in RESOURCE_MAP:
                return SycResponse.error(f'不支持的资源类型: {resource_type}', code=400)

            app_label, model_name = RESOURCE_MAP[resource_type]

            # 检查模型级权限
            if not resource_id:
                for perm in permissions_to_check:
                    codename = build_codename(model_name, perm)
                    full_perm = f'{app_label}.{codename}'
                    result[perm] = user.has_perm(full_perm)

            # 检查对象级权限
            else:
                try:
                    # 获取内容类型和模型类
                    content_type = ContentType.objects.get(app_label=app_label, model=model_name)
                    model_class = content_type.model_class()

                    # 获取具体对象
                    obj = model_class.objects.get(id=resource_id)

                    # 检查对象级权限
                    for perm in permissions_to_check:
                        codename = build_codename(model_name, perm)
                        full_perm = f'{app_label}.{codename}'
                        result[perm] = user.has_perm(full_perm, obj)

                except ContentType.DoesNotExist:
                    return SycResponse.not_found('资源类型不存在')
                except model_class.DoesNotExist:  # type: ignore[name-defined]
                    return SycResponse.not_found('资源不存在')
            
            return SycResponse.success({
                'user_id': user.id,
                'username': user.username,
                'resource_type': resource_type,
                'resource_id': resource_id,
                'permissions': result
            }, '权限检查成功')
            
        except Exception as e:
            return SycResponse.error(f'权限检查失败: {str(e)}', code=500)


class UserPermissionsView(APIView):
    """用户权限视图 - 获取当前用户的权限信息"""
    
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        """获取当前用户的权限摘要"""
        try:
            user = request.user
            
            # 获取用户基本信息
            data = {
                'user_id': user.id,
                'username': user.username,
                'is_superuser': user.is_superuser,
                'is_staff': user.is_staff,
                'groups': [group.name for group in user.groups.all()],
                'model_permissions': {},
                'object_permissions': {},
                'permission_count': 0
            }
            
            # 如果是超级用户，直接返回
            if user.is_superuser:
                data['permission_count'] = -1  # 表示拥有所有权限
                return SycResponse.success(data, message='获取用户权限成功')
            
            # 获取模型级权限
            model_permissions = {}
            for perm in user.user_permissions.all():
                key = f"{perm.content_type.app_label}.{perm.content_type.model}"
                if key not in model_permissions:
                    model_permissions[key] = []
                model_permissions[key].append(perm.codename)
            
            # 获取组权限
            for group in user.groups.all():
                for perm in group.permissions.all():
                    key = f"{perm.content_type.app_label}.{perm.content_type.model}"
                    if key not in model_permissions:
                        model_permissions[key] = []
                    if perm.codename not in model_permissions[key]:
                        model_permissions[key].append(perm.codename)
            
            data['model_permissions'] = model_permissions
            
            # 获取对象级权限（Guardian）
            object_permissions = {}
            
            # 获取用户直接的对象权限
            user_obj_perms = UserObjectPermission.objects.filter(user=user).select_related(
                'permission__content_type'
            )
            for obj_perm in user_obj_perms:
                ct = obj_perm.permission.content_type
                key = f"{ct.app_label}.{ct.model}"
                if key not in object_permissions:
                    object_permissions[key] = {}
                
                # 获取对象ID和权限名称
                obj_id = str(obj_perm.object_pk)
                perm_name = obj_perm.permission.codename
                
                if obj_id not in object_permissions[key]:
                    object_permissions[key][obj_id] = []
                
                if perm_name not in object_permissions[key][obj_id]:
                    object_permissions[key][obj_id].append(perm_name)
            
            # 获取用户所属组的对象权限
            for group in user.groups.all():
                group_obj_perms = GroupObjectPermission.objects.filter(group=group).select_related(
                    'permission__content_type'
                )
                for obj_perm in group_obj_perms:
                    ct = obj_perm.permission.content_type
                    key = f"{ct.app_label}.{ct.model}"
                    if key not in object_permissions:
                        object_permissions[key] = {}
                    
                    obj_id = str(obj_perm.object_pk)
                    perm_name = obj_perm.permission.codename
                    
                    if obj_id not in object_permissions[key]:
                        object_permissions[key][obj_id] = []
                    
                    if perm_name not in object_permissions[key][obj_id]:
                        object_permissions[key][obj_id].append(perm_name)
            
            data['object_permissions'] = object_permissions
            
            # 计算权限总数（模型级权限 + 对象级权限）
            total_perms = 0
            for perms in model_permissions.values():
                total_perms += len(perms)
            
            # 统计对象级权限数量
            for model_perms in object_permissions.values():
                for obj_perms in model_perms.values():
                    total_perms += len(obj_perms)
            
            data['permission_count'] = total_perms
            
            return SycResponse.success(data, message='获取用户权限成功')
            
        except Exception as e:
            return SycResponse.error(f'获取用户权限失败: {str(e)}', code=500)
    
    def post(self, request):
        """批量检查用户权限"""
        try:
            # 获取要检查的权限列表
            permissions_to_check = request.data.get('permissions', [])
            
            if not permissions_to_check:
                return SycResponse.error('必须提供要检查的权限列表', code=400)
            
            user = request.user
            result = {}
            
            # 检查每个权限
            for perm in permissions_to_check:
                if '.' in perm:
                    # 完整权限名
                    result[perm] = user.has_perm(perm)
                else:
                    # 只有权限名，需要补充应用名
                    # 这里可以根据业务逻辑补充
                    result[perm] = False
            
            return SycResponse.success({
                'user_id': user.id,
                'username': user.username,
                'permissions': result
            }, message='批量权限检查成功')
            
        except Exception as e:
            return SycResponse.error(f'批量权限检查失败: {str(e)}', code=500)


class ResourcePermissionsView(APIView):
    """资源权限视图 - 检查用户对特定资源的权限"""

    permission_classes = [IsAuthenticated]
    
    def post(self, request):
        """检查用户对资源的权限"""
        try:
            # 获取资源信息
            resource_type = request.data.get('resource_type')
            resource_ids = request.data.get('resource_ids', [])
            permissions_to_check = request.data.get('permissions', ['view', 'change', 'delete', 'add'])
            
            if not resource_type:
                return SycResponse.error('必须提供资源类型', code=400)
            
            user = request.user
            result = {}
            
            if resource_type not in RESOURCE_MAP:
                return SycResponse.error('不支持的资源类型', code=400)

            app_label, model_name = RESOURCE_MAP[resource_type]

            try:
                # 获取内容类型和模型类
                content_type = ContentType.objects.get(app_label=app_label, model=model_name)
                model_class = content_type.model_class()

                # 如果没有指定资源ID，返回模型级权限
                if not resource_ids:
                    for perm in permissions_to_check:
                        codename = build_codename(model_name, perm)
                        full_perm = f'{app_label}.{codename}'
                        result[perm] = user.has_perm(full_perm)

                    return SycResponse.success({
                        'user_id': user.id,
                        'username': user.username,
                        'resource_type': resource_type,
                        'permissions': result,
                        'level': 'model'
                    }, message='资源权限检查成功')

                # 检查对象级权限
                for resource_id in resource_ids:
                    try:
                        obj = model_class.objects.get(id=resource_id)
                        obj_perms = {}

                        for perm in permissions_to_check:
                            codename = build_codename(model_name, perm)
                            full_perm = f'{app_label}.{codename}'
                            obj_perms[perm] = user.has_perm(full_perm, obj)

                        result[str(resource_id)] = obj_perms

                    except model_class.DoesNotExist:
                        result[str(resource_id)] = {'error': '资源不存在'}

                return SycResponse.success({
                    'user_id': user.id,
                    'username': user.username,
                    'resource_type': resource_type,
                    'permissions': result,
                    'level': 'object'
                }, message='资源权限检查成功')

            except ContentType.DoesNotExist:
                return SycResponse.not_found('资源类型不存在')
                
        except Exception as e:
            return SycResponse.error(f'资源权限检查失败: {str(e)}', code=500)


class AuditLogViewSet(viewsets.ReadOnlyModelViewSet):
    """审计日志ViewSet - 统一的系统审计日志"""

    serializer_class = AuditLogSerializer
    permission_classes = [IsSuperUser]
    pagination_class = CustomPagination
    filter_backends = [DjangoFilterBackend]
    filterset_class = AuditLogFilter

    def get_queryset(self):
        return AuditLog.objects.select_related('user', 'resource_type').order_by('-created_at')

    @action(detail=False, methods=['get'])
    def export(self, request):
        """导出审计日志为excel文件"""
        try:
            queryset = self.filter_queryset(self.get_queryset())

            # 准备excel数据
            data = []
            for log in queryset:
                data.append({
                    'ID': log.id,
                    '用户名': log.user.username if log.user else '-',
                    '用户全名': getattr(log.user, 'first_name', '') + ' ' + getattr(log.user, 'last_name', '') if log.user else '-',
                    '操作类型': log.get_action_display(),
                    '资源名称': log.resource_name or '-',
                    '资源类型': log.resource_type.model if log.resource_type else '-',
                    '操作描述': log.description,
                    'IP地址': log.ip_address or '-',
                    '状态': '成功' if log.success else '失败',
                    '操作时间': log.created_at.strftime('%Y-%m-%d %H:%M:%S'),
                    '错误信息': log.error_message or '-',
                })
            
            # 创建DataFrame
            df = pd.DataFrame(data)
            
            # 创建Excel文件
            output = io.BytesIO()
            with pd.ExcelWriter(output, engine='openpyxl') as writer:
                df.to_excel(writer, sheet_name='审计日志', index=False)
                
                # 获取工作表并调整列宽
                worksheet = writer.sheets['审计日志']
                for column in worksheet.columns:
                    max_length = 0
                    column_letter = column[0].column_letter
                    for cell in column:
                        try:
                            if len(str(cell.value)) > max_length:
                                max_length = len(str(cell.value))
                        except:
                            pass
                    adjusted_width = min(max_length + 2, 50)  # 最大宽度50
                    worksheet.column_dimensions[column_letter].width = adjusted_width
            
            output.seek(0)
            
            # 生成文件名
            timestamp = timezone.now().strftime('%Y%m%d_%H%M%S')
            filename = f'audit_logs_{timestamp}.xlsx'
            
            # 使用FileResponse返回文件
            response = FileResponse(
                output,
                content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
            )
            response['Content-Disposition'] = f'attachment; filename="{filename}"'
            response['Content-Length'] = len(output.getvalue())
            
            return response
            
        except Exception as e:
            logger.error(f"导出审计日志失败: {e}")
            return SycResponse.error(f'导出失败: {str(e)}', code=500)
