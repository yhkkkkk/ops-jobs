from django import forms
from django.contrib.contenttypes.models import ContentType
from django.contrib.auth.models import Permission, Group
from django.urls import reverse
from guardian.models import GroupObjectPermission


class GroupObjectPermissionForm(forms.ModelForm):
    """组对象权限表单
    
    创建模式：使用 object_selection 和 permissions（多选）
    查看模式：显示相同的字段，但为只读状态
    """
    
    # 自定义字段：不在模型中，用于创建时的批量操作
    object_selection = forms.ChoiceField(
        choices=[],
        required=True,
        label="目标对象",
        help_text="选择要授权的对象"
    )
    
    permissions = forms.ModelMultipleChoiceField(
        queryset=Permission.objects.none(),
        widget=forms.CheckboxSelectMultiple,
        required=True,
        label="权限",
        help_text="可多选，为该对象分配多个权限"
    )

    class Meta:
        model = GroupObjectPermission
        fields = ['group', 'content_type']  # 只包含模型字段，自定义字段单独定义

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # 配置字段样式
        select2_attrs = {'class': 'admin-select2', 'style': 'width: 100%; max-width: 800px;'}
        
        # 配置模型字段
        for field_name in ['group', 'content_type']:
            if field_name in self.fields:
                self.fields[field_name].widget.attrs.update(select2_attrs)
        
        # 配置 content_type 的 AJAX URL（仅创建模式需要）
        if not (self.instance and self.instance.pk):
            try:
                ajax_url = reverse('admin:guardian_groupobjectpermission_get_data')
                if 'content_type' in self.fields and ajax_url:
                    self.fields['content_type'].widget.attrs['data-ajax-url'] = ajax_url
            except Exception:
                pass  # URL 解析失败不影响表单使用
        
        # 配置自定义字段
        if 'object_selection' in self.fields:
            self.fields['object_selection'].widget.attrs.update(select2_attrs)
        
        # 查看模式：填充已有数据
        if self.instance and self.instance.pk:
            self._populate_view_mode()
        # 创建模式：处理表单回填（验证失败时）
        elif self.is_bound and self.data.get('content_type'):
            self._populate_from_post_data()

    def _populate_view_mode(self):
        """查看模式：填充对象和权限的显示值"""
        try:
            instance = self.instance
            
            # 填充对象选择字段 - 在查看模式下显示对象名称
            if 'object_selection' in self.fields:
                # 获取对象名称
                obj_display = str(instance.object_pk)  # 默认显示 ID
                if instance.content_type:
                    model_class = instance.content_type.model_class()
                    if model_class:
                        try:
                            obj = model_class.objects.get(pk=instance.object_pk)
                            obj_display = str(obj)
                        except Exception:
                            obj_display = f"对象ID: {instance.object_pk}"
                
                # 设置 choices 和 initial，确保 Select2 能正确显示
                self.fields['object_selection'].choices = [(instance.object_pk, obj_display)]
                self.fields['object_selection'].initial = instance.object_pk
                # 对于只读字段，确保 widget 的 choices 也被设置
                if hasattr(self.fields['object_selection'].widget, 'choices'):
                    self.fields['object_selection'].widget.choices = [(instance.object_pk, obj_display)]
        except Exception:
            pass  # 静默失败，不影响表单显示

    def _populate_from_post_data(self):
        """创建模式：从 POST 数据填充字段（表单验证失败回填）"""
        try:
            ct_id = self.data.get('content_type')
            if not ct_id:
                return
            
            ct = ContentType.objects.get(pk=ct_id)
            model_class = ct.model_class()
            
            # 填充对象选择字段
            if 'object_selection' in self.fields:
                obj_id = self.data.get('object_selection')
                if obj_id and str(obj_id).strip():
                    try:
                        obj = model_class.objects.get(pk=obj_id)
                        self.fields['object_selection'].choices = [(obj.pk, str(obj))]
                    except Exception:
                        pass
            
            # 填充权限字段
            if 'permissions' in self.fields:
                self.fields['permissions'].queryset = Permission.objects.filter(content_type=ct)
        except Exception:
            pass  # 静默失败，不影响表单显示

    def clean_object_selection(self):
        """验证对象选择"""
        object_pk = self.cleaned_data.get('object_selection')
        
        if not object_pk or not str(object_pk).strip():
            raise forms.ValidationError('请选择目标对象。')
        
        try:
            object_pk = int(object_pk)
        except (ValueError, TypeError):
            raise forms.ValidationError('无效的对象ID。')
        
        # 验证对象是否存在
        content_type = self.cleaned_data.get('content_type')
        if content_type:
            try:
                model_class = content_type.model_class()
                if model_class:
                    model_class.objects.get(pk=object_pk)
            except model_class.DoesNotExist:
                raise forms.ValidationError('所选对象不存在。')
            except Exception as e:
                raise forms.ValidationError(f'验证对象时出错: {str(e)}')
        
        return object_pk

    def clean_permissions(self):
        """验证权限选择"""
        perms = self.cleaned_data.get('permissions')
        if not perms:
            raise forms.ValidationError('请至少选择一个权限。')
        return perms
