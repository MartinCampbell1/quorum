"""Machine-readable bounded protocol graphs and replayable traces."""

from __future__ import annotations

import hashlib
import json
import time
import uuid
from typing import Any, Literal

from pydantic import BaseModel, Field


ENTRY_NODE_ID = "__entry__"
TERMINAL_NODE_ID = "__end__"

FieldType = Literal["string", "number", "integer", "boolean", "array", "object", "null"]
PredicateOperator = Literal[
    "eq",
    "ne",
    "lt",
    "lte",
    "gt",
    "gte",
    "truthy",
    "falsy",
    "nonempty",
    "in",
    "contains",
    "not_contains",
]
PredicateMatch = Literal["all", "any"]


def stable_payload_hash(payload: dict[str, Any]) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha1(encoded.encode("utf-8")).hexdigest()


class OutputFieldSpec(BaseModel):
    name: str
    field_type: FieldType
    required: bool = True
    description: str = ""


class GuardPredicate(BaseModel):
    field: str
    operator: PredicateOperator
    value: Any = None


class TransitionGuard(BaseModel):
    guard_id: str = Field(default_factory=lambda: f"guard_{uuid.uuid4().hex[:12]}")
    source_node_id: str
    target_node_id: str
    description: str = ""
    predicates: list[GuardPredicate] = Field(default_factory=list)
    predicate_match: PredicateMatch = "all"
    shadow_only: bool = True


class StateNode(BaseModel):
    node_id: str
    label: str
    stage: str
    purpose: str
    role_hints: list[str] = Field(default_factory=list)
    allowed_outputs: list[str] = Field(default_factory=list)
    output_schema: list[OutputFieldSpec] = Field(default_factory=list)
    state_reads: list[str] = Field(default_factory=list)
    state_writes: list[str] = Field(default_factory=list)


class TerminalState(BaseModel):
    node_id: str = TERMINAL_NODE_ID
    label: str = "Terminal"
    outcome: Literal["success", "cancelled", "failed", "warning"] = "success"
    description: str = ""


class ProtocolBlueprint(BaseModel):
    blueprint_id: str = Field(default_factory=lambda: f"pb_{uuid.uuid4().hex[:12]}")
    cache_key: str
    compiled_at: float = Field(default_factory=time.time)
    mode: str
    mode_family: str
    protocol_key: str
    blueprint_class: str
    entry_node_id: str
    nodes: list[StateNode] = Field(default_factory=list)
    transitions: list[TransitionGuard] = Field(default_factory=list)
    terminal_states: list[TerminalState] = Field(default_factory=lambda: [TerminalState()])
    bounded: bool = True
    notes: list[str] = Field(default_factory=list)
    compiled_from: dict[str, Any] = Field(default_factory=dict)
    planner_hints: dict[str, Any] = Field(default_factory=dict)


class ShadowValidationResult(BaseModel):
    blueprint_id: str
    from_node_id: str
    to_node_id: str
    ok: bool = True
    guard_id: str | None = None
    errors: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    checked_at: float = Field(default_factory=time.time)


class ShadowValidationSummary(BaseModel):
    blueprint_id: str
    cache_key: str = ""
    cache_hit: bool = False
    validated_transitions: int = 0
    invalid_transitions: int = 0
    last_validation: ShadowValidationResult | None = None
    branched_from: dict[str, str] = Field(default_factory=dict)


class StateTransitionTrace(BaseModel):
    trace_id: str = Field(default_factory=lambda: f"trace_{uuid.uuid4().hex[:12]}")
    blueprint_id: str
    step_index: int
    from_node_id: str
    to_node_id: str
    checkpoint_id: str
    graph_checkpoint_id: str | None = None
    guard_id: str | None = None
    ok: bool = True
    timestamp: float = Field(default_factory=time.time)
    errors: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    state_excerpt: dict[str, Any] = Field(default_factory=dict)
