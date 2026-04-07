"""Deterministic self-play matches for prompt-profile evaluation."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Iterable, Literal
from uuid import uuid4

from pydantic import BaseModel, Field

from orchestrator.evolution.archive import PromptEvolutionProfile
from orchestrator.improvement.reflective_eval import ImprovementRole, ReflectiveEvalReport


SignalKind = Literal[
    "buyer",
    "distribution",
    "evidence",
    "risk",
    "scope",
    "novelty",
    "unsupported_claims",
    "scorecard",
]

_SIGNAL_TERMS: dict[SignalKind, tuple[str, ...]] = {
    "buyer": ("buyer", "icp", "segment", "persona", "founder", "operator", "customer"),
    "distribution": ("distribution", "channel", "wedge", "gtm", "go-to-market", "github", "integration", "outbound"),
    "evidence": ("evidence", "source", "metric", "repo", "issue", "readme", "validation", "benchmark"),
    "risk": ("risk", "objection", "failure", "trap", "downside", "constraint"),
    "scope": ("mvp", "thin slice", "first story", "scope", "narrow", "smallest"),
    "novelty": ("novel", "non-obvious", "adjacent", "surprising", "unfair"),
    "unsupported_claims": ("unsupported", "unverified", "discount", "hallucination"),
    "scorecard": ("scorecard", "criteria", "confidence", "rationale", "evidence used"),
}

_FAILURE_TAG_TO_SIGNALS: dict[str, tuple[SignalKind, ...]] = {
    "genericity": ("buyer", "distribution", "novelty"),
    "weak_distribution": ("distribution",),
    "evidence_gaps": ("evidence", "unsupported_claims"),
    "risk_blindness": ("risk",),
    "overbuild": ("scope",),
    "critic_softness": ("risk", "unsupported_claims"),
    "judge_leniency": ("unsupported_claims", "scorecard", "evidence"),
    "novelty_collapse": ("novelty",),
}


def _utcnow() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


def _new_id(prefix: str) -> str:
    return f"{prefix}_{uuid4().hex[:12]}"


def _compact(text: str | None, limit: int = 240) -> str:
    collapsed = " ".join(str(text or "").split())
    if len(collapsed) <= limit:
        return collapsed
    return f"{collapsed[: limit - 1].rstrip()}…"


class SelfPlayChallengeCard(BaseModel):
    challenge_id: str = Field(default_factory=lambda: _new_id("challenge"))
    task: str
    desired_signals: list[SignalKind] = Field(default_factory=list)
    pressure_tags: list[str] = Field(default_factory=list)
    role_focus: list[ImprovementRole] = Field(default_factory=list)


class SelfPlayCaseResult(BaseModel):
    challenge_id: str
    left_score: float = Field(default=0.0, ge=0.0, le=1.0)
    right_score: float = Field(default=0.0, ge=0.0, le=1.0)
    winner: Literal["left", "right", "tie"] = "tie"
    rationale: str = ""


class PromptSelfPlayMatch(BaseModel):
    match_id: str = Field(default_factory=lambda: _new_id("selfplay"))
    left_profile_id: str
    right_profile_id: str
    role_focus: list[ImprovementRole] = Field(default_factory=list)
    challenge_cards: list[SelfPlayChallengeCard] = Field(default_factory=list)
    case_results: list[SelfPlayCaseResult] = Field(default_factory=list)
    left_score_total: float = Field(default=0.0, ge=0.0, le=1.0)
    right_score_total: float = Field(default=0.0, ge=0.0, le=1.0)
    winner_profile_id: str | None = None
    winner_reason: str = ""
    created_at: datetime = Field(default_factory=_utcnow)


def build_challenge_cards(
    *,
    task: str,
    reflections: Iterable[ReflectiveEvalReport],
    role_focus: list[ImprovementRole],
    challenge_count: int,
) -> list[SelfPlayChallengeCard]:
    normalized_task = _compact(task or "Improve startup discovery quality for founder-facing product ideation.", 220)
    collected_tags: list[str] = []
    for reflection in reflections:
        for tag in reflection.failure_tags:
            if tag not in collected_tags:
                collected_tags.append(tag)
    collected_tags = collected_tags[:4]
    role_focus = role_focus or ["generator", "judge", "critic"]

    cards: list[SelfPlayChallengeCard] = []
    if "generator" in role_focus:
        cards.append(
            SelfPlayChallengeCard(
                task=normalized_task,
                desired_signals=["buyer", "distribution", "scope", "risk", "novelty"],
                pressure_tags=collected_tags,
                role_focus=["generator"],
            )
        )
    if "judge" in role_focus:
        cards.append(
            SelfPlayChallengeCard(
                task=f"Judge the outputs for: {normalized_task}",
                desired_signals=["evidence", "unsupported_claims", "scorecard", "risk"],
                pressure_tags=[tag for tag in collected_tags if tag in {"judge_leniency", "evidence_gaps", "genericity"}],
                role_focus=["judge"],
            )
        )
    if "critic" in role_focus:
        cards.append(
            SelfPlayChallengeCard(
                task=f"Stress-test the strongest candidate for: {normalized_task}",
                desired_signals=["risk", "unsupported_claims", "distribution", "scope"],
                pressure_tags=[tag for tag in collected_tags if tag in {"critic_softness", "overbuild", "weak_distribution", "risk_blindness"}],
                role_focus=["critic"],
            )
        )

    if not cards:
        cards.append(
            SelfPlayChallengeCard(
                task=normalized_task,
                desired_signals=["buyer", "distribution", "evidence", "risk"],
                pressure_tags=collected_tags,
                role_focus=["generator", "judge", "critic"],
            )
        )
    return cards[: max(1, challenge_count)]


def _role_text(profile: PromptEvolutionProfile, role_focus: list[ImprovementRole]) -> str:
    metadata = dict(profile.metadata or {})
    parts = [profile.instruction]
    if not role_focus or "generator" in role_focus:
        parts.append(str(metadata.get("generator_prefix") or ""))
    if not role_focus or "judge" in role_focus:
        parts.append(str(metadata.get("judge_prefix") or ""))
    if not role_focus or "critic" in role_focus:
        parts.append(str(metadata.get("critic_prefix") or ""))
    parts.extend(str(item) for item in list(metadata.get("tactics") or []))
    return "\n".join(part for part in parts if part).lower()


def _score_profile(profile: PromptEvolutionProfile, card: SelfPlayChallengeCard) -> float:
    text = _role_text(profile, card.role_focus)
    coverage = 0.0
    for signal in card.desired_signals:
        terms = _SIGNAL_TERMS.get(signal, ())
        if any(term in text for term in terms):
            coverage += 1.0

    failure_resolutions = 0.0
    for tag in card.pressure_tags:
        related_signals = _FAILURE_TAG_TO_SIGNALS.get(tag, ())
        if related_signals and any(any(term in text for term in _SIGNAL_TERMS.get(signal, ())) for signal in related_signals):
            failure_resolutions += 1.0

    metadata = dict(profile.metadata or {})
    tactics_bonus = min(len(list(metadata.get("tactics") or [])), 6) * 0.015
    score = 0.42
    if card.desired_signals:
        score += 0.4 * (coverage / len(card.desired_signals))
    if card.pressure_tags:
        score += 0.15 * (failure_resolutions / len(card.pressure_tags))
    score += tactics_bonus
    return max(0.0, min(score, 1.0))


def play_profiles(
    left: PromptEvolutionProfile,
    right: PromptEvolutionProfile,
    *,
    challenge_cards: list[SelfPlayChallengeCard],
    role_focus: list[ImprovementRole],
) -> PromptSelfPlayMatch:
    case_results: list[SelfPlayCaseResult] = []
    for card in challenge_cards:
        left_score = _score_profile(left, card)
        right_score = _score_profile(right, card)
        if abs(left_score - right_score) < 0.03:
            winner = "tie"
        else:
            winner = "left" if left_score > right_score else "right"
        rationale = (
            f"{left.label}={left_score:.2f}, {right.label}={right_score:.2f}. "
            f"Signals tested: {', '.join(card.desired_signals)}."
        )
        case_results.append(
            SelfPlayCaseResult(
                challenge_id=card.challenge_id,
                left_score=left_score,
                right_score=right_score,
                winner=winner,
                rationale=rationale,
            )
        )

    left_total = sum(item.left_score for item in case_results) / len(case_results)
    right_total = sum(item.right_score for item in case_results) / len(case_results)
    if abs(left_total - right_total) < 0.03:
        winner_profile_id = None
        winner_reason = "Profiles tie across the current challenge cards."
    elif left_total > right_total:
        winner_profile_id = left.profile_id
        winner_reason = f"{left.label} wins because it covers more required signals under the current failure pressure."
    else:
        winner_profile_id = right.profile_id
        winner_reason = f"{right.label} wins because it resolves more current failure tags without losing coverage."

    return PromptSelfPlayMatch(
        left_profile_id=left.profile_id,
        right_profile_id=right.profile_id,
        role_focus=role_focus,
        challenge_cards=challenge_cards,
        case_results=case_results,
        left_score_total=round(left_total, 4),
        right_score_total=round(right_total, 4),
        winner_profile_id=winner_profile_id,
        winner_reason=winner_reason,
    )
