"""Typed models for the research sensing pipeline."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any, Literal
from uuid import uuid4

from pydantic import BaseModel, Field

from orchestrator.shared_contracts import Confidence


ResearchSource = Literal[
    "github",
    "github_trending",
    "hackernews",
    "reddit",
    "npm",
    "pypi",
    "producthunt",
    "stackoverflow",
]


def _utcnow() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


def _new_id(prefix: str) -> str:
    return f"{prefix}_{uuid4().hex[:12]}"


class ResearchObservation(BaseModel):
    observation_id: str = Field(default_factory=lambda: _new_id("research"))
    source: ResearchSource
    entity: str
    query: str
    url: str
    raw_text: str
    topic_tags: list[str] = Field(default_factory=list)
    pain_score: float = 0.0
    trend_score: float = 0.0
    evidence_confidence: Confidence = Confidence.MEDIUM
    collected_at: datetime = Field(default_factory=_utcnow)
    freshness_deadline: datetime | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class ScanRequest(BaseModel):
    query: str
    sources: list[ResearchSource] = Field(default_factory=list)
    max_items_per_source: int = 5
    freshness_window_hours: int | None = None


class ScheduledScanSeed(BaseModel):
    query: str
    sources: list[ResearchSource] = Field(default_factory=list)
    freshness_windows_hours: dict[ResearchSource, int] = Field(default_factory=dict)


class ResearchScanRun(BaseModel):
    run_id: str = Field(default_factory=lambda: _new_id("scan"))
    query: str
    sources: list[ResearchSource] = Field(default_factory=list)
    started_at: datetime = Field(default_factory=_utcnow)
    finished_at: datetime | None = None
    status: Literal["running", "completed", "failed"] = "running"
    observation_count: int = 0
    error_messages: list[str] = Field(default_factory=list)


class DailyQueueItem(BaseModel):
    queue_id: str = Field(default_factory=lambda: _new_id("queue"))
    observation: ResearchObservation
    priority_score: float
    bucket: Literal["daily", "weekly"]


class ResearchSearchResult(BaseModel):
    items: list[ResearchObservation] = Field(default_factory=list)
    total: int = 0


def default_freshness_deadline(hours: int) -> datetime:
    return (_utcnow() + timedelta(hours=hours)).replace(tzinfo=None)
