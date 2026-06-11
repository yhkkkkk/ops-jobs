from rest_framework import serializers

from apps.hosts.models import Host
from apps.job_templates.models import ExecutionPlan

from .models import FlowEdge, FlowNode, FlowNodeRun, FlowRun, FlowTemplate
from .plugins import validate_flow_node_config
from .validators import get_execution_plan_resource_permission_error, get_file_source_errors


class FlowNodeSerializer(serializers.ModelSerializer):
    class Meta:
        model = FlowNode
        fields = [
            "id",
            "template",
            "uuid",
            "name",
            "node_type",
            "config",
            "position",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]

    def validate_template(self, template):
        request = self.context.get("request")
        if request and not request.user.is_superuser and template.created_by_id != request.user.id:
            raise serializers.ValidationError("无权操作该流程模板")
        return template

    def validate(self, attrs):
        request = self.context.get("request")
        node_type = attrs.get("node_type") or getattr(self.instance, "node_type", None)
        config = attrs.get("config")
        if config is None:
            config = getattr(self.instance, "config", {}) or {}
        plugin_errors = validate_flow_node_config(node_type, config)
        if plugin_errors:
            raise serializers.ValidationError({"config": plugin_errors})

        if not request:
            return attrs

        if node_type in (FlowNode.NodeType.SCRIPT, FlowNode.NodeType.FILE_TRANSFER):
            self._validate_target_hosts(config, request.user)
        if node_type == FlowNode.NodeType.FILE_TRANSFER:
            self._validate_file_sources(config)
        if node_type == FlowNode.NodeType.JOB_PLAN:
            self._validate_execution_plan(config, request.user)
        if node_type == FlowNode.NodeType.SUB_PROCESS:
            self._validate_sub_process_template(attrs, config, request.user)

        return attrs

    @staticmethod
    def _validate_target_hosts(config, user):
        host_ids = config.get("target_host_ids") or []
        if not host_ids:
            return

        existing_hosts = list(Host.objects.filter(id__in=host_ids))
        found_host_ids = {host.id for host in existing_hosts}
        invalid_host_ids = sorted(set(host_ids) - found_host_ids)
        if invalid_host_ids:
            raise serializers.ValidationError({"config": f"无效的目标主机: {invalid_host_ids}"})

        if user.is_superuser:
            return

        denied_host_ids = sorted(host.id for host in existing_hosts if host.created_by_id != user.id)
        if denied_host_ids:
            raise serializers.ValidationError({"config": f"无权引用目标主机: {denied_host_ids}"})

    @staticmethod
    def _validate_execution_plan(config, user):
        plan_id = config.get("execution_plan_id")
        if not plan_id:
            return

        execution_plan = ExecutionPlan.objects.filter(id=plan_id).first()
        if not execution_plan:
            raise serializers.ValidationError({"config": "执行方案不存在"})
        if not user.is_superuser and execution_plan.created_by_id != user.id:
            raise serializers.ValidationError({"config": "无权引用执行方案"})
        resource_error = get_execution_plan_resource_permission_error(execution_plan, user)
        if resource_error:
            raise serializers.ValidationError({"config": resource_error})

    @staticmethod
    def _validate_file_sources(config):
        file_sources = config.get("file_sources") or config.get("sources") or []
        if not file_sources:
            return
        source_errors = get_file_source_errors(file_sources)
        if source_errors:
            raise serializers.ValidationError({"config": "; ".join(source_errors)})

    def _validate_sub_process_template(self, attrs, config, user):
        template = attrs.get("template") or getattr(self.instance, "template", None)
        target_template_id = config.get("template_id")
        if not target_template_id:
            return

        target_template = FlowTemplate.objects.filter(id=target_template_id).first()
        if not target_template:
            raise serializers.ValidationError({"config": "子流程模板不存在"})
        if not target_template.is_active:
            raise serializers.ValidationError({"config": "子流程模板未启用"})
        if template and target_template.id == template.id:
            raise serializers.ValidationError({"config": "子流程不能引用当前流程模板"})
        if not user.is_superuser and target_template.created_by_id != user.id:
            raise serializers.ValidationError({"config": "无权引用子流程模板"})


class FlowEdgeSerializer(serializers.ModelSerializer):
    source = serializers.PrimaryKeyRelatedField(queryset=FlowNode.objects.all(), required=False)
    target = serializers.PrimaryKeyRelatedField(queryset=FlowNode.objects.all(), required=False)
    source_uuid = serializers.CharField(write_only=True, required=False)
    target_uuid = serializers.CharField(write_only=True, required=False)

    class Meta:
        model = FlowEdge
        fields = ["id", "template", "source", "target", "source_uuid", "target_uuid", "condition"]
        read_only_fields = ["id"]

    def validate(self, attrs):
        template = attrs.get("template") or getattr(self.instance, "template", None)
        source = attrs.get("source") or getattr(self.instance, "source", None)
        target = attrs.get("target") or getattr(self.instance, "target", None)

        if template and source and source.template_id != template.id:
            raise serializers.ValidationError({"source": "源节点必须属于同一个流程模板"})
        if template and target and target.template_id != template.id:
            raise serializers.ValidationError({"target": "目标节点必须属于同一个流程模板"})

        request = self.context.get("request")
        if request and template and not request.user.is_superuser and template.created_by_id != request.user.id:
            raise serializers.ValidationError({"template": "无权操作该流程模板"})

        return attrs

    def create(self, validated_data):
        validated_data.pop("source_uuid", None)
        validated_data.pop("target_uuid", None)
        return super().create(validated_data)

    def update(self, instance, validated_data):
        validated_data.pop("source_uuid", None)
        validated_data.pop("target_uuid", None)
        return super().update(instance, validated_data)


class FlowTemplateSerializer(serializers.ModelSerializer):
    nodes = serializers.ListField(child=serializers.DictField(), required=False, write_only=True)
    edges = serializers.ListField(child=serializers.DictField(), required=False, write_only=True)
    created_by_name = serializers.CharField(source="created_by.username", read_only=True)

    class Meta:
        model = FlowTemplate
        fields = [
            "id",
            "name",
            "description",
            "variables",
            "is_active",
            "created_by",
            "created_by_name",
            "created_at",
            "updated_at",
            "nodes",
            "edges",
        ]
        read_only_fields = ["id", "created_by", "created_at", "updated_at"]

    def to_representation(self, instance):
        data = super().to_representation(instance)
        data["nodes"] = FlowNodeSerializer(instance.nodes.all(), many=True).data
        data["edges"] = FlowEdgeSerializer(instance.edges.all(), many=True).data
        return data


class FlowNodeRunSerializer(serializers.ModelSerializer):
    node_name = serializers.CharField(source="node.name", read_only=True)
    node_uuid = serializers.CharField(source="node.uuid", read_only=True)
    node_type = serializers.CharField(source="node.node_type", read_only=True)
    execution_record_id = serializers.IntegerField(source="execution_record.id", read_only=True)

    class Meta:
        model = FlowNodeRun
        fields = [
            "id",
            "node",
            "node_name",
            "node_uuid",
            "node_type",
            "status",
            "inputs",
            "outputs",
            "error_message",
            "execution_record",
            "execution_record_id",
            "started_at",
            "finished_at",
            "created_at",
        ]
        read_only_fields = fields


class FlowRunSerializer(serializers.ModelSerializer):
    template_name = serializers.CharField(source="template.name", read_only=True)
    started_by_name = serializers.CharField(source="started_by.username", read_only=True)
    node_runs = FlowNodeRunSerializer(many=True, read_only=True)

    class Meta:
        model = FlowRun
        fields = [
            "id",
            "template",
            "template_name",
            "status",
            "trigger_type",
            "started_by",
            "started_by_name",
            "inputs",
            "outputs",
            "error_message",
            "started_at",
            "finished_at",
            "created_at",
            "node_runs",
        ]
        read_only_fields = fields


class FlowStartSerializer(serializers.Serializer):
    inputs = serializers.DictField(required=False, allow_empty=True)
    agent_server_id = serializers.IntegerField(required=True)
