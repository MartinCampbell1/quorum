"""Append-only audit store for guardrail decisions."""

from __future__ import annotations

import json
import threading
from pathlib import Path

from orchestrator.guardrails.policies import GuardrailAuditEvent, GuardrailScanReport


class GuardrailAuditStore:
    """Simple append-only JSONL audit store."""

    def __init__(self, path: str | Path | None = None):
        self._path = Path(path) if path else Path.home() / ".multi-agent" / "guardrail_audit.jsonl"
        self._lock = threading.Lock()

    def append(self, event: GuardrailAuditEvent) -> GuardrailAuditEvent:
        with self._lock:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            with self._path.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(event.model_dump(), ensure_ascii=False) + "\n")
        return event

    def list_recent(self, *, limit: int = 100, tool_id: str | None = None) -> list[GuardrailAuditEvent]:
        if not self._path.exists():
            return []
        events: list[GuardrailAuditEvent] = []
        with self._lock:
            with self._path.open(encoding="utf-8") as handle:
                for line in handle:
                    try:
                        payload = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    if tool_id and str(payload.get("tool_id") or "") != tool_id:
                        continue
                    try:
                        events.append(GuardrailAuditEvent.model_validate(payload))
                    except Exception:
                        continue
        events.sort(key=lambda item: item.created_at, reverse=True)
        return events[:limit]


def _report_excerpt(report: GuardrailScanReport | dict | None) -> dict:
    if report is None:
        return {}
    payload = report.model_dump() if isinstance(report, GuardrailScanReport) else dict(report)
    findings = payload.get("findings") or []
    payload["findings"] = findings[:5]
    return payload


guardrail_audit_store = GuardrailAuditStore()


def record_guardrail_event(
    *,
    source: str,
    action: str,
    phase: str,
    detail: str,
    tool_id: str | None = None,
    tool_name: str | None = None,
    report: GuardrailScanReport | dict | None = None,
    metadata: dict | None = None,
) -> GuardrailAuditEvent:
    event = GuardrailAuditEvent(
        source=source,
        action=action,
        phase=phase,
        tool_id=tool_id,
        tool_name=tool_name,
        detail=detail,
        report=_report_excerpt(report),
        metadata=metadata or {},
    )
    return guardrail_audit_store.append(event)
