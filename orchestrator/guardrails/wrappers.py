"""Guarded wrapper helpers for risky or untrusted tool flows."""

from __future__ import annotations

import re

from orchestrator.guardrails.policies import GuardrailScanReport

SECRET_REDACTIONS = [
    (re.compile(r"\bghp_[A-Za-z0-9]{12,}\b"), "ghp_[redacted]"),
    (re.compile(r"\bsk-[A-Za-z0-9]{12,}\b"), "sk-[redacted]"),
    (re.compile(r"\bBearer\s+[A-Za-z0-9._-]{12,}\b", re.IGNORECASE), "Bearer [redacted]"),
]


def sanitize_tool_result(result_text: str, report: GuardrailScanReport | None = None) -> str:
    rendered = str(result_text or "")
    for pattern, replacement in SECRET_REDACTIONS:
        rendered = pattern.sub(replacement, rendered)
    if report and report.recommended_action == "warn":
        return f"[guarded wrapper] {report.summary}\n\n{rendered}".strip()
    return rendered


def build_block_message(tool_name: str, report: GuardrailScanReport) -> str:
    return f"[{tool_name}] Blocked by guardrails: {report.summary}"


def build_guarded_tool_description(tool_label: str, report: GuardrailScanReport) -> str:
    if report.recommended_action == "block":
        return f"{tool_label}: blocked by guardrails ({report.summary})"
    if report.recommended_action in {"warn", "log"}:
        return f"{tool_label}: exposed through guarded wrapper ({report.summary})"
    return tool_label
