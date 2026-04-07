"""Helpers for exposing tool security posture across runtime surfaces."""

from __future__ import annotations

from typing import Any

from orchestrator.tool_configs import ToolConfig


def _tool_record(tool: ToolConfig | dict[str, Any]) -> dict[str, Any]:
    if isinstance(tool, ToolConfig):
        return tool.model_dump()
    return dict(tool)


def tool_guardrail_status(tool: ToolConfig | dict[str, Any]) -> str:
    return str(_tool_record(tool).get("guardrail_status", "unknown") or "unknown")


def tool_requires_guarded_wrapper(tool: ToolConfig | dict[str, Any]) -> bool:
    payload = _tool_record(tool)
    return str(payload.get("tool_type", "") or "") == "mcp_server" and str(payload.get("wrapper_mode", "direct") or "direct") == "guarded"


def tool_runtime_allowed(tool: ToolConfig | dict[str, Any]) -> bool:
    payload = _tool_record(tool)
    return bool(payload.get("enabled", True)) and tool_guardrail_status(payload) != "blocked"


def build_tool_security_posture(tool: ToolConfig | dict[str, Any]) -> dict[str, Any]:
    payload = _tool_record(tool)
    return {
        "guardrail_status": str(payload.get("guardrail_status", "unknown") or "unknown"),
        "wrapper_mode": str(payload.get("wrapper_mode", "direct") or "direct"),
        "trust_level": str(payload.get("trust_level", "unknown") or "unknown"),
        "runtime_allowed": tool_runtime_allowed(payload),
    }
