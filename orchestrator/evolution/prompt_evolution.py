"""DEEVO-style prompt evolution hooks backed by comparison outcomes."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Mapping, Sequence

from orchestrator.evolution.archive import IdeaGenome, PromptEvolutionProfile


def _utcnow() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


def _default_profiles() -> dict[str, PromptEvolutionProfile]:
    return {
        "deevo_founder_fit": PromptEvolutionProfile(
            profile_id="deevo_founder_fit",
            label="Founder-fit exploit",
            operator_kind="exploit",
            instruction="Sharpen the first buyer, force a credible distribution wedge, and cut anything that smells like generic platform ambition.",
        ),
        "deevo_distribution_mutation": PromptEvolutionProfile(
            profile_id="deevo_distribution_mutation",
            label="Distribution mutation",
            operator_kind="mutate",
            instruction="Hold the pain constant, mutate only the go-to-market wedge until one unfair channel becomes obvious.",
        ),
        "deevo_cross_domain": PromptEvolutionProfile(
            profile_id="deevo_cross_domain",
            label="Cross-domain crossover",
            operator_kind="crossover",
            instruction="Fuse a high-signal pain domain with a distant distribution or data loop from another niche.",
        ),
        "deevo_risk_hardening": PromptEvolutionProfile(
            profile_id="deevo_risk_hardening",
            label="Risk hardening",
            operator_kind="mutate",
            instruction="Keep the thesis, but reduce execution or sales-cycle risk without flattening the idea into banality.",
        ),
    }


def infer_prompt_profile_id(genome: IdeaGenome) -> str:
    if genome.novelty_score >= 0.72 and genome.domain in {"research_data", "security", "compliance"}:
        return "deevo_cross_domain"
    if genome.distribution_strategy in {"github", "integration", "community"}:
        return "deevo_distribution_mutation"
    if genome.complexity in {"high", "frontier"} or genome.stability_score < 0.5:
        return "deevo_risk_hardening"
    return "deevo_founder_fit"


def _comparison_weight(record: Mapping[str, object]) -> float:
    try:
        return max(float(record.get("comparison_weight", 1.0)), 0.1)
    except (TypeError, ValueError):
        return 1.0


def evolve_prompt_profiles(
    genomes: Sequence[IdeaGenome],
    comparisons: Sequence[Mapping[str, object]],
) -> list[PromptEvolutionProfile]:
    profiles = _default_profiles()
    profile_by_idea: dict[str, str] = {}
    for genome in genomes:
        profile_id = genome.prompt_profile_id or infer_prompt_profile_id(genome)
        genome.prompt_profile_id = profile_id
        profile_by_idea[genome.idea_id] = profile_id
        profiles[profile_id].usage_count += 1

    for record in comparisons:
        verdict = str(record.get("verdict") or "").strip()
        left_id = str(record.get("left_idea_id") or "").strip()
        right_id = str(record.get("right_idea_id") or "").strip()
        if not left_id or not right_id:
            continue
        metadata = record.get("metadata")
        left_profile_id = ""
        right_profile_id = ""
        if isinstance(metadata, Mapping):
            left_profile_id = str(metadata.get("left_prompt_profile_id") or "").strip()
            right_profile_id = str(metadata.get("right_prompt_profile_id") or "").strip()
        left_profile_id = left_profile_id or profile_by_idea.get(left_id, "deevo_founder_fit")
        right_profile_id = right_profile_id or profile_by_idea.get(right_id, "deevo_founder_fit")
        left_profile = profiles[left_profile_id]
        right_profile = profiles[right_profile_id]
        weight = _comparison_weight(record)

        if verdict == "tie" or left_profile_id == right_profile_id:
            left_profile.ties += 1
            right_profile.ties += 1
            left_profile.elo_rating += weight * 0.5
            right_profile.elo_rating += weight * 0.5
        else:
            actual_left = 1.0 if verdict == "left" else 0.0
            expected_left = 1.0 / (1.0 + 10.0 ** ((right_profile.elo_rating - left_profile.elo_rating) / 400.0))
            delta = 18.0 * weight * (actual_left - expected_left)
            left_profile.elo_rating += delta
            right_profile.elo_rating -= delta
            if verdict == "left":
                left_profile.wins += 1
                right_profile.losses += 1
            else:
                right_profile.wins += 1
                left_profile.losses += 1

        source = str(record.get("judge_source") or "").strip()
        debate_bonus = 0.12 * weight if source in {"agent", "council"} else 0.05 * weight
        left_profile.debate_influence += debate_bonus
        right_profile.debate_influence += debate_bonus
        left_profile.last_updated = _utcnow()
        right_profile.last_updated = _utcnow()

    ordered = list(profiles.values())
    ordered.sort(key=lambda item: (item.elo_rating, item.wins - item.losses, item.usage_count), reverse=True)
    return ordered
