export interface AgentConfig {
  role: string;
  provider: "claude" | "gemini" | "codex" | "minimax";
  system_prompt: string;
  tools?: string[];
  workspace_paths?: string[];
}

export interface ToolDefinition {
  key: string;
  name: string;
  description?: string;
  category?: string;
  icon?: string;
  tool_type?: string;
  transport?: string;
  compatibility?: Record<string, "native" | "bridged" | "unavailable">;
}

export interface ProviderAccount {
  name: string;
  label?: string;
  identity?: string | null;
  display_name?: string;
  available: boolean;
  auth_state?: "unknown" | "verified" | "error";
  requests_made: number;
  cooldown_remaining_sec: number;
  last_error?: string | null;
  last_failure_at?: number | null;
  last_used_at?: number | null;
  last_checked_at?: number | null;
}

export type AccountsByProvider = Record<string, ProviderAccount[]>;

export interface AccountHealth {
  total: number;
  available: number;
  on_cooldown: number;
}

export interface CustomToolConfig {
  key: string;
  name: string;
  description: string;
  category?: string;
  tool_type: string;
  config: Record<string, string>;
}

export interface ToolFieldSchema {
  name: string;
  label: string;
  type: string;
  required?: boolean;
  placeholder?: string;
  options?: string[];
}

export interface ToolTypeDefinition {
  name: string;
  description?: string;
  category: string;
  icon: string;
  fields: ToolFieldSchema[];
}

export interface ConfiguredTool {
  id: string;
  name: string;
  tool_type: string;
  icon?: string;
  enabled: boolean;
  config: Record<string, string>;
  transport?: string;
  compatibility?: Record<string, "native" | "bridged" | "unavailable">;
  validation_status?: string;
  guardrail_status?: string;
  wrapper_mode?: string;
  trust_level?: string;
  last_guardrail_report?: GuardrailScanReport;
  last_validation_result?: {
    ok?: boolean;
    error?: string;
    log?: string[];
    transport?: string;
    tool_count?: number;
  };
}

export interface GuardrailFinding {
  finding_id: string;
  category: string;
  severity: "low" | "medium" | "high" | "critical";
  action: "allow" | "log" | "warn" | "block";
  title: string;
  detail: string;
  evidence: string[];
}

export interface GuardrailScanReport {
  report_id: string;
  tool_id: string;
  tool_name: string;
  tool_type: string;
  phase: string;
  status: "safe" | "warn" | "blocked";
  recommended_action: "allow" | "log" | "warn" | "block";
  wrapper_mode: "direct" | "guarded" | "blocked";
  trust_level: "trusted" | "caution" | "untrusted" | "blocked";
  findings: GuardrailFinding[];
  summary: string;
  scanned_target: string;
  scanned_at: string;
}

export interface GuardrailAuditEvent {
  event_id: string;
  created_at: string;
  source: string;
  action: string;
  phase: string;
  tool_id?: string | null;
  tool_name?: string | null;
  detail: string;
  report: Record<string, unknown>;
  metadata: Record<string, unknown>;
}

export interface PromptTemplate {
  name: string;
  description: string;
  prompt: string;
}

export interface RunRequest {
  mode: string;
  task: string;
  scenario_id?: string | null;
  agents?: AgentConfig[];
  config?: Record<string, unknown>;
  workspace_preset_ids?: string[];
  workspace_paths?: string[];
  attached_tool_ids?: string[];
}

export type SharedConfidence = "high" | "medium" | "low" | "unknown";
export type SharedRiskLevel = "critical" | "high" | "medium" | "low" | "negligible";
export type SharedEffortEstimate = "trivial" | "small" | "medium" | "large" | "epic";
export type SharedUrgency = "now" | "this_week" | "this_month" | "backlog";
export type SharedBudgetTier = "micro" | "low" | "medium" | "high" | "unlimited";
export type SharedIdeaOutcomeStatus =
  | "validated"
  | "invalidated"
  | "pivot_candidate"
  | "execution_trap"
  | "cost_trap"
  | "follow_on_opportunity"
  | "in_progress"
  | "stalled";
export type SharedVerdictStatus = "pass" | "fail" | "partial" | "skip";
export type DiscoverySwipeState = "unseen" | "pass" | "maybe" | "yes" | "now";
export type DiscoverySwipeAction = "pass" | "maybe" | "yes" | "now";
export type DiscoveryValidationState =
  | "draft"
  | "queued"
  | "reviewed"
  | "validated"
  | "invalidated"
  | "pivot_candidate"
  | "execution_trap"
  | "cost_trap"
  | "follow_on_opportunity"
  | "in_progress"
  | "stalled"
  | "archived";
export type DiscoverySimulationState = "not_started" | "queued" | "running" | "complete" | "rejected";
export type DiscoveryDossierStage = "sourced" | "ranked" | "debated" | "simulated" | "swiped" | "handed_off" | "executed";
export type DiscoveryQueueKind = "active" | "maybe";
export type DiscoveryMaybeQueueStatus = "watching" | "ready";
export type PersonaArchetype = "operator" | "builder" | "leader" | "analyst" | "creator" | "skeptic";
export type PersonaBudgetBand = "low" | "medium" | "high" | "enterprise";
export type FocusGroupStance = "reject" | "doubt" | "curious" | "trial" | "champion";
export type SimulationVerdict = "reject" | "watch" | "pilot" | "advance";
export type MarketChannel = "founder_outreach" | "community" | "content" | "referral" | "partner" | "social";
export type MarketAdoptionStage = "unaware" | "aware" | "considering" | "trial" | "adopted" | "retained" | "churned";
export type MarketSimulationStatus = "queued" | "running" | "completed" | "failed";
export type MarketSimulationVerdict = "reject" | "watch" | "pilot" | "advance";

export interface EvidenceItemRecord {
  evidence_id: string;
  kind: string;
  summary: string;
  raw_content?: string | null;
  artifact_path?: string | null;
  source?: string | null;
  confidence: SharedConfidence;
  created_at: string;
  tags: string[];
}

export interface EvidenceBundleCandidate {
  bundle_id: string;
  parent_id: string;
  items: EvidenceItemRecord[];
  overall_confidence: SharedConfidence;
  created_at: string;
  updated_at: string;
}

export interface IdeaScoreSnapshot {
  snapshot_id: string;
  label: string;
  value: number;
  reason: string;
  created_at: string;
}

export interface IdeaReasonSnapshot {
  snapshot_id: string;
  category: string;
  summary: string;
  detail: string;
  created_at: string;
}

export interface DossierTimelineEvent {
  event_id: string;
  stage: DiscoveryDossierStage;
  title: string;
  detail: string;
  created_at: string;
  metadata: Record<string, unknown>;
}

export interface SourceObservation {
  observation_id: string;
  idea_id: string;
  source: string;
  entity: string;
  url: string;
  raw_text: string;
  topic_tags: string[];
  pain_score: number;
  trend_score: number;
  evidence_confidence: SharedConfidence;
  captured_at: string;
  freshness_deadline?: string | null;
  metadata: Record<string, unknown>;
}

export interface IdeaValidationReport {
  report_id: string;
  idea_id: string;
  summary: string;
  verdict: SharedVerdictStatus;
  findings: string[];
  confidence: SharedConfidence;
  evidence_bundle_id?: string | null;
  created_at: string;
  updated_at: string;
}

export interface IdeaDecision {
  decision_id: string;
  idea_id: string;
  decision_type: string;
  rationale: string;
  actor: string;
  metadata: Record<string, unknown>;
  created_at: string;
}

export interface IdeaArchiveEntry {
  archive_id: string;
  idea_id: string;
  reason: string;
  superseded_by_idea_id?: string | null;
  created_at: string;
}

export interface RiskItemRecord {
  category: string;
  description: string;
  level: SharedRiskLevel;
  mitigation?: string | null;
}

export interface StoryDecompositionSeedRecord {
  title: string;
  description: string;
  acceptance_criteria: string[];
  effort: SharedEffortEstimate;
}

export interface ExecutionBriefCandidateRecord {
  brief_id: string;
  idea_id: string;
  title: string;
  prd_summary: string;
  acceptance_criteria: string[];
  risks: RiskItemRecord[];
  recommended_tech_stack: string[];
  first_stories: StoryDecompositionSeedRecord[];
  repo_dna_snapshot?: Record<string, unknown> | null;
  judge_summary?: string | null;
  simulation_summary?: string | null;
  evidence_bundle_id?: string | null;
  confidence: SharedConfidence;
  effort: SharedEffortEstimate;
  urgency: SharedUrgency;
  budget_tier: SharedBudgetTier;
  created_at: string;
  updated_at: string;
}

export interface ExecutionOutcomeRecord {
  outcome_id: string;
  brief_id: string;
  idea_id: string;
  status: SharedIdeaOutcomeStatus;
  verdict: SharedVerdictStatus;
  total_cost_usd: number;
  total_duration_seconds: number;
  stories_attempted: number;
  stories_passed: number;
  stories_failed: number;
  bugs_found: number;
  critic_pass_rate: number;
  approvals_count: number;
  shipped_experiment_count: number;
  shipped_artifacts: string[];
  failure_modes: string[];
  lessons_learned: string[];
  evidence_bundle?: EvidenceBundleCandidate | null;
  autopilot_project_id?: string | null;
  autopilot_project_name?: string | null;
  autopilot_payload: Record<string, unknown>;
  created_at: string;
  ingested_at: string;
}

export interface PersonaMemoryEntry {
  memory_id: string;
  kind: string;
  content: string;
  weight: number;
  source: string;
}

export interface PersonaPlanStep {
  step_id: string;
  label: string;
  intent: string;
  urgency: number;
}

export interface VirtualPersona {
  persona_id: string;
  display_name: string;
  segment: string;
  archetype: PersonaArchetype;
  company_size: string;
  budget_band: PersonaBudgetBand;
  urgency: number;
  skepticism: number;
  ai_affinity: number;
  price_sensitivity: number;
  domain_context: string;
  needs: string[];
  objections: string[];
  memory: PersonaMemoryEntry[];
  daily_plan: PersonaPlanStep[];
}

export interface FocusGroupTurn {
  turn_id: string;
  round_index: number;
  persona_id: string;
  prompt: string;
  quote: string;
  stance: FocusGroupStance;
  sentiment: number;
  resonance_score: number;
  purchase_intent: number;
  key_reasons: string[];
}

export interface FocusGroupRound {
  round_id: string;
  round_index: number;
  prompt: string;
  aggregate_note: string;
  responses: FocusGroupTurn[];
}

export interface FocusGroupRun {
  run_id: string;
  idea_id: string;
  engine: string;
  world_name: string;
  persona_count: number;
  step_count: number;
  estimated_token_count: number;
  estimated_cost_usd: number;
  seed: number;
  created_at: string;
  rounds: FocusGroupRound[];
}

export interface SimulationFeedbackReport {
  report_id: string;
  idea_id: string;
  run: FocusGroupRun;
  personas: VirtualPersona[];
  summary_headline: string;
  verdict: SimulationVerdict;
  support_ratio: number;
  average_resonance: number;
  average_purchase_intent: number;
  strongest_segments: string[];
  positive_signals: string[];
  objections: string[];
  desired_capabilities: string[];
  pricing_signals: string[];
  go_to_market_signals: string[];
  sample_quotes: string[];
  recommended_actions: string[];
  created_at: string;
}

export interface SimulationParameters {
  population_size: number;
  round_count: number;
  seed?: number | null;
  target_market?: string | null;
  competition_pressure: number;
  network_density: number;
  evidence_weight: number;
  scenario_label: string;
  channel_mix: Record<string, number>;
}

export interface AgentActivityConfig {
  evaluation_rate: number;
  discussion_rate: number;
  trial_rate: number;
  referral_rate: number;
  churn_sensitivity: number;
}

export interface LabAgentState {
  agent_id: string;
  display_name: string;
  segment: string;
  archetype: PersonaArchetype;
  adoption_stage: MarketAdoptionStage;
  need_intensity: number;
  trust_threshold: number;
  budget_fit: number;
  network_reach: number;
  referral_propensity: number;
  skepticism: number;
  price_sensitivity: number;
  preferred_channel: MarketChannel;
  objections: string[];
  memory: string[];
  last_action_summary: string;
}

export interface AgentAction {
  action_id: string;
  round_index: number;
  agent_id: string;
  segment: string;
  action_type: string;
  channel: MarketChannel;
  summary: string;
  adoption_stage_before: MarketAdoptionStage;
  adoption_stage_after: MarketAdoptionStage;
  influence_delta: number;
  conversion_delta: number;
  pain_relief_delta: number;
}

export interface RoundSummary {
  round_id: string;
  round_index: number;
  awareness_rate: number;
  consideration_rate: number;
  trial_rate: number;
  adoption_rate: number;
  retention_rate: number;
  virality_score: number;
  pain_relief_score: number;
  objection_pressure: number;
  channel_lift: Record<string, number>;
  top_objections: string[];
  key_events: string[];
}

export interface SimulationRunState {
  run_id: string;
  status: MarketSimulationStatus;
  current_round: number;
  completed_rounds: number;
  world_state: Record<string, unknown>;
  round_summaries: RoundSummary[];
  agent_actions: AgentAction[];
}

export interface ReportOutlineSection {
  title: string;
  bullets: string[];
}

export interface MarketSimulationReport {
  report_id: string;
  idea_id: string;
  parameters: SimulationParameters;
  activity_config: AgentActivityConfig;
  run_state: SimulationRunState;
  agents: LabAgentState[];
  executive_summary: string;
  verdict: MarketSimulationVerdict;
  adoption_rate: number;
  retention_rate: number;
  virality_score: number;
  pain_relief_score: number;
  objection_score: number;
  market_fit_score: number;
  build_priority_score: number;
  ranking_delta: Record<string, number>;
  strongest_segments: string[];
  weakest_segments: string[];
  channel_findings: string[];
  key_objections: string[];
  report_outline: ReportOutlineSection[];
  recommended_actions: string[];
  created_at: string;
}

export interface IdeaGraphNode {
  node_id: string;
  kind: string;
  label: string;
  summary: string;
  weight: number;
  metadata: Record<string, unknown>;
}

export interface IdeaGraphEdge {
  edge_id: string;
  kind: string;
  source_node_id: string;
  target_node_id: string;
  weight: number;
  evidence: string[];
  metadata: Record<string, unknown>;
}

export interface IdeaGraphCommunity {
  community_id: string;
  title: string;
  summary: string;
  node_ids: string[];
  idea_ids: string[];
  highlights: string[];
  score: number;
}

export interface IdeaGraphContext {
  idea_id: string;
  graph_id?: string | null;
  related_idea_ids: string[];
  lineage_idea_ids: string[];
  domain_clusters: string[];
  buyer_segments: string[];
  evidence_highlights: string[];
  failure_patterns: string[];
  reusable_patterns: string[];
}

export interface IdeaGraphSnapshot {
  graph_id: string;
  created_at: string;
  idea_count: number;
  node_count: number;
  edge_count: number;
  nodes: IdeaGraphNode[];
  edges: IdeaGraphEdge[];
  communities: IdeaGraphCommunity[];
  idea_contexts: IdeaGraphContext[];
}

export interface MemoryEpisode {
  episode_id: string;
  idea_id: string;
  kind: string;
  title: string;
  summary: string;
  categories: string[];
  source_ref?: string | null;
  weight: number;
  created_at: string;
  metadata: Record<string, unknown>;
}

export interface SemanticMemoryRecord {
  memory_id: string;
  key: string;
  category: string;
  summary: string;
  supporting_idea_ids: string[];
  supporting_episode_ids: string[];
  strength: number;
  recency_score: number;
  metadata: Record<string, unknown>;
}

export interface IdeaSkillLibraryEntry {
  skill_id: string;
  label: string;
  pattern_type: string;
  description: string;
  trigger_signals: string[];
  recommended_moves: string[];
  supporting_idea_ids: string[];
  source_episode_ids: string[];
  confidence: number;
}

export interface CrossSessionPreferenceMemory {
  profile_id?: string | null;
  summary_points: string[];
  top_domains: string[];
  buyer_tilt: string;
  ai_necessity_preference: number;
  preferred_complexity: number;
  updated_at?: string | null;
}

export interface InstitutionalMemoryContext {
  idea_id: string;
  snapshot_id?: string | null;
  semantic_highlights: string[];
  related_episode_ids: string[];
  related_idea_ids: string[];
  skill_hits: IdeaSkillLibraryEntry[];
  preference_notes: string[];
}

export interface MemoryGraphSnapshot {
  snapshot_id: string;
  created_at: string;
  episode_count: number;
  semantic_memory_count: number;
  skill_count: number;
  episodes: MemoryEpisode[];
  semantic_memories: SemanticMemoryRecord[];
  skill_library: IdeaSkillLibraryEntry[];
  preference_memory?: CrossSessionPreferenceMemory | null;
}

export interface MemoryQueryMatch {
  match_id: string;
  kind: "semantic_memory" | "skill" | "episode";
  title: string;
  summary: string;
  score: number;
  supporting_idea_ids: string[];
  supporting_episode_ids: string[];
  metadata: Record<string, unknown>;
}

export interface MemoryQueryRequest {
  query: string;
  limit?: number;
}

export interface MemoryQueryResponse {
  query: string;
  snapshot_id?: string | null;
  matches: MemoryQueryMatch[];
  related_idea_ids: string[];
  explanation: string;
}

export interface IdeaCandidate {
  idea_id: string;
  title: string;
  thesis: string;
  summary: string;
  description: string;
  source: string;
  source_urls: string[];
  topic_tags: string[];
  provenance: Record<string, unknown>;
  lineage_parent_ids: string[];
  evolved_from: string[];
  superseded_by: string[];
  swipe_state: DiscoverySwipeState;
  rank_score: number;
  belief_score: number;
  validation_state: DiscoveryValidationState;
  simulation_state: DiscoverySimulationState;
  latest_stage: DiscoveryDossierStage;
  latest_scorecard: Record<string, number>;
  score_snapshots: IdeaScoreSnapshot[];
  reason_snapshots: IdeaReasonSnapshot[];
  last_evidence_refresh_at?: string | null;
  last_debate_refresh_at?: string | null;
  created_at: string;
  updated_at: string;
}

export interface IdeaDossier {
  idea: IdeaCandidate;
  evidence_bundle?: EvidenceBundleCandidate | null;
  observations: SourceObservation[];
  validation_reports: IdeaValidationReport[];
  decisions: IdeaDecision[];
  archive_entries: IdeaArchiveEntry[];
  timeline: DossierTimelineEvent[];
  execution_brief_candidate?: ExecutionBriefCandidateRecord | null;
  execution_outcomes: ExecutionOutcomeRecord[];
  simulation_report?: SimulationFeedbackReport | null;
  market_simulation_report?: MarketSimulationReport | null;
  idea_graph_context?: IdeaGraphContext | null;
  memory_context?: InstitutionalMemoryContext | null;
  explainability_context?: IdeaExplainabilitySnapshot | null;
}

export interface IdeaEvaluationScorecard {
  idea_id: string;
  title: string;
  novelty_score: number;
  evidence_quality_score: number;
  anti_banality_score: number;
  judge_consistency_score: number;
  simulation_calibration_score: number;
  overall_health: number;
  flags: string[];
  rationales: string[];
}

export interface DiscoveryEvaluationPack {
  generated_at: string;
  portfolio_id: string;
  averages: Record<string, number>;
  highlights: string[];
  items: IdeaEvaluationScorecard[];
}

export type ObservabilityTraceKind =
  | "evidence"
  | "validation"
  | "ranking"
  | "swipe"
  | "decision"
  | "simulation"
  | "timeline";

export interface IdeaTraceStep {
  trace_id: string;
  trace_kind: ObservabilityTraceKind;
  stage: string;
  title: string;
  detail: string;
  actor: string;
  created_at: string;
  score_delta: Record<string, number>;
  latency_sec: number;
  cost_usd: number;
  metadata: Record<string, unknown>;
}

export interface IdeaTraceBundle {
  idea_id: string;
  title: string;
  latest_stage: DiscoveryDossierStage;
  last_updated_at?: string | null;
  linked_session_ids: string[];
  steps: IdeaTraceStep[];
}

export interface SessionTraceSummary {
  session_id: string;
  mode: string;
  task: string;
  status: string;
  created_at: number;
  elapsed_sec?: number | null;
  selected_template?: string | null;
  execution_mode?: string | null;
  step_count: number;
  invalid_transition_count: number;
  generation_artifact_count: number;
}

export interface DiscoveryTraceSnapshot {
  snapshot_id: string;
  created_at: string;
  trace_count: number;
  idea_count: number;
  session_count: number;
  traces: IdeaTraceBundle[];
  recent_sessions: SessionTraceSummary[];
  metrics: Record<string, number>;
}

export interface ObservabilityMetricRecord {
  key: string;
  label: string;
  value: number;
  unit: string;
  detail: string;
}

export interface ProtocolRegressionRecord {
  protocol_key: string;
  mode: string;
  session_count: number;
  completed_count: number;
  failed_count: number;
  avg_latency_sec: number;
  invalid_transition_rate: number;
  cache_hit_rate: number;
}

export interface DiscoveryObservabilityScoreboard {
  generated_at: string;
  idea_count: number;
  active_idea_count: number;
  session_count: number;
  stage_distribution: Record<string, number>;
  swipe_distribution: Record<string, number>;
  metrics: ObservabilityMetricRecord[];
  evaluation_averages: Record<string, number>;
  weakest_ideas: IdeaEvaluationScorecard[];
  strongest_ideas: IdeaEvaluationScorecard[];
  protocol_regressions: ProtocolRegressionRecord[];
  highlights: string[];
}

export interface DebateReplayStep {
  replay_id: string;
  timestamp: number;
  kind: "session_event" | "checkpoint" | "protocol_transition" | "generation_artifact";
  title: string;
  detail: string;
  agent_id?: string | null;
  checkpoint_id?: string | null;
  node_id?: string | null;
  status?: string | null;
  metadata: Record<string, unknown>;
}

export interface ReplayParticipant {
  role: string;
  provider: string;
  tools: string[];
}

export interface DebateReplaySession {
  session_id: string;
  mode: string;
  task: string;
  status: string;
  created_at: number;
  elapsed_sec?: number | null;
  result?: string | null;
  selected_template?: string | null;
  execution_mode?: string | null;
  participants: ReplayParticipant[];
  event_count: number;
  checkpoint_count: number;
  invalid_transition_count: number;
  generation_artifact_count: number;
  timeline: DebateReplayStep[];
  protocol_trace: Record<string, unknown>[];
}

export interface IdeaExplainabilitySnapshot {
  idea_id: string;
  generated_at: string;
  ranking_summary: string;
  ranking_drivers: string[];
  ranking_risks: string[];
  judge_summary: string;
  judge_pass_reasons: string[];
  judge_fail_reasons: string[];
  evidence_change_summary: string;
  evidence_changes: string[];
  simulation_summary: string;
  simulation_objections: string[];
  simulation_recommendations: string[];
  evaluation?: IdeaEvaluationScorecard | null;
  supporting_sessions: string[];
  linked_protocols: string[];
}

export interface FounderPreferenceProfile {
  profile_id: string;
  owner: string;
  swipe_count: number;
  action_counts: Record<string, number>;
  domain_weights: Record<string, number>;
  market_weights: Record<string, number>;
  buyer_preferences: Record<string, number>;
  ai_necessity_preference: number;
  preferred_complexity: number;
  complexity_tolerance: number;
  updated_at: string;
}

export interface SwipeEventRecord {
  event_id: string;
  idea_id: string;
  action: DiscoverySwipeAction;
  rationale: string;
  actor: string;
  feature_snapshot: Record<string, unknown>;
  preference_delta: Record<string, number>;
  created_at: string;
  metadata: Record<string, unknown>;
}

export interface MaybeQueueEntry {
  entry_id: string;
  idea_id: string;
  queued_at: string;
  due_at: string;
  last_seen_at?: string | null;
  last_rechecked_at?: string | null;
  metadata: Record<string, unknown>;
}

export interface IdeaQueueExplanation {
  headline: string;
  source_signals: string[];
  score_deltas: Record<string, number>;
  lineage: string[];
  newest_evidence: string[];
  repo_dna_match?: string | null;
  preference_signals: string[];
  change_summary: string[];
}

export interface IdeaQueueItem {
  queue_id: string;
  queue_kind: DiscoveryQueueKind;
  idea: IdeaCandidate;
  priority_score: number;
  explanation: IdeaQueueExplanation;
  latest_observation?: SourceObservation | null;
  latest_validation_report?: IdeaValidationReport | null;
  last_swipe_action?: DiscoverySwipeAction | null;
  last_swiped_at?: string | null;
  maybe_entry?: MaybeQueueEntry | null;
  recheck_status?: DiscoveryMaybeQueueStatus | null;
  has_new_evidence: boolean;
  repo_dna_match_score: number;
}

export interface SwipeQueueSummary {
  active_count: number;
  unseen_count: number;
  maybe_ready_count: number;
  maybe_waiting_count: number;
  pass_count: number;
  yes_count: number;
  now_count: number;
}

export interface MaybeQueueSummary {
  total_count: number;
  ready_count: number;
  waiting_count: number;
}

export interface SwipeQueueResponse {
  items: IdeaQueueItem[];
  preference_profile: FounderPreferenceProfile;
  summary: SwipeQueueSummary;
}

export interface MaybeQueueResponse {
  items: IdeaQueueItem[];
  summary: MaybeQueueSummary;
}

export interface IdeaChangeRecord {
  idea_id: string;
  since?: string | null;
  summary_points: string[];
  new_observations: SourceObservation[];
  new_validation_reports: IdeaValidationReport[];
  new_timeline_events: DossierTimelineEvent[];
}

export interface IdeaSwipeResult {
  idea: IdeaCandidate;
  decision: IdeaDecision;
  swipe_event: SwipeEventRecord;
  maybe_entry?: MaybeQueueEntry | null;
  preference_profile: FounderPreferenceProfile;
}

export interface SimulationRunRequest {
  persona_count?: number;
  max_rounds?: number;
  seed?: number | null;
  target_market?: string | null;
  force_refresh?: boolean;
}

export interface SimulationRunResponse {
  idea: IdeaCandidate;
  report: SimulationFeedbackReport;
  cached: boolean;
}

export interface MarketSimulationRunRequest {
  population_size?: number;
  round_count?: number;
  seed?: number | null;
  target_market?: string | null;
  competition_pressure?: number;
  network_density?: number;
  evidence_weight?: number;
  force_refresh?: boolean;
}

export interface MarketSimulationRunResponse {
  idea: IdeaCandidate;
  report: MarketSimulationReport;
  cached: boolean;
}

export type DaemonMode = "stopped" | "running" | "paused";
export type DaemonRoutineKind = "hourly_refresh" | "daily_digest" | "overnight_queue";
export type DaemonRunStatus = "queued" | "running" | "completed" | "failed" | "skipped";
export type DaemonAlertSeverity = "info" | "warning" | "critical";
export type InboxItemStatus = "open" | "resolved";
export type DiscoveryInboxSubjectKind = "idea" | "debate" | "simulation" | "handoff" | "digest" | "daemon";
export type DiscoveryInboxActionKind = "accept" | "ignore" | "edit" | "compare" | "respond" | "resolve";
export type DiscoveryInboxAgingBucket = "fresh" | "aging" | "stale";

export interface DiscoveryDaemonAlert {
  alert_id: string;
  severity: DaemonAlertSeverity;
  code: string;
  title: string;
  detail: string;
  created_at: string;
  metadata: Record<string, unknown>;
}

export interface DiscoveryDaemonCheckpoint {
  checkpoint_id: string;
  label: string;
  detail: string;
  created_at: string;
  metadata: Record<string, unknown>;
}

export interface DiscoveryRoutineState {
  routine_kind: DaemonRoutineKind;
  label: string;
  enabled: boolean;
  cadence_minutes: number;
  max_ideas: number;
  stale_after_minutes: number;
  budget_limit_usd: number;
  last_run_at?: string | null;
  next_due_at?: string | null;
  last_status: DaemonRunStatus | "idle";
  last_run_id?: string | null;
  summary: string;
}

export interface DiscoveryDailyDigestIdea {
  idea_id: string;
  title: string;
  latest_stage: DiscoveryDossierStage;
  rank_score: number;
  belief_score: number;
  reason: string;
  tags: string[];
}

export interface DiscoveryDailyDigestRoutineSummary {
  routine_kind: DaemonRoutineKind;
  headline: string;
  touched_count: number;
  inbox_count: number;
  checkpoint_count: number;
  budget_used_usd: number;
}

export interface DiscoveryDailyDigest {
  digest_id: string;
  digest_date: string;
  created_at: string;
  headline: string;
  highlights: string[];
  alerts: string[];
  top_ideas: DiscoveryDailyDigestIdea[];
  overnight_queue: DiscoveryDailyDigestIdea[];
  routine_summaries: DiscoveryDailyDigestRoutineSummary[];
  inbox_item_ids: string[];
  metadata: Record<string, unknown>;
}

export interface DiscoveryInterruptActionRequest {
  action: string;
  args: Record<string, unknown>;
}

export interface DiscoveryInterruptConfig {
  allow_ignore: boolean;
  allow_respond: boolean;
  allow_edit: boolean;
  allow_accept: boolean;
  allow_compare: boolean;
}

export interface DiscoveryInterruptPayload {
  action_request: DiscoveryInterruptActionRequest;
  config: DiscoveryInterruptConfig;
  description: string;
  summary: string;
}

export interface DiscoveryReviewEvent {
  event_id: string;
  action: DiscoveryInboxActionKind;
  actor: string;
  note: string;
  created_at: string;
  metadata: Record<string, unknown>;
}

export interface DiscoveryInboxEvidencePreview {
  observations: string[];
  validations: string[];
  timeline: string[];
}

export interface DiscoveryInboxCompareOption {
  idea_id: string;
  title: string;
  latest_stage: DiscoveryDossierStage;
  reason: string;
}

export interface DiscoveryInboxDossierPreview {
  headline: string;
  idea_summary: string;
  latest_stage: DiscoveryDossierStage;
  rank_score: number;
  belief_score: number;
  evidence: DiscoveryInboxEvidencePreview;
  debate_summary?: string | null;
  simulation_summary?: string | null;
  handoff_summary?: string | null;
  compare_options: DiscoveryInboxCompareOption[];
  raw_trace: Record<string, unknown>;
}

export interface DiscoveryInboxItem {
  item_id: string;
  kind: string;
  status: InboxItemStatus;
  subject_kind: DiscoveryInboxSubjectKind;
  title: string;
  detail: string;
  created_at: string;
  due_at?: string | null;
  idea_id?: string | null;
  digest_id?: string | null;
  run_id?: string | null;
  priority_score: number;
  age_minutes: number;
  aging_bucket: DiscoveryInboxAgingBucket;
  interrupt?: DiscoveryInterruptPayload | null;
  dossier_preview?: DiscoveryInboxDossierPreview | null;
  review_history: DiscoveryReviewEvent[];
  resolution?: DiscoveryReviewEvent | null;
  metadata: Record<string, unknown>;
}

export interface DiscoveryInboxSummary {
  open_count: number;
  resolved_count: number;
  stale_count: number;
  action_required_count: number;
  kinds: Record<string, number>;
  subject_kinds: Record<string, number>;
}

export interface DiscoveryInboxFeed {
  items: DiscoveryInboxItem[];
  summary: DiscoveryInboxSummary;
}

export interface DiscoveryInboxActionRequest {
  action: DiscoveryInboxActionKind;
  actor?: string;
  note?: string;
  response_text?: string | null;
  edited_fields?: Record<string, string>;
  compare_target_idea_id?: string | null;
  resolve?: boolean | null;
  metadata?: Record<string, unknown>;
}

export interface DiscoveryDaemonRun {
  run_id: string;
  routine_kind: DaemonRoutineKind;
  status: DaemonRunStatus;
  cycle_id: string;
  fresh_session_id: string;
  triggered_by: string;
  started_at: string;
  finished_at?: string | null;
  summary: string;
  touched_idea_ids: string[];
  digest_id?: string | null;
  inbox_item_ids: string[];
  budget_used_usd: number;
  checkpoints: DiscoveryDaemonCheckpoint[];
  alerts: DiscoveryDaemonAlert[];
  metadata: Record<string, unknown>;
}

export interface DiscoveryDaemonStatus {
  daemon_id: string;
  mode: DaemonMode;
  fresh_session_policy: string;
  loop_interval_sec: number;
  started_at?: string | null;
  worker_heartbeat_at?: string | null;
  last_tick_at?: string | null;
  next_tick_at?: string | null;
  inbox_pending_count: number;
  latest_digest_id?: string | null;
  routines: DiscoveryRoutineState[];
  recent_runs: DiscoveryDaemonRun[];
  alerts: DiscoveryDaemonAlert[];
}

export type RankingJudgeSource = "human" | "agent" | "council" | "system";
export type PairwiseVerdict = "left" | "right" | "tie";

export interface PairwiseComparisonRecord {
  comparison_id: string;
  left_idea_id: string;
  right_idea_id: string;
  verdict: PairwiseVerdict;
  winner_idea_id?: string | null;
  loser_idea_id?: string | null;
  rationale: string;
  judge_source: RankingJudgeSource;
  judge_model?: string | null;
  judge_agent_id?: string | null;
  domain_key?: string | null;
  judge_confidence: number;
  evidence_weight: number;
  agent_importance_score: number;
  believability_weight: number;
  comparison_weight: number;
  created_at: string;
  metadata: Record<string, unknown>;
}

export interface RankedIdeaRecord {
  idea: IdeaCandidate;
  rank_position: number;
  rating: number;
  merit_score: number;
  matches_played: number;
  wins: number;
  losses: number;
  ties: number;
  win_rate: number;
  stability_score: number;
  volatility_score: number;
  confidence_low: number;
  confidence_high: number;
  last_compared_at?: string | null;
}

export interface RankingJudgeBelievability {
  judge_key: string;
  judge_source: RankingJudgeSource;
  judge_model?: string | null;
  judge_agent_id?: string | null;
  domain_key?: string | null;
  comparisons_count: number;
  agreement_rate: number;
  believability_score: number;
}

export interface RankingMetrics {
  comparisons_count: number;
  unique_pairs: number;
  reliability_weighted: number;
  rank_stability: number;
  volatility_mean: number;
  average_ci_width: number;
}

export interface RankingLeaderboardResponse {
  items: RankedIdeaRecord[];
  judges: RankingJudgeBelievability[];
  metrics: RankingMetrics;
}

export interface PromptEvolutionProfile {
  profile_id: string;
  label: string;
  operator_kind: string;
  instruction: string;
  elo_rating: number;
  wins: number;
  losses: number;
  ties: number;
  usage_count: number;
  debate_influence: number;
  last_updated: string;
  metadata: Record<string, unknown>;
}

export interface IdeaGenome {
  genome_id: string;
  idea_id: string;
  title: string;
  lineage_idea_ids: string[];
  domain: string;
  complexity: string;
  distribution_strategy: string;
  buyer_type: string;
  fitness: number;
  novelty_score: number;
  rating: number;
  merit_score: number;
  stability_score: number;
  prompt_profile_id?: string | null;
  metadata: Record<string, unknown>;
  created_at: string;
}

export interface IdeaArchiveCell {
  cell_id: string;
  key: string;
  domain: string;
  complexity: string;
  distribution_strategy: string;
  buyer_type: string;
  elite: IdeaGenome;
  replaced_genome_id?: string | null;
  occupied_at: string;
}

export interface EvolutionRecommendation {
  recommendation_id: string;
  operator_kind: string;
  headline: string;
  description: string;
  source_genome_ids: string[];
  target_axes: Record<string, string>;
  prompt_profile_id?: string | null;
}

export interface ArchiveCheckpointDigest {
  checkpoint_id: string;
  generation: number;
  filled_cells: number;
  coverage: number;
  qd_score: number;
  created_at: string;
}

export interface IdeaArchiveSnapshot {
  archive_id: string;
  generation: number;
  total_possible_cells: number;
  filled_cells: number;
  coverage: number;
  qd_score: number;
  diversity_score: number;
  novelty_mean: number;
  cells: IdeaArchiveCell[];
  top_genomes: IdeaGenome[];
  prompt_profiles: PromptEvolutionProfile[];
  recommendations: EvolutionRecommendation[];
  checkpoints: ArchiveCheckpointDigest[];
  checkpointed: boolean;
  created_at: string;
}

export interface NextPairResponse {
  left: RankedIdeaRecord;
  right: RankedIdeaRecord;
  utility_score: number;
  reason: string;
  direct_comparisons: number;
  candidate_pool_size: number;
}

export interface PairwiseComparisonResponse {
  comparison: PairwiseComparisonRecord;
  leaderboard: RankingLeaderboardResponse;
  next_pair?: NextPairResponse | null;
}

export interface FinalVoteBallot {
  voter_id: string;
  ranked_idea_ids: string[];
  weight: number;
  judge_source: RankingJudgeSource;
  judge_model?: string | null;
  judge_agent_id?: string | null;
  domain_key?: string | null;
  confidence: number;
  agent_importance_score: number;
}

export interface FinalVoteRound {
  round_number: number;
  tallies: Record<string, number>;
  eliminated_idea_id?: string | null;
  total_weight: number;
}

export interface FinalVoteResult {
  winner_idea_id?: string | null;
  rounds: FinalVoteRound[];
  aggregate_rankings: Array<{
    idea_id: string;
    average_rank: number;
    rankings_count: number;
  }>;
}

export type ResearchSource =
  | "github"
  | "github_trending"
  | "hackernews"
  | "reddit"
  | "npm"
  | "pypi"
  | "producthunt"
  | "stackoverflow";

export interface ResearchObservation {
  observation_id: string;
  source: ResearchSource;
  entity: string;
  query: string;
  url: string;
  raw_text: string;
  topic_tags: string[];
  pain_score: number;
  trend_score: number;
  evidence_confidence: SharedConfidence;
  collected_at: string;
  freshness_deadline?: string | null;
  metadata: Record<string, unknown>;
}

export interface ResearchScanRun {
  run_id: string;
  query: string;
  sources: ResearchSource[];
  started_at: string;
  finished_at?: string | null;
  status: "running" | "completed" | "failed";
  observation_count: number;
  error_messages: string[];
}

export interface DailyQueueItem {
  queue_id: string;
  observation: ResearchObservation;
  priority_score: number;
  bucket: "daily" | "weekly";
}

export interface ResearchSearchResult {
  items: ResearchObservation[];
  total: number;
}

export type RepoSourceType = "local" | "github";
export type RepoComplexity = "low" | "medium" | "high" | "very_high";

export interface RepoHotFile {
  path: string;
  language?: string | null;
  line_count: number;
  importance_score: number;
  reasons: string[];
}

export interface RepoIssueTheme {
  label: string;
  frequency: number;
  evidence: string[];
}

export interface RepoDigestSummary {
  digest_id: string;
  source: string;
  source_type: RepoSourceType;
  repo_name: string;
  repo_root?: string | null;
  branch?: string | null;
  commit_sha?: string | null;
  generated_at: number;
  tree_preview: string[];
  languages: Record<string, number>;
  tech_stack: string[];
  dominant_domains: string[];
  readme_claims: string[];
  issue_themes: RepoIssueTheme[];
  hot_files: RepoHotFile[];
  key_paths: string[];
  file_count: number;
}

export interface RepoDNAProfile {
  profile_id: string;
  source: string;
  repo_name: string;
  generated_at: number;
  languages: string[];
  domain_clusters: string[];
  preferred_complexity: RepoComplexity;
  recurring_pain_areas: string[];
  adjacent_product_opportunities: string[];
  repeated_builds: string[];
  avoids: string[];
  breaks_often: string[];
  adjacent_buyer_pain: string[];
  idea_generation_context: string;
  ranking_priors: string[];
  swipe_explanation_points: string[];
}

export interface RepoDigestResult {
  digest: RepoDigestSummary;
  profile: RepoDNAProfile;
  cache_hit: boolean;
  warnings: string[];
}

export type RepoGraphTrigger = "promoted" | "explicit" | "background";

export interface RepoGraphNodeRecord {
  node_id: string;
  kind: string;
  label: string;
  source_ref?: string | null;
  weight: number;
  metadata: Record<string, unknown>;
}

export interface RepoGraphEdgeRecord {
  edge_id: string;
  kind: string;
  source_node_id: string;
  target_node_id: string;
  weight: number;
  evidence: string[];
  metadata: Record<string, unknown>;
}

export interface RepoGraphCommunityRecord {
  community_id: string;
  title: string;
  summary: string;
  node_ids: string[];
  finding_points: string[];
  rank_score: number;
}

export interface RepoGraphEvidenceTrail {
  trail_id: string;
  thesis: string;
  explanation: string;
  supporting_node_ids: string[];
  supporting_edge_ids: string[];
}

export interface RepoDeepDiveRecord {
  deep_dive_id: string;
  graph_id: string;
  startup_territories: string[];
  architectural_focus: string[];
  risk_hotspots: string[];
  adjacency_opportunities: string[];
  why_now: string[];
  evidence_trails: RepoGraphEvidenceTrail[];
}

export interface RepoGraphStats {
  node_count: number;
  edge_count: number;
  community_count: number;
  api_count: number;
  package_count: number;
  problem_count: number;
  generated_at: number;
}

export interface RepoGraphResult {
  graph_id: string;
  source: string;
  source_type: RepoSourceType;
  repo_name: string;
  branch?: string | null;
  commit_sha?: string | null;
  trigger: RepoGraphTrigger;
  generated_at: number;
  repo_dna_profile?: RepoDNAProfile | null;
  nodes: RepoGraphNodeRecord[];
  edges: RepoGraphEdgeRecord[];
  communities: RepoGraphCommunityRecord[];
  deep_dive: RepoDeepDiveRecord;
  stats: RepoGraphStats;
  cache_hit: boolean;
  warnings: string[];
}

export interface WorkspacePreset {
  id: string;
  name: string;
  description?: string | null;
  paths: string[];
  created_at?: number;
}

export interface Message {
  agent_id: string;
  content: string;
  timestamp: number;
  phase: string;
}

export interface SessionEvent {
  id: number;
  timestamp: number;
  type: string;
  title: string;
  detail: string;
  status?: string;
  agent_id?: string;
  phase?: string;
  checkpoint_id?: string;
  next_node?: string | null;
  pending_instructions?: number;
  applied_count?: number;
  mode?: string;
  forked_from?: string;
  branch_to?: string;
  tool_name?: string;
  elapsed_sec?: number;
  success?: boolean;
  round?: number;
}

export interface ParallelChildSummary {
  id: string;
  mode: string;
  status: string;
  created_at: number;
  slot_key?: string | null;
  stage?: string | null;
  label: string;
  winner_label?: string | null;
}

export interface ParallelProgress {
  execution_mode?: "sequential" | "parallel";
  stage_label?: string | null;
  total?: number;
  running?: number;
  completed?: number;
  failed?: number;
  group_id?: string | null;
}

export interface AttachedToolDetail {
  id: string;
  name: string;
  tool_type?: string | null;
  transport: string;
  subtitle: string;
  icon: string;
  capability: "native" | "bridged" | "unavailable";
}

export interface ProtocolOutputField {
  name: string;
  field_type: "string" | "number" | "integer" | "boolean" | "array" | "object" | "null";
  required: boolean;
  description: string;
}

export interface ProtocolGuardPredicate {
  field: string;
  operator:
    | "eq"
    | "ne"
    | "lt"
    | "lte"
    | "gt"
    | "gte"
    | "truthy"
    | "falsy"
    | "nonempty"
    | "in"
    | "contains"
    | "not_contains";
  value?: unknown;
}

export interface ProtocolTransitionGuard {
  guard_id: string;
  source_node_id: string;
  target_node_id: string;
  description: string;
  predicates: ProtocolGuardPredicate[];
  predicate_match: "all" | "any";
  shadow_only: boolean;
}

export interface ProtocolStateNode {
  node_id: string;
  label: string;
  stage: string;
  purpose: string;
  role_hints: string[];
  allowed_outputs: string[];
  output_schema: ProtocolOutputField[];
  state_reads: string[];
  state_writes: string[];
}

export interface ProtocolTerminalState {
  node_id: string;
  label: string;
  outcome: "success" | "cancelled" | "failed" | "warning";
  description: string;
}

export interface ProtocolBlueprint {
  blueprint_id: string;
  cache_key: string;
  compiled_at: number;
  mode: string;
  mode_family: string;
  protocol_key: string;
  blueprint_class: string;
  entry_node_id: string;
  nodes: ProtocolStateNode[];
  transitions: ProtocolTransitionGuard[];
  terminal_states: ProtocolTerminalState[];
  bounded: boolean;
  notes: string[];
  compiled_from: Record<string, unknown>;
  planner_hints: Record<string, unknown>;
}

export interface ProtocolShadowValidationResult {
  blueprint_id: string;
  from_node_id: string;
  to_node_id: string;
  ok: boolean;
  guard_id?: string | null;
  errors: string[];
  warnings: string[];
  checked_at: number;
}

export interface ProtocolShadowValidationSummary {
  blueprint_id: string;
  cache_key: string;
  cache_hit: boolean;
  validated_transitions: number;
  invalid_transitions: number;
  last_validation?: ProtocolShadowValidationResult | null;
  branched_from: Record<string, string>;
}

export interface ProtocolTraceStep {
  trace_id: string;
  blueprint_id: string;
  step_index: number;
  from_node_id: string;
  to_node_id: string;
  checkpoint_id: string;
  graph_checkpoint_id?: string | null;
  guard_id?: string | null;
  ok: boolean;
  timestamp: number;
  errors: string[];
  warnings: string[];
  state_excerpt: Record<string, unknown>;
}

export interface TopologyTaskProfile {
  domain_key: string;
  complexity: "low" | "medium" | "high" | "frontier";
  uncertainty: number;
  coordination_need: number;
  delivery_pressure: number;
  reasoning_depth: number;
  recommended_execution_mode: "sequential" | "parallel";
  specializations: string[];
  evidence_bias: number;
}

export interface TeamRoleRecommendation {
  role: string;
  provider: string;
  tools: string[];
  expertise_tags: string[];
  importance_score: number;
  believability_score: number;
  origin: "existing" | "suggested";
  rationale: string;
}

export interface DynamicTeamPlan {
  strategy: "baseline" | "parallel_fanout" | "branch_merge" | "blackboard";
  quorum_size: number;
  branch_factor: number;
  blackboard_enabled: boolean;
  task_profile: TopologyTaskProfile;
  role_recommendations: TeamRoleRecommendation[];
  suggested_roles: TeamRoleRecommendation[];
  notes: string[];
}

export interface WeightedTopologyNode {
  node_id: string;
  label: string;
  stage: string;
  importance_weight: number;
  parallelizable: boolean;
  branch_candidate: boolean;
  reason: string;
}

export interface WeightedTopologyEdge {
  guard_id: string;
  source_node_id: string;
  target_node_id: string;
  transition_weight: number;
  routing_bias: "sequential" | "parallel" | "branch" | "blackboard";
  reason: string;
}

export interface GraphOptimizationResult {
  selected_template: "baseline" | "parallel_fanout" | "branch_merge" | "blackboard";
  recommended_execution_mode: "sequential" | "parallel";
  estimated_parallelism: number;
  branch_factor: number;
  blackboard_enabled: boolean;
  node_weights: WeightedTopologyNode[];
  edge_weights: WeightedTopologyEdge[];
  optimization_notes: string[];
}

export interface TopologyBranchLine {
  branch_id: string;
  focus: string;
  owner_roles: string[];
  target_node_ids: string[];
  merge_node_id?: string | null;
}

export interface DynamicRoutingPlan {
  route_family: string;
  recommended_execution_mode: string;
  branch_merge_enabled: boolean;
  blackboard_enabled: boolean;
  route_reasons: string[];
  opportunistic_roles: string[];
  branch_lines: TopologyBranchLine[];
}

export interface MetaSearchCandidate {
  candidate_id: string;
  template: "baseline" | "parallel_fanout" | "branch_merge" | "blackboard";
  score: number;
  recommended_execution_mode: string;
  strengths: string[];
  risks: string[];
  estimated_parallelism: number;
}

export interface MetaTopologyState {
  search_id: string;
  generated_at: number;
  class_key: string;
  selected_template: "baseline" | "parallel_fanout" | "branch_merge" | "blackboard";
  selected_execution_mode: string;
  chosen_reason: string;
  task_profile: TopologyTaskProfile;
  team_plan: DynamicTeamPlan;
  graph_optimization: GraphOptimizationResult;
  routing_plan: DynamicRoutingPlan;
  candidates: MetaSearchCandidate[];
}

export interface Session {
  id: string;
  mode: string;
  task: string;
  agents: AgentConfig[];
  messages: Message[];
  result: string | null;
  status: "running" | "pause_requested" | "paused" | "cancel_requested" | "cancelled" | "completed" | "failed";
  config: Record<string, unknown>;
  active_scenario?: string | null;
  forked_from?: string | null;
  forked_checkpoint_id?: string | null;
  parallel_parent_id?: string | null;
  parallel_group_id?: string | null;
  parallel_slot_key?: string | null;
  parallel_stage?: string | null;
  parallel_label?: string | null;
  capabilities?: Record<string, boolean>;
  created_at: number;
  elapsed_sec: number | null;
  current_checkpoint_id?: string | null;
  checkpoints?: Array<{
    id: string;
    timestamp: number;
    next_node?: string | null;
    status: string;
    result_preview?: string;
    graph_checkpoint_id?: string | null;
  }>;
  events?: SessionEvent[];
  pending_instructions?: number;
  active_node?: string | null;
  workspace_preset_ids?: string[];
  workspace_paths?: string[];
  attached_tool_ids?: string[];
  attached_tools?: AttachedToolDetail[];
  provider_capabilities_snapshot?: Record<string, {
    provider: string;
    tools: Record<string, {
      capability: "native" | "bridged" | "unavailable";
      tool_type?: string | null;
      name?: string | null;
    }>;
  }>;
  branch_children?: Array<{
    id: string;
    mode: string;
    status: string;
    created_at: number;
    forked_checkpoint_id?: string | null;
  }>;
  parallel_children?: ParallelChildSummary[];
  parallel_progress?: ParallelProgress;
  protocol_blueprint?: ProtocolBlueprint | null;
  protocol_trace?: ProtocolTraceStep[];
  protocol_shadow_validation?: ProtocolShadowValidationSummary | null;
  topology_state?: MetaTopologyState | null;
  generation_trace?: {
    local_first?: boolean;
    aggregator_count?: number;
    judge_criteria?: string[];
    novelty_context?: Record<string, unknown>;
    layer1_outputs?: Array<{
      artifact_id: string;
      layer: string;
      agent_role: string;
      provider: string;
      candidate_id?: string | null;
      content: string;
      summary?: string;
      metadata?: Record<string, unknown>;
      generated_at?: number;
    }>;
    layer2_outputs?: Array<{
      artifact_id: string;
      layer: string;
      agent_role: string;
      provider: string;
      candidate_id?: string | null;
      content: string;
      summary?: string;
      metadata?: Record<string, unknown>;
      generated_at?: number;
    }>;
    judge_scores?: Array<{
      judge_role: string;
      candidate_id: string;
      overall_score: number;
      criteria?: Record<string, number>;
      rationale?: string;
    }>;
    trace_artifacts?: Array<{
      artifact_id: string;
      layer: string;
      agent_role: string;
      provider: string;
      candidate_id?: string | null;
      content: string;
      summary?: string;
      metadata?: Record<string, unknown>;
      generated_at?: number;
    }>;
    selected_candidate_id?: string | null;
    final_artifact?: {
      artifact_id: string;
      layer: string;
      agent_role: string;
      provider: string;
      candidate_id?: string | null;
      content: string;
      summary?: string;
      metadata?: Record<string, unknown>;
      generated_at?: number;
    } | null;
  };
  runtime_state?: {
    live_runtime_available?: boolean;
    checkpoint_runtime_available?: boolean;
    has_checkpoints?: boolean;
    has_branchable_checkpoints?: boolean;
    can_pause?: boolean;
    can_resume?: boolean;
    can_send_message?: boolean;
    can_inject_instruction?: boolean;
    can_cancel?: boolean;
    can_continue_conversation?: boolean;
    can_branch_from_checkpoint?: boolean;
    reasons?: Record<string, { code: string; message: string } | null>;
  };
}

export interface SessionSummary {
  id: string;
  mode: string;
  task: string;
  status: string;
  created_at: number;
  active_scenario?: string | null;
  forked_from?: string | null;
  parallel_parent_id?: string | null;
  parallel_group_id?: string | null;
  parallel_slot_key?: string | null;
  parallel_stage?: string | null;
  parallel_label?: string | null;
}

export interface ExecutionBrief {
  version: string;
  title: string;
  thesis: string;
  summary: string;
  tags: string[];
  founder: {
    mode: string;
    strengths: string[];
    interests: string[];
    constraints: string[];
    unfair_advantages: string[];
    available_capital_usd?: number | null;
    weekly_hours?: number | null;
  };
  market: {
    icp: string;
    pain: string;
    why_now: string;
    wedge: string;
  };
  execution: {
    mvp_scope: string[];
    non_goals: string[];
    required_capabilities: string[];
    required_connectors: string[];
    existing_repos: string[];
  };
  monetization: {
    revenue_model: string;
    pricing_hint: string;
    time_to_first_dollar: string;
  };
  evaluation: {
    success_metrics: string[];
    kill_criteria: string[];
    open_questions: string[];
    major_risks: string[];
  };
  provenance: {
    source_system: string;
    source_session_id: string;
    source_mode: string;
    source_scenario_id: string;
    ranking_rationale: string;
  };
}

export interface TournamentPreparationCandidate {
  label: string;
  thesis: string;
  rationale: string;
  source_workspace_path: string;
  tags: string[];
}

export interface TournamentPreparation {
  version: string;
  title: string;
  scenario_id: string;
  mode: string;
  task: string;
  recommended_max_rounds: number;
  recommended_execution_mode: "sequential" | "parallel";
  contestants: TournamentPreparationCandidate[];
  agents: AgentConfig[];
  workspace_paths: string[];
}

export interface AutopilotLaunchProfile {
  preset: string;
  story_execution_mode?: string | null;
  project_concurrency_mode?: string | null;
  max_parallel_stories?: number | null;
}

export interface AutopilotLaunchPreset {
  id: string;
  label: string;
  description: string;
  launch_profile: AutopilotLaunchProfile;
}

export interface AutopilotProjectSummary {
  id: string;
  name: string;
  path: string;
  priority: string;
  archived: boolean;
  status: string;
  paused: boolean;
  stories_done: number;
  stories_total: number;
  current_story_id: number | null;
  current_story_title: string | null;
  last_activity_at: string | null;
  last_message: string;
  pid: number | null;
  launch_profile: AutopilotLaunchProfile;
}

export interface ModeInfo {
  description: string;
  default_agents: AgentConfig[];
}

export interface ScenarioDefinition {
  id: string;
  name: string;
  mode: string;
  headline: string;
  description: string;
  recommended_for: string;
  task_placeholder: string;
  tags: string[];
  default_config: Record<string, number>;
  default_agents: AgentConfig[];
  is_local_fallback?: boolean;
}
