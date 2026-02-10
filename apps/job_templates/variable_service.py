# coding: utf-8
"""Variable service for job templates execution.

Core responsibilities:
- Build execution context including builtin and user variables
- Prevent overriding builtin variables
- Validate required variables
- Render payload fields (script content, step params, file sources paths)
- Mask secret variables for logs/archiving

This module is intentionally framework-light for reuse across execution entrypoints.
"""
from __future__ import annotations
import re
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, Any, List, Tuple

from django.core.exceptions import ValidationError
from django.utils import timezone


BUILTIN_KEYS = {
    "JOB_ID",
    "TEMPLATE_ID",
    "PLAN_ID",
    "STEP_ID",
    "EXECUTOR",
    "EXECUTE_AT",
    "TARGET_IPS",
    "TARGET_COUNT",
    "BATCH_ID",
}

PLACEHOLDER_PATTERN = re.compile(r"\${([^}]+)}|{{\s*([^}\s]+)\s*}}")


@dataclass
class VariableValue:
    value: Any
    type: str = "text"  # text | secret
    required: bool = False
    description: str | None = None
    inject_into: List[str] = field(default_factory=lambda: ["script", "step_params", "file_sources"])

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "VariableValue":
        return cls(
            value=d.get("value"),
            type=d.get("type", "text") or "text",
            required=bool(d.get("required", False)),
            description=d.get("description"),
            inject_into=d.get("inject_into") or ["script", "step_params", "file_sources"],
        )

    def is_secret(self) -> bool:
        return self.type == "secret"


@dataclass
class VariableContext:
    builtin: Dict[str, VariableValue]
    user: Dict[str, VariableValue]

    def merged(self) -> Dict[str, VariableValue]:
        # Prevent overriding builtin keys
        conflict = BUILTIN_KEYS.intersection(self.user.keys())
        if conflict:
            raise ValidationError({"variables": [f"Cannot override system variable(s): {', '.join(sorted(conflict))}"]})
        merged = {**self.builtin, **self.user}
        return merged


def build_builtin_vars(context: Dict[str, Any]) -> Dict[str, VariableValue]:
    """Create builtin variables. context expects keys: job_id, template_id, plan_id, step_id, executor, targets(list), batch_id."""
    targets = context.get("targets") or []
    target_ips = ",".join([str(t) for t in targets]) if targets else ""
    now_iso = timezone.now().isoformat()
    mapping = {
        "JOB_ID": context.get("job_id"),
        "TEMPLATE_ID": context.get("template_id"),
        "PLAN_ID": context.get("plan_id"),
        "STEP_ID": context.get("step_id"),
        "EXECUTOR": context.get("executor"),
        "EXECUTE_AT": now_iso,
        "TARGET_IPS": target_ips,
        "TARGET_COUNT": len(targets),
        "BATCH_ID": context.get("batch_id"),
    }
    result: Dict[str, VariableValue] = {}
    for k, v in mapping.items():
        result[k] = VariableValue(value=v, type="text", required=False, description="system")
    return result


def normalize_user_vars(raw: Dict[str, Any] | None) -> Dict[str, VariableValue]:
    if not raw:
        return {}
    normalized: Dict[str, VariableValue] = {}
    for name, meta in raw.items():
        if not name:
            continue
        if isinstance(meta, dict):
            normalized[name] = VariableValue.from_dict(meta)
        else:
            normalized[name] = VariableValue(value=meta)
    return normalized


def validate_required(vars_ctx: Dict[str, VariableValue]):
    missing = [k for k, v in vars_ctx.items() if v.required and (v.value is None or str(v.value) == "")]
    if missing:
        raise ValidationError({"variables": [f"Missing required variables: {', '.join(missing)}"]})


def render_string(s: str, vars_ctx: Dict[str, VariableValue]) -> str:
    def repl(match: re.Match):
        key = match.group(1) or match.group(2)
        if key in vars_ctx:
            val = vars_ctx[key].value
            return "" if val is None else str(val)
        return match.group(0)  # leave untouched

    return PLACEHOLDER_PATTERN.sub(repl, s)


def render_payload(vars_ctx: Dict[str, VariableValue], payload: Dict[str, Any]) -> Dict[str, Any]:
    rendered = payload.copy()

    def render_in_obj(obj: Any, inject_into: List[str]) -> Any:
        if isinstance(obj, str):
            return render_string(obj, vars_ctx)
        if isinstance(obj, list):
            return [render_in_obj(x, inject_into) for x in obj]
        if isinstance(obj, dict):
            new_obj = {}
            for k, v in obj.items():
                if isinstance(v, str):
                    new_obj[k] = render_string(v, vars_ctx)
                else:
                    new_obj[k] = render_in_obj(v, inject_into)
            return new_obj
        return obj

    # script content
    if rendered.get("script_content"):
        rendered["script_content"] = render_string(rendered["script_content"], vars_ctx)

    # step_parameters (list of strings)
    if isinstance(rendered.get("step_parameters"), list):
        rendered["step_parameters"] = [render_in_obj(p, ["step_params"]) for p in rendered["step_parameters"]]

    # file_sources
    if isinstance(rendered.get("file_sources"), list):
        new_fs = []
        for fs in rendered["file_sources"]:
            if isinstance(fs, dict):
                new_fs.append(render_in_obj(fs, ["file_sources"]))
            else:
                new_fs.append(fs)
        rendered["file_sources"] = new_fs

    return rendered


def mask_secrets(text: str, vars_ctx: Dict[str, VariableValue]) -> str:
    if not text:
        return text
    secret_keys = [k for k, v in vars_ctx.items() if v.is_secret()]
    if not secret_keys:
        return text
    masked = text
    for key in secret_keys:
        val = vars_ctx[key].value
        if val:
            masked = masked.replace(str(val), "****")
    return masked


def build_and_render(context: Dict[str, Any], user_vars_raw: Dict[str, Any], payload: Dict[str, Any]) -> Tuple[Dict[str, VariableValue], Dict[str, Any]]:
    """High-level helper for execution entrypoints.

    Returns merged variables and rendered payload. Raises ValidationError on problems.
    """
    builtin = build_builtin_vars(context)
    user_vars = normalize_user_vars(user_vars_raw)
    ctx = VariableContext(builtin=builtin, user=user_vars)
    merged = ctx.merged()
    validate_required(merged)
    rendered = render_payload(merged, payload)
    return merged, rendered
