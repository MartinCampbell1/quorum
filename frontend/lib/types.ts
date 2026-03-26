export interface AgentConfig {
  role: string;
  provider: "claude" | "gemini" | "codex" | "minimax";
  system_prompt: string;
}

export interface RunRequest {
  mode: string;
  task: string;
  agents?: AgentConfig[];
  config?: Record<string, unknown>;
}

export interface Message {
  agent_id: string;
  content: string;
  timestamp: number;
  phase: string;
}

export interface Session {
  id: string;
  mode: string;
  task: string;
  agents: AgentConfig[];
  messages: Message[];
  result: string | null;
  status: "running" | "completed" | "failed";
  config: Record<string, unknown>;
  created_at: number;
  elapsed_sec: number | null;
}

export interface SessionSummary {
  id: string;
  mode: string;
  task: string;
  status: string;
  created_at: number;
}

export interface ModeInfo {
  description: string;
  default_agents: AgentConfig[];
}
