export interface AgentConfig {
  role: string;
  provider: "claude" | "gemini" | "codex" | "minimax";
  system_prompt: string;
  tools?: string[];
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

export interface CustomToolConfig {
  key: string;
  name: string;
  description: string;
  category?: string;
  tool_type: "http_api" | "ssh" | "shell_command";
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
}

export interface SessionSummary {
  id: string;
  mode: string;
  task: string;
  status: string;
  created_at: number;
  active_scenario?: string | null;
  forked_from?: string | null;
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
}
