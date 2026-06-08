from collections import defaultdict, deque

from django.utils import timezone

from apps.agents.execution_service import AgentExecutionService
from apps.executor.services import ExecutionRecordService
from apps.hosts.models import Host

from .models import FlowNode, FlowNodeRun, FlowRun, FlowTemplate


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
            for node in cls._topological_nodes(template):
                node_run = cls._execute_node(flow_run, node, user, agent_server_id=agent_server_id)
                if node_run.status == FlowRun.Status.FAILED:
                    flow_run.mark_finished(FlowRun.Status.FAILED, node_run.error_message)
                    return flow_run
                if node_run.status == FlowRun.Status.PAUSED:
                    flow_run.status = FlowRun.Status.PAUSED
                    flow_run.save(update_fields=["status"])
                    return flow_run

            flow_run.mark_finished(FlowRun.Status.SUCCESS)
            return flow_run
        except Exception as exc:
            flow_run.mark_finished(FlowRun.Status.FAILED, str(exc))
            raise

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

        if node.node_type == FlowNode.NodeType.SCRIPT:
            try:
                return cls._execute_script_node(node_run, user, agent_server_id=agent_server_id)
            except Exception as exc:
                node_run.status = FlowRun.Status.FAILED
                node_run.error_message = str(exc)
                node_run.finished_at = timezone.now()
                node_run.save(update_fields=["status", "error_message", "finished_at"])
                raise

        node_run.status = FlowRun.Status.FAILED
        node_run.error_message = f"unsupported node type: {node.node_type}"
        node_run.finished_at = timezone.now()
        node_run.save(update_fields=["status", "error_message", "finished_at"])
        return node_run

    @staticmethod
    def _execute_script_node(node_run: FlowNodeRun, user, agent_server_id=None) -> FlowNodeRun:
        config = node_run.node.config or {}
        host_ids = config.get("target_host_ids") or []
        target_hosts = list(Host.objects.filter(id__in=host_ids))

        if not target_hosts:
            node_run.status = FlowRun.Status.FAILED
            node_run.error_message = "script node requires at least one valid target host"
            node_run.finished_at = timezone.now()
            node_run.save(update_fields=["status", "error_message", "finished_at"])
            return node_run

        found_host_ids = {host.id for host in target_hosts}
        invalid_host_ids = sorted(set(host_ids) - found_host_ids)
        if invalid_host_ids:
            node_run.status = FlowRun.Status.FAILED
            node_run.error_message = f"script node has invalid target host ids: {invalid_host_ids}"
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
