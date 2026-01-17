#!/usr/bin/env python3
"""
渲染配置脚本（control-plane 使用）
- 优先使用 ruamel.yaml 合并 base config 与覆盖字段（保留注释）
- 回退使用 PyYAML 合并 base config 与覆盖字段（若可用，会丢失注释）
- 最后回退为内置简单 YAML emitter（仅生成覆盖字段）

输出渲染后的 YAML 到 stdout
"""
from __future__ import annotations
import argparse
import sys
import os
import json
from typing import Any, Dict


def deep_update(dst: Dict[str, Any], src: Dict[str, Any]) -> None:
    for k, v in src.items():
        if isinstance(v, dict) and isinstance(dst.get(k), dict):
            deep_update(dst[k], v)
        else:
            dst[k] = v


def emit_yaml(obj: Any, indent: int = 0) -> str:
    lines = []
    pad = '  ' * indent
    if isinstance(obj, dict):
        for k, v in obj.items():
            if isinstance(v, (dict, list)):
                lines.append(f"{pad}{k}:")
                lines.append(emit_yaml(v, indent + 1))
            else:
                if v is True:
                    val = "true"
                elif v is False:
                    val = "false"
                elif v is None:
                    val = ""
                elif isinstance(v, (int, float)):
                    val = str(v)
                else:
                    s = str(v)
                    if any(ch in s for ch in ['\\n', ':', '"', "'"]) or s.strip() != s:
                        s = '"' + s.replace('"', '\\\\"') + '"'
                    val = s
                lines.append(f"{pad}{k}: {val}")
    elif isinstance(obj, list):
        for item in obj:
            if isinstance(item, (dict, list)):
                lines.append(f"{pad}-")
                lines.append(emit_yaml(item, indent + 1))
            else:
                if item is True:
                    vv = "true"
                elif item is False:
                    vv = "false"
                elif item is None:
                    vv = ""
                elif isinstance(item, (int, float)):
                    vv = str(item)
                else:
                    s = str(item)
                    if any(ch in s for ch in ['\\n', ':', '"', "'"]) or s.strip() != s:
                        s = '"' + s.replace('"', '\\\\"') + '"'
                    vv = s
                lines.append(f"{pad}- {vv}")
    else:
        lines.append(pad + str(obj))
    return "\n".join(lines)


def parse_args():
    p = argparse.ArgumentParser(description="Render agent config YAML")
    p.add_argument("--config", "-c", help="base config file (optional)", default=None)
    p.add_argument("--install-type", help="install type", default="agent")
    p.add_argument("--agent-token", help="agent token", default="")
    p.add_argument("--host-id", help="host id", default=None)
    p.add_argument("--agent-name", help="agent name", default=None)
    p.add_argument("--agent-server-url", help="agent server url", default="")
    p.add_argument("--control-plane-url", help="control plane url", default="")
    p.add_argument("--ws-backoff-initial", help="ws backoff initial", default=None)
    p.add_argument("--ws-backoff-max", help="ws backoff max", default=None)
    p.add_argument("--ws-max-retries", help="ws max retries", default=None)
    p.add_argument("--agent-server-listen-addr", help="agent-server listen addr", default=None)
    p.add_argument("--max-connections", help="max connections", default=None)
    p.add_argument("--heartbeat-timeout", help="heartbeat timeout", default=None)
    return p.parse_args()


def render_config_yaml(
    install_type: str = "agent",
    agent_token: str = "",
    host_id: int = None,
    agent_name: str = None,
    agent_server_url: str = "",
    control_plane_url: str = "",
    ws_backoff_initial: int = None,
    ws_backoff_max: int = None,
    ws_max_retries: int = None,
    agent_server_listen_addr: str = None,
    max_connections: int = None,
    heartbeat_timeout: int = None,
    base_config_path: str = None,
) -> str:
    """
    渲染配置 YAML 字符串（可直接被 Python 调用）

    Args:
        install_type: 安装类型 ('agent' 或 'agent-server')
        agent_token: Agent Token
        agent_server_url: Agent Server URL
        control_plane_url: Control Plane URL（仅 agent-server 安装使用）
        ws_backoff_initial: WebSocket 初始退避时间（毫秒）
        ws_backoff_max: WebSocket 最大退避时间（毫秒）
        ws_max_retries: WebSocket 最大重试次数
        agent_server_listen_addr: Agent Server 监听地址
        max_connections: 最大连接数
        heartbeat_timeout: 心跳超时（秒）
        base_config_path: 基础配置文件路径（可选）

    Returns:
        str: 渲染后的 YAML 配置字符串
    """
    overrides: Dict[str, Any] = {}
    if install_type == "agent":
        overrides = {
            "connection": {
                "agent_server_url": agent_server_url,
            },
            "identification": {
                "agent_token": agent_token,
                "agent_name": agent_name or "",
            },
            "logging": {
                "log_level": "info",
            },
            "task": {
                "heartbeat_interval": 10,
                "max_concurrent_tasks": 5,
                "max_execution_time_sec": 7200,
            },
            "resource_limit": {
                "bandwidth_limit": 0,
            },
        }
        # Add optional fields only if provided
        if ws_backoff_initial:
            overrides["connection"]["ws_backoff_initial_ms"] = int(ws_backoff_initial)
        if ws_backoff_max:
            overrides["connection"]["ws_backoff_max_ms"] = int(ws_backoff_max)
        if ws_max_retries:
            overrides["connection"]["ws_max_retries"] = int(ws_max_retries)
        if host_id:
            overrides["identification"]["host_id"] = int(host_id)
    else:
        host = "0.0.0.0"
        port = 8080
        if agent_server_listen_addr and ":" in agent_server_listen_addr:
            host, port_str = agent_server_listen_addr.rsplit(":", 1)
            try:
                port = int(port_str)
            except ValueError:
                port = 8080

        overrides = {
            "server": {"host": host, "port": port},
            "control_plane": {"url": control_plane_url, "token": agent_token},
            "logging": {"level": "info", "file": "logs/agent-server.log"},
        }

        # Add agent config section
        agent_config = {"cleanup_interval": "30s"}
        if max_connections:
            agent_config["max_connections"] = int(max_connections)
        else:
            agent_config["max_connections"] = 1000

        if heartbeat_timeout:
            agent_config["heartbeat_timeout"] = f"{heartbeat_timeout}s"
        else:
            agent_config["heartbeat_timeout"] = "60s"

        overrides["agent"] = agent_config

    base_path = base_config_path

    # Try ruamel.yaml first (preserves comments and formatting)
    ruamel_yaml = None
    try:
        from ruamel.yaml import YAML
        ruamel_yaml = YAML()
        ruamel_yaml.preserve_quotes = True
        ruamel_yaml.default_flow_style = False
    except Exception:
        ruamel_yaml = None

    # Fallback to PyYAML (loses comments)
    pyyaml = None
    try:
        import yaml as pyyaml_module
        pyyaml = pyyaml_module
    except Exception:
        pyyaml = None

    if base_path and os.path.exists(base_path):
        with open(base_path, "r", encoding="utf-8") as f:
            base_text = f.read()

        # Try ruamel.yaml first (preserves comments)
        if ruamel_yaml:
            try:
                from io import StringIO
                loaded = ruamel_yaml.load(base_text)
                if not isinstance(loaded, dict):
                    loaded = {}
                deep_update(loaded, overrides)
                output = StringIO()
                ruamel_yaml.dump(loaded, output)
                return output.getvalue()
            except Exception as e:
                # Log warning but continue to fallback
                import sys
                print(f"Warning: ruamel.yaml failed ({e}), falling back to PyYAML", file=sys.stderr)

        # Fallback to PyYAML (loses comments)
        if pyyaml:
            try:
                loaded = pyyaml.safe_load(base_text) or {}
                if not isinstance(loaded, dict):
                    loaded = {}
                deep_update(loaded, overrides)
                return pyyaml.safe_dump(loaded, allow_unicode=False, default_flow_style=False, sort_keys=False)
            except Exception:
                pass

    # Fallback: emit YAML only from overrides
    return emit_yaml(overrides)


def main():
    args = parse_args()
    result = render_config_yaml(
        install_type=args.install_type,
        agent_token=args.agent_token,
        host_id=int(args.host_id) if args.host_id else None,
        agent_name=args.agent_name,
        agent_server_url=args.agent_server_url,
        control_plane_url=args.control_plane_url,
        ws_backoff_initial=int(args.ws_backoff_initial) if args.ws_backoff_initial else None,
        ws_backoff_max=int(args.ws_backoff_max) if args.ws_backoff_max else None,
        ws_max_retries=int(args.ws_max_retries) if args.ws_max_retries else None,
        agent_server_listen_addr=args.agent_server_listen_addr,
        max_connections=int(args.max_connections) if args.max_connections else None,
        heartbeat_timeout=int(args.heartbeat_timeout) if args.heartbeat_timeout else None,
        base_config_path=args.config,
    )
    print(result)


if __name__ == "__main__":
    main()
