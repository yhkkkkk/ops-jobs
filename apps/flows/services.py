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
    def _continue_flow(cls, flow_run: FlowRun, user, agent_server_id=None) -> FlowRun:
        if flow_run.status in (FlowRun.Status.SUCCESS, FlowRun.Status.FAILED, FlowRun.Status.CANCELLED):
            return flow_run
        if flow_run.status != FlowRun.Status.RUNNING:
            flow_run.status = FlowRun.Status.RUNNING
            flow_run.finished_at = None
            flow_run.save(update_fields=["status", "finished_at"])

        node_runs_by_node_id = {node_run.node_id: node_run for node_run in flow_run.node_runs.all()}
        for node in cls._topological_nodes(flow_run.template):
            node_run = node_runs_by_node_id.get(node.id)
            if node_run and node_run.status == FlowRun.Status.SUCCESS:
                continue
            if node_run and node_run.status == FlowRun.Status.PAUSED:
                flow_run.status = FlowRun.Status.PAUSED
                flow_run.save(update_fields=["status"])
                return flow_run
            if node_run and node_run.status in (FlowRun.Status.PENDING, FlowRun.Status.RUNNING):
                flow_run.status = FlowRun.Status.PAUSED
                flow_run.save(update_fields=["status"])
                return flow_run
            if node_run and node_run.status == FlowRun.Status.FAILED:
                flow_run.mark_finished(FlowRun.Status.FAILED, node_run.error_message)
                return flow_run

            if node_run is None:
                node_run = cls._execute_node(flow_run, node, user, agent_server_id=agent_server_id)
                node_runs_by_node_id[node.id] = node_run

            if node_run.status == FlowRun.Status.FAILED:
                flow_run.mark_finished(FlowRun.Status.FAILED, node_run.error_message)
                return flow_run
            if node_run.status == FlowRun.Status.PAUSED:
                flow_run.status = FlowRun.Status.PAUSED
                flow_run.save(update_fields=["status"])
                return flow_run

        flow_run.mark_finished(FlowRun.Status.SUCCESS)
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
                flow_run.mark_finished(FlowRun.Status.FAILED, error_message)

        if should_continue:
            return cls._continue_flow(flow_run, flow_run.started_by, agent_server_id=agent_server_id)

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

    @classmethod
    def _execute_node(cls, flow_run: FlowRun, node: FlowNode, user, agent_server_id=None) -> FlowNodeRun:
        node_run = FlowNodeRun.objects.create(
            flow_run=flow_run,
            node=node,
            status=FlowRun.Status.RUNNING,
            inputs=node.config or {},
            started_at=timezone.now(),
        )

        if node.node_type in (
            FlowNode.NodeType.SCRIPT,
            FlowNode.NodeType.FILE_TRANSFER,
            FlowNode.NodeType.JOB_PLAN,
        ):
            try:
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
        config = node_run.node.config or {}
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
        config = node_run.node.config or {}
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
        config = node_run.node.config or {}
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
            **(node_run.flow_run.inputs or {}),
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
