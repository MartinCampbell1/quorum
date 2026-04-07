"""Typed guardrail contracts and policy catalog."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Literal, Sequence

from pydantic import BaseModel, Field

GuardrailSeverity = Literal["low", "medium", "high", "critical"]
GuardrailAction = Literal["allow", "log", "warn", "block"]
GuardrailStatus = Literal["safe", "warn", "blocked"]
GuardrailWrapperMode = Literal["direct", "guarded", "blocked"]
GuardrailTrustLevel = Literal["trusted", "caution", "untrusted", "blocked"]


POLICY_CATALOG: list[dict[str, str]] = [
    {
        "code": "MCP-2025-01",
        "category": "prompt_injection",
        "title": "Prompt injection and instruction override",
        "description": "Reject tool descriptions, inputs, or outputs that try to override system, developer, or operator instructions.",
    },
    {
        "code": "MCP-2025-02",
        "category": "tool_poisoning",
        "title": "Tool poisoning and shadow servers",
        "description": "Detect poisoned tool metadata, suspicious server indirection, and remote tools that try to manipulate routing.",
    },
    {
        "code": "MCP-2025-03",
        "category": "unsafe_transport",
        "title": "Unsafe transport and connector posture",
        "description": "Block insecure remote transports and flag suspicious private or shadow endpoints before enabling them.",
    },
    {
        "code": "MCP-2025-04",
        "category": "supply_chain",
        "title": "Supply-chain and launcher risk",
        "description": "Warn on unpinned package runners, shell launchers, and code execution chains used to start MCP servers.",
    },
    {
        "code": "MCP-2025-05",
        "category": "secret_exposure",
        "title": "Secrets and sensitive context exposure",
        "description": "Warn when configs include inline secrets and block outputs that leak tokens or credentials.",
    },
    {
        "code": "MCP-2025-06",
        "category": "unsafe_capability",
        "title": "Destructive or high-impact tool capability",
        "description": "Mark shell, SSH, and code execution surfaces as high-risk and require explicit guarded posture.",
    },
]


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class GuardrailFinding(BaseModel):
    """A single policy hit emitted by config or runtime scans."""

    finding_id: str = Field(default_factory=lambda: f"grf_{uuid.uuid4().hex[:12]}")
    category: str
    severity: GuardrailSeverity
    action: GuardrailAction
    title: str
    detail: str
    evidence: list[str] = Field(default_factory=list)


class GuardrailScanReport(BaseModel):
    """Consolidated scan result for one tool or runtime observation."""

    report_id: str = Field(default_factory=lambda: f"grr_{uuid.uuid4().hex[:12]}")
    tool_id: str
    tool_name: str
    tool_type: str
    phase: str = "config"
    status: GuardrailStatus = "safe"
    recommended_action: GuardrailAction = "allow"
    wrapper_mode: GuardrailWrapperMode = "direct"
    trust_level: GuardrailTrustLevel = "trusted"
    findings: list[GuardrailFinding] = Field(default_factory=list)
    summary: str = "No guardrail issues detected."
    scanned_target: str = ""
    scanned_at: str = Field(default_factory=utc_now_iso)


class GuardrailAuditEvent(BaseModel):
    """Append-only audit entry for guardrail decisions."""

    event_id: str = Field(default_factory=lambda: f"gra_{uuid.uuid4().hex[:12]}")
    created_at: str = Field(default_factory=utc_now_iso)
    source: str
    action: str
    phase: str
    tool_id: str | None = None
    tool_name: str | None = None
    detail: str
    report: dict = Field(default_factory=dict)
    metadata: dict = Field(default_factory=dict)


def _highest_action(findings: Sequence[GuardrailFinding]) -> GuardrailAction:
    if any(finding.action == "block" for finding in findings):
        return "block"
    if any(finding.action == "warn" for finding in findings):
        return "warn"
    if any(finding.action == "log" for finding in findings):
        return "log"
    return "allow"


def _highest_severity(findings: Sequence[GuardrailFinding]) -> GuardrailSeverity | None:
    rank = {"low": 0, "medium": 1, "high": 2, "critical": 3}
    ordered = sorted(findings, key=lambda finding: rank[finding.severity], reverse=True)
    return ordered[0].severity if ordered else None


def _summary_for_findings(findings: Sequence[GuardrailFinding]) -> str:
    if not findings:
        return "No guardrail issues detected."
    titles = ", ".join(finding.title for finding in findings[:3])
    if len(findings) > 3:
        titles += f" (+{len(findings) - 3} more)"
    return titles


def compile_scan_report(
    tool_id: str,
    tool_name: str,
    tool_type: str,
    findings: Sequence[GuardrailFinding],
    *,
    phase: str = "config",
    scanned_target: str = "",
) -> GuardrailScanReport:
    findings_list = list(findings)
    recommended_action = _highest_action(findings_list)
    highest_severity = _highest_severity(findings_list)
    status: GuardrailStatus = "safe"
    wrapper_mode: GuardrailWrapperMode = "direct"
    trust_level: GuardrailTrustLevel = "trusted"
    if recommended_action == "block":
        status = "blocked"
        wrapper_mode = "blocked"
        trust_level = "blocked"
    elif recommended_action in {"warn", "log"}:
        status = "warn"
        trust_level = "untrusted" if highest_severity in {"high", "critical"} else "caution"
        if tool_type == "mcp_server":
            wrapper_mode = "guarded"
    return GuardrailScanReport(
        tool_id=tool_id,
        tool_name=tool_name,
        tool_type=tool_type,
        phase=phase,
        status=status,
        recommended_action=recommended_action,
        wrapper_mode=wrapper_mode,
        trust_level=trust_level,
        findings=findings_list,
        summary=_summary_for_findings(findings_list),
        scanned_target=scanned_target,
    )


def policy_catalog_payload() -> list[dict[str, str]]:
    return list(POLICY_CATALOG)
