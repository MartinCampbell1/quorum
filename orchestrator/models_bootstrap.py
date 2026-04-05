"""Request/response models for the founder GitHub bootstrap pipeline."""
from __future__ import annotations

from pydantic import BaseModel, Field


class FounderBootstrapRequest(BaseModel):
    github_username: str
    max_repos: int = 100
    deep_scan_top_n: int = 8
    include_forks: bool = False
    include_archived: bool = False
    portfolio_id: str = "founder_default"


class InterestCluster(BaseModel):
    cluster_id: str
    label: str
    repos: list[str] = []
    topics: list[str] = []
    languages: list[str] = []
    strength: float = 0.0


class OpportunityHypothesis(BaseModel):
    hypothesis_id: str
    title: str
    description: str = ""
    source_clusters: list[str] = []
    unfair_advantages: list[str] = []
    likely_icps: list[str] = []
    confidence: float = 0.0
    provenance: str = "github_portfolio"


class FounderProfileSynthesis(BaseModel):
    interests: list[str] = []
    strengths: list[str] = []
    repeat_patterns: list[str] = []
    unfair_advantages: list[str] = []
    likely_icps: list[str] = []
    natural_distribution_wedges: list[str] = []


class FounderBootstrapResponse(BaseModel):
    github_username: str
    repos_scanned: int = 0
    repos_deep_scanned: int = 0
    profile: FounderProfileSynthesis = Field(default_factory=FounderProfileSynthesis)
    clusters: list[InterestCluster] = []
    hypotheses: list[OpportunityHypothesis] = []
