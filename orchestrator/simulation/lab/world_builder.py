"""Builds bounded market worlds for the Quorum simulation lab."""

from __future__ import annotations

from collections import Counter
from typing import Any

from pydantic import BaseModel, Field

from orchestrator.discovery_models import IdeaDossier, SimulationParameters


def _clamp(value: float, minimum: float = 0.0, maximum: float = 1.0) -> float:
    return max(minimum, min(maximum, value))


class MarketWorldConfig(BaseModel):
    world_name: str
    target_market: str
    segment_mix: dict[str, float] = Field(default_factory=dict)
    channel_strength: dict[str, float] = Field(default_factory=dict)
    competition_pressure: float
    network_density: float
    evidence_strength: float
    social_proof: float
    problem_surface: list[str] = Field(default_factory=list)
    objection_surface: list[str] = Field(default_factory=list)
    world_state: dict[str, Any] = Field(default_factory=dict)


def _infer_target_market(dossier: IdeaDossier, parameters: SimulationParameters) -> str:
    if parameters.target_market:
        return parameters.target_market
    idea = dossier.idea
    text = " ".join([idea.title, idea.summary, idea.description, " ".join(idea.topic_tags)]).lower()
    if any(token in text for token in ("consumer", "creator", "family", "personal", "social")):
        return "b2c"
    return "b2b"


def _segment_mix(dossier: IdeaDossier, target_market: str) -> dict[str, float]:
    focus = dossier.simulation_report
    if focus and focus.strongest_segments:
        base = {segment: 1.0 for segment in focus.strongest_segments}
    elif target_market == "b2c":
        base = {
            "creator_operator": 0.28,
            "skeptical_consumer": 0.24,
            "busy_manager": 0.22,
            "power_user": 0.26,
        }
    else:
        base = {
            "ops_lead": 0.24,
            "builder_founder": 0.23,
            "product_analyst": 0.21,
            "skeptical_exec": 0.18,
            "growth_owner": 0.14,
        }
    total = sum(base.values()) or 1.0
    return {label: round(value / total, 4) for label, value in base.items()}


def _channel_strength(dossier: IdeaDossier, parameters: SimulationParameters) -> dict[str, float]:
    idea = dossier.idea
    text = " ".join([idea.title, idea.summary, idea.description, " ".join(idea.topic_tags)]).lower()
    channel_strength = {
        "founder_outreach": 0.58,
        "content": 0.49,
        "community": 0.52,
        "referral": 0.46,
        "partner": 0.36,
        "social": 0.41,
    }
    if any(token in text for token in ("repo", "developer", "sdk", "api", "tooling")):
        channel_strength["community"] += 0.08
        channel_strength["content"] += 0.05
    if any(token in text for token in ("workflow", "ops", "triage", "automation")):
        channel_strength["founder_outreach"] += 0.06
        channel_strength["referral"] += 0.04
    if any(token in text for token in ("growth", "buyer", "market", "sales", "distribution")):
        channel_strength["partner"] += 0.08
        channel_strength["social"] += 0.06
    for key, value in list(channel_strength.items()):
        mix_bonus = parameters.channel_mix.get(key, 0.0) * 0.2
        channel_strength[key] = round(_clamp(value + mix_bonus), 4)
    return channel_strength


def build_market_world(dossier: IdeaDossier, parameters: SimulationParameters) -> MarketWorldConfig:
    target_market = _infer_target_market(dossier, parameters)
    focus = dossier.simulation_report

    evidence_count = len(dossier.observations) + len(dossier.validation_reports)
    if dossier.evidence_bundle:
        evidence_count += len(dossier.evidence_bundle.items)
    evidence_strength = 0.34 + min(0.24, evidence_count * 0.022)
    if focus:
        evidence_strength += focus.support_ratio * 0.12
    evidence_strength = round(_clamp(evidence_strength), 4)

    social_proof = 0.28
    if focus:
        social_proof += focus.support_ratio * 0.22
        social_proof += min(len(focus.positive_signals), 4) * 0.03
    social_proof = round(_clamp(social_proof), 4)

    problems = []
    problems.extend(dossier.idea.topic_tags[:4])
    problems.extend(item.summary for item in (dossier.evidence_bundle.items if dossier.evidence_bundle else [])[:3])
    problems.extend(report.summary for report in dossier.validation_reports[:2])

    objections = []
    if focus:
        objections.extend(focus.objections[:4])
    objections.extend(report.summary for report in dossier.validation_reports[:1])
    objections.extend(entry.reason for entry in dossier.archive_entries[:1])

    return MarketWorldConfig(
        world_name=f"{dossier.idea.title} market sandbox",
        target_market=target_market,
        segment_mix=_segment_mix(dossier, target_market),
        channel_strength=_channel_strength(dossier, parameters),
        competition_pressure=parameters.competition_pressure,
        network_density=parameters.network_density,
        evidence_strength=evidence_strength,
        social_proof=social_proof,
        problem_surface=list(dict.fromkeys(item for item in problems if item))[:8],
        objection_surface=list(dict.fromkeys(item for item in objections if item))[:8],
        world_state={
            "competition_pressure": parameters.competition_pressure,
            "network_density": parameters.network_density,
            "evidence_strength": evidence_strength,
            "social_proof": social_proof,
            "active_segments": list(_segment_mix(dossier, target_market).keys()),
        },
    )
