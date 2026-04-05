"""Runtime safety scans for tool metadata, inputs, and outputs."""

from __future__ import annotations

import json
import re
from typing import Any, Iterable

from orchestrator.guardrails.policies import GuardrailFinding, GuardrailScanReport, compile_scan_report

STRONG_PROMPT_INJECTION_PATTERNS = [
    re.compile(r"ignore\s+(all\s+)?(previous|prior)\s+(instructions|prompts?)", re.IGNORECASE),
    re.compile(r"disregard\s+.*\b(instructions|system prompt|developer message)\b", re.IGNORECASE),
    re.compile(r"reveal\s+.*\b(system prompt|developer message|hidden instructions)\b", re.IGNORECASE),
    re.compile(r"override\s+.*\b(system|developer)\b", re.IGNORECASE),
]
SENSITIVE_CONTEXT_PATTERNS = [
    re.compile(r"\bsystem prompt\b", re.IGNORECASE),
    re.compile(r"\bdeveloper message\b", re.IGNORECASE),
    re.compile(r"\bhidden instructions?\b", re.IGNORECASE),
    re.compile(r"\bexfiltrat(e|ion)\b", re.IGNORECASE),
]
SECRET_PATTERNS = [
    re.compile(r"\bghp_[A-Za-z0-9]{12,}\b"),
    re.compile(r"\bsk-[A-Za-z0-9]{12,}\b"),
    re.compile(r"\bBearer\s+[A-Za-z0-9._-]{12,}\b", re.IGNORECASE),
    re.compile(r"\bapi[_-]?key\s*[:=]\s*[A-Za-z0-9._-]{8,}\b", re.IGNORECASE),
]
SHADOW_SERVER_PATTERNS = [
    re.compile(r"\buse\s+another\s+tool\b", re.IGNORECASE),
    re.compile(r"\bconnect\s+to\s+external\s+server\b", re.IGNORECASE),
    re.compile(r"\bcall\s+.*\bproxy\b", re.IGNORECASE),
]


def _render_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    try:
        return json.dumps(value, ensure_ascii=False, sort_keys=True)
    except TypeError:
        return str(value)


def _collect_matches(patterns: Iterable[re.Pattern[str]], text: str, *, limit: int = 5) -> list[str]:
    matches: list[str] = []
    for pattern in patterns:
        for match in pattern.finditer(text):
            snippet = match.group(0).strip()
            if snippet and snippet not in matches:
                matches.append(snippet)
            if len(matches) >= limit:
                return matches
    return matches


def prompt_injection_signals(text: str) -> list[str]:
    rendered = _render_text(text)
    strong = _collect_matches(STRONG_PROMPT_INJECTION_PATTERNS, rendered)
    if strong:
        return strong
    sensitive = _collect_matches(SENSITIVE_CONTEXT_PATTERNS, rendered)
    if len(sensitive) >= 2:
        return sensitive
    return []


def secret_exposure_signals(text: str) -> list[str]:
    return _collect_matches(SECRET_PATTERNS, _render_text(text))


def shadow_server_signals(text: str) -> list[str]:
    return _collect_matches(SHADOW_SERVER_PATTERNS, _render_text(text))


def _metadata_findings(text: str) -> list[GuardrailFinding]:
    findings: list[GuardrailFinding] = []
    injection_hits = prompt_injection_signals(text)
    if injection_hits:
        findings.append(
            GuardrailFinding(
                category="tool_poisoning",
                severity="high",
                action="block",
                title="Poisoned tool metadata",
                detail="Remote tool metadata includes prompt-injection patterns and cannot be exposed directly.",
                evidence=injection_hits,
            )
        )
    shadow_hits = shadow_server_signals(text)
    if shadow_hits:
        findings.append(
            GuardrailFinding(
                category="tool_poisoning",
                severity="medium",
                action="warn",
                title="Shadow-server routing hint",
                detail="Remote tool metadata suggests indirect or proxy-style routing and should stay behind a guarded wrapper.",
                evidence=shadow_hits,
            )
        )
    return findings


def scan_remote_tool_metadata(
    tool_cfg: dict[str, Any],
    remote_name: str,
    description: str,
) -> GuardrailScanReport:
    findings = _metadata_findings(description)
    return compile_scan_report(
        str(tool_cfg.get("id", "")),
        f"{tool_cfg.get('name', '')}::{remote_name}",
        "mcp_remote_tool",
        findings,
        phase="metadata",
        scanned_target=remote_name,
    )


def scan_tool_arguments(
    tool_cfg: dict[str, Any],
    arguments: dict[str, Any],
    *,
    remote_name: str | None = None,
) -> GuardrailScanReport:
    rendered = _render_text(arguments)
    findings: list[GuardrailFinding] = []
    injection_hits = prompt_injection_signals(rendered)
    if injection_hits:
        findings.append(
            GuardrailFinding(
                category="prompt_injection",
                severity="high",
                action="block",
                title="Prompt injection in tool input",
                detail="Tool input contains instruction-override patterns and was rejected before execution.",
                evidence=injection_hits,
            )
        )
    return compile_scan_report(
        str(tool_cfg.get("id", "")),
        str(tool_cfg.get("name", "")),
        str(tool_cfg.get("tool_type", "")),
        findings,
        phase="arguments",
        scanned_target=remote_name or str(tool_cfg.get("id", "")),
    )


def scan_tool_result(
    tool_cfg: dict[str, Any],
    result_text: str,
    *,
    remote_name: str | None = None,
) -> GuardrailScanReport:
    findings: list[GuardrailFinding] = []
    injection_hits = prompt_injection_signals(result_text)
    if injection_hits:
        findings.append(
            GuardrailFinding(
                category="prompt_injection",
                severity="critical",
                action="block",
                title="Prompt injection in tool output",
                detail="Tool output contains instruction-override content and was blocked before it could reach the model.",
                evidence=injection_hits,
            )
        )
    secret_hits = secret_exposure_signals(result_text)
    if secret_hits:
        findings.append(
            GuardrailFinding(
                category="secret_exposure",
                severity="critical",
                action="block",
                title="Secret leakage in tool output",
                detail="Tool output appears to contain credentials or bearer tokens and was blocked.",
                evidence=secret_hits,
            )
        )
    shadow_hits = shadow_server_signals(result_text)
    if shadow_hits and not findings:
        findings.append(
            GuardrailFinding(
                category="tool_poisoning",
                severity="medium",
                action="warn",
                title="Indirect routing hint in tool output",
                detail="Tool output mentions proxy-style routing and will stay behind the guarded wrapper.",
                evidence=shadow_hits,
            )
        )
    return compile_scan_report(
        str(tool_cfg.get("id", "")),
        str(tool_cfg.get("name", "")),
        str(tool_cfg.get("tool_type", "")),
        findings,
        phase="result",
        scanned_target=remote_name or str(tool_cfg.get("id", "")),
    )
