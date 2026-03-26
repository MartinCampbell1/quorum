import type { Session, SessionSummary, ModeInfo, RunRequest } from "./types";

const BASE = "http://localhost:8800";

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
  sessionId: string,
  content: string
): Promise<void> {
  await request(`/orchestrate/session/${sessionId}/message`, {
    method: "POST",
    body: JSON.stringify({ content }),
  });
}
