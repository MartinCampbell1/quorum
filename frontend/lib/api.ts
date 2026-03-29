import type {
  AccountHealth,
  AccountsByProvider,
  AutopilotLaunchPreset,
  AutopilotProjectSummary,
  ConfiguredTool,
  CustomToolConfig,
  ExecutionBrief,
  ModeInfo,
  PromptTemplate,
  RunRequest,
  ScenarioDefinition,
  Session,
  SessionSummary,
  TournamentPreparation,
  ToolDefinition,
  ToolTypeDefinition,
  WorkspacePreset,
} from "./types";

export const API_BASE = process.env.NEXT_PUBLIC_API_BASE ?? "http://127.0.0.1:8800";

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...options?.headers,
    },
  });
  if (!res.ok) {
    throw new Error(`API error: ${res.status} ${res.statusText}`);
  }
  return res.json();
}

export async function getModes(): Promise<Record<string, ModeInfo>> {
  return request("/orchestrate/modes");
}

export async function getScenarios(): Promise<ScenarioDefinition[]> {
  return request("/orchestrate/scenarios");
}

export async function getAutopilotLaunchPresets(): Promise<AutopilotLaunchPreset[]> {
  const payload = await request<{ launch_presets: AutopilotLaunchPreset[] }>("/orchestrate/autopilot/launch-presets");
  return payload.launch_presets;
}

export async function getAutopilotProjects(): Promise<AutopilotProjectSummary[]> {
  const payload = await request<{ projects: AutopilotProjectSummary[] }>("/orchestrate/autopilot/projects");
  return payload.projects;
}

export async function pauseAutopilotProject(projectId: string): Promise<{ status: string; message: string }> {
  return request(`/orchestrate/autopilot/projects/${projectId}/pause`, { method: "POST" });
}

export async function resumeAutopilotProject(projectId: string): Promise<{ status: string; message: string }> {
  return request(`/orchestrate/autopilot/projects/${projectId}/resume`, { method: "POST" });
}

export function getSessionEventsStreamUrl(sessionId: string, since: number = 0): string {
  const params = new URLSearchParams();
  if (since > 0) {
    params.set("since", String(since));
  }
  const suffix = params.toString();
  return `${API_BASE}/orchestrate/session/${sessionId}/events${suffix ? `?${suffix}` : ""}`;
}

export async function getTools(): Promise<ToolDefinition[]> {
  return request("/orchestrate/tools");
}

export async function addCustomTool(
  _config: CustomToolConfig
): Promise<CustomToolConfig> {
  void _config;
  throw new Error("Custom tools are not supported in this build.");
}

export async function getCustomTools(): Promise<CustomToolConfig[]> {
  return [];
}

export async function removeCustomTool(_key: string): Promise<void> {
  void _key;
  throw new Error("Custom tools are not supported in this build.");
}

export async function getToolLogs(
  limit: number = 50
): Promise<Record<string, unknown>[]> {
  return request(`/orchestrate/tool-logs?limit=${limit}`);
}

export async function getSessions(): Promise<SessionSummary[]> {
  return request("/orchestrate/sessions");
}

export async function getSession(id: string): Promise<Session> {
  return request(`/orchestrate/session/${id}`);
}

export async function exportExecutionBrief(
  sessionId: string,
  provider?: string
): Promise<{ status: string; brief: ExecutionBrief }> {
  return request(`/orchestrate/session/${sessionId}/execution-brief`, {
    method: "POST",
    body: JSON.stringify({ provider: provider ?? null }),
  });
}

export async function sendExecutionBriefToAutopilot(
  sessionId: string,
  body?: {
    provider?: string;
    autopilot_url?: string;
    project_name?: string;
    project_path?: string;
    priority?: string;
    launch?: boolean;
    launch_profile?: {
      preset?: string;
      story_execution_mode?: string | null;
      project_concurrency_mode?: string | null;
      max_parallel_stories?: number | null;
    } | null;
  }
): Promise<{ status: string; brief: ExecutionBrief; autopilot: Record<string, unknown> }> {
  return request(`/orchestrate/session/${sessionId}/send-to-autopilot`, {
    method: "POST",
    body: JSON.stringify(body ?? {}),
  });
}

export async function prepareTournamentFromSession(
  sessionId: string,
  provider?: string
): Promise<{ status: string; tournament: TournamentPreparation }> {
  return request(`/orchestrate/session/${sessionId}/tournament-preparation`, {
    method: "POST",
    body: JSON.stringify({ provider: provider ?? null }),
  });
}

export async function runSession(
  body: RunRequest
): Promise<{ session_id: string }> {
  return request("/orchestrate/run", {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export async function sendMessage(
  sessionId: string,
  content: string
): Promise<void> {
  await request(`/orchestrate/session/${sessionId}/message`, {
    method: "POST",
    body: JSON.stringify({ content }),
  });
}

export async function continueSession(
  sessionId: string,
  content: string
): Promise<{ status: string; new_session_id?: string }> {
  return request(`/orchestrate/session/${sessionId}/continue`, {
    method: "POST",
    body: JSON.stringify({ content }),
  });
}

export async function controlSession(
  sessionId: string,
  action: "pause" | "resume" | "inject_instruction" | "cancel" | "restart_from_checkpoint",
  content?: string,
  checkpointId?: string
): Promise<{ status: string; pending_instructions?: number; new_session_id?: string }> {
  return request(`/orchestrate/session/${sessionId}/control`, {
    method: "POST",
    body: JSON.stringify({ action, content: content ?? "", checkpoint_id: checkpointId ?? "" }),
  });
}

export async function getAccountsHealth(): Promise<AccountHealth> {
  return request("/accounts/health");
}

export async function getAccounts(): Promise<{ accounts: AccountsByProvider }> {
  return request("/accounts");
}

export async function reloadAccounts(): Promise<{ status: string; accounts: AccountsByProvider }> {
  return request("/accounts/reload", { method: "POST" });
}

export async function openProviderLogin(
  provider: string
): Promise<{ status: string; provider: string; command: string; message: string }> {
  return request(`/accounts/${encodeURIComponent(provider)}/open-login`, {
    method: "POST",
  });
}

export async function importProviderSession(
  provider: string
): Promise<{ status: string; provider: string; account_name: string; accounts: AccountsByProvider[string]; message: string }> {
  return request(`/accounts/${encodeURIComponent(provider)}/import`, {
    method: "POST",
  });
}

export async function reauthorizeProviderAccount(
  provider: string,
  accountName: string
): Promise<{ status: string; provider: string; account_name: string; accounts: AccountsByProvider[string]; message: string }> {
  return request(`/accounts/${encodeURIComponent(provider)}/${encodeURIComponent(accountName)}/reauthorize`, {
    method: "POST",
  });
}

export async function updateProviderAccount(
  provider: string,
  accountName: string,
  label: string
): Promise<{ status: string; provider: string; account_name: string; label: string; accounts: AccountsByProvider[string]; message: string }> {
  return request(`/accounts/${encodeURIComponent(provider)}/${encodeURIComponent(accountName)}`, {
    method: "PATCH",
    body: JSON.stringify({ label }),
  });
}

// Settings API

export async function getConfiguredTools(): Promise<ConfiguredTool[]> {
  return request("/orchestrate/settings/tools");
}

export async function getToolTypes(): Promise<Record<string, ToolTypeDefinition>> {
  return request("/orchestrate/settings/tools/types");
}

export async function addConfiguredTool(tool: ConfiguredTool): Promise<ConfiguredTool> {
  return request("/orchestrate/settings/tools", {
    method: "POST",
    body: JSON.stringify(tool),
  });
}

export async function updateConfiguredTool(
  id: string,
  updates: Partial<ConfiguredTool>
): Promise<ConfiguredTool> {
  return request(`/orchestrate/settings/tools/${id}`, {
    method: "PUT",
    body: JSON.stringify(updates),
  });
}

export async function deleteConfiguredTool(id: string): Promise<void> {
  await request(`/orchestrate/settings/tools/${id}`, { method: "DELETE" });
}

export async function getPromptTemplates(): Promise<Record<string, PromptTemplate>> {
  return request("/orchestrate/settings/prompts");
}

export async function getProviderCapabilities(): Promise<{
  providers: string[];
  tools: Record<string, Record<string, "native" | "bridged" | "unavailable">>;
}> {
  return request("/orchestrate/settings/providers/capabilities");
}

export async function validateConfiguredTool(id: string): Promise<ConfiguredTool> {
  return request(`/orchestrate/settings/tools/${id}/validate`, {
    method: "POST",
  });
}

export async function getWorkspacePresets(): Promise<WorkspacePreset[]> {
  return request("/orchestrate/settings/workspaces");
}

export async function addWorkspacePreset(preset: WorkspacePreset): Promise<WorkspacePreset> {
  return request("/orchestrate/settings/workspaces", {
    method: "POST",
    body: JSON.stringify(preset),
  });
}

export async function updateWorkspacePreset(
  id: string,
  updates: Partial<WorkspacePreset>
): Promise<WorkspacePreset> {
  return request(`/orchestrate/settings/workspaces/${id}`, {
    method: "PUT",
    body: JSON.stringify(updates),
  });
}

export async function deleteWorkspacePreset(id: string): Promise<void> {
  await request(`/orchestrate/settings/workspaces/${id}`, { method: "DELETE" });
}
