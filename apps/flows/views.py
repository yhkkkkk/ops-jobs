from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import transaction
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError as DRFValidationError
from rest_framework.permissions import IsAuthenticated

from utils.responses import SycResponse

from .models import FlowEdge, FlowNode, FlowRun, FlowTemplate
from .serializers import (
    FlowEdgeSerializer,
    FlowNodeSerializer,
    FlowRunSerializer,
    FlowStartSerializer,
    FlowTemplateSerializer,
)
from .services import FlowRunner


class FlowTemplateViewSet(viewsets.ModelViewSet):
    queryset = FlowTemplate.objects.all()
    serializer_class = FlowTemplateSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        queryset = super().get_queryset().select_related("created_by").prefetch_related("nodes", "edges")
        if self.request.user.is_superuser:
            return queryset
        return queryset.filter(created_by=self.request.user)

    def list(self, request, *args, **kwargs):
        serializer = self.get_serializer(self.get_queryset(), many=True)
        return SycResponse.success(content=serializer.data, message="获取流程模板列表成功")

    def retrieve(self, request, *args, **kwargs):
        serializer = self.get_serializer(self.get_object())
        return SycResponse.success(content=serializer.data, message="获取流程模板详情成功")

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        if not serializer.is_valid():
            return SycResponse.validation_error(serializer.errors)
        nodes_data = list(serializer.validated_data.pop("nodes", []) or [])
        edges_data = list(serializer.validated_data.pop("edges", []) or [])

        try:
            with transaction.atomic():
                template = serializer.save(created_by=request.user)
                self._replace_graph(template, nodes_data, edges_data, request)
        except DjangoValidationError as exc:
            return SycResponse.validation_error(exc.message_dict if hasattr(exc, "message_dict") else exc.messages)
        except DRFValidationError as exc:
            return SycResponse.validation_error(exc.detail)

        return SycResponse.success(
            content=self.get_serializer(template).data,
            message="流程模板创建成功",
        )

    def update(self, request, *args, **kwargs):
        partial = kwargs.pop("partial", False)
        serializer = self.get_serializer(self.get_object(), data=request.data, partial=partial)
        if not serializer.is_valid():
            return SycResponse.validation_error(serializer.errors)
        nodes_data = serializer.validated_data.pop("nodes", None)
        edges_data = serializer.validated_data.pop("edges", None)
        try:
            with transaction.atomic():
                template = serializer.save()
                if nodes_data is not None or edges_data is not None:
                    self._replace_graph(template, nodes_data or [], edges_data or [], request)
        except DjangoValidationError as exc:
            return SycResponse.validation_error(exc.message_dict if hasattr(exc, "message_dict") else exc.messages)
        except DRFValidationError as exc:
            return SycResponse.validation_error(exc.detail)

        return SycResponse.success(
            content=self.get_serializer(template).data,
            message="流程模板更新成功",
        )

    def destroy(self, request, *args, **kwargs):
        template = self.get_object()
        self.perform_destroy(template)
        return SycResponse.success(message="流程模板删除成功")

    @staticmethod
    def _replace_graph(template, nodes_data, edges_data, request=None):
        if not nodes_data and not edges_data:
            return

        template.edges.all().delete()
        template.nodes.all().delete()

        nodes_by_uuid = {}
        for node_data in nodes_data:
            node_data = dict(node_data)
            node_uuid = node_data.get("uuid")
            if not node_uuid:
                raise DjangoValidationError({"nodes": "节点必须包含 uuid"})
            if node_uuid in nodes_by_uuid:
                raise DjangoValidationError({"nodes": f"节点 uuid 重复: {node_uuid}"})
            serializer = FlowNodeSerializer(
                data={
                    "template": template.id,
                    "uuid": node_uuid,
                    "name": node_data.get("name") or node_uuid,
                    "node_type": node_data.get("node_type"),
                    "config": node_data.get("config") or {},
                    "position": node_data.get("position") or {},
                },
                context={"request": request} if request else {},
            )
            if not serializer.is_valid():
                raise DRFValidationError({"nodes": serializer.errors})
            validated_node = serializer.validated_data

            node = FlowNode.objects.create(
                template=template,
                uuid=validated_node["uuid"],
                name=validated_node["name"],
                node_type=validated_node["node_type"],
                config=validated_node.get("config") or {},
                position=validated_node.get("position") or {},
            )
            nodes_by_uuid[node_uuid] = node

        for edge_data in edges_data:
            edge_data = dict(edge_data)
            source_uuid = edge_data.get("source_uuid")
            target_uuid = edge_data.get("target_uuid")
            if source_uuid not in nodes_by_uuid or target_uuid not in nodes_by_uuid:
                raise DjangoValidationError({"edges": "边的 source_uuid/target_uuid 必须引用同一模板内节点"})
            FlowEdge.objects.create(
                template=template,
                source=nodes_by_uuid[source_uuid],
                target=nodes_by_uuid[target_uuid],
                condition=edge_data.get("condition") or {},
            )

    @action(detail=True, methods=["post"])
    def start(self, request, pk=None):
        template = self.get_object()
        serializer = FlowStartSerializer(data=request.data)
        if not serializer.is_valid():
            return SycResponse.validation_error(serializer.errors)

        try:
            flow_run = FlowRunner.start(
                template=template,
                user=request.user,
                inputs=serializer.validated_data.get("inputs") or {},
                agent_server_id=serializer.validated_data["agent_server_id"],
            )
        except Exception as exc:
            return SycResponse.error(message=f"流程启动失败: {exc}")

        return SycResponse.success(
            content=FlowRunSerializer(flow_run).data,
            message="流程启动成功",
        )


class FlowNodeViewSet(viewsets.ModelViewSet):
    queryset = FlowNode.objects.all()
    serializer_class = FlowNodeSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        queryset = super().get_queryset().select_related("template")
        if not self.request.user.is_superuser:
            queryset = queryset.filter(template__created_by=self.request.user)
        template_id = self.request.query_params.get("template")
        if template_id:
            queryset = queryset.filter(template_id=template_id)
        return queryset

    def list(self, request, *args, **kwargs):
        serializer = self.get_serializer(self.get_queryset(), many=True)
        return SycResponse.success(content=serializer.data, message="获取流程节点列表成功")

    def retrieve(self, request, *args, **kwargs):
        serializer = self.get_serializer(self.get_object())
        return SycResponse.success(content=serializer.data, message="获取流程节点详情成功")

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        if not serializer.is_valid():
            return SycResponse.validation_error(serializer.errors)
        node = serializer.save()
        return SycResponse.success(content=self.get_serializer(node).data, message="流程节点创建成功")

    def update(self, request, *args, **kwargs):
        partial = kwargs.pop("partial", False)
        serializer = self.get_serializer(self.get_object(), data=request.data, partial=partial)
        if not serializer.is_valid():
            return SycResponse.validation_error(serializer.errors)
        node = serializer.save()
        return SycResponse.success(content=self.get_serializer(node).data, message="流程节点更新成功")

    def destroy(self, request, *args, **kwargs):
        node = self.get_object()
        self.perform_destroy(node)
        return SycResponse.success(message="流程节点删除成功")


class FlowEdgeViewSet(viewsets.ModelViewSet):
    queryset = FlowEdge.objects.all()
    serializer_class = FlowEdgeSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        queryset = super().get_queryset().select_related("template", "source", "target")
        if not self.request.user.is_superuser:
            queryset = queryset.filter(template__created_by=self.request.user)
        template_id = self.request.query_params.get("template")
        if template_id:
            queryset = queryset.filter(template_id=template_id)
        return queryset

    def list(self, request, *args, **kwargs):
        serializer = self.get_serializer(self.get_queryset(), many=True)
        return SycResponse.success(content=serializer.data, message="获取流程边列表成功")

    def retrieve(self, request, *args, **kwargs):
        serializer = self.get_serializer(self.get_object())
        return SycResponse.success(content=serializer.data, message="获取流程边详情成功")

    def create(self, request, *args, **kwargs):
        try:
            data = self._resolve_uuid_edge_data(request.data, request=request)
        except DjangoValidationError as exc:
            return SycResponse.validation_error(exc.message_dict if hasattr(exc, "message_dict") else exc.messages)
        serializer = self.get_serializer(data=data)
        if not serializer.is_valid():
            return SycResponse.validation_error(serializer.errors)
        try:
            edge = serializer.save()
        except DjangoValidationError as exc:
            return SycResponse.validation_error(exc.message_dict if hasattr(exc, "message_dict") else exc.messages)
        return SycResponse.success(content=self.get_serializer(edge).data, message="流程边创建成功")

    def update(self, request, *args, **kwargs):
        partial = kwargs.pop("partial", False)
        instance = self.get_object()
        try:
            data = self._resolve_uuid_edge_data(request.data, request=request, instance=instance)
        except DjangoValidationError as exc:
            return SycResponse.validation_error(exc.message_dict if hasattr(exc, "message_dict") else exc.messages)
        serializer = self.get_serializer(instance, data=data, partial=partial)
        if not serializer.is_valid():
            return SycResponse.validation_error(serializer.errors)
        try:
            edge = serializer.save()
        except DjangoValidationError as exc:
            return SycResponse.validation_error(exc.message_dict if hasattr(exc, "message_dict") else exc.messages)
        return SycResponse.success(content=self.get_serializer(edge).data, message="流程边更新成功")

    def destroy(self, request, *args, **kwargs):
        edge = self.get_object()
        self.perform_destroy(edge)
        return SycResponse.success(message="流程边删除成功")

    @staticmethod
    def _resolve_uuid_edge_data(data, request=None, instance=None):
        mutable = dict(data)
        template_id = mutable.get("template") or (instance.template_id if instance else None)
        errors = {}
        if template_id and request:
            template_queryset = FlowTemplate.objects.filter(id=template_id)
            if not request.user.is_superuser:
                template_queryset = template_queryset.filter(created_by=request.user)
            if not template_queryset.exists():
                errors["template"] = "流程模板不存在或无权操作"
        if not template_id and (mutable.get("source_uuid") or mutable.get("target_uuid")):
            errors["template"] = "使用节点 uuid 时必须指定流程模板"
        if errors:
            raise DjangoValidationError(errors)
        if template_id and mutable.get("source_uuid") and not mutable.get("source"):
            source = FlowNode.objects.filter(template_id=template_id, uuid=mutable["source_uuid"]).first()
            if source:
                mutable["source"] = source.id
            else:
                errors["source_uuid"] = "源节点不存在或不属于模板"
        if template_id and mutable.get("target_uuid") and not mutable.get("target"):
            target = FlowNode.objects.filter(template_id=template_id, uuid=mutable["target_uuid"]).first()
            if target:
                mutable["target"] = target.id
            else:
                errors["target_uuid"] = "目标节点不存在或不属于模板"
        if errors:
            raise DjangoValidationError(errors)
        return mutable


class FlowRunViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = FlowRun.objects.all()
    serializer_class = FlowRunSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        queryset = (
            super()
            .get_queryset()
            .select_related("template", "started_by")
            .prefetch_related("node_runs__node", "node_runs__execution_record")
        )
        if self.request.user.is_superuser:
            return queryset
        return queryset.filter(template__created_by=self.request.user)

    def list(self, request, *args, **kwargs):
        serializer = self.get_serializer(self.get_queryset(), many=True)
        return SycResponse.success(content=serializer.data, message="获取流程执行列表成功")

    def retrieve(self, request, *args, **kwargs):
        serializer = self.get_serializer(self.get_object())
        return SycResponse.success(content=serializer.data, message="获取流程执行详情成功")
