from django.core.exceptions import ValidationError as DjangoValidationError
from django.contrib.contenttypes.models import ContentType
from django.db import IntegrityError, transaction
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError as DRFValidationError
from rest_framework.permissions import IsAuthenticated

import logging

from apps.permissions.models import AuditLog
from apps.permissions.serializers import AuditLogSerializer
from utils.audit_service import AuditLogService
from utils.responses import SycResponse

from .models import FlowEdge, FlowNode, FlowNodeRun, FlowRun, FlowSchedule, FlowTemplate
from .plugins import list_flow_node_plugins
from .serializers import (
    FlowEdgeSerializer,
    FlowNodeSerializer,
    FlowRunSerializer,
    FlowScheduleSerializer,
    FlowScheduleRunSerializer,
    FlowStartSerializer,
    FlowTemplateSerializer,
)
from .services import FlowRunner

logger = logging.getLogger(__name__)

ACTIVE_FLOW_RUN_STATUSES = [
    FlowRun.Status.PENDING,
    FlowRun.Status.RUNNING,
    FlowRun.Status.PAUSED,
]


def _flow_run_resource_name(flow_run):
    return f"{flow_run.template.name} #{flow_run.id}"


def _build_flow_audit_extra(flow_run, node_run=None, **extra_data):
    extra = {
        "flow_run_id": flow_run.id,
        "flow_run_status": flow_run.status,
        "template_id": flow_run.template_id,
        "template_name": flow_run.template.name,
    }
    if node_run is not None:
        extra.update(
            {
                "node_run_id": node_run.id,
                "node_uuid": node_run.node.uuid,
                "node_name": node_run.node.name,
                "node_type": node_run.node.node_type,
                "node_status": node_run.status,
            }
        )
    extra.update({key: value for key, value in extra_data.items() if value is not None})
    return extra


def _log_flow_run_action(
    request,
    flow_run,
    action,
    description,
    node_run=None,
    extra_data=None,
    success=True,
    error_message="",
):
    """Record flow operation audit logs without affecting the user operation."""
    try:
        AuditLogService.log_action(
            user=request.user,
            action=action,
            description=description,
            request=request,
            success=success,
            error_message=error_message or "",
            resource_type=ContentType.objects.get_for_model(FlowRun),
            resource_id=flow_run.id,
            resource_name=_flow_run_resource_name(flow_run),
            extra_data=_build_flow_audit_extra(flow_run, node_run=node_run, **(extra_data or {})),
        )
    except Exception as exc:
        logger.warning("流程审计日志记录失败: %s", exc)


def _raise_if_template_has_active_runs(template):
    if FlowRun.objects.filter(template=template, status__in=ACTIVE_FLOW_RUN_STATUSES).exists():
        raise DjangoValidationError(
            {
                "template": (
                    "流程存在等待中、执行中或暂停的实例，不能修改拓扑或节点配置；"
                    "请先结束实例，或复制为草稿后编辑。"
                )
            }
        )


def _lock_template_for_graph_change(template):
    try:
        locked_template = FlowTemplate.objects.select_for_update().get(pk=template.pk)
    except FlowTemplate.DoesNotExist:
        raise DjangoValidationError({"template": "流程模板不存在或已被删除"})
    _raise_if_template_has_active_runs(locked_template)
    return locked_template


def _raise_if_node_has_history(node, message):
    if FlowNodeRun.objects.filter(node=node).exists():
        raise DjangoValidationError({"node": message})


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
                    if nodes_data is None:
                        nodes_data = self._current_nodes_data(template)
                    if edges_data is None:
                        edges_data = self._current_edges_data(template)
                    self._replace_graph(template, nodes_data, edges_data, request)
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
        try:
            with transaction.atomic():
                _lock_template_for_graph_change(template)
                self.perform_destroy(template)
        except DjangoValidationError as exc:
            return SycResponse.validation_error(exc.message_dict if hasattr(exc, "message_dict") else exc.messages)
        return SycResponse.success(message="流程模板删除成功")

    @action(detail=True, methods=["post"])
    def copy(self, request, pk=None):
        source = self.get_object()
        requested_name = str(request.data.get("name") or "").strip()
        base_name = self._normalize_copy_base_name(requested_name or f"{source.name} 副本")

        copied = None
        transient_conflicts = set()
        try:
            for _ in range(5):
                new_name = self._next_copy_name(base_name, reserved_names=transient_conflicts)
                try:
                    with transaction.atomic():
                        locked_source = FlowTemplate.objects.select_for_update().get(pk=source.pk)
                        copied = self._create_template_copy(locked_source, request.user, new_name)
                    break
                except FlowTemplate.DoesNotExist:
                    raise DjangoValidationError({"template": "源流程模板不存在或已被删除"})
                except IntegrityError:
                    transient_conflicts.add(new_name)
            if copied is None:
                raise DjangoValidationError({"name": "复制模板名称冲突，请稍后重试"})
        except DjangoValidationError as exc:
            return SycResponse.validation_error(exc.message_dict if hasattr(exc, "message_dict") else exc.messages)

        return SycResponse.success(content=self.get_serializer(copied).data, message="流程模板复制成功")

    @staticmethod
    def _current_nodes_data(template):
        return [
            {
                "uuid": node.uuid,
                "name": node.name,
                "node_type": node.node_type,
                "config": node.config or {},
                "position": node.position or {},
            }
            for node in template.nodes.all().order_by("id")
        ]

    @staticmethod
    def _current_edges_data(template):
        return [
            {
                "source_uuid": edge.source.uuid,
                "target_uuid": edge.target.uuid,
                "condition": edge.condition or {},
            }
            for edge in template.edges.select_related("source", "target").order_by("id")
        ]

    @staticmethod
    def _copy_name_max_length():
        return FlowTemplate._meta.get_field("name").max_length or 200

    @classmethod
    def _normalize_copy_base_name(cls, base_name):
        normalized = str(base_name or "").strip() or "流程模板副本"
        return normalized[: cls._copy_name_max_length()]

    @staticmethod
    def _copy_name_candidate(base_name, index):
        max_length = FlowTemplate._meta.get_field("name").max_length or 200
        suffix = "" if index == 1 else f" {index}"
        return f"{base_name[: max_length - len(suffix)]}{suffix}"

    @classmethod
    def _next_copy_name(cls, base_name, reserved_names=None):
        reserved_names = reserved_names or set()
        candidate = cls._copy_name_candidate(base_name, 1)
        index = 2
        while candidate in reserved_names or FlowTemplate.objects.filter(name=candidate).exists():
            candidate = cls._copy_name_candidate(base_name, index)
            index += 1
        return candidate

    @staticmethod
    def _create_template_copy(source, user, name):
        copied = FlowTemplate.objects.create(
            name=name,
            description=source.description,
            variables=source.variables or {},
            is_active=False,
            created_by=user,
        )
        nodes_by_source_id = {}
        for source_node in source.nodes.all().order_by("id"):
            node = FlowNode.objects.create(
                template=copied,
                uuid=source_node.uuid,
                name=source_node.name,
                node_type=source_node.node_type,
                config=source_node.config or {},
                position=source_node.position or {},
            )
            nodes_by_source_id[source_node.id] = node

        for source_edge in source.edges.select_related("source", "target").order_by("id"):
            source_node = nodes_by_source_id.get(source_edge.source_id)
            target_node = nodes_by_source_id.get(source_edge.target_id)
            if not source_node or not target_node:
                raise DjangoValidationError({"edges": "复制模板时发现异常连线"})
            FlowEdge.objects.create(
                template=copied,
                source=source_node,
                target=target_node,
                condition=source_edge.condition or {},
            )
        return copied

    @staticmethod
    def _replace_graph(template, nodes_data, edges_data, request=None):
        template = _lock_template_for_graph_change(template)

        existing_nodes = {node.uuid: node for node in template.nodes.select_for_update().order_by("id")}
        referenced_node_uuids = set(
            FlowNodeRun.objects.filter(node__template=template)
            .values_list("node__uuid", flat=True)
            .distinct()
        )

        validated_nodes = []
        seen_node_uuids = set()
        for node_data in nodes_data:
            node_data = dict(node_data)
            node_uuid = node_data.get("uuid")
            if not node_uuid:
                raise DjangoValidationError({"nodes": "节点必须包含 uuid"})
            if node_uuid in seen_node_uuids:
                raise DjangoValidationError({"nodes": f"节点 uuid 重复: {node_uuid}"})
            seen_node_uuids.add(node_uuid)

            existing_node = existing_nodes.get(node_uuid)
            serializer = FlowNodeSerializer(
                instance=existing_node,
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
            validated_nodes.append(serializer.validated_data)

        for node_uuid, node in existing_nodes.items():
            if node_uuid not in seen_node_uuids:
                if node_uuid in referenced_node_uuids:
                    raise DjangoValidationError(
                        {
                            "nodes": (
                                f"节点 {node.name} 已有执行历史，不能从模板中删除；"
                                "如需大幅调整流程，请复制为草稿后编辑。"
                            )
                        }
                    )
                node.delete()

        nodes_by_uuid = {}
        for validated_node in validated_nodes:
            node_uuid = validated_node["uuid"]
            node = existing_nodes.get(node_uuid)
            if node:
                if node_uuid in referenced_node_uuids and node.node_type != validated_node["node_type"]:
                    raise DjangoValidationError(
                        {
                            "nodes": (
                                f"节点 {node.name} 已有执行历史，不能变更节点类型；"
                                "如需替换插件，请新增节点或复制为草稿。"
                            )
                        }
                    )
                node.name = validated_node["name"]
                node.node_type = validated_node["node_type"]
                node.config = validated_node.get("config") or {}
                node.position = validated_node.get("position") or {}
                node.save(update_fields=["name", "node_type", "config", "position", "updated_at"])
            else:
                node = FlowNode.objects.create(
                    template=template,
                    uuid=node_uuid,
                    name=validated_node["name"],
                    node_type=validated_node["node_type"],
                    config=validated_node.get("config") or {},
                    position=validated_node.get("position") or {},
                )
            nodes_by_uuid[node_uuid] = node

        existing_edges = {
            (edge.source_id, edge.target_id): edge
            for edge in template.edges.select_for_update().select_related("source", "target").order_by("id")
        }
        seen_edge_keys = set()
        for edge_data in edges_data:
            edge_data = dict(edge_data)
            source_uuid = edge_data.get("source_uuid")
            target_uuid = edge_data.get("target_uuid")
            if source_uuid not in nodes_by_uuid or target_uuid not in nodes_by_uuid:
                raise DjangoValidationError({"edges": "边的 source_uuid/target_uuid 必须引用同一模板内节点"})
            source_node = nodes_by_uuid[source_uuid]
            target_node = nodes_by_uuid[target_uuid]
            edge_key = (source_node.id, target_node.id)
            if edge_key in seen_edge_keys:
                raise DjangoValidationError({"edges": f"重复连线: {source_uuid} -> {target_uuid}"})
            seen_edge_keys.add(edge_key)
            edge = existing_edges.get(edge_key)
            if edge:
                edge.condition = edge_data.get("condition") or {}
                edge.save(update_fields=["condition"])
            else:
                FlowEdge.objects.create(
                    template=template,
                    source=source_node,
                    target=target_node,
                    condition=edge_data.get("condition") or {},
                )

        for edge_key, edge in existing_edges.items():
            if edge_key not in seen_edge_keys:
                edge.delete()

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
            )
            _log_flow_run_action(
                request,
                flow_run,
                action="start_flow",
                description=f"启动流程: {template.name}",
                extra_data={
                    "input_keys": sorted((serializer.validated_data.get("inputs") or {}).keys()),
                    "new_status": flow_run.status,
                },
            )
        except ValueError as exc:
            return SycResponse.validation_error({"inputs": str(exc)})
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

    @action(detail=False, methods=["get"])
    def plugins(self, request):
        return SycResponse.success(content=list_flow_node_plugins(), message="获取流程节点插件列表成功")

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        if not serializer.is_valid():
            return SycResponse.validation_error(serializer.errors)
        try:
            with transaction.atomic():
                _lock_template_for_graph_change(serializer.validated_data["template"])
                node = serializer.save()
        except DjangoValidationError as exc:
            return SycResponse.validation_error(exc.message_dict if hasattr(exc, "message_dict") else exc.messages)
        return SycResponse.success(content=self.get_serializer(node).data, message="流程节点创建成功")

    def update(self, request, *args, **kwargs):
        partial = kwargs.pop("partial", False)
        serializer = self.get_serializer(self.get_object(), data=request.data, partial=partial)
        if not serializer.is_valid():
            return SycResponse.validation_error(serializer.errors)
        try:
            with transaction.atomic():
                instance = serializer.instance
                new_template = serializer.validated_data.get("template", instance.template)
                if new_template.id != instance.template_id:
                    raise DjangoValidationError({"template": "流程节点不能移动到其他流程模板"})
                _lock_template_for_graph_change(instance.template)
                new_node_type = serializer.validated_data.get("node_type", instance.node_type)
                if new_node_type != instance.node_type:
                    _raise_if_node_has_history(instance, "节点已有执行历史，不能变更节点类型")
                node = serializer.save()
        except DjangoValidationError as exc:
            return SycResponse.validation_error(exc.message_dict if hasattr(exc, "message_dict") else exc.messages)
        return SycResponse.success(content=self.get_serializer(node).data, message="流程节点更新成功")

    def destroy(self, request, *args, **kwargs):
        node = self.get_object()
        try:
            with transaction.atomic():
                _lock_template_for_graph_change(node.template)
                _raise_if_node_has_history(node, "节点已有执行历史，不能删除")
                self.perform_destroy(node)
        except DjangoValidationError as exc:
            return SycResponse.validation_error(exc.message_dict if hasattr(exc, "message_dict") else exc.messages)
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
        try:
            if data.get("template"):
                with transaction.atomic():
                    template = self._get_accessible_template_for_request(data["template"], request, for_update=True)
                    _raise_if_template_has_active_runs(template)
                    serializer = self.get_serializer(data=data)
                    if not serializer.is_valid():
                        return SycResponse.validation_error(serializer.errors)
                    edge = serializer.save()
            else:
                serializer = self.get_serializer(data=data)
                if not serializer.is_valid():
                    return SycResponse.validation_error(serializer.errors)
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
        try:
            if data.get("template") and int(data["template"]) != instance.template_id:
                raise DjangoValidationError({"template": "流程边不能移动到其他流程模板"})
            with transaction.atomic():
                _lock_template_for_graph_change(instance.template)
                serializer = self.get_serializer(instance, data=data, partial=partial)
                if not serializer.is_valid():
                    return SycResponse.validation_error(serializer.errors)
                edge = serializer.save()
        except DjangoValidationError as exc:
            return SycResponse.validation_error(exc.message_dict if hasattr(exc, "message_dict") else exc.messages)
        return SycResponse.success(content=self.get_serializer(edge).data, message="流程边更新成功")

    def destroy(self, request, *args, **kwargs):
        edge = self.get_object()
        try:
            with transaction.atomic():
                _lock_template_for_graph_change(edge.template)
                self.perform_destroy(edge)
        except DjangoValidationError as exc:
            return SycResponse.validation_error(exc.message_dict if hasattr(exc, "message_dict") else exc.messages)
        return SycResponse.success(message="流程边删除成功")

    @staticmethod
    def _parse_template_id(template_id):
        if template_id in (None, ""):
            return None
        try:
            return int(template_id)
        except (TypeError, ValueError):
            raise DjangoValidationError({"template": "流程模板不存在或无权操作"})

    @classmethod
    def _get_accessible_template_for_request(cls, template_id, request, for_update=False):
        parsed_template_id = cls._parse_template_id(template_id)
        if parsed_template_id is None:
            raise DjangoValidationError({"template": "流程模板不存在或无权操作"})
        template_queryset = FlowTemplate.objects.all()
        if for_update:
            template_queryset = template_queryset.select_for_update()
        if not request.user.is_superuser:
            template_queryset = template_queryset.filter(created_by=request.user)
        template = template_queryset.filter(id=parsed_template_id).first()
        if not template:
            raise DjangoValidationError({"template": "流程模板不存在或无权操作"})
        return template

    @staticmethod
    def _resolve_uuid_edge_data(data, request=None, instance=None):
        mutable = dict(data)
        template_id = mutable.get("template") if "template" in mutable else (instance.template_id if instance else None)
        errors = {}
        if template_id not in (None, "") and request:
            try:
                template = FlowEdgeViewSet._get_accessible_template_for_request(template_id, request)
                template_id = template.id
                mutable["template"] = template.id
            except DjangoValidationError:
                errors["template"] = "流程模板不存在或无权操作"
        if template_id in (None, "") and (mutable.get("source_uuid") or mutable.get("target_uuid")):
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

    @action(detail=True, methods=["get"])
    def operation_logs(self, request, pk=None):
        flow_run = self.get_object()
        queryset = (
            AuditLog.objects.filter(
                resource_type=ContentType.objects.get_for_model(FlowRun),
                resource_id=flow_run.id,
            )
            .select_related("user", "resource_type")
            .order_by("-created_at")
        )

        action_filter = request.query_params.get("action")
        if action_filter:
            queryset = queryset.filter(action=action_filter)

        serializer = AuditLogSerializer(queryset, many=True)
        return SycResponse.success(content=serializer.data, message="获取流程操作记录成功")

    @action(detail=True, methods=["post"])
    def skip_node(self, request, pk=None):
        flow_run = self.get_object()
        node_run_id = request.data.get("node_run_id")
        if not node_run_id:
            _log_flow_run_action(
                request,
                flow_run,
                action="skip_flow_node",
                description="跳过流程节点失败：缺少节点执行 ID",
                extra_data={"node_run_id": node_run_id},
                success=False,
                error_message="必须指定节点执行 ID",
            )
            return SycResponse.validation_error({"node_run_id": "必须指定节点执行 ID"})

        try:
            node_run = flow_run.node_runs.get(id=node_run_id)
        except (TypeError, ValueError, FlowNodeRun.DoesNotExist):
            _log_flow_run_action(
                request,
                flow_run,
                action="skip_flow_node",
                description="跳过流程节点失败：节点执行不存在或不属于该流程",
                extra_data={"node_run_id": node_run_id},
                success=False,
                error_message="节点执行不存在或不属于该流程",
            )
            return SycResponse.validation_error({"node_run_id": "节点执行不存在或不属于该流程"})

        try:
            previous_status = node_run.status
            flow_run = FlowRunner.skip_node(
                flow_run=flow_run,
                node_run=node_run,
                user=request.user,
                reason=request.data.get("reason", ""),
            )
            node_run.refresh_from_db()
            _log_flow_run_action(
                request,
                flow_run,
                action="skip_flow_node",
                description=f"跳过流程节点: {node_run.node.name}",
                node_run=node_run,
                extra_data={
                    "previous_status": previous_status,
                    "new_status": node_run.status,
                    "reason": request.data.get("reason", ""),
                },
            )
        except ValueError as exc:
            _log_flow_run_action(
                request,
                flow_run,
                action="skip_flow_node",
                description=f"跳过流程节点失败: {node_run.node.name}",
                node_run=node_run,
                extra_data={"reason": request.data.get("reason", "")},
                success=False,
                error_message=str(exc),
            )
            return SycResponse.validation_error({"node_run_id": str(exc)})
        except Exception as exc:
            _log_flow_run_action(
                request,
                flow_run,
                action="skip_flow_node",
                description=f"跳过流程节点异常: {node_run.node.name}",
                node_run=node_run,
                extra_data={"reason": request.data.get("reason", ""), "exception": str(exc)},
                success=False,
                error_message=str(exc),
            )
            return SycResponse.error(message=f"跳过流程节点失败: {exc}")

        return SycResponse.success(
            content=FlowRunSerializer(flow_run).data,
            message="流程节点已跳过并继续执行",
        )

    @action(detail=True, methods=["post"])
    def retry_node(self, request, pk=None):
        flow_run = self.get_object()
        node_run_id = request.data.get("node_run_id")
        if not node_run_id:
            _log_flow_run_action(
                request,
                flow_run,
                action="retry_flow_node",
                description="重试流程节点失败：缺少节点执行 ID",
                extra_data={"node_run_id": node_run_id},
                success=False,
                error_message="必须指定节点执行 ID",
            )
            return SycResponse.validation_error({"node_run_id": "必须指定节点执行 ID"})

        try:
            node_run = flow_run.node_runs.get(id=node_run_id)
        except (TypeError, ValueError, FlowNodeRun.DoesNotExist):
            _log_flow_run_action(
                request,
                flow_run,
                action="retry_flow_node",
                description="重试流程节点失败：节点执行不存在或不属于该流程",
                extra_data={"node_run_id": node_run_id},
                success=False,
                error_message="节点执行不存在或不属于该流程",
            )
            return SycResponse.validation_error({"node_run_id": "节点执行不存在或不属于该流程"})

        try:
            previous_status = node_run.status
            flow_run = FlowRunner.retry_node(
                flow_run=flow_run,
                node_run=node_run,
                user=request.user,
            )
            node_run.refresh_from_db()
            _log_flow_run_action(
                request,
                flow_run,
                action="retry_flow_node",
                description=f"重试流程节点: {node_run.node.name}",
                node_run=node_run,
                extra_data={
                    "previous_status": previous_status,
                    "new_status": node_run.status,
                },
            )
        except ValueError as exc:
            _log_flow_run_action(
                request,
                flow_run,
                action="retry_flow_node",
                description=f"重试流程节点失败: {node_run.node.name}",
                node_run=node_run,
                success=False,
                error_message=str(exc),
            )
            return SycResponse.validation_error({"node_run_id": str(exc)})
        except Exception as exc:
            _log_flow_run_action(
                request,
                flow_run,
                action="retry_flow_node",
                description=f"重试流程节点异常: {node_run.node.name}",
                node_run=node_run,
                extra_data={"exception": str(exc)},
                success=False,
                error_message=str(exc),
            )
            return SycResponse.error(message=f"重试流程节点失败: {exc}")

        return SycResponse.success(
            content=FlowRunSerializer(flow_run).data,
            message="流程节点已重试",
        )

    @action(detail=True, methods=["post"])
    def confirm_manual_node(self, request, pk=None):
        flow_run = self.get_object()
        node_run_id = request.data.get("node_run_id")
        if not node_run_id:
            _log_flow_run_action(
                request,
                flow_run,
                action="confirm_flow_node",
                description="确认人工节点失败：缺少节点执行 ID",
                extra_data={"node_run_id": node_run_id},
                success=False,
                error_message="必须指定节点执行 ID",
            )
            return SycResponse.validation_error({"node_run_id": "必须指定节点执行 ID"})

        try:
            node_run = flow_run.node_runs.get(id=node_run_id)
        except (TypeError, ValueError, FlowNodeRun.DoesNotExist):
            _log_flow_run_action(
                request,
                flow_run,
                action="confirm_flow_node",
                description="确认人工节点失败：节点执行不存在或不属于该流程",
                extra_data={"node_run_id": node_run_id},
                success=False,
                error_message="节点执行不存在或不属于该流程",
            )
            return SycResponse.validation_error({"node_run_id": "节点执行不存在或不属于该流程"})

        try:
            previous_status = node_run.status
            flow_run = FlowRunner.confirm_manual_node(
                flow_run=flow_run,
                node_run=node_run,
                user=request.user,
                remark=request.data.get("remark", ""),
            )
            node_run.refresh_from_db()
            _log_flow_run_action(
                request,
                flow_run,
                action="confirm_flow_node",
                description=f"确认人工节点: {node_run.node.name}",
                node_run=node_run,
                extra_data={
                    "previous_status": previous_status,
                    "new_status": node_run.status,
                    "remark": request.data.get("remark", ""),
                },
            )
        except ValueError as exc:
            _log_flow_run_action(
                request,
                flow_run,
                action="confirm_flow_node",
                description=f"确认人工节点失败: {node_run.node.name}",
                node_run=node_run,
                extra_data={"remark": request.data.get("remark", "")},
                success=False,
                error_message=str(exc),
            )
            return SycResponse.validation_error({"node_run_id": str(exc)})
        except Exception as exc:
            _log_flow_run_action(
                request,
                flow_run,
                action="confirm_flow_node",
                description=f"确认人工节点异常: {node_run.node.name}",
                node_run=node_run,
                extra_data={"remark": request.data.get("remark", ""), "exception": str(exc)},
                success=False,
                error_message=str(exc),
            )
            return SycResponse.error(message=f"确认流程节点失败: {exc}")

        return SycResponse.success(
            content=FlowRunSerializer(flow_run).data,
            message="人工确认节点已确认，流程继续执行",
        )

    @action(detail=True, methods=["post"])
    def cancel(self, request, pk=None):
        flow_run = self.get_object()

        try:
            previous_status = flow_run.status
            flow_run = FlowRunner.cancel_flow(flow_run=flow_run, user=request.user)
            _log_flow_run_action(
                request,
                flow_run,
                action="cancel_flow",
                description=f"取消流程: {flow_run.template.name}",
                extra_data={
                    "previous_status": previous_status,
                    "new_status": flow_run.status,
                },
            )
        except Exception as exc:
            _log_flow_run_action(
                request,
                flow_run,
                action="cancel_flow",
                description=f"取消流程异常: {flow_run.template.name}",
                extra_data={"previous_status": flow_run.status, "exception": str(exc)},
                success=False,
                error_message=str(exc),
            )
            return SycResponse.error(message=f"取消流程失败: {exc}")

        return SycResponse.success(
            content=FlowRunSerializer(flow_run).data,
            message="流程已取消",
        )

class FlowScheduleViewSet(viewsets.ModelViewSet):
    queryset = FlowSchedule.objects.all()
    serializer_class = FlowScheduleSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        queryset = super().get_queryset().select_related('template', 'created_by')
        if not self.request.user.is_superuser:
            queryset = queryset.filter(created_by=self.request.user)
        template_id = self.request.query_params.get('template')
        if template_id:
            queryset = queryset.filter(template_id=template_id)
        return queryset

    def list(self, request, *args, **kwargs):
        return SycResponse.success(content=self.get_serializer(self.get_queryset(), many=True).data, message='获取流程调度列表成功')

    def retrieve(self, request, *args, **kwargs):
        return SycResponse.success(content=self.get_serializer(self.get_object()).data, message='获取流程调度详情成功')

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        if not serializer.is_valid():
            return SycResponse.validation_error(serializer.errors)
        schedule = serializer.save(created_by=request.user, updated_by=request.user)
        return SycResponse.success(content=self.get_serializer(schedule).data, message='流程调度创建成功')

    def update(self, request, *args, **kwargs):
        serializer = self.get_serializer(self.get_object(), data=request.data, partial=kwargs.pop('partial', False))
        if not serializer.is_valid():
            return SycResponse.validation_error(serializer.errors)
        schedule = serializer.save(updated_by=request.user)
        return SycResponse.success(content=self.get_serializer(schedule).data, message='流程调度更新成功')

    @action(detail=True, methods=['get'])
    def runs(self, request, pk=None):
        schedule = self.get_object()
        schedule_runs = schedule.runs.select_related('flow_run').all()
        return SycResponse.success(
            content=FlowScheduleRunSerializer(schedule_runs, many=True).data,
            message='获取流程调度运行历史成功',
        )
    def destroy(self, request, *args, **kwargs):
        self.get_object().delete()
        return SycResponse.success(message='流程调度删除成功')