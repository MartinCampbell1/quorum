"""Typed models for idea evolution and archive checkpoints."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field


DOMAIN_BUCKETS = [
    "developer_tooling",
    "compliance",
    "security",
    "operations",
    "sales_marketing",
    "finance",
    "research_data",
    "consumer",
    "general",
]
COMPLEXITY_LEVELS = ["low", "medium", "high", "frontier"]
DISTRIBUTION_STRATEGIES = [
    "github",
    "integration",
    "outbound",
    "community",
    "content",
    "marketplace",
    "sales_led",
    "ecosystem",
]
BUYER_TYPES = [
    "developer",
    "operator",
    "compliance",
    "executive",
    "founder",
    "consumer",
    "smb",
]


def _utcnow() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


def _new_id(prefix: str) -> str:
    return f"{prefix}_{uuid4().hex[:12]}"


def cell_key_for_axes(
    domain: str,
    complexity: str,
    distribution_strategy: str,
    buyer_type: str,
) -> str:
    return "|".join(
        [
            str(domain or "general").strip(),
            str(complexity or "medium").strip(),
            str(distribution_strategy or "integration").strip(),
            str(buyer_type or "operator").strip(),
        ]
    )


def total_possible_cells() -> int:
    return len(DOMAIN_BUCKETS) * len(COMPLEXITY_LEVELS) * len(DISTRIBUTION_STRATEGIES) * len(BUYER_TYPES)


class PromptEvolutionProfile(BaseModel):
    profile_id: str
    label: str
    operator_kind: str
    instruction: str
    elo_rating: float = 1200.0
    wins: int = 0
    losses: int = 0
    ties: int = 0
    usage_count: int = 0
    debate_influence: float = 0.0
    last_updated: datetime = Field(default_factory=_utcnow)
    metadata: dict[str, Any] = Field(default_factory=dict)


class IdeaGenome(BaseModel):
    genome_id: str = Field(default_factory=lambda: _new_id("genome"))
    idea_id: str
    title: str
    lineage_idea_ids: list[str] = Field(default_factory=list)
    domain: str
    complexity: str
    distribution_strategy: str
    buyer_type: str
    fitness: float = Field(default=0.0, ge=0.0, le=1.0)
    novelty_score: float = Field(default=0.0, ge=0.0, le=1.0)
    rating: float = 0.0
    merit_score: float = Field(default=0.0, ge=0.0, le=1.0)
    stability_score: float = Field(default=0.0, ge=0.0, le=1.0)
    prompt_profile_id: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=_utcnow)

    @property
    def cell_key(self) -> str:
        return cell_key_for_axes(
            self.domain,
            self.complexity,
            self.distribution_strategy,
            self.buyer_type,
        )


class IdeaArchiveCell(BaseModel):
    cell_id: str = Field(default_factory=lambda: _new_id("cell"))
    key: str
    domain: str
    complexity: str
    distribution_strategy: str
    buyer_type: str
    elite: IdeaGenome
    replaced_genome_id: str | None = None
    occupied_at: datetime = Field(default_factory=_utcnow)


class EvolutionRecommendation(BaseModel):
    recommendation_id: str = Field(default_factory=lambda: _new_id("reco"))
    operator_kind: str
    headline: str
    description: str
    source_genome_ids: list[str] = Field(default_factory=list)
    target_axes: dict[str, str] = Field(default_factory=dict)
    prompt_profile_id: str | None = None


class ArchiveCheckpointDigest(BaseModel):
    checkpoint_id: str
    generation: int
    filled_cells: int
    coverage: float
    qd_score: float
    created_at: datetime


class IdeaArchiveSnapshot(BaseModel):
    archive_id: str = Field(default_factory=lambda: _new_id("archive"))
    generation: int = 0
    total_possible_cells: int = Field(default_factory=total_possible_cells)
    filled_cells: int = 0
    coverage: float = Field(default=0.0, ge=0.0, le=1.0)
    qd_score: float = 0.0
    diversity_score: float = Field(default=0.0, ge=0.0, le=1.0)
    novelty_mean: float = Field(default=0.0, ge=0.0, le=1.0)
    cells: list[IdeaArchiveCell] = Field(default_factory=list)
    top_genomes: list[IdeaGenome] = Field(default_factory=list)
    prompt_profiles: list[PromptEvolutionProfile] = Field(default_factory=list)
    recommendations: list[EvolutionRecommendation] = Field(default_factory=list)
    checkpoints: list[ArchiveCheckpointDigest] = Field(default_factory=list)
    checkpointed: bool = False
    created_at: datetime = Field(default_factory=_utcnow)
