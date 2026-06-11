import copy
from collections import defaultdict, deque

from django.db import transaction
from django.utils import timezone

from apps.agents.execution_service import AgentExecutionService
from apps.executor.models import ExecutionRecord
from apps.executor.services import ExecutionRecordService
from apps.hosts.models import Host
from apps.job_templates.models import ExecutionPlan

from .models import FlowNode, FlowNodeRun, FlowRun, FlowTemplate
from .validators import get_execution_plan_resource_permission_error, get_file_source_errors


class FlowRunner:
    """Internal DAG runner for flow templates."""

    CONTROL_INPUT_KEYS = frozenset(
        {
            "__execution_scope",
            "__selected_node_uuids",
            "__node_overrides",
            "__parent_flow_run_id",
            "__parent_node_run_id",
            "__parent_agent_server_id",
            "__flow_template_stack",
            "__defer_sub_process_parent_notify",
        }
    )

    @classmethod
    def start(cls, template: FlowTemplate, user, inputs=None, agent_server_id=None) -> FlowRun:
        flow_run = FlowRun.objects.create(
            template=template,
            status=FlowRun.Status.RUNNING,
            started_by=user,
            inputs=inputs or {},
            started_at=timezone.now(),
        )

        try:
            return cls._continue_flow(flow_run, user, agent_server_id=agent_server_id)
        except Exception as exc:
            flow_run.mark_finished(FlowRun.Status.FAILED, str(exc))
            raise

    @classmethod
    def skip_node(cls, flow_run: FlowRun, node_run: FlowNodeRun, user=None, reason="", agent_server_id=None) -> FlowRun:
        with transaction.atomic():
            flow_run = FlowRun.objects.select_for_update().select_related("started_by").get(pk=flow_run.pk)
            if flow_run.status in (FlowRun.Status.SUCCESS, FlowRun.Status.CANCELLED):
                raise ValueError(f"cannot skip node in {flow_run.status} flow")

            node_run = (
                FlowNodeRun.objects.select_for_update()
                .select_related("node", "execution_record")
                .get(pk=node_run.pk, flow_run=flow_run)
            )
            if node_run.status not in (FlowRun.Status.FAILED, FlowRun.Status.PAUSED):
                raise ValueError(f"cannot skip {node_run.status} node")
            if agent_server_id is None and node_run.execution_record_id:
                agent_server_id = (node_run.execution_record.execution_parameters or {}).get("agent_server_id")

            outputs = dict(node_run.outputs or {})
            outputs.update(
                {
                    "skipped": True,
                    "skip_reason": reason or "",
                    "skipped_at": timezone.now().isoformat(),
                }
            )
            node_run.status = FlowRun.Status.SUCCESS
            node_run.outputs = outputs
            node_run.error_message = ""
            node_run.finished_at = timezone.now()
            node_run.save(update_fields=["status", "outputs", "error_message", "finished_at"])

            flow_run.status = FlowRun.Status.RUNNING
            flow_run.error_message = ""
            flow_run.finished_at = None
            flow_run.save(update_fields=["status", "error_message", "finished_at"])

        return cls._continue_flow(flow_run, user or flow_run.started_by, agent_server_id=agent_server_id)

    @classmethod
    def retry_node(cls, flow_run: FlowRun, node_run: FlowNodeRun, user=None, agent_server_id=None) -> FlowRun:
        with transaction.atomic():
            flow_run = FlowRun.objects.select_for_update().select_related("started_by").get(pk=flow_run.pk)
            if flow_run.status == FlowRun.Status.CANCELLED:
                raise ValueError("cannot retry node in cancelled flow")

            node_run = (
                FlowNodeRun.objects.select_for_update()
                .select_related("node", "execution_record")
                .get(pk=node_run.pk, flow_run=flow_run)
            )
            if node_run.status not in (FlowRun.Status.FAILED, FlowRun.Status.PAUSED):
                raise ValueError(f"cannot retry {node_run.status} node")
            if agent_server_id is None and node_run.execution_record_id:
                agent_server_id = (node_run.execution_record.execution_parameters or {}).get("agent_server_id")

            node_run.status = FlowRun.Status.RUNNING
            node_run.outputs = {}
            node_run.error_message = ""
            node_run.execution_record = None
            node_run.started_at = timezone.now()
            node_run.finished_at = None
            node_run.save(
                update_fields=[
                    "status",
                    "outputs",
                    "error_message",
                    "execution_record",
                    "started_at",
                    "finished_at",
                ]
            )

            flow_run.status = FlowRun.Status.RUNNING
            flow_run.error_message = ""
            flow_run.finished_at = None
            flow_run.save(update_fields=["status", "error_message", "finished_at"])

        cls._dispatch_node_run(node_run, user or flow_run.started_by, agent_server_id=agent_server_id)
        node_run.refresh_from_db()
        if node_run.status == FlowRun.Status.FAILED:
            cls._apply_failed_node_policy(flow_run, node_run)
            flow_run.refresh_from_db()
            return flow_run
        if node_run.status == FlowRun.Status.PAUSED:
            flow_run.status = FlowRun.Status.PAUSED
            flow_run.save(update_fields=["status"])
            return flow_run
        return cls._continue_flow(flow_run, user or flow_run.started_by, agent_server_id=agent_server_id)

    @classmethod
    def confirm_manual_node(
        cls,
        flow_run: FlowRun,
        node_run: FlowNodeRun,
        user=None,
        remark="",
        agent_server_id=None,
    ) -> FlowRun:
        with transaction.atomic():
            flow_run = FlowRun.objects.select_for_update().select_related("started_by").get(pk=flow_run.pk)
            if flow_run.status in (FlowRun.Status.SUCCESS, FlowRun.Status.FAILED, FlowRun.Status.CANCELLED):
                raise ValueError(f"cannot confirm node in {flow_run.status} flow")

            node_run = (
                FlowNodeRun.objects.select_for_update()
                .select_related("node")
                .get(pk=node_run.pk, flow_run=flow_run)
            )
            if node_run.node.node_type != FlowNode.NodeType.MANUAL:
                raise ValueError("only manual nodes can be confirmed")
            if node_run.status != FlowRun.Status.PAUSED:
                raise ValueError(f"cannot confirm {node_run.status} manual node")
            if agent_server_id is None:
                agent_server_id = (node_run.outputs or {}).get("agent_server_id")

            actor = user or flow_run.started_by
            outputs = dict(node_run.outputs or {})
            outputs.update(
                {
                    "manual": True,
                    "confirmed": True,
                    "confirmed_by": getattr(actor, "username", "") or str(getattr(actor, "id", "")),
                    "confirmed_by_id": getattr(actor, "id", None),
                    "confirmed_at": timezone.now().isoformat(),
                    "confirm_remark": remark or "",
                }
            )
            node_run.status = FlowRun.Status.SUCCESS
            node_run.outputs = outputs
            node_run.error_message = ""
            node_run.finished_at = timezone.now()
            node_run.save(update_fields=["status", "outputs", "error_message", "finished_at"])

            flow_run.status = FlowRun.Status.RUNNING
            flow_run.error_message = ""
            flow_run.finished_at = None
            flow_run.save(update_fields=["status", "error_message", "finished_at"])

        return cls._continue_flow(flow_run, user or flow_run.started_by, agent_server_id=agent_server_id)

    @classmethod
    def cancel_flow(cls, flow_run: FlowRun, user=None, notify_parent=True) -> FlowRun:
        should_notify_parent = False
        with transaction.atomic():
            flow_run = FlowRun.objects.select_for_update().get(pk=flow_run.pk)
            if flow_run.status in (FlowRun.Status.SUCCESS, FlowRun.Status.FAILED, FlowRun.Status.CANCELLED):
                return flow_run

            active_node_runs = list(
                FlowNodeRun.objects.select_for_update()
                .select_related("node", "execution_record")
                .filter(flow_run=flow_run, status__in=[FlowRun.Status.PENDING, FlowRun.Status.RUNNING, FlowRun.Status.PAUSED])
            )

            now = timezone.now()
            for node_run in active_node_runs:
                if node_run.node.node_type == FlowNode.NodeType.SUB_PROCESS:
                    cls._cancel_child_flow_for_sub_process(node_run, user=user)

                node_run.status = FlowRun.Status.CANCELLED
                node_run.error_message = "flow cancelled"
                node_run.finished_at = now
                node_run.save(update_fields=["status", "error_message", "finished_at"])

                execution_record = node_run.execution_record
                if execution_record and execution_record.status in ("pending", "running"):
                    agent_server_id = (execution_record.execution_parameters or {}).get("agent_server_id")
                    if agent_server_id:
                        AgentExecutionService.cancel_task_via_agent(
                            execution_record=execution_record,
                            agent_server_id=agent_server_id,
                        )
                    execution_record.status = "cancelled"
                    execution_record.error_message = "flow cancelled"
                    execution_record.finished_at = now
                    execution_record.save(update_fields=["status", "error_message", "finished_at"])

            flow_run.status = FlowRun.Status.CANCELLED
            flow_run.error_message = "flow cancelled"
            flow_run.finished_at = now
            flow_run.save(update_fields=["status", "error_message", "finished_at"])
            should_notify_parent = notify_parent and cls._has_parent_sub_process(flow_run)

        if should_notify_parent:
            return cls._finalize_parent_sub_process(flow_run, agent_server_id=cls._parent_agent_server_id(flow_run)) or flow_run
        return flow_run

    @classmethod
    def _continue_flow(cls, flow_run: FlowRun, user, agent_server_id=None) -> FlowRun:
        if flow_run.status in (FlowRun.Status.SUCCESS, FlowRun.Status.FAILED, FlowRun.Status.CANCELLED):
            return flow_run
        if flow_run.status != FlowRun.Status.RUNNING:
            flow_run.status = FlowRun.Status.RUNNING
            flow_run.finished_at = None
            flow_run.save(update_fields=["status", "finished_at"])

        node_runs_by_node_id = {node_run.node_id: node_run for node_run in flow_run.node_runs.all()}
        incoming_edges_by_target = cls._incoming_edges_by_target(flow_run.template)
        selected_node_uuids = cls._selected_node_uuids(flow_run.inputs)
        has_blocking_nodes = False
        for node in cls._topological_nodes(flow_run.template):
            if selected_node_uuids is not None and node.uuid not in selected_node_uuids:
                continue

            node_run = node_runs_by_node_id.get(node.id)
            if (
                selected_node_uuids is None
                and node_run is None
                and not cls._is_node_reachable(node, incoming_edges_by_target, node_runs_by_node_id)
            ):
                continue
            if node_run and node_run.status == FlowRun.Status.SUCCESS:
                continue
            if node_run and node_run.status == FlowRun.Status.PAUSED:
                has_blocking_nodes = True
                continue
            if node_run and node_run.status in (FlowRun.Status.PENDING, FlowRun.Status.RUNNING):
                has_blocking_nodes = True
                continue
            if node_run and node_run.status == FlowRun.Status.FAILED:
                if cls._apply_failed_node_policy(flow_run, node_run) == "continue":
                    continue
                cls._notify_parent_if_terminal(flow_run, agent_server_id=agent_server_id)
                return flow_run
            if node_run and node_run.status == FlowRun.Status.CANCELLED:
                if cls._apply_failed_node_policy(flow_run, node_run) == "continue":
                    continue
                cls._notify_parent_if_terminal(flow_run, agent_server_id=agent_server_id)
                return flow_run

            if node_run is None:
                node_run = cls._execute_node(
                    flow_run,
                    node,
                    user,
                    agent_server_id=agent_server_id,
                    config=cls._node_config_for_run(node, flow_run.inputs),
                )
                node_runs_by_node_id[node.id] = node_run

            if node_run.status == FlowRun.Status.FAILED:
                if cls._apply_failed_node_policy(flow_run, node_run) == "continue":
                    continue
                cls._notify_parent_if_terminal(flow_run, agent_server_id=agent_server_id)
                return flow_run
            if node_run.status == FlowRun.Status.CANCELLED:
                if cls._apply_failed_node_policy(flow_run, node_run) == "continue":
                    continue
                cls._notify_parent_if_terminal(flow_run, agent_server_id=agent_server_id)
                return flow_run
            if node_run.status == FlowRun.Status.PAUSED:
                has_blocking_nodes = True
                continue
            if node_run.status in (FlowRun.Status.PENDING, FlowRun.Status.RUNNING):
                has_blocking_nodes = True
                continue

        if has_blocking_nodes:
            flow_run.status = FlowRun.Status.PAUSED
            flow_run.finished_at = None
            flow_run.save(update_fields=["status", "finished_at"])
            return flow_run

        flow_run.mark_finished(FlowRun.Status.SUCCESS)
        cls._notify_parent_if_terminal(flow_run, agent_server_id=agent_server_id)
        return flow_run

    @classmethod
    def handle_execution_record_finished(cls, execution_record: ExecutionRecord):
        terminal_failed_statuses = {"failed", "cancelled", "timeout"}
        should_continue = False
        flow_run = None
        agent_server_id = None

        with transaction.atomic():
            execution_record = ExecutionRecord.objects.select_for_update().get(pk=execution_record.pk)
            related_object = execution_record.related_object
            if not isinstance(related_object, FlowNodeRun):
                return None

            node_run = (
                FlowNodeRun.objects.select_for_update()
                .select_related("flow_run", "flow_run__started_by")
                .get(pk=related_object.pk)
            )
            flow_run = FlowRun.objects.select_for_update().get(pk=node_run.flow_run_id)
            if flow_run.status != FlowRun.Status.PAUSED or node_run.status not in (
                FlowRun.Status.PAUSED,
                FlowRun.Status.RUNNING,
            ):
                return flow_run

            if execution_record.status == "success":
                node_run.status = FlowRun.Status.SUCCESS
                node_run.outputs = execution_record.execution_results or {}
                node_run.error_message = ""
                node_run.finished_at = timezone.now()
                node_run.execution_record = execution_record
                node_run.save(
                    update_fields=[
                        "status",
                        "outputs",
                        "error_message",
                        "finished_at",
                        "execution_record",
                    ]
                )
                should_continue = True
                agent_server_id = (execution_record.execution_parameters or {}).get("agent_server_id")
            elif execution_record.status in terminal_failed_statuses:
                error_message = execution_record.error_message or f"job_plan node {execution_record.status}"
                node_run.status = FlowRun.Status.FAILED
                node_run.outputs = execution_record.execution_results or {}
                node_run.error_message = error_message
                node_run.finished_at = timezone.now()
                node_run.execution_record = execution_record
                node_run.save(
                    update_fields=[
                        "status",
                        "outputs",
                        "error_message",
                        "finished_at",
                        "execution_record",
                    ]
                )
                policy_result = cls._apply_failed_node_policy(flow_run, node_run)
                if policy_result == "continue":
                    should_continue = True
                    agent_server_id = (execution_record.execution_parameters or {}).get("agent_server_id")

        if should_continue:
            return cls._continue_flow(flow_run, flow_run.started_by, agent_server_id=agent_server_id)

        if flow_run and flow_run.status in (FlowRun.Status.FAILED, FlowRun.Status.CANCELLED):
            cls._notify_parent_if_terminal(flow_run, agent_server_id=agent_server_id)

        return flow_run

    @staticmethod
    def _topological_nodes(template: FlowTemplate):
        nodes = list(template.nodes.all().order_by("id"))
        by_id = {node.id: node for node in nodes}
        incoming_count = {node.id: 0 for node in nodes}
        outgoing = defaultdict(list)

        for edge in template.edges.select_related("source", "target"):
            if edge.source_id not in by_id or edge.target_id not in by_id:
                raise ValueError("flow edge nodes must belong to the template")
            outgoing[edge.source_id].append(edge.target_id)
            incoming_count[edge.target_id] += 1

        queue = deque([node_id for node_id, count in incoming_count.items() if count == 0])
        ordered = []

        while queue:
            node_id = queue.popleft()
            ordered.append(by_id[node_id])
            for target_id in outgoing[node_id]:
                incoming_count[target_id] -= 1
                if incoming_count[target_id] == 0:
                    queue.append(target_id)

        if len(ordered) != len(nodes):
            raise ValueError("flow graph contains cycle")

        return ordered

    @staticmethod
    def _incoming_edges_by_target(template: FlowTemplate):
        edges_by_target = defaultdict(list)
        for edge in template.edges.select_related("source", "target").order_by("id"):
            edges_by_target[edge.target_id].append(edge)
        return edges_by_target

    @classmethod
    def _is_node_reachable(cls, node: FlowNode, incoming_edges_by_target, node_runs_by_node_id):
        incoming_edges = incoming_edges_by_target.get(node.id, [])
        if not incoming_edges:
            return True
        if node.node_type == FlowNode.NodeType.JOIN:
            return cls._is_join_ready(incoming_edges, incoming_edges_by_target, node_runs_by_node_id)

        for edge in incoming_edges:
            source_run = node_runs_by_node_id.get(edge.source_id)
            if not source_run:
                continue
            if source_run.node.node_type == FlowNode.NodeType.CONDITION:
                if source_run.status == FlowRun.Status.SUCCESS and cls._is_condition_edge_selected(edge, source_run):
                    return True
                continue
            if source_run.status == FlowRun.Status.SUCCESS:
                return True
            if cls._is_ignored_failed_or_cancelled(source_run):
                return True

        return False

    @classmethod
    def _is_join_ready(cls, incoming_edges, incoming_edges_by_target, node_runs_by_node_id):
        active_edges = []
        for edge in incoming_edges:
            if not cls._is_incoming_edge_active(edge, incoming_edges_by_target, node_runs_by_node_id):
                continue
            active_edges.append(edge)
            source_run = node_runs_by_node_id.get(edge.source_id)
            if not source_run or not cls._is_upstream_complete_for_join(edge, source_run):
                return False
        return bool(active_edges)

    @classmethod
    def _is_incoming_edge_active(cls, edge, incoming_edges_by_target, node_runs_by_node_id):
        source_run = node_runs_by_node_id.get(edge.source_id)
        if source_run:
            if source_run.node.node_type == FlowNode.NodeType.CONDITION:
                return cls._is_condition_edge_selected(edge, source_run)
            return True
        return cls._is_node_reachable(edge.source, incoming_edges_by_target, node_runs_by_node_id)

    @staticmethod
    def _is_condition_edge_selected(edge, source_run: FlowNodeRun):
        selected_node_ids = set((source_run.outputs or {}).get("selected_node_ids") or [])
        selected_node_uuids = set((source_run.outputs or {}).get("selected_node_uuids") or [])
        return edge.target_id in selected_node_ids or edge.target.uuid in selected_node_uuids

    @classmethod
    def _is_upstream_complete_for_join(cls, edge, source_run: FlowNodeRun):
        if source_run.node.node_type == FlowNode.NodeType.CONDITION:
            return source_run.status == FlowRun.Status.SUCCESS and cls._is_condition_edge_selected(edge, source_run)
        if source_run.status == FlowRun.Status.SUCCESS:
            return True
        return cls._is_ignored_failed_or_cancelled(source_run)

    @staticmethod
    def _is_ignored_failed_or_cancelled(source_run: FlowNodeRun):
        return source_run.status in (FlowRun.Status.FAILED, FlowRun.Status.CANCELLED) and (
            source_run.inputs or {}
        ).get("failure_policy") == "ignore"

    @classmethod
    def _selected_node_uuids(cls, inputs):
        inputs = inputs or {}
        if inputs.get("__execution_scope") != "selected":
            return None
        selected = inputs.get("__selected_node_uuids") or []
        return {str(node_uuid) for node_uuid in selected if node_uuid}

    @classmethod
    def _node_config_for_run(cls, node: FlowNode, inputs):
        config = copy.deepcopy(node.config or {})
        overrides = (inputs or {}).get("__node_overrides") or {}
        if not isinstance(overrides, dict):
            return config

        override = overrides.get(node.uuid) or overrides.get(str(node.id))
        if isinstance(override, dict):
            config.update(copy.deepcopy(override))
        return config

    @classmethod
    def _business_inputs(cls, inputs):
        return {key: value for key, value in (inputs or {}).items() if key not in cls.CONTROL_INPUT_KEYS}

    @classmethod
    def _apply_failed_node_policy(cls, flow_run: FlowRun, node_run: FlowNodeRun):
        policy = (node_run.inputs or {}).get("failure_policy") or "stop"
        if policy == "ignore":
            return "continue"

        if policy == "pause":
            node_run.status = FlowRun.Status.PAUSED
            node_run.finished_at = None
            node_run.save(update_fields=["status", "finished_at"])
            flow_run.status = FlowRun.Status.PAUSED
            flow_run.error_message = node_run.error_message
            flow_run.finished_at = None
            flow_run.save(update_fields=["status", "error_message", "finished_at"])
            return "pause"

        flow_run.mark_finished(FlowRun.Status.FAILED, node_run.error_message)
        return "stop"

    @classmethod
    def _execute_node(cls, flow_run: FlowRun, node: FlowNode, user, agent_server_id=None, config=None) -> FlowNodeRun:
        config = copy.deepcopy(config if config is not None else node.config or {})
        node_run = FlowNodeRun.objects.create(
            flow_run=flow_run,
            node=node,
            status=FlowRun.Status.RUNNING,
            inputs=config,
            started_at=timezone.now(),
        )

        return cls._dispatch_node_run(node_run, user, agent_server_id=agent_server_id)

    @classmethod
    def _dispatch_node_run(cls, node_run: FlowNodeRun, user, agent_server_id=None) -> FlowNodeRun:
        node = node_run.node
        if node.node_type in (
            FlowNode.NodeType.SCRIPT,
            FlowNode.NodeType.FILE_TRANSFER,
            FlowNode.NodeType.JOB_PLAN,
            FlowNode.NodeType.MANUAL,
            FlowNode.NodeType.CONDITION,
            FlowNode.NodeType.PARALLEL,
            FlowNode.NodeType.JOIN,
            FlowNode.NodeType.SUB_PROCESS,
        ):
            try:
                if node.node_type == FlowNode.NodeType.SUB_PROCESS:
                    return cls._execute_sub_process_node(node_run, user, agent_server_id=agent_server_id)
                if node.node_type in (FlowNode.NodeType.PARALLEL, FlowNode.NodeType.JOIN):
                    return cls._execute_gateway_node(node_run, agent_server_id=agent_server_id)
                if node.node_type == FlowNode.NodeType.CONDITION:
                    return cls._execute_condition_node(node_run, user, agent_server_id=agent_server_id)
                if node.node_type == FlowNode.NodeType.MANUAL:
                    return cls._execute_manual_node(node_run, user, agent_server_id=agent_server_id)
                if node.node_type == FlowNode.NodeType.SCRIPT:
                    return cls._execute_script_node(node_run, user, agent_server_id=agent_server_id)
                if node.node_type == FlowNode.NodeType.FILE_TRANSFER:
                    return cls._execute_file_transfer_node(node_run, user, agent_server_id=agent_server_id)
                return cls._execute_job_plan_node(node_run, user, agent_server_id=agent_server_id)
            except Exception as exc:
                node_run.status = FlowRun.Status.FAILED
                node_run.error_message = str(exc)
                node_run.finished_at = timezone.now()
                node_run.save(update_fields=["status", "error_message", "finished_at"])
                if node_run.execution_record_id:
                    node_run.execution_record.status = "failed"
                    node_run.execution_record.error_message = str(exc)
                    node_run.execution_record.finished_at = timezone.now()
                    node_run.execution_record.save(update_fields=["status", "error_message", "finished_at"])
                raise

        node_run.status = FlowRun.Status.FAILED
        node_run.error_message = f"unsupported node type: {node.node_type}"
        node_run.finished_at = timezone.now()
        node_run.save(update_fields=["status", "error_message", "finished_at"])
        return node_run

    @classmethod
    def _execute_sub_process_node(cls, node_run: FlowNodeRun, user, agent_server_id=None) -> FlowNodeRun:
        config = node_run.inputs or {}
        child_template = cls._get_sub_process_template_or_fail(node_run, config, user)
        if child_template is None:
            return node_run

        stack = cls._flow_template_stack(node_run.flow_run)
        if child_template.id in stack:
            cls._fail_node_run(
                node_run,
                f"sub_process recursion detected for template id {child_template.id}",
            )
            return node_run

        child_inputs = {}
        if config.get("inherit_inputs", True):
            child_inputs.update(copy.deepcopy(cls._business_inputs(node_run.flow_run.inputs)))
        child_inputs.update(copy.deepcopy(config.get("inputs") or {}))
        child_inputs.update(
            {
                "__parent_flow_run_id": node_run.flow_run_id,
                "__parent_node_run_id": node_run.id,
                "__parent_agent_server_id": agent_server_id,
                "__flow_template_stack": stack,
                "__defer_sub_process_parent_notify": True,
            }
        )

        child_flow_run = cls.start(
            template=child_template,
            user=user,
            inputs=child_inputs,
            agent_server_id=agent_server_id,
        )
        child_flow_run.refresh_from_db()
        if child_flow_run.status not in (FlowRun.Status.SUCCESS, FlowRun.Status.FAILED, FlowRun.Status.CANCELLED):
            updated_inputs = dict(child_flow_run.inputs or {})
            updated_inputs.pop("__defer_sub_process_parent_notify", None)
            child_flow_run.inputs = updated_inputs
            child_flow_run.save(update_fields=["inputs"])

        return cls._sync_sub_process_node_with_child(
            node_run=node_run,
            child_flow_run=child_flow_run,
            agent_server_id=agent_server_id,
        )

    @classmethod
    def _get_sub_process_template_or_fail(cls, node_run: FlowNodeRun, config, user):
        template_id = config.get("template_id")
        if not template_id:
            cls._fail_node_run(node_run, "sub_process node requires template_id")
            return None

        child_template = FlowTemplate.objects.filter(id=template_id).first()
        if not child_template:
            cls._fail_node_run(node_run, "sub_process template not found")
            return None
        if not child_template.is_active:
            cls._fail_node_run(node_run, "sub_process template is inactive")
            return None
        if child_template.id == node_run.flow_run.template_id:
            cls._fail_node_run(node_run, "sub_process cannot reference current template")
            return None
        if not user.is_superuser and child_template.created_by_id != user.id:
            cls._fail_node_run(node_run, "permission denied for sub_process template")
            return None
        if "inputs" in config and not isinstance(config.get("inputs"), dict):
            cls._fail_node_run(node_run, "sub_process inputs must be an object")
            return None
        return child_template

    @staticmethod
    def _fail_node_run(node_run: FlowNodeRun, error_message):
        node_run.status = FlowRun.Status.FAILED
        node_run.error_message = error_message
        node_run.finished_at = timezone.now()
        node_run.save(update_fields=["status", "error_message", "finished_at"])

    @classmethod
    def _flow_template_stack(cls, flow_run: FlowRun):
        raw_stack = (flow_run.inputs or {}).get("__flow_template_stack") or []
        stack = []
        for template_id in raw_stack:
            try:
                stack.append(int(template_id))
            except (TypeError, ValueError):
                continue
        if flow_run.template_id not in stack:
            stack.append(flow_run.template_id)
        return stack

    @classmethod
    def _sync_sub_process_node_with_child(cls, node_run: FlowNodeRun, child_flow_run: FlowRun, agent_server_id=None):
        outputs = dict(node_run.outputs or {})
        outputs.update(
            {
                "sub_process": True,
                "child_flow_run_id": child_flow_run.id,
                "child_template_id": child_flow_run.template_id,
                "child_status": child_flow_run.status,
                "agent_server_id": agent_server_id,
            }
        )
        node_run.outputs = outputs

        if child_flow_run.status == FlowRun.Status.SUCCESS:
            node_run.status = FlowRun.Status.SUCCESS
            node_run.error_message = ""
            node_run.finished_at = timezone.now()
        elif child_flow_run.status == FlowRun.Status.CANCELLED:
            node_run.status = FlowRun.Status.CANCELLED
            node_run.error_message = child_flow_run.error_message or "sub_process child flow cancelled"
            node_run.finished_at = timezone.now()
        elif child_flow_run.status == FlowRun.Status.FAILED:
            node_run.status = FlowRun.Status.FAILED
            node_run.error_message = child_flow_run.error_message or "sub_process child flow failed"
            node_run.finished_at = timezone.now()
        else:
            node_run.status = FlowRun.Status.PAUSED
            node_run.error_message = ""
            node_run.finished_at = None

        node_run.save(update_fields=["status", "outputs", "error_message", "finished_at"])
        return node_run

    @classmethod
    def _has_parent_sub_process(cls, flow_run: FlowRun):
        inputs = flow_run.inputs or {}
        return bool(inputs.get("__parent_flow_run_id") and inputs.get("__parent_node_run_id"))

    @staticmethod
    def _parent_agent_server_id(flow_run: FlowRun):
        return (flow_run.inputs or {}).get("__parent_agent_server_id")

    @classmethod
    def _notify_parent_if_terminal(cls, flow_run: FlowRun, agent_server_id=None):
        if flow_run.status not in (FlowRun.Status.SUCCESS, FlowRun.Status.FAILED, FlowRun.Status.CANCELLED):
            return None
        if (flow_run.inputs or {}).get("__defer_sub_process_parent_notify"):
            return None
        if not cls._has_parent_sub_process(flow_run):
            return None
        return cls._finalize_parent_sub_process(flow_run, agent_server_id=agent_server_id)

    @classmethod
    def _finalize_parent_sub_process(cls, child_flow_run: FlowRun, agent_server_id=None):
        parent_node_run = None
        parent_flow_run = None
        should_continue = False

        with transaction.atomic():
            child_flow_run = FlowRun.objects.select_for_update().get(pk=child_flow_run.pk)
            parent_node_run_id = (child_flow_run.inputs or {}).get("__parent_node_run_id")
            if not parent_node_run_id:
                return None
            try:
                parent_node_run = (
                    FlowNodeRun.objects.select_for_update()
                    .select_related("node", "flow_run", "flow_run__started_by")
                    .get(pk=parent_node_run_id)
                )
            except FlowNodeRun.DoesNotExist:
                return None
            if parent_node_run.node.node_type != FlowNode.NodeType.SUB_PROCESS:
                return parent_node_run.flow_run
            if parent_node_run.status in (FlowRun.Status.SUCCESS, FlowRun.Status.FAILED, FlowRun.Status.CANCELLED):
                return parent_node_run.flow_run

            parent_flow_run = FlowRun.objects.select_for_update().get(pk=parent_node_run.flow_run_id)
            cls._sync_sub_process_node_with_child(
                node_run=parent_node_run,
                child_flow_run=child_flow_run,
                agent_server_id=agent_server_id or cls._parent_agent_server_id(child_flow_run),
            )
            parent_node_run.refresh_from_db()

            if parent_node_run.status == FlowRun.Status.SUCCESS:
                parent_flow_run.status = FlowRun.Status.RUNNING
                parent_flow_run.error_message = ""
                parent_flow_run.finished_at = None
                parent_flow_run.save(update_fields=["status", "error_message", "finished_at"])
                should_continue = True
            elif parent_node_run.status in (FlowRun.Status.FAILED, FlowRun.Status.CANCELLED):
                policy_result = cls._apply_failed_node_policy(parent_flow_run, parent_node_run)
                should_continue = policy_result == "continue"
            elif parent_node_run.status == FlowRun.Status.PAUSED:
                parent_flow_run.status = FlowRun.Status.PAUSED
                parent_flow_run.finished_at = None
                parent_flow_run.save(update_fields=["status", "finished_at"])

        if should_continue:
            return cls._continue_flow(
                parent_flow_run,
                parent_flow_run.started_by,
                agent_server_id=agent_server_id or cls._parent_agent_server_id(child_flow_run),
            )
        return parent_flow_run

    @classmethod
    def _cancel_child_flow_for_sub_process(cls, node_run: FlowNodeRun, user=None):
        child_flow_run_id = (node_run.outputs or {}).get("child_flow_run_id")
        if not child_flow_run_id:
            return None
        child_flow_run = FlowRun.objects.filter(id=child_flow_run_id).first()
        if not child_flow_run or child_flow_run.status in (
            FlowRun.Status.SUCCESS,
            FlowRun.Status.FAILED,
            FlowRun.Status.CANCELLED,
        ):
            return child_flow_run
        return cls.cancel_flow(child_flow_run, user=user, notify_parent=False)

    @staticmethod
    def _execute_gateway_node(node_run: FlowNodeRun, agent_server_id=None) -> FlowNodeRun:
        node_run.status = FlowRun.Status.SUCCESS
        node_run.outputs = {
            "gateway": True,
            "gateway_type": node_run.node.node_type,
            "agent_server_id": agent_server_id,
        }
        node_run.error_message = ""
        node_run.finished_at = timezone.now()
        node_run.save(update_fields=["status", "outputs", "error_message", "finished_at"])
        return node_run

    @staticmethod
    def _execute_manual_node(node_run: FlowNodeRun, user, agent_server_id=None) -> FlowNodeRun:
        node_run.status = FlowRun.Status.PAUSED
        node_run.outputs = {
            "manual": True,
            "confirmed": False,
            "instructions": (node_run.inputs or {}).get("instructions", ""),
            "agent_server_id": agent_server_id,
        }
        node_run.error_message = ""
        node_run.finished_at = None
        node_run.save(update_fields=["status", "outputs", "error_message", "finished_at"])
        return node_run

    @classmethod
    def _execute_condition_node(cls, node_run: FlowNodeRun, user, agent_server_id=None) -> FlowNodeRun:
        outgoing_edges = list(node_run.node.out_edges.select_related("target").order_by("id"))
        matched_edges = []
        default_edges = []

        for edge in outgoing_edges:
            condition = edge.condition or {}
            if condition.get("default") is True:
                default_edges.append(edge)
                continue
            if cls._evaluate_edge_condition(node_run.flow_run, condition):
                matched_edges.append(edge)

        selected_edges = matched_edges or default_edges
        node_run.status = FlowRun.Status.SUCCESS
        node_run.outputs = {
            "condition": True,
            "matched_count": len(matched_edges),
            "default_used": bool(default_edges and not matched_edges),
            "selected_node_ids": [edge.target_id for edge in selected_edges],
            "selected_node_uuids": [edge.target.uuid for edge in selected_edges],
            "selected_edges": [
                {
                    "source_uuid": edge.source.uuid,
                    "target_uuid": edge.target.uuid,
                    "condition": edge.condition or {},
                }
                for edge in selected_edges
            ],
            "agent_server_id": agent_server_id,
        }
        node_run.error_message = ""
        node_run.finished_at = timezone.now()
        node_run.save(update_fields=["status", "outputs", "error_message", "finished_at"])
        return node_run

    @classmethod
    def _evaluate_edge_condition(cls, flow_run: FlowRun, condition):
        if not condition:
            return False

        variable = condition.get("variable") or condition.get("left") or condition.get("key")
        operator = condition.get("operator") or condition.get("op") or "truthy"
        actual = cls._resolve_condition_value(flow_run, variable)
        expected = condition.get("value", condition.get("right"))

        if operator in ("truthy", "is_true"):
            return bool(actual)
        if operator in ("falsy", "is_false"):
            return not bool(actual)
        if operator in ("empty", "is_empty"):
            return actual in (None, "", [], {})
        if operator in ("not_empty", "is_not_empty"):
            return actual not in (None, "", [], {})
        if operator in ("eq", "equals", "=="):
            return actual == expected
        if operator in ("ne", "not_equals", "!="):
            return actual != expected
        if operator == "contains":
            return cls._contains(actual, expected)
        if operator == "not_contains":
            return not cls._contains(actual, expected)
        if operator in ("gt", "gte", "lt", "lte", ">", ">=", "<", "<="):
            return cls._compare(actual, expected, operator)
        return False

    @classmethod
    def _resolve_condition_value(cls, flow_run: FlowRun, variable):
        if not variable:
            return None

        path = str(variable).strip()
        if path.startswith("inputs."):
            return cls._get_path(cls._business_inputs(flow_run.inputs), path.removeprefix("inputs."))
        if path.startswith("outputs."):
            parts = path.split(".", 2)
            if len(parts) < 3:
                return None
            node_run = flow_run.node_runs.select_related("node").filter(node__uuid=parts[1]).first()
            if not node_run:
                return None
            return cls._get_path(node_run.outputs or {}, parts[2])
        return cls._get_path(cls._business_inputs(flow_run.inputs), path)

    @staticmethod
    def _get_path(data, path):
        current = data or {}
        for part in str(path).split("."):
            if isinstance(current, dict):
                current = current.get(part)
            elif isinstance(current, list) and part.isdigit():
                index = int(part)
                current = current[index] if index < len(current) else None
            else:
                return None
        return current

    @staticmethod
    def _contains(actual, expected):
        if actual is None:
            return False
        if isinstance(actual, dict):
            return expected in actual or str(expected) in actual
        if isinstance(actual, (list, tuple, set)):
            return expected in actual
        return str(expected) in str(actual)

    @staticmethod
    def _compare(actual, expected, operator):
        try:
            actual_number = float(actual)
            expected_number = float(expected)
        except (TypeError, ValueError):
            return False

        if operator in ("gt", ">"):
            return actual_number > expected_number
        if operator in ("gte", ">="):
            return actual_number >= expected_number
        if operator in ("lt", "<"):
            return actual_number < expected_number
        if operator in ("lte", "<="):
            return actual_number <= expected_number
        return False

    @staticmethod
    def _get_target_hosts_or_fail(node_run: FlowNodeRun, config, user):
        host_ids = config.get("target_host_ids") or []
        existing_hosts = list(Host.objects.filter(id__in=host_ids))
        target_hosts = existing_hosts
        if not user.is_superuser:
            target_hosts = [host for host in existing_hosts if host.created_by_id == user.id]

        if not target_hosts:
            node_run.status = FlowRun.Status.FAILED
            if existing_hosts:
                node_run.error_message = f"permission denied for target host ids: {host_ids}"
            else:
                node_run.error_message = f"{node_run.node.node_type} node requires at least one valid target host"
            node_run.finished_at = timezone.now()
            node_run.save(update_fields=["status", "error_message", "finished_at"])
            return None

        found_host_ids = {host.id for host in existing_hosts}
        invalid_host_ids = sorted(set(host_ids) - found_host_ids)
        if invalid_host_ids:
            node_run.status = FlowRun.Status.FAILED
            node_run.error_message = f"{node_run.node.node_type} node has invalid target host ids: {invalid_host_ids}"
            node_run.finished_at = timezone.now()
            node_run.save(update_fields=["status", "error_message", "finished_at"])
            return None

        permitted_host_ids = {host.id for host in target_hosts}
        denied_host_ids = sorted(set(host_ids) - permitted_host_ids)
        if denied_host_ids:
            node_run.status = FlowRun.Status.FAILED
            node_run.error_message = f"permission denied for target host ids: {denied_host_ids}"
            node_run.finished_at = timezone.now()
            node_run.save(update_fields=["status", "error_message", "finished_at"])
            return None

        return target_hosts

    @staticmethod
    def _execute_script_node(node_run: FlowNodeRun, user, agent_server_id=None) -> FlowNodeRun:
        config = node_run.inputs or {}
        host_ids = config.get("target_host_ids") or []
        target_hosts = FlowRunner._get_target_hosts_or_fail(node_run, config, user)
        if target_hosts is None:
            return node_run

        execution_record = ExecutionRecordService.create_execution_record(
            execution_type="flow_node",
            name=f"流程节点: {node_run.node.name}",
            executed_by=user,
            related_object=node_run,
            trigger_type=node_run.flow_run.trigger_type,
            execution_parameters={
                "flow_run_id": node_run.flow_run_id,
                "flow_node_id": node_run.node_id,
                "agent_server_id": agent_server_id,
                "script_type": config.get("script_type", "shell"),
                "timeout": config.get("timeout", 300),
                "target_host_ids": host_ids,
            },
        )
        execution_record.status = "running"
        execution_record.started_at = timezone.now()
        execution_record.save(update_fields=["status", "started_at"])

        result = AgentExecutionService.execute_script_via_agent(
            execution_record=execution_record,
            script_content=config.get("script_content", ""),
            script_type=config.get("script_type", "shell"),
            target_hosts=target_hosts,
            timeout=config.get("timeout", 300),
            global_variables=config.get("global_variables") or {},
            step_id=None,
            agent_server_id=agent_server_id,
            account_id=config.get("account_id"),
        )

        success = bool(result.get("success")) and result.get("failed_count", 0) == 0
        node_run.status = FlowRun.Status.SUCCESS if success else FlowRun.Status.FAILED
        node_run.outputs = {
            "success_count": result.get("success_count", 0),
            "failed_count": result.get("failed_count", 0),
            "results": result.get("results", []),
        }
        node_run.error_message = "" if success else result.get("error", "script node failed")
        node_run.execution_record = execution_record
        node_run.finished_at = timezone.now()
        node_run.save(
            update_fields=[
                "status",
                "outputs",
                "error_message",
                "execution_record",
                "finished_at",
            ]
        )

        execution_record.status = "success" if success else "failed"
        execution_record.finished_at = timezone.now()
        execution_record.execution_results = {"summary": node_run.outputs}
        execution_record.error_message = node_run.error_message
        execution_record.save(
            update_fields=[
                "status",
                "finished_at",
                "execution_results",
                "error_message",
            ]
        )

        return node_run

    @staticmethod
    def _execute_file_transfer_node(node_run: FlowNodeRun, user, agent_server_id=None) -> FlowNodeRun:
        config = node_run.inputs or {}
        target_hosts = FlowRunner._get_target_hosts_or_fail(node_run, config, user)
        if target_hosts is None:
            return node_run

        file_sources = config.get("file_sources") or config.get("sources") or []
        if not file_sources:
            node_run.status = FlowRun.Status.FAILED
            node_run.error_message = "file_transfer node requires file_sources"
            node_run.finished_at = timezone.now()
            node_run.save(update_fields=["status", "error_message", "finished_at"])
            return node_run

        source_errors = FlowRunner._validate_file_sources(file_sources)
        if source_errors:
            node_run.status = FlowRun.Status.FAILED
            node_run.error_message = "; ".join(source_errors)
            node_run.finished_at = timezone.now()
            node_run.save(update_fields=["status", "error_message", "finished_at"])
            return node_run

        execution_record = ExecutionRecordService.create_execution_record(
            execution_type="flow_node",
            name=f"流程节点: {node_run.node.name}",
            executed_by=user,
            related_object=node_run,
            trigger_type=node_run.flow_run.trigger_type,
            execution_parameters={
                "flow_run_id": node_run.flow_run_id,
                "flow_node_id": node_run.node_id,
                "agent_server_id": agent_server_id,
                "timeout": config.get("timeout", 300),
                "bandwidth_limit": config.get("bandwidth_limit", 0),
                "target_host_ids": config.get("target_host_ids") or [],
                "file_sources": file_sources,
            },
        )
        execution_record.status = "running"
        execution_record.started_at = timezone.now()
        execution_record.save(update_fields=["status", "started_at"])
        node_run.execution_record = execution_record
        node_run.save(update_fields=["execution_record"])

        aggregate = {
            "success_count": 0,
            "failed_count": 0,
            "results": [],
        }
        errors = []

        for source in file_sources:
            result = AgentExecutionService.execute_file_transfer_via_agent(
                execution_record=execution_record,
                remote_path=source.get("remote_path", ""),
                target_hosts=target_hosts,
                timeout=config.get("timeout", 300),
                bandwidth_limit=config.get("bandwidth_limit", 0),
                download_url=source.get("download_url"),
                checksum=source.get("sha256") or source.get("checksum"),
                size=source.get("size"),
                auth_headers=source.get("auth_headers") or {},
                step_id=None,
                agent_server_id=agent_server_id,
                account_id=config.get("account_id"),
                file_sources=[source],
            )
            aggregate["success_count"] += result.get("success_count", 0)
            aggregate["failed_count"] += result.get("failed_count", 0)
            aggregate["results"].extend(result.get("results", []))
            if not result.get("success"):
                errors.append(result.get("error", "file transfer failed"))

        success = aggregate["success_count"] > 0 and aggregate["failed_count"] == 0 and not errors
        node_run.status = FlowRun.Status.SUCCESS if success else FlowRun.Status.FAILED
        node_run.outputs = aggregate
        node_run.error_message = "" if success else "; ".join(errors) or "file_transfer node failed"
        node_run.execution_record = execution_record
        node_run.finished_at = timezone.now()
        node_run.save(
            update_fields=[
                "status",
                "outputs",
                "error_message",
                "execution_record",
                "finished_at",
            ]
        )

        execution_record.status = "success" if success else "failed"
        execution_record.finished_at = timezone.now()
        execution_record.execution_results = {"summary": aggregate}
        execution_record.error_message = node_run.error_message
        execution_record.save(
            update_fields=[
                "status",
                "finished_at",
                "execution_results",
                "error_message",
            ]
        )

        return node_run

    @staticmethod
    def _validate_file_sources(file_sources):
        return get_file_source_errors(file_sources)

    @staticmethod
    def _execute_job_plan_node(node_run: FlowNodeRun, user, agent_server_id=None) -> FlowNodeRun:
        config = node_run.inputs or {}
        plan_id = config.get("execution_plan_id")
        if not plan_id:
            node_run.status = FlowRun.Status.FAILED
            node_run.error_message = "job_plan node requires execution_plan_id"
            node_run.finished_at = timezone.now()
            node_run.save(update_fields=["status", "error_message", "finished_at"])
            return node_run

        plan_queryset = ExecutionPlan.objects.filter(id=plan_id)
        execution_plan = plan_queryset.first()
        if not execution_plan:
            node_run.status = FlowRun.Status.FAILED
            node_run.error_message = "job_plan execution plan not found"
            node_run.finished_at = timezone.now()
            node_run.save(update_fields=["status", "error_message", "finished_at"])
            return node_run
        if not user.is_superuser and execution_plan.created_by_id != user.id:
            node_run.status = FlowRun.Status.FAILED
            node_run.error_message = "permission denied for execution plan"
            node_run.finished_at = timezone.now()
            node_run.save(update_fields=["status", "error_message", "finished_at"])
            return node_run
        resource_error = get_execution_plan_resource_permission_error(execution_plan, user)
        if resource_error:
            node_run.status = FlowRun.Status.FAILED
            node_run.error_message = resource_error
            node_run.finished_at = timezone.now()
            node_run.save(update_fields=["status", "error_message", "finished_at"])
            return node_run

        from apps.job_templates.services import ExecutionPlanService

        execution_parameters = {
            **FlowRunner._business_inputs(node_run.flow_run.inputs),
            **(config.get("execution_parameters") or {}),
        }
        result = ExecutionPlanService.execute_plan(
            execution_plan=execution_plan,
            user=user,
            trigger_type=node_run.flow_run.trigger_type,
            execution_parameters=execution_parameters,
            name=f"流程节点: {node_run.node.name}",
            description=f"流程 {node_run.flow_run.template.name} 执行方案 {execution_plan.name}",
            execution_mode=config.get("execution_mode", "parallel"),
            rolling_batch_size=config.get("rolling_batch_size", 1),
            rolling_batch_delay=config.get("rolling_batch_delay", 0),
            agent_server_id=config.get("agent_server_id") or agent_server_id,
            execution_type="flow_node",
            related_object=node_run,
        )

        execution_record_id = result.get("execution_record_id")
        execution_record = None
        if execution_record_id:
            execution_record = ExecutionRecord.objects.filter(id=execution_record_id).first()
            if (
                not execution_record
                or execution_record.execution_type != "flow_node"
                or execution_record.executed_by_id != user.id
                or execution_record.related_object != node_run
            ):
                node_run.status = FlowRun.Status.FAILED
                node_run.outputs = result
                node_run.error_message = "job_plan returned invalid flow node execution record"
                node_run.finished_at = timezone.now()
                node_run.save(update_fields=["status", "outputs", "error_message", "finished_at"])
                return node_run

        if not result.get("success"):
            node_status = FlowRun.Status.FAILED
            error_message = result.get("error", "job_plan node failed")
        elif execution_record and execution_record.status == "success":
            node_status = FlowRun.Status.SUCCESS
            error_message = ""
        elif execution_record and execution_record.status in ["failed", "cancelled", "timeout"]:
            node_status = FlowRun.Status.FAILED
            error_message = execution_record.error_message or "job_plan node failed"
        else:
            node_status = FlowRun.Status.PAUSED
            error_message = ""

        node_run.status = node_status
        node_run.outputs = result
        node_run.error_message = error_message
        node_run.finished_at = None if node_status == FlowRun.Status.PAUSED else timezone.now()
        node_run.execution_record = execution_record

        node_run.save(
            update_fields=[
                "status",
                "outputs",
                "error_message",
                "execution_record",
                "finished_at",
            ]
        )
        return node_run
