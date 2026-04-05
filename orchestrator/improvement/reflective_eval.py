"""Reflective evaluation helpers for prompt-improvement loops."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, Literal
from uuid import uuid4

from pydantic import BaseModel, Field


ImprovementRole = Literal["generator", "judge", "critic"]

_GENERIC_PHRASES = ("ai saas", "platform", "end-to-end", "all-in-one", "marketplace of")
_BUYER_TERMS = ("buyer", "icp", "segment", "persona", "founder", "operator", "developer", "customer")
_DISTRIBUTION_TERMS = ("distribution", "channel", "gtm", "go-to-market", "wedge", "community", "github", "integration", "outbound")
_EVIDENCE_TERMS = ("evidence", "source", "benchmark", "metric", "observed", "validation", "repo", "issue", "readme", "data")
_RISK_TERMS = ("risk", "objection", "failure", "downside", "trap", "constraint")
_CRITIC_TERMS = ("challenge", "objection", "skeptic", "fatal", "counter", "risk")
_UNSUPPORTED_TERMS = ("unsupported", "hallucinat", "unverified", "weak claim", "discounted")
_NOVELTY_TERMS = ("novel", "non-obvious", "surprising", "adjacent", "unfair", "unexpected")
_SCOPE_TERMS = ("mvp", "thin slice", "first story", "scope", "small", "narrow")


def _utcnow() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


def _new_id(prefix: str) -> str:
    return f"{prefix}_{uuid4().hex[:12]}"


def _compact(text: str | None, limit: int = 220) -> str:
    collapsed = " ".join(str(text or "").split())
    if len(collapsed) <= limit:
        return collapsed
    return f"{collapsed[: limit - 1].rstrip()}…"


class ImprovementArtifact(BaseModel):
    artifact_id: str = Field(default_factory=lambda: _new_id("artifact"))
    role: ImprovementRole | str = "generator"
    content: str
    metadata: dict[str, Any] = Field(default_factory=dict)


class ReflectiveSignal(BaseModel):
    code: str
    severity: Literal["low", "medium", "high"] = "medium"
    detail: str
    target_roles: list[ImprovementRole] = Field(default_factory=list)
    suggested_patch: str = ""


class ReflectiveEvalReport(BaseModel):
    reflection_id: str = Field(default_factory=lambda: _new_id("reflection"))
    source_kind: str = "manual"
    source_id: str | None = None
    task: str = ""
    role_focus: list[ImprovementRole] = Field(default_factory=list)
    strengths: list[str] = Field(default_factory=list)
    failure_tags: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    signals: list[ReflectiveSignal] = Field(default_factory=list)
    score_hint: float = Field(default=0.5, ge=0.0, le=1.0)
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=_utcnow)


def _contains_any(text: str, terms: tuple[str, ...]) -> bool:
    lowered = text.lower()
    return any(term in lowered for term in terms)


def _detect_strengths(text: str, judge_scores: list[dict[str, Any]]) -> list[str]:
    strengths: list[str] = []
    if _contains_any(text, _BUYER_TERMS):
        strengths.append("Buyer or ICP is explicitly named instead of implied.")
    if _contains_any(text, _DISTRIBUTION_TERMS):
        strengths.append("Distribution wedge is surfaced as a concrete go-to-market mechanic.")
    if _contains_any(text, _EVIDENCE_TERMS):
        strengths.append("Evidence language is present, which helps the system avoid hand-wavy claims.")
    if _contains_any(text, _RISK_TERMS):
        strengths.append("The output admits risk rather than hiding it.")
    if _contains_any(text, _NOVELTY_TERMS):
        strengths.append("The framing pushes toward non-obvious or unfair angles.")

    overall_scores: list[float] = []
    for item in judge_scores:
        try:
            overall_scores.append(float(item.get("overall_score", 0.0)))
        except (TypeError, ValueError):
            continue
    if overall_scores and sum(overall_scores) / len(overall_scores) >= 7.6:
        strengths.append("Judge pack scores suggest the current prompt family is producing above-baseline candidates.")
    return strengths[:5]


def _append_signal(
    signals: list[ReflectiveSignal],
    failure_tags: list[str],
    recommendations: list[str],
    *,
    code: str,
    severity: Literal["low", "medium", "high"],
    detail: str,
    target_roles: list[ImprovementRole],
    suggested_patch: str,
    recommendation: str,
) -> None:
    if code not in failure_tags:
        failure_tags.append(code)
    signals.append(
        ReflectiveSignal(
            code=code,
            severity=severity,
            detail=detail,
            target_roles=target_roles,
            suggested_patch=suggested_patch,
        )
    )
    if recommendation not in recommendations:
        recommendations.append(recommendation)


def build_reflective_report(
    *,
    task: str,
    source_kind: str,
    source_id: str | None,
    artifacts: list[ImprovementArtifact],
    judge_scores: list[dict[str, Any]],
    failure_tags: list[str],
    notes: list[str],
    role_focus: list[ImprovementRole],
    metadata: dict[str, Any] | None = None,
) -> ReflectiveEvalReport:
    artifact_text = "\n\n".join(item.content for item in artifacts if item.content).strip()
    note_text = "\n".join(str(item) for item in notes if str(item).strip())
    text = "\n\n".join(part for part in (artifact_text, note_text) if part).strip()
    lowered = text.lower()

    derived_failure_tags = list(dict.fromkeys(tag for tag in failure_tags if tag))
    recommendations: list[str] = []
    signals: list[ReflectiveSignal] = []

    if (
        (_contains_any(lowered, _GENERIC_PHRASES) and not _contains_any(lowered, _BUYER_TERMS))
        or ("generic" in lowered and not _contains_any(lowered, _NOVELTY_TERMS))
    ):
        _append_signal(
            signals,
            derived_failure_tags,
            recommendations,
            code="genericity",
            severity="high",
            detail="The prompt family is allowing vague 'AI platform' framing without a named buyer or unfair wedge.",
            target_roles=["generator", "judge"],
            suggested_patch="Force the generator to name one buyer, one distribution wedge, and one reason this is not a generic AI wrapper.",
            recommendation="Tighten generator instructions around ICP clarity and ban generic platform language unless it is earned by evidence.",
        )

    if not _contains_any(lowered, _DISTRIBUTION_TERMS):
        _append_signal(
            signals,
            derived_failure_tags,
            recommendations,
            code="weak_distribution",
            severity="high",
            detail="The current artifacts do not force a concrete distribution or acquisition mechanic.",
            target_roles=["generator", "critic", "judge"],
            suggested_patch="Require a named acquisition wedge or integration path before a candidate can score highly.",
            recommendation="Make distribution wedge a hard requirement in generator output and a hard penalty in judge scoring.",
        )

    unsupported_count = sum(1 for item in judge_scores if _contains_any(str(item.get("rationale", "")), _UNSUPPORTED_TERMS))
    if not _contains_any(lowered, _EVIDENCE_TERMS) or unsupported_count:
        _append_signal(
            signals,
            derived_failure_tags,
            recommendations,
            code="evidence_gaps",
            severity="high",
            detail="Evidence support is thin or the judge rationale explicitly mentions unsupported claims.",
            target_roles=["generator", "judge"],
            suggested_patch="Force candidate memos to separate evidence used from evidence missing; tell judges to discount unsupported claims aggressively.",
            recommendation="Increase evidence pressure in both generator and judge templates so unsupported claims lose points instead of slipping through.",
        )

    if not _contains_any(lowered, _RISK_TERMS):
        _append_signal(
            signals,
            derived_failure_tags,
            recommendations,
            code="risk_blindness",
            severity="medium",
            detail="The outputs are not surfacing explicit execution or market failure modes.",
            target_roles=["generator", "critic"],
            suggested_patch="Require one fatal risk or trap per candidate and one concrete mitigation path.",
            recommendation="Bias prompts toward naming the biggest trap early instead of tacking risk on as a footnote.",
        )

    if _contains_any(lowered, _GENERIC_PHRASES) and not _contains_any(lowered, _SCOPE_TERMS):
        _append_signal(
            signals,
            derived_failure_tags,
            recommendations,
            code="overbuild",
            severity="medium",
            detail="The candidate framing sounds broader than a believable first sprint or MVP.",
            target_roles=["generator", "critic"],
            suggested_patch="Push the generator toward a thin slice, first story, or one-workflow MVP framing.",
            recommendation="Strengthen scope guardrails so ambition does not outrun execution fit.",
        )

    critic_artifacts = [item for item in artifacts if str(item.role) == "critic"]
    if critic_artifacts and not _contains_any("\n".join(item.content for item in critic_artifacts).lower(), _CRITIC_TERMS):
        _append_signal(
            signals,
            derived_failure_tags,
            recommendations,
            code="critic_softness",
            severity="medium",
            detail="Critic turns exist but they are not pushing on objections, fatal flaws, or execution traps hard enough.",
            target_roles=["critic"],
            suggested_patch="Tell critics to surface one kill shot, one evidence gap, and one execution trap every time.",
            recommendation="Make critic templates less polite and more falsification-oriented.",
        )

    if judge_scores:
        numeric_scores: list[float] = []
        for item in judge_scores:
            try:
                numeric_scores.append(float(item.get("overall_score", 0.0)))
            except (TypeError, ValueError):
                continue
        if numeric_scores and (sum(numeric_scores) / len(numeric_scores)) > 8.6 and unsupported_count:
            _append_signal(
                signals,
                derived_failure_tags,
                recommendations,
                code="judge_leniency",
                severity="medium",
                detail="Judge scores remain too generous even when rationales mention unsupported claims.",
                target_roles=["judge"],
                suggested_patch="Lower judge scores when evidence is missing and require an explicit discounted-claims section.",
                recommendation="Harden judge templates so high scores require evidence-backed reasoning, not polished prose.",
            )

    if not _contains_any(lowered, _NOVELTY_TERMS):
        _append_signal(
            signals,
            derived_failure_tags,
            recommendations,
            code="novelty_collapse",
            severity="low",
            detail="The outputs are not signaling any non-obvious wedge or adjacent-domain move.",
            target_roles=["generator", "judge"],
            suggested_patch="Reinforce anti-banality and require one surprising but believable edge.",
            recommendation="Inject more novelty pressure into prompt variants so the system does not regress to safe generic startup ideas.",
        )

    strengths = _detect_strengths(text, judge_scores)
    if not role_focus:
        focus: list[ImprovementRole] = []
        for signal in signals:
            for role in signal.target_roles:
                if role not in focus:
                    focus.append(role)
        role_focus = focus or ["generator", "judge", "critic"]

    score_hint = 0.62 + (0.05 * len(strengths)) - (0.08 * len(derived_failure_tags))
    score_hint = max(0.05, min(score_hint, 0.95))
    return ReflectiveEvalReport(
        source_kind=source_kind,
        source_id=source_id,
        task=_compact(task, 260),
        role_focus=role_focus,
        strengths=strengths,
        failure_tags=derived_failure_tags,
        recommendations=recommendations,
        signals=signals,
        score_hint=score_hint,
        metadata=dict(metadata or {}),
    )
