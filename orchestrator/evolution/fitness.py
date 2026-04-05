"""Genome classification and fitness scoring for discovery ideas."""

from __future__ import annotations

from typing import Any, Mapping

from orchestrator.discovery_models import IdeaCandidate
from orchestrator.evolution.archive import IdeaGenome


def _clamp(value: float, minimum: float = 0.0, maximum: float = 1.0) -> float:
    return max(minimum, min(maximum, value))


def _normalized_score(value: object, default: float = 0.5) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return default
    if number > 1.0:
        number = number / 10.0
    return _clamp(number)


def _joined_text(idea: IdeaCandidate) -> str:
    return " ".join(
        part
        for part in [
            idea.title,
            idea.summary,
            idea.thesis,
            idea.description,
            " ".join(idea.topic_tags),
            " ".join(str(value) for value in (idea.provenance or {}).values() if isinstance(value, str)),
        ]
        if str(part or "").strip()
    ).lower()


def _has_any(text: str, needles: tuple[str, ...]) -> bool:
    return any(needle in text for needle in needles)


def infer_domain(idea: IdeaCandidate) -> str:
    text = _joined_text(idea)
    if _has_any(text, ("developer", "repo", "github", "code", "sdk", "api", "devtools")):
        return "developer_tooling"
    if _has_any(text, ("compliance", "audit", "policy", "regulatory", "governance")):
        return "compliance"
    if _has_any(text, ("security", "threat", "incident", "vulnerability", "soc2")):
        return "security"
    if _has_any(text, ("workflow", "operations", "ops", "approval", "support", "backoffice")):
        return "operations"
    if _has_any(text, ("sales", "marketing", "crm", "revops", "outreach", "pipeline")):
        return "sales_marketing"
    if _has_any(text, ("finance", "billing", "accounting", "payment", "procurement")):
        return "finance"
    if _has_any(text, ("research", "dataset", "knowledge", "evidence", "benchmark")):
        return "research_data"
    if _has_any(text, ("consumer", "family", "travel", "creator", "social", "personal")):
        return "consumer"
    return "general"


def infer_complexity(idea: IdeaCandidate) -> str:
    scorecard = dict(idea.latest_scorecard or {})
    buildability = _normalized_score(scorecard.get("buildability"), default=0.55)
    text = _joined_text(idea)
    if _has_any(text, ("research lab", "frontier", "new model", "foundation model")):
        return "frontier"
    if buildability >= 0.78:
        return "low"
    if buildability >= 0.58:
        return "medium"
    if buildability >= 0.34:
        return "high"
    return "frontier"


def infer_distribution_strategy(idea: IdeaCandidate) -> str:
    text = _joined_text(idea)
    if idea.source in {"github", "repo_graph", "repo_dna"} or _has_any(text, ("github", "repo", "oss", "developer community")):
        return "github"
    if _has_any(text, ("integration", "api", "plugin", "embedded", "workflow hook")):
        return "integration"
    if _has_any(text, ("community", "forum", "slack", "discord", "open source")):
        return "community"
    if _has_any(text, ("outbound", "sales team", "cold", "account list")):
        return "outbound"
    if _has_any(text, ("marketplace", "app store", "listing")):
        return "marketplace"
    if _has_any(text, ("content", "seo", "newsletter", "media")):
        return "content"
    if _has_any(text, ("ecosystem", "channel partner", "reseller", "platform partner")):
        return "ecosystem"
    return "sales_led"


def infer_buyer_type(idea: IdeaCandidate) -> str:
    text = _joined_text(idea)
    if _has_any(text, ("developer", "engineer", "cto", "sdk")):
        return "developer"
    if _has_any(text, ("compliance", "legal", "risk", "security leader")):
        return "compliance"
    if _has_any(text, ("ops", "operations", "support", "backoffice", "revops")):
        return "operator"
    if _has_any(text, ("founder", "indie hacker", "solo founder")):
        return "founder"
    if _has_any(text, ("consumer", "family", "parent", "traveler")):
        return "consumer"
    if _has_any(text, ("smb", "small business")):
        return "smb"
    return "executive"


def compute_novelty_score(idea: IdeaCandidate) -> float:
    scorecard = dict(idea.latest_scorecard or {})
    novelty_penalty = _normalized_score(scorecard.get("novelty_penalty"), default=0.25)
    topic_bonus = min(len(idea.topic_tags), 5) * 0.06
    source_bonus = 0.14 if idea.source in {"github", "research", "repo_graph", "repo_dna"} else 0.04
    return _clamp((1.0 - novelty_penalty) * 0.62 + topic_bonus + source_bonus)


def compute_fitness(
    idea: IdeaCandidate,
    *,
    rating: float = 1200.0,
    merit_score: float = 0.5,
    stability_score: float = 0.5,
) -> tuple[float, dict[str, float]]:
    scorecard = dict(idea.latest_scorecard or {})
    rating_component = _clamp((float(rating) - 900.0) / 600.0)
    evidence = _normalized_score(scorecard.get("evidence_quality"), default=0.52)
    ai_necessity = _normalized_score(scorecard.get("ai_necessity"), default=0.56)
    distribution = _normalized_score(scorecard.get("distribution_plausibility"), default=0.55)
    moat = _normalized_score(scorecard.get("moat"), default=0.48)
    novelty = compute_novelty_score(idea)
    fitness = _clamp(
        (rating_component * 0.34)
        + (_clamp(merit_score) * 0.16)
        + (_clamp(stability_score) * 0.16)
        + (evidence * 0.12)
        + (distribution * 0.08)
        + (moat * 0.06)
        + (ai_necessity * 0.08)
        + (novelty * 0.10)
    )
    return fitness, {
        "rating": round(rating_component, 4),
        "merit": round(_clamp(merit_score), 4),
        "stability": round(_clamp(stability_score), 4),
        "evidence_quality": round(evidence, 4),
        "distribution_plausibility": round(distribution, 4),
        "moat": round(moat, 4),
        "ai_necessity": round(ai_necessity, 4),
        "novelty": round(novelty, 4),
    }


def _get_value(entry: Mapping[str, Any] | Any, key: str, default: Any) -> Any:
    if isinstance(entry, Mapping):
        return entry.get(key, default)
    return getattr(entry, key, default)


def build_idea_genome(
    idea: IdeaCandidate,
    ranked_entry: Mapping[str, Any] | Any,
    *,
    prompt_profile_id: str | None = None,
) -> IdeaGenome:
    rating = float(_get_value(ranked_entry, "rating", 1200.0))
    merit_score = float(_get_value(ranked_entry, "merit_score", idea.rank_score))
    stability_score = float(_get_value(ranked_entry, "stability_score", idea.belief_score))
    fitness, breakdown = compute_fitness(
        idea,
        rating=rating,
        merit_score=merit_score,
        stability_score=stability_score,
    )
    novelty = breakdown["novelty"]
    return IdeaGenome(
        idea_id=idea.idea_id,
        title=idea.title,
        lineage_idea_ids=list(dict.fromkeys([*idea.lineage_parent_ids, *idea.evolved_from])),
        domain=infer_domain(idea),
        complexity=infer_complexity(idea),
        distribution_strategy=infer_distribution_strategy(idea),
        buyer_type=infer_buyer_type(idea),
        fitness=round(fitness, 4),
        novelty_score=round(novelty, 4),
        rating=round(rating, 4),
        merit_score=round(_clamp(merit_score), 4),
        stability_score=round(_clamp(stability_score), 4),
        prompt_profile_id=prompt_profile_id,
        metadata={
            "fitness_breakdown": breakdown,
            "source": idea.source,
            "swipe_state": idea.swipe_state,
            "latest_scorecard": dict(idea.latest_scorecard or {}),
        },
    )
