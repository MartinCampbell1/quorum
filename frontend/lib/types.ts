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
  last_validation_result?: {
    ok?: boolean;
    error?: string;
    log?: string[];
    transport?: string;
    tool_count?: number;
  };
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
  runtime_state?: {
    live_runtime_available?: boolean;
    checkpoint_runtime_available?: boolean;
    has_checkpoints?: boolean;
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
