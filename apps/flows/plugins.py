from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class FlowNodePlugin:
    type: str
    name: str
    category: str
    description: str
    config_schema: dict[str, Any]

    def to_dict(self):
        return {
            "type": self.type,
            "name": self.name,
            "category": self.category,
            "description": self.description,
            "config_schema": self.config_schema,
        }


FLOW_NODE_PLUGINS = [
    FlowNodePlugin(
        type="script",
        name="脚本执行",
        category="作业平台原子",
        description="在目标主机上执行脚本内容。",
        config_schema={
            "type": "object",
            "properties": {
                "script_content": {"type": "string", "title": "脚本内容"},
                "script_type": {"type": "string", "title": "脚本类型", "default": "shell"},
                "target_host_ids": {"type": "array", "title": "目标主机"},
                "timeout": {"type": "number", "title": "超时时间", "default": 300},
                "failure_policy": {"type": "string", "title": "失败策略", "default": "stop"},
            },
        },
    ),
    FlowNodePlugin(
        type="file_transfer",
        name="文件分发",
        category="作业平台原子",
        description="向目标主机分发一个或多个文件。",
        config_schema={
            "type": "object",
            "properties": {
                "file_sources": {"type": "array", "title": "文件源"},
                "target_host_ids": {"type": "array", "title": "目标主机"},
                "timeout": {"type": "number", "title": "超时时间", "default": 300},
                "bandwidth_limit": {"type": "number", "title": "带宽限制", "default": 0},
                "failure_policy": {"type": "string", "title": "失败策略", "default": "stop"},
            },
        },
    ),
    FlowNodePlugin(
        type="job_plan",
        name="作业执行方案",
        category="作业平台原子",
        description="调用已有作业执行方案并等待执行结果。",
        config_schema={
            "type": "object",
            "properties": {
                "execution_plan_id": {"type": "number", "title": "执行方案"},
                "execution_parameters": {"type": "object", "title": "执行参数"},
                "execution_mode": {"type": "string", "title": "执行模式", "default": "parallel"},
                "failure_policy": {"type": "string", "title": "失败策略", "default": "pause"},
            },
        },
    ),
    FlowNodePlugin(
        type="manual",
        name="人工确认",
        category="控制节点",
        description="暂停流程，等待人工确认后继续。",
        config_schema={
            "type": "object",
            "properties": {
                "instructions": {"type": "string", "title": "确认说明"},
                "failure_policy": {"type": "string", "title": "失败策略", "default": "stop"},
            },
        },
    ),
    FlowNodePlugin(
        type="condition",
        name="条件分支",
        category="控制节点",
        description="根据出边条件选择后续分支。",
        config_schema={"type": "object", "properties": {"description": {"type": "string", "title": "说明"}}},
    ),
    FlowNodePlugin(
        type="parallel",
        name="并行网关",
        category="控制节点",
        description="同时激活所有下游分支。",
        config_schema={"type": "object", "properties": {"description": {"type": "string", "title": "说明"}}},
    ),
    FlowNodePlugin(
        type="join",
        name="汇聚网关",
        category="控制节点",
        description="等待所有活跃上游分支完成后继续。",
        config_schema={"type": "object", "properties": {"description": {"type": "string", "title": "说明"}}},
    ),
    FlowNodePlugin(
        type="sub_process",
        name="子流程",
        category="控制节点",
        description="调用另一个流程模板作为当前节点执行。",
        config_schema={
            "type": "object",
            "required": ["template_id"],
            "properties": {
                "template_id": {"type": "number", "title": "子流程模板"},
                "inherit_inputs": {"type": "boolean", "title": "继承父流程输入", "default": True},
                "inputs": {"type": "object", "title": "子流程输入"},
                "failure_policy": {"type": "string", "title": "失败策略", "default": "stop"},
            },
        },
    ),
]

FLOW_NODE_PLUGIN_MAP = {plugin.type: plugin for plugin in FLOW_NODE_PLUGINS}


def list_flow_node_plugins():
    return [plugin.to_dict() for plugin in FLOW_NODE_PLUGINS]


def get_flow_node_plugin(node_type: str):
    return FLOW_NODE_PLUGIN_MAP.get(node_type)


def validate_flow_node_config(node_type: str, config: dict | None, context: dict | None = None):
    plugin = get_flow_node_plugin(node_type)
    if not plugin:
        return [f"unsupported flow node type: {node_type}"]
    if config is not None and not isinstance(config, dict):
        return ["node config must be an object"]
    config = config or {}
    errors = []
    for field in plugin.config_schema.get("required", []):
        if config.get(field) in (None, ""):
            errors.append(f"{field} is required")

    if node_type == "sub_process":
        if "inputs" in config and not isinstance(config.get("inputs"), dict):
            errors.append("inputs must be an object")
        if "inherit_inputs" in config and not isinstance(config.get("inherit_inputs"), bool):
            errors.append("inherit_inputs must be a boolean")
    if errors:
        return errors
    return []
