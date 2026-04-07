"""Shared contracts that must stay identical between Quorum and Autopilot."""

from __future__ import annotations

from dataclasses import dataclass, field, fields, is_dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import Any, TypeVar, get_args, get_origin, get_type_hints


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


class Confidence(str, Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    UNKNOWN = "unknown"


class RiskLevel(str, Enum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    NEGLIGIBLE = "negligible"


class EffortEstimate(str, Enum):
    TRIVIAL = "trivial"
    SMALL = "small"
    MEDIUM = "medium"
    LARGE = "large"
    EPIC = "epic"


class Urgency(str, Enum):
    NOW = "now"
    THIS_WEEK = "this_week"
    THIS_MONTH = "this_month"
    BACKLOG = "backlog"


class BudgetTier(str, Enum):
    MICRO = "micro"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    UNLIMITED = "unlimited"


class IdeaOutcomeStatus(str, Enum):
    VALIDATED = "validated"
    INVALIDATED = "invalidated"
    PIVOT_CANDIDATE = "pivot_candidate"
    EXECUTION_TRAP = "execution_trap"
    COST_TRAP = "cost_trap"
    FOLLOW_ON_OPPORTUNITY = "follow_on_opportunity"
    IN_PROGRESS = "in_progress"
    STALLED = "stalled"


class VerdictStatus(str, Enum):
    PASS = "pass"
    FAIL = "fail"
    PARTIAL = "partial"
    SKIP = "skip"


@dataclass
class EvidenceItem:
    evidence_id: str
    kind: str
    summary: str
    raw_content: str | None = None
    artifact_path: str | None = None
    source: str | None = None
    confidence: Confidence = Confidence.MEDIUM
    created_at: datetime = field(default_factory=_utcnow)
    tags: list[str] = field(default_factory=list)


@dataclass
class EvidenceBundle:
    bundle_id: str
    parent_id: str
    items: list[EvidenceItem] = field(default_factory=list)
    overall_confidence: Confidence = Confidence.MEDIUM
    created_at: datetime = field(default_factory=_utcnow)
    updated_at: datetime = field(default_factory=_utcnow)


@dataclass
class RiskItem:
    category: str
    description: str
    level: RiskLevel
    mitigation: str | None = None


@dataclass
class StoryDecompositionSeed:
    title: str
    description: str
    acceptance_criteria: list[str]
    effort: EffortEstimate = EffortEstimate.MEDIUM


@dataclass
class ExecutionBrief:
    brief_id: str
    idea_id: str
    title: str
    prd_summary: str
    acceptance_criteria: list[str]
    risks: list[RiskItem]
    recommended_tech_stack: list[str]
    first_stories: list[StoryDecompositionSeed]
    repo_dna_snapshot: dict | None = None
    judge_summary: str | None = None
    simulation_summary: str | None = None
    evidence: EvidenceBundle | None = None
    confidence: Confidence = Confidence.MEDIUM
    effort: EffortEstimate = EffortEstimate.MEDIUM
    urgency: Urgency = Urgency.BACKLOG
    budget_tier: BudgetTier = BudgetTier.MEDIUM
    created_at: datetime = field(default_factory=_utcnow)


@dataclass
class ExecutionOutcomeBundle:
    outcome_id: str
    brief_id: str
    idea_id: str
    status: IdeaOutcomeStatus
    verdict: VerdictStatus
    total_cost_usd: float
    total_duration_seconds: float
    stories_attempted: int
    stories_passed: int
    stories_failed: int
    bugs_found: int
    critic_pass_rate: float
    shipped_artifacts: list[str]
    failure_modes: list[str]
    lessons_learned: list[str]
    evidence: EvidenceBundle | None = None
    created_at: datetime = field(default_factory=_utcnow)


T = TypeVar("T")


def to_jsonable(value: Any) -> Any:
    """Serialize shared contract values to JSON-compatible primitives."""
    if is_dataclass(value):
        return {
            item.name: to_jsonable(getattr(value, item.name))
            for item in fields(value)
        }
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, datetime):
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        return value.isoformat()
    if isinstance(value, list):
        return [to_jsonable(item) for item in value]
    if isinstance(value, tuple):
        return [to_jsonable(item) for item in value]
    if isinstance(value, dict):
        return {str(key): to_jsonable(item) for key, item in value.items()}
    return value


def from_jsonable(cls: type[T], payload: Any) -> T:
    """Deserialize JSON-compatible payloads back into shared contract values."""
    return _coerce_value(cls, payload)


def _coerce_value(annotation: Any, value: Any) -> Any:
    origin = get_origin(annotation)
    args = get_args(annotation)

    if value is None:
        return None

    if is_dataclass(annotation):
        if not isinstance(value, dict):
            raise TypeError(f"Expected mapping for {annotation}, got {type(value)!r}")
        type_hints = get_type_hints(annotation)
        kwargs = {}
        for item in fields(annotation):
            if item.name not in value:
                continue
            kwargs[item.name] = _coerce_value(type_hints.get(item.name, item.type), value[item.name])
        return annotation(**kwargs)

    if type(None) in args:
        non_none = [item for item in args if item is not type(None)]
        target = non_none[0] if non_none else Any
        return _coerce_value(target, value)

    if origin is list:
        item_type = args[0] if args else Any
        return [_coerce_value(item_type, item) for item in value]

    if origin is dict:
        key_type = args[0] if args else Any
        value_type = args[1] if len(args) > 1 else Any
        return {
            _coerce_value(key_type, key): _coerce_value(value_type, item)
            for key, item in value.items()
        }

    if origin is tuple:
        item_types = args or (Any,)
        return tuple(
            _coerce_value(item_types[min(index, len(item_types) - 1)], item)
            for index, item in enumerate(value)
        )

    if origin is None and isinstance(annotation, type):
        if issubclass(annotation, Enum):
            return annotation(value)
        if annotation is datetime:
            if isinstance(value, datetime):
                return value
            parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=timezone.utc)
            return parsed.astimezone(timezone.utc).replace(tzinfo=None)

    if origin is None:
        return value

    return value


__all__ = [
    "BudgetTier",
    "Confidence",
    "EffortEstimate",
    "EvidenceBundle",
    "EvidenceItem",
    "ExecutionBrief",
    "ExecutionOutcomeBundle",
    "IdeaOutcomeStatus",
    "RiskItem",
    "RiskLevel",
    "StoryDecompositionSeed",
    "Urgency",
    "VerdictStatus",
    "from_jsonable",
    "to_jsonable",
]
