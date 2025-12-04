"""
脚本模板序列化器
"""
from django.db import transaction
from rest_framework import serializers
from drf_spectacular.utils import extend_schema_field
from .models import ScriptTemplate, DefaultScriptTemplate, ScriptTemplateVersion


class ScriptTemplateSerializer(serializers.ModelSerializer):
    """脚本模板序列化器"""
    
    created_by_name = serializers.CharField(source='created_by.username', read_only=True)
    script_type_display = serializers.CharField(source='get_script_type_display', read_only=True)
    template_type_display = serializers.CharField(source='get_template_type_display', read_only=True)
    category_display = serializers.CharField(source='get_category_display', read_only=True)
    tag_list = serializers.SerializerMethodField()

    @extend_schema_field(serializers.ListField(child=serializers.CharField()))
    def get_tag_list(self, obj):
        """获取标签列表"""
        return obj.tag_list
    
    class Meta:
        model = ScriptTemplate
        fields = [
            'id', 'name', 'description', 'script_type', 'script_type_display',
            'template_type', 'template_type_display', 'category', 'category_display',
            'script_content', 'version', 'is_active', 'tags_json', 'tag_list', 'usage_count',
            'is_public', 'created_by', 'created_by_name', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'usage_count', 'created_by', 'created_at', 'updated_at']
    
    def validate_script_content(self, value):
        """验证脚本内容"""
        if not value.strip():
            raise serializers.ValidationError("脚本内容不能为空")
        return value


class ScriptTemplateCreateSerializer(serializers.ModelSerializer):
    """脚本模板创建序列化器"""

    class Meta:
        model = ScriptTemplate
        fields = [
            'name', 'description', 'script_type', 'template_type', 'category',
            'script_content', 'version', 'is_active', 'tags_json', 'is_public'
        ]
    
    def validate_name(self, value):
        """验证模板名称唯一性"""
        user = self.context['request'].user

        query = ScriptTemplate.objects.filter(name=value, created_by=user)

        # 如果是更新操作，排除当前模板
        if self.instance:
            query = query.exclude(id=self.instance.id)

        # 检查同一用户下的模板名称是否重复
        if query.exists():
            raise serializers.ValidationError("您已经有同名的脚本模板")

        return value

    def update(self, instance, validated_data):
        """
        更新脚本模板时，如果版本号发生变化，同步更新当前激活版本记录的版本号，
        保证「版本管理」列表中的版本号与模板当前版本保持一致。
        """
        old_version = instance.version
        new_version = validated_data.get('version', old_version)

        active_version = None

        # 只有在显式修改了 version 且存在激活版本记录时才做同步和冲突检查
        if 'version' in validated_data and new_version != old_version:
            active_version = instance.versions.filter(is_active=True).first()

            if active_version:
                # 检查是否与其他版本号冲突
                if instance.versions.exclude(id=active_version.id).filter(version=new_version).exists():
                    raise serializers.ValidationError({
                        'version': ['该模板下已存在相同的版本号']
                    })

        with transaction.atomic():
            instance = super().update(instance, validated_data)

            # 同步更新当前激活版本记录的 version 字段
            if active_version and new_version != old_version:
                active_version.version = new_version
                active_version.save(update_fields=['version'])

        return instance


class DefaultScriptTemplateSerializer(serializers.ModelSerializer):
    """默认脚本模板序列化器"""
    
    script_type_display = serializers.CharField(source='get_script_type_display', read_only=True)
    
    class Meta:
        model = DefaultScriptTemplate
        fields = [
            'id', 'script_type', 'script_type_display', 
            'template_content', 'description', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']


class ScriptTemplateVersionSerializer(serializers.ModelSerializer):
    """脚本模板版本序列化器"""

    created_by_name = serializers.CharField(source='created_by.username', read_only=True)

    class Meta:
        model = ScriptTemplateVersion
        fields = [
            'id', 'template', 'version', 'script_content', 'description',
            'is_active', 'created_by', 'created_by_name', 'created_at'
        ]
        read_only_fields = ['id', 'created_by', 'created_at']
