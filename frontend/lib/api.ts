import type {
  ConfiguredTool,
  CustomToolConfig,
  ModeInfo,
  PromptTemplate,
  RunRequest,
  Session,
  SessionSummary,
  ToolDefinition,
  ToolTypeDefinition,
} from "./types";

const BASE = process.env.NEXT_PUBLIC_API_BASE ?? "http://127.0.0.1:8800";

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
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

export async function runSession(
  body: RunRequest
): Promise<{ session_id: string }> {
  return request("/orchestrate/run", {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export async function sendMessage(
  _sessionId: string,
  _content: string
): Promise<void> {
  void _sessionId;
  void _content;
  throw new Error("Live user messages are not supported in this build.");
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
