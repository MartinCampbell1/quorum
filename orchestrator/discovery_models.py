"""Discovery-domain models for Quorum idea storage and dossiers."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, Literal
from uuid import uuid4

from pydantic import BaseModel, Field

from orchestrator.shared_contracts import (
    BudgetTier,
    Confidence,
    EffortEstimate,
    IdeaOutcomeStatus,
    RiskLevel,
    Urgency,
    VerdictStatus,
)


SwipeState = Literal["unseen", "pass", "maybe", "yes", "now"]
SwipeAction = Literal["pass", "maybe", "yes", "now"]
ValidationState = Literal[
    "draft",
    "queued",
    "reviewed",
    "validated",
    "invalidated",
    "pivot_candidate",
    "execution_trap",
    "cost_trap",
    "follow_on_opportunity",
    "in_progress",
    "stalled",
    "archived",
]
SimulationState = Literal["not_started", "queued", "running", "complete", "rejected"]
DossierStage = Literal["sourced", "ranked", "debated", "simulated", "swiped", "handed_off", "executed"]
QueueKind = Literal["active", "maybe"]
MaybeQueueStatus = Literal["watching", "ready"]
PersonaArchetype = Literal["operator", "builder", "leader", "analyst", "creator", "skeptic"]
PersonaBudgetBand = Literal["low", "medium", "high", "enterprise"]
FocusGroupStance = Literal["reject", "doubt", "curious", "trial", "champion"]
SimulationVerdict = Literal["reject", "watch", "pilot", "advance"]
MarketChannel = Literal["founder_outreach", "community", "content", "referral", "partner", "social"]
MarketAdoptionStage = Literal["unaware", "aware", "considering", "trial", "adopted", "retained", "churned"]
MarketSimulationStatus = Literal["queued", "running", "completed", "failed"]
MarketSimulationVerdict = Literal["reject", "watch", "pilot", "advance"]
DaemonMode = Literal["stopped", "running", "paused"]
DaemonRoutineKind = Literal["hourly_refresh", "daily_digest", "overnight_queue"]
DaemonRunStatus = Literal["queued", "running", "completed", "failed", "skipped"]
DaemonAlertSeverity = Literal["info", "warning", "critical"]
InboxItemStatus = Literal["open", "resolved"]
DiscoveryInboxSubjectKind = Literal["idea", "debate", "simulation", "handoff", "digest", "daemon"]
DiscoveryInboxActionKind = Literal["accept", "ignore", "edit", "compare", "respond", "resolve"]
DiscoveryInboxAgingBucket = Literal["fresh", "aging", "stale"]
ExecutionBriefApprovalStatus = Literal["pending", "approved", "rejected", "editing"]
IdeaGraphNodeKind = Literal[
    "idea",
    "domain",
    "source",
    "buyer",
    "persona",
    "evidence",
    "failure",
    "decision",
    "outcome",
    "pattern",
    "channel",
]
MemoryMatchKind = Literal["semantic_memory", "skill", "episode"]
ObservabilityTraceKind = Literal[
    "evidence",
    "validation",
    "ranking",
    "swipe",
    "decision",
    "simulation",
    "timeline",
]
ReplayStepKind = Literal[
    "session_event",
    "checkpoint",
    "protocol_transition",
    "generation_artifact",
]


def _utcnow() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


def _new_id(prefix: str) -> str:
    return f"{prefix}_{uuid4().hex[:12]}"


class EvidenceItemRecord(BaseModel):
    evidence_id: str = Field(default_factory=lambda: _new_id("evidence"))
    kind: str
    summary: str
    raw_content: str | None = None
    artifact_path: str | None = None
    source: str | None = None
    confidence: Confidence = Confidence.MEDIUM
    created_at: datetime = Field(default_factory=_utcnow)
    tags: list[str] = Field(default_factory=list)


class EvidenceBundleCandidate(BaseModel):
    bundle_id: str = Field(default_factory=lambda: _new_id("bundle"))
    parent_id: str
    items: list[EvidenceItemRecord] = Field(default_factory=list)
    overall_confidence: Confidence = Confidence.MEDIUM
    created_at: datetime = Field(default_factory=_utcnow)
    updated_at: datetime = Field(default_factory=_utcnow)


class IdeaScoreSnapshot(BaseModel):
    snapshot_id: str = Field(default_factory=lambda: _new_id("score"))
    label: str
    value: float
    reason: str = ""
    created_at: datetime = Field(default_factory=_utcnow)


class IdeaReasonSnapshot(BaseModel):
    snapshot_id: str = Field(default_factory=lambda: _new_id("reason"))
    category: str
    summary: str
    detail: str = ""
    created_at: datetime = Field(default_factory=_utcnow)


class DossierTimelineEvent(BaseModel):
    event_id: str = Field(default_factory=lambda: _new_id("timeline"))
    stage: DossierStage
    title: str
    detail: str = ""
    created_at: datetime = Field(default_factory=_utcnow)
    metadata: dict[str, Any] = Field(default_factory=dict)


class SourceObservation(BaseModel):
    observation_id: str = Field(default_factory=lambda: _new_id("observation"))
    idea_id: str
    source: str
    entity: str
    url: str
    raw_text: str
    topic_tags: list[str] = Field(default_factory=list)
    pain_score: float = 0.0
    trend_score: float = 0.0
    evidence_confidence: Confidence = Confidence.MEDIUM
    captured_at: datetime = Field(default_factory=_utcnow)
    freshness_deadline: datetime | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class IdeaValidationReport(BaseModel):
    report_id: str = Field(default_factory=lambda: _new_id("validation"))
    idea_id: str
    summary: str
    verdict: VerdictStatus = VerdictStatus.SKIP
    findings: list[str] = Field(default_factory=list)
    confidence: Confidence = Confidence.MEDIUM
    evidence_bundle_id: str | None = None
    created_at: datetime = Field(default_factory=_utcnow)
    updated_at: datetime = Field(default_factory=_utcnow)


class IdeaDecision(BaseModel):
    decision_id: str = Field(default_factory=lambda: _new_id("decision"))
    idea_id: str
    decision_type: str
    rationale: str
    actor: str = "system"
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=_utcnow)


class IdeaArchiveEntry(BaseModel):
    archive_id: str = Field(default_factory=lambda: _new_id("archive"))
    idea_id: str
    reason: str
    superseded_by_idea_id: str | None = None
    created_at: datetime = Field(default_factory=_utcnow)


class RiskItemRecord(BaseModel):
    category: str
    description: str
    level: RiskLevel
    mitigation: str | None = None


class StoryDecompositionSeedRecord(BaseModel):
    title: str
    description: str
    acceptance_criteria: list[str] = Field(default_factory=list)
    effort: EffortEstimate = EffortEstimate.MEDIUM


class ExecutionBriefCandidate(BaseModel):
    brief_id: str = Field(default_factory=lambda: _new_id("brief"))
    revision_id: str = Field(default_factory=lambda: _new_id("brief_rev"))
    idea_id: str
    title: str
    prd_summary: str = ""
    acceptance_criteria: list[str] = Field(default_factory=list)
    risks: list[RiskItemRecord] = Field(default_factory=list)
    recommended_tech_stack: list[str] = Field(default_factory=list)
    first_stories: list[StoryDecompositionSeedRecord] = Field(default_factory=list)
    repo_dna_snapshot: dict[str, Any] | None = None
    judge_summary: str | None = None
    simulation_summary: str | None = None
    evidence_bundle_id: str | None = None
    confidence: Confidence = Confidence.MEDIUM
    effort: EffortEstimate = EffortEstimate.MEDIUM
    urgency: Urgency = Urgency.BACKLOG
    budget_tier: BudgetTier = BudgetTier.MEDIUM
    founder_approval_required: bool = True
    brief_approval_status: ExecutionBriefApprovalStatus = "pending"
    approved_at: datetime | None = None
    approved_by: str | None = None
    created_at: datetime = Field(default_factory=_utcnow)
    updated_at: datetime = Field(default_factory=_utcnow)


class ExecutionOutcomeRecord(BaseModel):
    outcome_id: str
    brief_id: str
    idea_id: str
    status: IdeaOutcomeStatus
    verdict: VerdictStatus = VerdictStatus.SKIP
    total_cost_usd: float = 0.0
    total_duration_seconds: float = 0.0
    stories_attempted: int = 0
    stories_passed: int = 0
    stories_failed: int = 0
    bugs_found: int = 0
    critic_pass_rate: float = 0.0
    approvals_count: int = 0
    shipped_experiment_count: int = 0
    shipped_artifacts: list[str] = Field(default_factory=list)
    failure_modes: list[str] = Field(default_factory=list)
    lessons_learned: list[str] = Field(default_factory=list)
    evidence_bundle: EvidenceBundleCandidate | None = None
    autopilot_project_id: str | None = None
    autopilot_project_name: str | None = None
    autopilot_payload: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=_utcnow)
    ingested_at: datetime = Field(default_factory=_utcnow)


class PersonaMemoryEntry(BaseModel):
    memory_id: str = Field(default_factory=lambda: _new_id("persona_memory"))
    kind: str = "belief"
    content: str
    weight: float = 0.5
    source: str = "synthetic_seed"


class PersonaPlanStep(BaseModel):
    step_id: str = Field(default_factory=lambda: _new_id("persona_plan"))
    label: str
    intent: str
    urgency: float = 0.5


class VirtualPersona(BaseModel):
    persona_id: str = Field(default_factory=lambda: _new_id("persona"))
    display_name: str
    segment: str
    archetype: PersonaArchetype
    company_size: str = "smb"
    budget_band: PersonaBudgetBand = "medium"
    urgency: float = 0.5
    skepticism: float = 0.5
    ai_affinity: float = 0.5
    price_sensitivity: float = 0.5
    domain_context: str = ""
    needs: list[str] = Field(default_factory=list)
    objections: list[str] = Field(default_factory=list)
    memory: list[PersonaMemoryEntry] = Field(default_factory=list)
    daily_plan: list[PersonaPlanStep] = Field(default_factory=list)


class FocusGroupTurn(BaseModel):
    turn_id: str = Field(default_factory=lambda: _new_id("focus_turn"))
    round_index: int
    persona_id: str
    prompt: str
    quote: str
    stance: FocusGroupStance
    sentiment: float = 0.0
    resonance_score: float = 0.0
    purchase_intent: float = 0.0
    key_reasons: list[str] = Field(default_factory=list)


class FocusGroupRound(BaseModel):
    round_id: str = Field(default_factory=lambda: _new_id("focus_round"))
    round_index: int
    prompt: str
    aggregate_note: str = ""
    responses: list[FocusGroupTurn] = Field(default_factory=list)


class FocusGroupRun(BaseModel):
    run_id: str = Field(default_factory=lambda: _new_id("focus_run"))
    idea_id: str
    engine: str = "quorum.mvp.focus_group"
    world_name: str
    persona_count: int
    step_count: int
    estimated_token_count: int = 0
    estimated_cost_usd: float = 0.0
    seed: int
    created_at: datetime = Field(default_factory=_utcnow)
    rounds: list[FocusGroupRound] = Field(default_factory=list)


class SimulationFeedbackReport(BaseModel):
    report_id: str = Field(default_factory=lambda: _new_id("simulation"))
    idea_id: str
    run: FocusGroupRun
    personas: list[VirtualPersona] = Field(default_factory=list)
    summary_headline: str
    verdict: SimulationVerdict = "watch"
    support_ratio: float = 0.0
    average_resonance: float = 0.0
    average_purchase_intent: float = 0.0
    strongest_segments: list[str] = Field(default_factory=list)
    positive_signals: list[str] = Field(default_factory=list)
    objections: list[str] = Field(default_factory=list)
    desired_capabilities: list[str] = Field(default_factory=list)
    pricing_signals: list[str] = Field(default_factory=list)
    go_to_market_signals: list[str] = Field(default_factory=list)
    sample_quotes: list[str] = Field(default_factory=list)
    recommended_actions: list[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=_utcnow)


class SimulationParameters(BaseModel):
    population_size: int = Field(default=60, ge=24, le=240)
    round_count: int = Field(default=4, ge=2, le=8)
    seed: int | None = None
    target_market: str | None = None
    competition_pressure: float = Field(default=0.42, ge=0.0, le=1.0)
    network_density: float = Field(default=0.38, ge=0.0, le=1.0)
    evidence_weight: float = Field(default=0.62, ge=0.0, le=1.0)
    scenario_label: str = "market_lab"
    channel_mix: dict[str, float] = Field(
        default_factory=lambda: {
            "founder_outreach": 0.24,
            "content": 0.18,
            "community": 0.2,
            "referral": 0.16,
            "partner": 0.1,
            "social": 0.12,
        }
    )


class AgentActivityConfig(BaseModel):
    evaluation_rate: float = Field(default=0.56, ge=0.0, le=1.0)
    discussion_rate: float = Field(default=0.42, ge=0.0, le=1.0)
    trial_rate: float = Field(default=0.28, ge=0.0, le=1.0)
    referral_rate: float = Field(default=0.22, ge=0.0, le=1.0)
    churn_sensitivity: float = Field(default=0.38, ge=0.0, le=1.0)


class LabAgentState(BaseModel):
    agent_id: str = Field(default_factory=lambda: _new_id("market_agent"))
    display_name: str
    segment: str
    archetype: PersonaArchetype
    adoption_stage: MarketAdoptionStage = "unaware"
    need_intensity: float = 0.5
    trust_threshold: float = 0.5
    budget_fit: float = 0.5
    network_reach: float = 0.5
    referral_propensity: float = 0.5
    skepticism: float = 0.5
    price_sensitivity: float = 0.5
    preferred_channel: MarketChannel = "community"
    objections: list[str] = Field(default_factory=list)
    memory: list[str] = Field(default_factory=list)
    last_action_summary: str = ""


class AgentAction(BaseModel):
    action_id: str = Field(default_factory=lambda: _new_id("market_action"))
    round_index: int
    agent_id: str
    segment: str
    action_type: str
    channel: MarketChannel
    summary: str
    adoption_stage_before: MarketAdoptionStage
    adoption_stage_after: MarketAdoptionStage
    influence_delta: float = 0.0
    conversion_delta: float = 0.0
    pain_relief_delta: float = 0.0


class RoundSummary(BaseModel):
    round_id: str = Field(default_factory=lambda: _new_id("market_round"))
    round_index: int
    awareness_rate: float = 0.0
    consideration_rate: float = 0.0
    trial_rate: float = 0.0
    adoption_rate: float = 0.0
    retention_rate: float = 0.0
    virality_score: float = 0.0
    pain_relief_score: float = 0.0
    objection_pressure: float = 0.0
    channel_lift: dict[str, float] = Field(default_factory=dict)
    top_objections: list[str] = Field(default_factory=list)
    key_events: list[str] = Field(default_factory=list)


class SimulationRunState(BaseModel):
    run_id: str = Field(default_factory=lambda: _new_id("market_run"))
    status: MarketSimulationStatus = "queued"
    current_round: int = 0
    completed_rounds: int = 0
    world_state: dict[str, Any] = Field(default_factory=dict)
    round_summaries: list[RoundSummary] = Field(default_factory=list)
    agent_actions: list[AgentAction] = Field(default_factory=list)


class ReportOutlineSection(BaseModel):
    title: str
    bullets: list[str] = Field(default_factory=list)


class MarketSimulationReport(BaseModel):
    report_id: str = Field(default_factory=lambda: _new_id("market_report"))
    idea_id: str
    parameters: SimulationParameters
    activity_config: AgentActivityConfig
    run_state: SimulationRunState
    agents: list[LabAgentState] = Field(default_factory=list)
    executive_summary: str
    verdict: MarketSimulationVerdict = "watch"
    adoption_rate: float = 0.0
    retention_rate: float = 0.0
    virality_score: float = 0.0
    pain_relief_score: float = 0.0
    objection_score: float = 0.0
    market_fit_score: float = 0.0
    build_priority_score: float = 0.0
    ranking_delta: dict[str, float] = Field(default_factory=dict)
    strongest_segments: list[str] = Field(default_factory=list)
    weakest_segments: list[str] = Field(default_factory=list)
    channel_findings: list[str] = Field(default_factory=list)
    key_objections: list[str] = Field(default_factory=list)
    report_outline: list[ReportOutlineSection] = Field(default_factory=list)
    recommended_actions: list[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=_utcnow)


class IdeaGraphNode(BaseModel):
    node_id: str = Field(default_factory=lambda: _new_id("idea_graph_node"))
    kind: IdeaGraphNodeKind
    label: str
    summary: str = ""
    weight: float = 1.0
    metadata: dict[str, Any] = Field(default_factory=dict)


class IdeaGraphEdge(BaseModel):
    edge_id: str = Field(default_factory=lambda: _new_id("idea_graph_edge"))
    kind: str
    source_node_id: str
    target_node_id: str
    weight: float = 1.0
    evidence: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class IdeaGraphCommunity(BaseModel):
    community_id: str = Field(default_factory=lambda: _new_id("idea_graph_comm"))
    title: str
    summary: str = ""
    node_ids: list[str] = Field(default_factory=list)
    idea_ids: list[str] = Field(default_factory=list)
    highlights: list[str] = Field(default_factory=list)
    score: float = 0.0


class IdeaGraphContext(BaseModel):
    idea_id: str
    graph_id: str | None = None
    related_idea_ids: list[str] = Field(default_factory=list)
    lineage_idea_ids: list[str] = Field(default_factory=list)
    domain_clusters: list[str] = Field(default_factory=list)
    buyer_segments: list[str] = Field(default_factory=list)
    evidence_highlights: list[str] = Field(default_factory=list)
    failure_patterns: list[str] = Field(default_factory=list)
    reusable_patterns: list[str] = Field(default_factory=list)


class IdeaGraphSnapshot(BaseModel):
    graph_id: str = Field(default_factory=lambda: _new_id("idea_graph"))
    created_at: datetime = Field(default_factory=_utcnow)
    idea_count: int = 0
    node_count: int = 0
    edge_count: int = 0
    nodes: list[IdeaGraphNode] = Field(default_factory=list)
    edges: list[IdeaGraphEdge] = Field(default_factory=list)
    communities: list[IdeaGraphCommunity] = Field(default_factory=list)
    idea_contexts: list[IdeaGraphContext] = Field(default_factory=list)


class MemoryEpisode(BaseModel):
    episode_id: str = Field(default_factory=lambda: _new_id("memory_episode"))
    idea_id: str
    kind: str
    title: str
    summary: str
    categories: list[str] = Field(default_factory=list)
    source_ref: str | None = None
    weight: float = 0.5
    created_at: datetime = Field(default_factory=_utcnow)
    metadata: dict[str, Any] = Field(default_factory=dict)


class SemanticMemoryRecord(BaseModel):
    memory_id: str = Field(default_factory=lambda: _new_id("semantic_memory"))
    key: str
    category: str
    summary: str
    supporting_idea_ids: list[str] = Field(default_factory=list)
    supporting_episode_ids: list[str] = Field(default_factory=list)
    strength: float = 0.0
    recency_score: float = 0.0
    metadata: dict[str, Any] = Field(default_factory=dict)


class IdeaSkillLibraryEntry(BaseModel):
    skill_id: str = Field(default_factory=lambda: _new_id("idea_skill"))
    label: str
    pattern_type: str
    description: str
    trigger_signals: list[str] = Field(default_factory=list)
    recommended_moves: list[str] = Field(default_factory=list)
    supporting_idea_ids: list[str] = Field(default_factory=list)
    source_episode_ids: list[str] = Field(default_factory=list)
    confidence: float = 0.0


class CrossSessionPreferenceMemory(BaseModel):
    profile_id: str | None = None
    summary_points: list[str] = Field(default_factory=list)
    top_domains: list[str] = Field(default_factory=list)
    buyer_tilt: str = ""
    ai_necessity_preference: float = 0.0
    preferred_complexity: float = 0.0
    updated_at: datetime | None = None


class InstitutionalMemoryContext(BaseModel):
    idea_id: str
    snapshot_id: str | None = None
    semantic_highlights: list[str] = Field(default_factory=list)
    related_episode_ids: list[str] = Field(default_factory=list)
    related_idea_ids: list[str] = Field(default_factory=list)
    skill_hits: list[IdeaSkillLibraryEntry] = Field(default_factory=list)
    preference_notes: list[str] = Field(default_factory=list)


class MemoryGraphSnapshot(BaseModel):
    snapshot_id: str = Field(default_factory=lambda: _new_id("memory_graph"))
    created_at: datetime = Field(default_factory=_utcnow)
    episode_count: int = 0
    semantic_memory_count: int = 0
    skill_count: int = 0
    episodes: list[MemoryEpisode] = Field(default_factory=list)
    semantic_memories: list[SemanticMemoryRecord] = Field(default_factory=list)
    skill_library: list[IdeaSkillLibraryEntry] = Field(default_factory=list)
    preference_memory: CrossSessionPreferenceMemory | None = None


class MemoryQueryMatch(BaseModel):
    match_id: str = Field(default_factory=lambda: _new_id("memory_match"))
    kind: MemoryMatchKind
    title: str
    summary: str
    score: float = 0.0
    supporting_idea_ids: list[str] = Field(default_factory=list)
    supporting_episode_ids: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class MemoryQueryRequest(BaseModel):
    query: str
    limit: int = Field(default=8, ge=1, le=20)


class MemoryQueryResponse(BaseModel):
    query: str
    snapshot_id: str | None = None
    matches: list[MemoryQueryMatch] = Field(default_factory=list)
    related_idea_ids: list[str] = Field(default_factory=list)
    explanation: str = ""


class IdeaEvaluationScorecard(BaseModel):
    idea_id: str
    title: str
    novelty_score: float = 0.0
    evidence_quality_score: float = 0.0
    anti_banality_score: float = 0.0
    judge_consistency_score: float = 0.0
    simulation_calibration_score: float = 0.0
    overall_health: float = 0.0
    flags: list[str] = Field(default_factory=list)
    rationales: list[str] = Field(default_factory=list)


class DiscoveryEvaluationPack(BaseModel):
    generated_at: datetime = Field(default_factory=_utcnow)
    portfolio_id: str = "founder_default"
    averages: dict[str, float] = Field(default_factory=dict)
    highlights: list[str] = Field(default_factory=list)
    items: list[IdeaEvaluationScorecard] = Field(default_factory=list)


class IdeaTraceStep(BaseModel):
    trace_id: str = Field(default_factory=lambda: _new_id("trace"))
    trace_kind: ObservabilityTraceKind
    stage: str
    title: str
    detail: str = ""
    actor: str = ""
    created_at: datetime = Field(default_factory=_utcnow)
    score_delta: dict[str, float] = Field(default_factory=dict)
    latency_sec: float = 0.0
    cost_usd: float = 0.0
    metadata: dict[str, Any] = Field(default_factory=dict)


class IdeaTraceBundle(BaseModel):
    idea_id: str
    title: str
    latest_stage: DossierStage
    last_updated_at: datetime | None = None
    linked_session_ids: list[str] = Field(default_factory=list)
    steps: list[IdeaTraceStep] = Field(default_factory=list)


class SessionTraceSummary(BaseModel):
    session_id: str
    mode: str
    task: str
    status: str
    created_at: float = 0.0
    elapsed_sec: float | None = None
    selected_template: str | None = None
    execution_mode: str | None = None
    step_count: int = 0
    invalid_transition_count: int = 0
    generation_artifact_count: int = 0


class DiscoveryTraceSnapshot(BaseModel):
    snapshot_id: str = Field(default_factory=lambda: _new_id("obs_trace"))
    created_at: datetime = Field(default_factory=_utcnow)
    trace_count: int = 0
    idea_count: int = 0
    session_count: int = 0
    traces: list[IdeaTraceBundle] = Field(default_factory=list)
    recent_sessions: list[SessionTraceSummary] = Field(default_factory=list)
    metrics: dict[str, float] = Field(default_factory=dict)


class ObservabilityMetricRecord(BaseModel):
    key: str
    label: str
    value: float = 0.0
    unit: str = "number"
    detail: str = ""


class ProtocolRegressionRecord(BaseModel):
    protocol_key: str
    mode: str
    session_count: int = 0
    completed_count: int = 0
    failed_count: int = 0
    avg_latency_sec: float = 0.0
    invalid_transition_rate: float = 0.0
    cache_hit_rate: float = 0.0


class DiscoveryObservabilityScoreboard(BaseModel):
    generated_at: datetime = Field(default_factory=_utcnow)
    idea_count: int = 0
    active_idea_count: int = 0
    session_count: int = 0
    stage_distribution: dict[str, int] = Field(default_factory=dict)
    swipe_distribution: dict[str, int] = Field(default_factory=dict)
    metrics: list[ObservabilityMetricRecord] = Field(default_factory=list)
    evaluation_averages: dict[str, float] = Field(default_factory=dict)
    weakest_ideas: list[IdeaEvaluationScorecard] = Field(default_factory=list)
    strongest_ideas: list[IdeaEvaluationScorecard] = Field(default_factory=list)
    protocol_regressions: list[ProtocolRegressionRecord] = Field(default_factory=list)
    highlights: list[str] = Field(default_factory=list)


class ReplayParticipant(BaseModel):
    role: str
    provider: str
    tools: list[str] = Field(default_factory=list)


class DebateReplayStep(BaseModel):
    replay_id: str = Field(default_factory=lambda: _new_id("replay_step"))
    timestamp: float = 0.0
    kind: ReplayStepKind
    title: str
    detail: str = ""
    agent_id: str | None = None
    checkpoint_id: str | None = None
    node_id: str | None = None
    status: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class DebateReplaySession(BaseModel):
    session_id: str
    mode: str
    task: str
    status: str
    created_at: float = 0.0
    elapsed_sec: float | None = None
    result: str | None = None
    selected_template: str | None = None
    execution_mode: str | None = None
    participants: list[ReplayParticipant] = Field(default_factory=list)
    event_count: int = 0
    checkpoint_count: int = 0
    invalid_transition_count: int = 0
    generation_artifact_count: int = 0
    timeline: list[DebateReplayStep] = Field(default_factory=list)
    protocol_trace: list[dict[str, Any]] = Field(default_factory=list)


class IdeaExplainabilitySnapshot(BaseModel):
    idea_id: str
    generated_at: datetime = Field(default_factory=_utcnow)
    ranking_summary: str = ""
    ranking_drivers: list[str] = Field(default_factory=list)
    ranking_risks: list[str] = Field(default_factory=list)
    judge_summary: str = ""
    judge_pass_reasons: list[str] = Field(default_factory=list)
    judge_fail_reasons: list[str] = Field(default_factory=list)
    evidence_change_summary: str = ""
    evidence_changes: list[str] = Field(default_factory=list)
    simulation_summary: str = ""
    simulation_objections: list[str] = Field(default_factory=list)
    simulation_recommendations: list[str] = Field(default_factory=list)
    evaluation: IdeaEvaluationScorecard | None = None
    supporting_sessions: list[str] = Field(default_factory=list)
    linked_protocols: list[str] = Field(default_factory=list)


class IdeaCandidate(BaseModel):
    idea_id: str = Field(default_factory=lambda: _new_id("idea"))
    title: str
    thesis: str = ""
    summary: str = ""
    description: str = ""
    source: str = "manual"
    source_urls: list[str] = Field(default_factory=list)
    topic_tags: list[str] = Field(default_factory=list)
    provenance: dict[str, Any] = Field(default_factory=dict)
    lineage_parent_ids: list[str] = Field(default_factory=list)
    evolved_from: list[str] = Field(default_factory=list)
    superseded_by: list[str] = Field(default_factory=list)
    swipe_state: SwipeState = "unseen"
    rank_score: float = 0.0
    belief_score: float = 0.0
    validation_state: ValidationState = "draft"
    simulation_state: SimulationState = "not_started"
    latest_stage: DossierStage = "sourced"
    latest_scorecard: dict[str, float] = Field(default_factory=dict)
    score_snapshots: list[IdeaScoreSnapshot] = Field(default_factory=list)
    reason_snapshots: list[IdeaReasonSnapshot] = Field(default_factory=list)
    last_evidence_refresh_at: datetime | None = None
    last_debate_refresh_at: datetime | None = None
    created_at: datetime = Field(default_factory=_utcnow)
    updated_at: datetime = Field(default_factory=_utcnow)


class IdeaDossier(BaseModel):
    idea: IdeaCandidate
    evidence_bundle: EvidenceBundleCandidate | None = None
    observations: list[SourceObservation] = Field(default_factory=list)
    validation_reports: list[IdeaValidationReport] = Field(default_factory=list)
    decisions: list[IdeaDecision] = Field(default_factory=list)
    archive_entries: list[IdeaArchiveEntry] = Field(default_factory=list)
    timeline: list[DossierTimelineEvent] = Field(default_factory=list)
    execution_brief_candidate: ExecutionBriefCandidate | None = None
    execution_outcomes: list[ExecutionOutcomeRecord] = Field(default_factory=list)
    simulation_report: SimulationFeedbackReport | None = None
    market_simulation_report: MarketSimulationReport | None = None
    idea_graph_context: IdeaGraphContext | None = None
    memory_context: InstitutionalMemoryContext | None = None
    explainability_context: IdeaExplainabilitySnapshot | None = None


class IdeaCreateRequest(BaseModel):
    title: str
    thesis: str = ""
    summary: str = ""
    description: str = ""
    source: str = "manual"
    source_urls: list[str] = Field(default_factory=list)
    topic_tags: list[str] = Field(default_factory=list)
    provenance: dict[str, Any] = Field(default_factory=dict)
    lineage_parent_ids: list[str] = Field(default_factory=list)
    evolved_from: list[str] = Field(default_factory=list)
    latest_scorecard: dict[str, float] = Field(default_factory=dict)


class IdeaUpdateRequest(BaseModel):
    title: str | None = None
    thesis: str | None = None
    summary: str | None = None
    description: str | None = None
    source: str | None = None
    source_urls: list[str] | None = None
    topic_tags: list[str] | None = None
    provenance: dict[str, Any] | None = None
    lineage_parent_ids: list[str] | None = None
    evolved_from: list[str] | None = None
    superseded_by: list[str] | None = None
    swipe_state: SwipeState | None = None
    rank_score: float | None = None
    belief_score: float | None = None
    validation_state: ValidationState | None = None
    simulation_state: SimulationState | None = None
    latest_stage: DossierStage | None = None
    latest_scorecard: dict[str, float] | None = None
    score_snapshots: list[IdeaScoreSnapshot] | None = None
    reason_snapshots: list[IdeaReasonSnapshot] | None = None
    last_evidence_refresh_at: datetime | None = None
    last_debate_refresh_at: datetime | None = None


class SourceObservationCreateRequest(BaseModel):
    source: str
    entity: str
    url: str
    raw_text: str
    topic_tags: list[str] = Field(default_factory=list)
    pain_score: float = 0.0
    trend_score: float = 0.0
    evidence_confidence: Confidence = Confidence.MEDIUM
    freshness_deadline: datetime | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class IdeaValidationReportCreateRequest(BaseModel):
    summary: str
    verdict: VerdictStatus = VerdictStatus.SKIP
    findings: list[str] = Field(default_factory=list)
    confidence: Confidence = Confidence.MEDIUM
    evidence_bundle_id: str | None = None


class IdeaDecisionCreateRequest(BaseModel):
    decision_type: str
    rationale: str
    actor: str = "system"
    metadata: dict[str, Any] = Field(default_factory=dict)


class IdeaArchiveRequest(BaseModel):
    reason: str
    superseded_by_idea_id: str | None = None


class DossierTimelineEventCreateRequest(BaseModel):
    stage: DossierStage
    title: str
    detail: str = ""
    metadata: dict[str, Any] = Field(default_factory=dict)


class EvidenceBundleUpsertRequest(BaseModel):
    items: list[EvidenceItemRecord] = Field(default_factory=list)
    overall_confidence: Confidence = Confidence.MEDIUM


class ExecutionBriefCandidateUpsertRequest(BaseModel):
    title: str
    prd_summary: str = ""
    acceptance_criteria: list[str] = Field(default_factory=list)
    risks: list[RiskItemRecord] = Field(default_factory=list)
    recommended_tech_stack: list[str] = Field(default_factory=list)
    first_stories: list[StoryDecompositionSeedRecord] = Field(default_factory=list)
    repo_dna_snapshot: dict[str, Any] | None = None
    judge_summary: str | None = None
    simulation_summary: str | None = None
    evidence_bundle_id: str | None = None
    confidence: Confidence = Confidence.MEDIUM
    effort: EffortEstimate = EffortEstimate.MEDIUM
    urgency: Urgency = Urgency.BACKLOG
    budget_tier: BudgetTier = BudgetTier.MEDIUM
    founder_approval_required: bool = True


class ExecutionBriefApprovalUpdateRequest(BaseModel):
    status: ExecutionBriefApprovalStatus
    actor: str = "founder"
    note: str = ""
    expected_brief_id: str | None = None
    expected_revision_id: str | None = None


class ExecutionFeedbackIngestRequest(BaseModel):
    outcome: dict[str, Any]
    actor: str = "autopilot"
    autopilot_project_id: str | None = None
    autopilot_project_name: str | None = None
    approvals_count: int | None = Field(default=None, ge=0)
    shipped_experiment_count: int | None = Field(default=None, ge=0)
    autopilot_payload: dict[str, Any] = Field(default_factory=dict)


class SimulationRunRequest(BaseModel):
    persona_count: int = Field(default=12, ge=10, le=50)
    max_rounds: int = Field(default=3, ge=2, le=5)
    seed: int | None = None
    target_market: str | None = None
    force_refresh: bool = False


class MarketSimulationRunRequest(BaseModel):
    population_size: int = Field(default=60, ge=24, le=240)
    round_count: int = Field(default=4, ge=2, le=8)
    seed: int | None = None
    target_market: str | None = None
    competition_pressure: float = Field(default=0.42, ge=0.0, le=1.0)
    network_density: float = Field(default=0.38, ge=0.0, le=1.0)
    evidence_weight: float = Field(default=0.62, ge=0.0, le=1.0)
    force_refresh: bool = False


class FounderPreferenceProfile(BaseModel):
    profile_id: str = Field(default_factory=lambda: _new_id("pref"))
    owner: str = "founder"
    swipe_count: int = 0
    action_counts: dict[str, int] = Field(
        default_factory=lambda: {"pass": 0, "maybe": 0, "yes": 0, "now": 0}
    )
    domain_weights: dict[str, float] = Field(default_factory=dict)
    market_weights: dict[str, float] = Field(default_factory=dict)
    buyer_preferences: dict[str, float] = Field(default_factory=lambda: {"b2b": 0.0, "b2c": 0.0})
    ai_necessity_preference: float = 0.5
    preferred_complexity: float = 0.5
    complexity_tolerance: float = 0.45
    updated_at: datetime = Field(default_factory=_utcnow)


class SwipeEventRecord(BaseModel):
    event_id: str = Field(default_factory=lambda: _new_id("swipe"))
    idea_id: str
    action: SwipeAction
    rationale: str = ""
    actor: str = "founder"
    feature_snapshot: dict[str, Any] = Field(default_factory=dict)
    preference_delta: dict[str, float] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=_utcnow)
    metadata: dict[str, Any] = Field(default_factory=dict)


class MaybeQueueEntry(BaseModel):
    entry_id: str = Field(default_factory=lambda: _new_id("maybe"))
    idea_id: str
    queued_at: datetime = Field(default_factory=_utcnow)
    due_at: datetime = Field(default_factory=_utcnow)
    last_seen_at: datetime | None = None
    last_rechecked_at: datetime | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class IdeaQueueExplanation(BaseModel):
    headline: str
    source_signals: list[str] = Field(default_factory=list)
    score_deltas: dict[str, float] = Field(default_factory=dict)
    lineage: list[str] = Field(default_factory=list)
    newest_evidence: list[str] = Field(default_factory=list)
    repo_dna_match: str | None = None
    preference_signals: list[str] = Field(default_factory=list)
    change_summary: list[str] = Field(default_factory=list)


class IdeaQueueItem(BaseModel):
    queue_id: str = Field(default_factory=lambda: _new_id("queue"))
    queue_kind: QueueKind
    idea: IdeaCandidate
    priority_score: float
    explanation: IdeaQueueExplanation
    latest_observation: SourceObservation | None = None
    latest_validation_report: IdeaValidationReport | None = None
    last_swipe_action: SwipeAction | None = None
    last_swiped_at: datetime | None = None
    maybe_entry: MaybeQueueEntry | None = None
    recheck_status: MaybeQueueStatus | None = None
    has_new_evidence: bool = False
    repo_dna_match_score: float = 0.0


class SwipeQueueSummary(BaseModel):
    active_count: int = 0
    unseen_count: int = 0
    maybe_ready_count: int = 0
    maybe_waiting_count: int = 0
    pass_count: int = 0
    yes_count: int = 0
    now_count: int = 0


class MaybeQueueSummary(BaseModel):
    total_count: int = 0
    ready_count: int = 0
    waiting_count: int = 0


class SwipeQueueResponse(BaseModel):
    items: list[IdeaQueueItem] = Field(default_factory=list)
    preference_profile: FounderPreferenceProfile
    summary: SwipeQueueSummary = Field(default_factory=SwipeQueueSummary)


class MaybeQueueResponse(BaseModel):
    items: list[IdeaQueueItem] = Field(default_factory=list)
    summary: MaybeQueueSummary = Field(default_factory=MaybeQueueSummary)


class IdeaChangeRecord(BaseModel):
    idea_id: str
    since: datetime | None = None
    summary_points: list[str] = Field(default_factory=list)
    new_observations: list[SourceObservation] = Field(default_factory=list)
    new_validation_reports: list[IdeaValidationReport] = Field(default_factory=list)
    new_timeline_events: list[DossierTimelineEvent] = Field(default_factory=list)


class IdeaSwipeRequest(BaseModel):
    action: SwipeAction
    rationale: str = ""
    actor: str = "founder"
    revisit_after_hours: int = 72
    metadata: dict[str, Any] = Field(default_factory=dict)


class IdeaSwipeResult(BaseModel):
    idea: IdeaCandidate
    decision: IdeaDecision
    swipe_event: SwipeEventRecord
    maybe_entry: MaybeQueueEntry | None = None
    preference_profile: FounderPreferenceProfile


class SimulationRunResponse(BaseModel):
    idea: IdeaCandidate
    report: SimulationFeedbackReport
    cached: bool = False


class MarketSimulationRunResponse(BaseModel):
    idea: IdeaCandidate
    report: MarketSimulationReport
    cached: bool = False


class DiscoveryDaemonAlert(BaseModel):
    alert_id: str = Field(default_factory=lambda: _new_id("daemon_alert"))
    severity: DaemonAlertSeverity = "info"
    code: str
    title: str
    detail: str
    created_at: datetime = Field(default_factory=_utcnow)
    metadata: dict[str, Any] = Field(default_factory=dict)


class DiscoveryDaemonCheckpoint(BaseModel):
    checkpoint_id: str = Field(default_factory=lambda: _new_id("daemon_ckpt"))
    label: str
    detail: str = ""
    created_at: datetime = Field(default_factory=_utcnow)
    metadata: dict[str, Any] = Field(default_factory=dict)


class DiscoveryRoutineState(BaseModel):
    routine_kind: DaemonRoutineKind
    label: str
    enabled: bool = True
    cadence_minutes: int = 60
    max_ideas: int = 6
    stale_after_minutes: int = 720
    budget_limit_usd: float = 1.0
    last_run_at: datetime | None = None
    next_due_at: datetime | None = None
    last_status: DaemonRunStatus | Literal["idle"] = "idle"
    last_run_id: str | None = None
    summary: str = ""


class DiscoveryDailyDigestIdea(BaseModel):
    idea_id: str
    title: str
    latest_stage: DossierStage
    rank_score: float = 0.0
    belief_score: float = 0.0
    reason: str = ""
    tags: list[str] = Field(default_factory=list)


class DiscoveryDailyDigestRoutineSummary(BaseModel):
    routine_kind: DaemonRoutineKind
    headline: str
    touched_count: int = 0
    inbox_count: int = 0
    checkpoint_count: int = 0
    budget_used_usd: float = 0.0


class DiscoveryDailyDigest(BaseModel):
    digest_id: str = Field(default_factory=lambda: _new_id("digest"))
    digest_date: str
    created_at: datetime = Field(default_factory=_utcnow)
    headline: str
    highlights: list[str] = Field(default_factory=list)
    alerts: list[str] = Field(default_factory=list)
    top_ideas: list[DiscoveryDailyDigestIdea] = Field(default_factory=list)
    overnight_queue: list[DiscoveryDailyDigestIdea] = Field(default_factory=list)
    routine_summaries: list[DiscoveryDailyDigestRoutineSummary] = Field(default_factory=list)
    inbox_item_ids: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class DiscoveryInterruptActionRequest(BaseModel):
    action: str
    args: dict[str, Any] = Field(default_factory=dict)


class DiscoveryInterruptConfig(BaseModel):
    allow_ignore: bool = True
    allow_respond: bool = True
    allow_edit: bool = False
    allow_accept: bool = True
    allow_compare: bool = False


class DiscoveryInterruptPayload(BaseModel):
    action_request: DiscoveryInterruptActionRequest
    config: DiscoveryInterruptConfig = Field(default_factory=DiscoveryInterruptConfig)
    description: str = ""
    summary: str = ""


class DiscoveryReviewEvent(BaseModel):
    event_id: str = Field(default_factory=lambda: _new_id("review_evt"))
    action: DiscoveryInboxActionKind
    actor: str = "founder"
    note: str = ""
    created_at: datetime = Field(default_factory=_utcnow)
    metadata: dict[str, Any] = Field(default_factory=dict)


class DiscoveryInboxEvidencePreview(BaseModel):
    observations: list[str] = Field(default_factory=list)
    validations: list[str] = Field(default_factory=list)
    timeline: list[str] = Field(default_factory=list)


class DiscoveryInboxCompareOption(BaseModel):
    idea_id: str
    title: str
    latest_stage: DossierStage = "sourced"
    reason: str = ""


class DiscoveryInboxDossierPreview(BaseModel):
    headline: str = ""
    idea_summary: str = ""
    latest_stage: DossierStage = "sourced"
    rank_score: float = 0.0
    belief_score: float = 0.0
    evidence: DiscoveryInboxEvidencePreview = Field(default_factory=DiscoveryInboxEvidencePreview)
    debate_summary: str | None = None
    simulation_summary: str | None = None
    handoff_summary: str | None = None
    compare_options: list[DiscoveryInboxCompareOption] = Field(default_factory=list)
    raw_trace: dict[str, Any] = Field(default_factory=dict)


class DiscoveryInboxItem(BaseModel):
    item_id: str = Field(default_factory=lambda: _new_id("inbox"))
    kind: str
    status: InboxItemStatus = "open"
    subject_kind: DiscoveryInboxSubjectKind = "daemon"
    title: str
    detail: str = ""
    created_at: datetime = Field(default_factory=_utcnow)
    due_at: datetime | None = None
    idea_id: str | None = None
    digest_id: str | None = None
    run_id: str | None = None
    priority_score: float = 0.0
    age_minutes: int = 0
    aging_bucket: DiscoveryInboxAgingBucket = "fresh"
    interrupt: DiscoveryInterruptPayload | None = None
    dossier_preview: DiscoveryInboxDossierPreview | None = None
    review_history: list[DiscoveryReviewEvent] = Field(default_factory=list)
    resolution: DiscoveryReviewEvent | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class DiscoveryInboxSummary(BaseModel):
    open_count: int = 0
    resolved_count: int = 0
    stale_count: int = 0
    action_required_count: int = 0
    kinds: dict[str, int] = Field(default_factory=dict)
    subject_kinds: dict[str, int] = Field(default_factory=dict)


class DiscoveryInboxResponse(BaseModel):
    items: list[DiscoveryInboxItem] = Field(default_factory=list)
    summary: DiscoveryInboxSummary = Field(default_factory=DiscoveryInboxSummary)


class DiscoveryDaemonRun(BaseModel):
    run_id: str = Field(default_factory=lambda: _new_id("daemon_run"))
    routine_kind: DaemonRoutineKind
    status: DaemonRunStatus = "queued"
    cycle_id: str = Field(default_factory=lambda: _new_id("cycle"))
    fresh_session_id: str = Field(default_factory=lambda: _new_id("fresh"))
    triggered_by: str = "manual"
    started_at: datetime = Field(default_factory=_utcnow)
    finished_at: datetime | None = None
    summary: str = ""
    touched_idea_ids: list[str] = Field(default_factory=list)
    digest_id: str | None = None
    inbox_item_ids: list[str] = Field(default_factory=list)
    budget_used_usd: float = 0.0
    checkpoints: list[DiscoveryDaemonCheckpoint] = Field(default_factory=list)
    alerts: list[DiscoveryDaemonAlert] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class DiscoveryDaemonStatus(BaseModel):
    daemon_id: str = "discovery_daemon"
    mode: DaemonMode = "stopped"
    fresh_session_policy: str = "new_cycle_per_run"
    loop_interval_sec: int = 30
    started_at: datetime | None = None
    worker_heartbeat_at: datetime | None = None
    last_tick_at: datetime | None = None
    next_tick_at: datetime | None = None
    inbox_pending_count: int = 0
    latest_digest_id: str | None = None
    routines: list[DiscoveryRoutineState] = Field(default_factory=list)
    recent_runs: list[DiscoveryDaemonRun] = Field(default_factory=list)
    alerts: list[DiscoveryDaemonAlert] = Field(default_factory=list)


class DiscoveryDaemonControlRequest(BaseModel):
    action: Literal["start", "pause", "resume", "stop", "tick", "run_routine"]
    routine_kind: DaemonRoutineKind | None = None


class DiscoveryInboxResolveRequest(BaseModel):
    status: InboxItemStatus = "resolved"


class DiscoveryInboxActionRequest(BaseModel):
    action: DiscoveryInboxActionKind
    actor: str = "founder"
    note: str = ""
    response_text: str | None = None
    edited_fields: dict[str, str] = Field(default_factory=dict)
    compare_target_idea_id: str | None = None
    resolve: bool | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
