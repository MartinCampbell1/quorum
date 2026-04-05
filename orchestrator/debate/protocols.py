"""Reusable debate protocol registry and telemetry helpers."""

from __future__ import annotations

import re
from dataclasses import dataclass
from statistics import fmean
from typing import Any, Literal

from pydantic import BaseModel, Field


ProtocolName = Literal[
    "standard_debate",
    "dag_debate",
    "crossfire",
    "panel_judging",
    "creator_critic",
    "council_vote",
]

_TOKEN_RE = re.compile(r"[a-z0-9_]+", re.IGNORECASE)
_EVIDENCE_RE = re.compile(
    r"(https?://|github|readme|issue|pr\b|commit|docs?/|test[s]?/|evidence|data|study|benchmark|source|observed|measured)",
    re.IGNORECASE,
)


def _clamp(value: float, minimum: float = 0.0, maximum: float = 1.0) -> float:
    return max(minimum, min(maximum, value))


def _token_set(text: str) -> set[str]:
    return {token.lower() for token in _TOKEN_RE.findall(str(text or ""))}


def _text_similarity(left: str, right: str) -> float:
    left_tokens = _token_set(left)
    right_tokens = _token_set(right)
    if not left_tokens and not right_tokens:
        return 1.0
    union = left_tokens | right_tokens
    if not union:
        return 1.0
    return len(left_tokens & right_tokens) / len(union)


def _evidence_density(texts: list[str]) -> float:
    if not texts:
        return 0.0
    densities: list[float] = []
    for text in texts:
        tokens = max(len(_TOKEN_RE.findall(text)), 1)
        markers = len(_EVIDENCE_RE.findall(text))
        densities.append(_clamp((markers * 9.0) / tokens))
    return round(fmean(densities), 4)


def _novelty_score(texts: list[str]) -> float:
    if len(texts) < 2:
        return 0.6 if texts else 0.0
    similarities = [_text_similarity(left, right) for left, right in zip(texts, texts[1:])]
    return round(_clamp(1.0 - fmean(similarities)), 4)


@dataclass(frozen=True)
class DebateProtocolSpec:
    name: ProtocolName
    display_name: str
    mode_family: str
    common_roles: tuple[str, ...]
    prompt_style: str
    supports_factcheck: bool
    supports_panel_judging: bool
    scrutiny_on_unanimous_consensus: bool
    telemetry_metrics: tuple[str, ...]
    default_rounds: int = 2
    notes: str = ""


class ProtocolTelemetry(BaseModel):
    protocol_name: str
    convergence: float = Field(default=0.0, ge=0.0, le=1.0)
    dissent: float = Field(default=0.0, ge=0.0, le=1.0)
    evidence_density: float = Field(default=0.0, ge=0.0, le=1.0)
    novelty: float = Field(default=0.0, ge=0.0, le=1.0)
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)


PROTOCOL_REGISTRY: dict[ProtocolName, DebateProtocolSpec] = {
    "standard_debate": DebateProtocolSpec(
        name="standard_debate",
        display_name="Standard Debate",
        mode_family="debate",
        common_roles=("proposer", "critic", "judge"),
        prompt_style="standard",
        supports_factcheck=True,
        supports_panel_judging=False,
        scrutiny_on_unanimous_consensus=False,
        telemetry_metrics=("convergence", "dissent", "evidence_density", "novelty", "confidence"),
        default_rounds=2,
        notes="Classic alternating pro/con rounds with an evidence-aware judge.",
    ),
    "dag_debate": DebateProtocolSpec(
        name="dag_debate",
        display_name="DAG Debate",
        mode_family="debate",
        common_roles=("proposer", "critic", "moderator", "judge"),
        prompt_style="dag",
        supports_factcheck=True,
        supports_panel_judging=False,
        scrutiny_on_unanimous_consensus=False,
        telemetry_metrics=("convergence", "evidence_density", "novelty", "confidence"),
        default_rounds=3,
        notes="Graph-like argument structure with explicit thesis/evidence/rebuttal steps.",
    ),
    "crossfire": DebateProtocolSpec(
        name="crossfire",
        display_name="Crossfire",
        mode_family="debate",
        common_roles=("proposer", "critic", "moderator", "judge"),
        prompt_style="crossfire",
        supports_factcheck=True,
        supports_panel_judging=False,
        scrutiny_on_unanimous_consensus=False,
        telemetry_metrics=("convergence", "dissent", "evidence_density", "confidence"),
        default_rounds=2,
        notes="Shorter, more adversarial turns with direct challenge-response structure.",
    ),
    "panel_judging": DebateProtocolSpec(
        name="panel_judging",
        display_name="Panel Judging",
        mode_family="tournament",
        common_roles=("proposer", "critic", "moderator", "judge", "red-team judge"),
        prompt_style="panel",
        supports_factcheck=True,
        supports_panel_judging=True,
        scrutiny_on_unanimous_consensus=False,
        telemetry_metrics=("convergence", "dissent", "evidence_density", "novelty", "confidence"),
        default_rounds=2,
        notes="Single or multi-judge panel with dissent surfaced instead of hidden.",
    ),
    "creator_critic": DebateProtocolSpec(
        name="creator_critic",
        display_name="Creator Critic",
        mode_family="creator_critic",
        common_roles=("proposer", "critic", "judge"),
        prompt_style="refinement",
        supports_factcheck=False,
        supports_panel_judging=False,
        scrutiny_on_unanimous_consensus=False,
        telemetry_metrics=("convergence", "novelty", "confidence"),
        default_rounds=3,
        notes="Iterative produce-review-refine loop.",
    ),
    "council_vote": DebateProtocolSpec(
        name="council_vote",
        display_name="Council Vote",
        mode_family="council",
        common_roles=("proposer", "critic", "moderator", "judge"),
        prompt_style="council",
        supports_factcheck=False,
        supports_panel_judging=False,
        scrutiny_on_unanimous_consensus=True,
        telemetry_metrics=("convergence", "dissent", "evidence_density", "novelty", "confidence"),
        default_rounds=2,
        notes="Board and democracy style aggregation with mandatory scrutiny on unanimity.",
    ),
}

MODE_DEFAULT_PROTOCOLS: dict[str, ProtocolName] = {
    "debate": "standard_debate",
    "tournament": "panel_judging",
    "tournament_match": "panel_judging",
    "board": "council_vote",
    "democracy": "council_vote",
    "creator_critic": "creator_critic",
}


def list_protocols() -> list[DebateProtocolSpec]:
    return list(PROTOCOL_REGISTRY.values())


def get_protocol(name: str) -> DebateProtocolSpec:
    normalized = str(name or "").strip().lower()
    if normalized not in PROTOCOL_REGISTRY:
        raise KeyError(f"Unknown debate protocol: {name}")
    return PROTOCOL_REGISTRY[normalized]  # type: ignore[index]


def resolve_protocol_for_mode(mode: str, config: dict[str, Any] | None = None) -> DebateProtocolSpec:
    requested = str((config or {}).get("protocol", "") or "").strip().lower()
    if requested:
        if requested in PROTOCOL_REGISTRY:
            return get_protocol(requested)
        if requested == "tournament_kernel":
            return get_protocol("panel_judging")
    default_name = MODE_DEFAULT_PROTOCOLS.get(str(mode or "").strip().lower(), "standard_debate")
    return get_protocol(default_name)


def build_protocol_telemetry(
    protocol_name: str,
    texts: list[str],
    confidence: float = 0.5,
    stances: list[str] | None = None,
) -> ProtocolTelemetry:
    normalized_confidence = _clamp(float(confidence))
    novelty = _novelty_score(texts)
    evidence_density = _evidence_density(texts)

    dissent = 0.0
    convergence = normalized_confidence
    if stances:
        normalized_stances = [str(item or "").strip().lower() for item in stances if str(item or "").strip()]
        if normalized_stances:
            top_count = max(normalized_stances.count(item) for item in set(normalized_stances))
            consensus_ratio = top_count / len(normalized_stances)
            dissent = round(_clamp(1.0 - consensus_ratio), 4)
            convergence = round(_clamp((consensus_ratio * 0.65) + (normalized_confidence * 0.35)), 4)
    else:
        convergence = round(_clamp((normalized_confidence * 0.6) + ((1.0 - novelty) * 0.1) + (evidence_density * 0.3)), 4)
        dissent = round(_clamp((1.0 - normalized_confidence) * 0.55 + novelty * 0.45), 4)

    return ProtocolTelemetry(
        protocol_name=protocol_name,
        convergence=convergence,
        dissent=dissent,
        evidence_density=evidence_density,
        novelty=novelty,
        confidence=round(normalized_confidence, 4),
    )
