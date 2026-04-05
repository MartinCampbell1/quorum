"""Lightweight fact-check gate for debate-family protocols."""

from __future__ import annotations

import re
from typing import Callable

from pydantic import BaseModel, Field


_META_RE = re.compile(
    r"\b(i need|need .*permission|need search|need tool|need more context|cannot access|can't access|let me analyze first)\b",
    re.IGNORECASE,
)
_HARD_CLAIM_RE = re.compile(
    r"(\b\d+(?:\.\d+)?%|\b\d{2,}\b|\bstud(?:y|ies)\b|\bresearch shows\b|\bbenchmark\b|\bguarantee(?:d)?\b|\bproves?\b)",
    re.IGNORECASE,
)
_EVIDENCE_RE = re.compile(
    r"(https?://|github|readme|issue|commit|docs?/|test[s]?/|source|evidence|observed|measured|according to)",
    re.IGNORECASE,
)


class FactCheckIssue(BaseModel):
    code: str
    message: str
    severity: str = "medium"


class FactCheckReport(BaseModel):
    ok: bool
    issues: list[FactCheckIssue] = Field(default_factory=list)
    evidence_density: float = Field(default=0.0, ge=0.0, le=1.0)

    @property
    def retry_note(self) -> str:
        if not self.issues:
            return ""
        return "; ".join(issue.message for issue in self.issues)


class ValidatedTurn(BaseModel):
    response: str
    report: FactCheckReport
    retried: bool = False
    disqualified: bool = False
    disqualification_note: str = ""


def _evidence_density(text: str) -> float:
    tokens = max(len(re.findall(r"[a-z0-9_]+", str(text or ""), re.IGNORECASE)), 1)
    markers = len(_EVIDENCE_RE.findall(str(text or "")))
    return max(0.0, min(1.0, (markers * 8.0) / tokens))


def assess_argument(text: str) -> FactCheckReport:
    rendered = str(text or "").strip()
    if not rendered:
        return FactCheckReport(ok=False, issues=[FactCheckIssue(code="empty", message="response was empty", severity="high")], evidence_density=0.0)

    issues: list[FactCheckIssue] = []
    evidence_density = _evidence_density(rendered)
    if _META_RE.search(rendered):
        issues.append(FactCheckIssue(code="meta", message="response asked for more permissions or context instead of arguing", severity="high"))
    hard_claim = bool(_HARD_CLAIM_RE.search(rendered))
    if hard_claim and evidence_density < 0.05:
        issues.append(FactCheckIssue(code="unsupported_claim", message="response made hard numerical or study-like claims without visible support", severity="high"))
    elif hard_claim and evidence_density < 0.1:
        issues.append(FactCheckIssue(code="thin_evidence", message="response made hard claims with thin evidence support", severity="medium"))

    return FactCheckReport(
        ok=not any(issue.severity == "high" for issue in issues),
        issues=issues,
        evidence_density=round(evidence_density, 4),
    )


def validate_with_retry(
    *,
    response: str,
    responder: Callable[[str], str],
) -> ValidatedTurn:
    initial = assess_argument(response)
    if initial.ok:
        return ValidatedTurn(response=response, report=initial)

    retry_prompt = (
        "FACT-CHECK REVIEW FAILED.\n"
        f"Issues: {initial.retry_note or 'unsupported claims'}.\n"
        "Rewrite the answer using only supportable claims. Remove naked statistics or study references unless you can point to concrete evidence already in context."
    )
    retry_response = str(responder(retry_prompt) or "").strip()
    retry_report = assess_argument(retry_response)
    if retry_report.ok:
        return ValidatedTurn(response=retry_response, report=retry_report, retried=True)

    note = (
        "Disqualified after retry because the response still contained unsupported claims or meta/tool-seeking behavior."
    )
    return ValidatedTurn(
        response=retry_response or response,
        report=retry_report,
        retried=True,
        disqualified=True,
        disqualification_note=note,
    )
