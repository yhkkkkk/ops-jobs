#!/usr/bin/env python3
"""
渲染配置脚本（control-plane 使用）
- 优先使用 PyYAML 合并 base config 与覆盖字段（若可用）
- 否则使用 Jinja2 渲染模板（如果 base 文件包含模板占位）
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
                    if any(ch in s for ch in ['\n', ':', '"', "'"]) or s.strip() != s:
                        s = '"' + s.replace('"', '\\"') + '"'
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
                    if any(ch in s for ch in ['\n', ':', '"', "'']) or s.strip() != s:
                        s = '"' + s.replace('"', '\\"') + '"'
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
    p.add_argument("--agent-server-url", help="agent server url", default="")
    p.add_argument("--control-plane-url", help="control plane url", default="")
    p.add_argument("--ws-backoff-initial", help="ws backoff initial", default=None)
    p.add_argument("--ws-backoff-max", help="ws backoff max", default=None)
    p.add_argument("--ws-max-retries", help="ws max retries", default=None)
    p.add_argument("--agent-server-listen-addr", help="agent-server listen addr", default=None)
    p.add_argument("--max-connections", help="max connections", default=None)
    p.add_argument("--heartbeat-timeout", help="heartbeat timeout", default=None)
    return p.parse_args()


def main():
    args = parse_args()
    overrides: Dict[str, Any] = {}
    if args.install_type == "agent":
        overrides = {
            "mode": "agent-server",
            "agent_server_url": args.agent_server_url,
            "ws_backoff_initial_ms": int(args.ws_backoff_initial) if args.ws_backoff_initial else None,
            "ws_backoff_max_ms": int(args.ws_backoff_max) if args.ws_backoff_max else None,
            "ws_max_retries": int(args.ws_max_retries) if args.ws_max_retries else None,
            "agent_token": args.agent_token,
            "log_level": "info",
        }
    else:
        host = "0.0.0.0"
        port = 8080
        if args.agent_server_listen_addr and ":" in args.agent_server_listen_addr:
            host, port = args.agent_server_listen_addr.rsplit(":", 1)
        overrides = {
            "server": {"host": host, "port": int(port)},
            "control_plane": {"url": args.control_plane_url, "token": args.agent_token},
            "agent": {"max_connections": int(args.max_connections) if args.max_connections else 1000,
                      "heartbeat_timeout": f"{args.heartbeat_timeout}s" if args.heartbeat_timeout else "60s",
                      "cleanup_interval": "30s"},
            "logging": {"level": "info", "file": "logs/agent-server.log"},
        }

    base_path = args.config
    # Try PyYAML first for structured merge
    try:
        import yaml  # type: ignore
    except Exception:
        yaml = None

    if base_path and os.path.exists(base_path):
        with open(base_path, "r", encoding="utf-8") as f:
            base_text = f.read()
        # If YAML lib available, merge structures
        if yaml:
            try:
                loaded = yaml.safe_load(base_text) or {}
                if not isinstance(loaded, dict):
                    loaded = {}
                deep_update(loaded, overrides)
                out = yaml.safe_dump(loaded, allow_unicode=False, default_flow_style=False, sort_keys=False)
                print(out)
                return
            except Exception:
                # fallback to template/text rendering
                pass
        # If base contains Jinja2 markers, render it as template
        if "{{" in base_text or "{%" in base_text:
            try:
                from jinja2 import Template  # type: ignore
                tpl = Template(base_text)
                ctx = overrides.copy()
                ctx["install_type"] = args.install_type
                out = tpl.render(**ctx)
                print(out)
                return
            except Exception:
                pass

    # Fallback: emit YAML only from overrides
    print(emit_yaml(overrides))


if __name__ == "__main__":
    main()


