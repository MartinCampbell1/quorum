import type {
  AccountHealth,
  AccountsByProvider,
  AutopilotLaunchPreset,
  AutopilotProjectSummary,
  ConfiguredTool,
  CustomToolConfig,
  DossierTimelineEvent,
  DiscoveryDaemonRun,
  DiscoveryDaemonStatus,
  DiscoveryDailyDigest,
  DiscoveryEvaluationPack,
  DiscoveryInboxActionRequest,
  DiscoveryInboxFeed,
  DiscoveryInboxItem,
  DiscoveryObservabilityScoreboard,
  DiscoveryTraceSnapshot,
  DebateReplaySession,
  EvidenceBundleCandidate,
  ExecutionBrief,
  ExecutionBriefCandidateRecord,
  GuardrailAuditEvent,
  GuardrailScanReport,
  IdeaArchiveEntry,
  IdeaArchiveSnapshot,
  IdeaCandidate,
  IdeaDecision,
  IdeaDossier,
  IdeaExplainabilitySnapshot,
  IdeaGraphContext,
  IdeaGraphSnapshot,
  IdeaTraceBundle,
  IdeaValidationReport,
  InstitutionalMemoryContext,
  DailyQueueItem,
  FinalVoteBallot,
  FinalVoteResult,
  MemoryGraphSnapshot,
  MemoryQueryRequest,
  MemoryQueryResponse,
  ModeInfo,
  NextPairResponse,
  PairwiseComparisonResponse,
  PairwiseVerdict,
  PromptTemplate,
  FounderPreferenceProfile,
  IdeaChangeRecord,
  ResearchObservation,
  ResearchScanRun,
  ResearchSearchResult,
  ResearchSource,
  IdeaSwipeResult,
  MaybeQueueResponse,
  RankingJudgeSource,
  RankingLeaderboardResponse,
  RepoDigestResult,
  RepoGraphResult,
  RepoDNAProfile,
  RunRequest,
  ScenarioDefinition,
  Session,
  SessionSummary,
  MarketSimulationReport,
  MarketSimulationRunRequest,
  MarketSimulationRunResponse,
  SimulationFeedbackReport,
  SimulationRunRequest,
  SimulationRunResponse,
  SourceObservation,
  SwipeQueueResponse,
  TournamentPreparation,
  ToolDefinition,
  ToolTypeDefinition,
  WorkspacePreset,
} from "./types";

export const API_BASE = process.env.NEXT_PUBLIC_API_BASE ?? "http://127.0.0.1:8800";

function formatValidationDetail(detail: unknown): string | null {
  if (!Array.isArray(detail) || detail.length === 0) return null;
  const lines = detail
    .map((item) => {
      if (!item || typeof item !== "object") return null;
      const message = "msg" in item && typeof item.msg === "string" ? item.msg : null;
      if (!message) return null;
      const location =
        "loc" in item && Array.isArray(item.loc)
          ? item.loc
              .map((part: unknown) => String(part))
              .filter((part: string) => part !== "body")
              .join(".")
          : "";
      return location ? `${location}: ${message}` : message;
    })
    .filter((line): line is string => Boolean(line));
  if (lines.length === 0) return null;
  return lines.join(" | ");
}

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...options?.headers,
    },
  });
  const text = await res.text();
  let payload: unknown = null;
  if (text) {
    try {
      payload = JSON.parse(text);
    } catch {
      payload = text;
    }
  }
  if (!res.ok) {
    if (
      payload &&
      typeof payload === "object" &&
      "detail" in payload &&
      typeof payload.detail === "object" &&
      payload.detail &&
      !Array.isArray(payload.detail)
    ) {
      const message =
        "message" in payload.detail && typeof payload.detail.message === "string"
          ? payload.detail.message
          : null;
      const errors =
        "errors" in payload.detail && Array.isArray(payload.detail.errors)
          ? payload.detail.errors
              .filter((item): item is string => typeof item === "string" && item.trim().length > 0)
              .join(" | ")
          : "";
      if (message && errors) {
        throw new Error(`${message}: ${errors}`);
      }
      if (message) {
        throw new Error(message);
      }
    }
    if (
      payload &&
      typeof payload === "object" &&
      "detail" in payload &&
      Array.isArray(payload.detail)
    ) {
      const validationError = formatValidationDetail(payload.detail);
      if (validationError) {
        throw new Error(validationError);
      }
    }
    if (
      payload &&
      typeof payload === "object" &&
      "detail" in payload &&
      typeof payload.detail === "string"
    ) {
      throw new Error(payload.detail);
    }
    if (typeof payload === "string" && payload.trim()) {
      throw new Error(payload);
    }
    throw new Error(`API error: ${res.status} ${res.statusText}`);
  }
  return payload as T;
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

export async function getDiscoveryIdeas(limit: number = 100): Promise<IdeaCandidate[]> {
  const payload = await request<{ ideas: IdeaCandidate[] }>(`/orchestrate/discovery/ideas?limit=${limit}`);
  return payload.ideas;
}

export async function createDiscoveryIdea(
  body: Partial<IdeaCandidate> & Pick<IdeaCandidate, "title">
): Promise<IdeaCandidate> {
  return request("/orchestrate/discovery/ideas", {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export async function getDiscoveryIdea(ideaId: string): Promise<IdeaCandidate> {
  return request(`/orchestrate/discovery/ideas/${ideaId}`);
}

export async function updateDiscoveryIdea(
  ideaId: string,
  body: Partial<IdeaCandidate>
): Promise<IdeaCandidate> {
  return request(`/orchestrate/discovery/ideas/${ideaId}`, {
    method: "PATCH",
    body: JSON.stringify(body),
  });
}

export async function getDiscoveryDossier(ideaId: string): Promise<IdeaDossier> {
  return request(`/orchestrate/discovery/ideas/${ideaId}/dossier`);
}

export async function getDiscoveryIdeaExplainability(ideaId: string): Promise<IdeaExplainabilitySnapshot> {
  return request(`/orchestrate/discovery/ideas/${ideaId}/explainability`);
}

export async function getDiscoverySimulation(ideaId: string): Promise<SimulationFeedbackReport> {
  return request(`/orchestrate/discovery/ideas/${ideaId}/simulation`);
}

export async function runDiscoverySimulation(
  ideaId: string,
  body: SimulationRunRequest
): Promise<SimulationRunResponse> {
  return request(`/orchestrate/discovery/ideas/${ideaId}/simulation`, {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export async function getDiscoveryMarketSimulation(ideaId: string): Promise<MarketSimulationReport> {
  return request(`/orchestrate/discovery/ideas/${ideaId}/simulation/lab`);
}

export async function runDiscoveryMarketSimulation(
  ideaId: string,
  body: MarketSimulationRunRequest
): Promise<MarketSimulationRunResponse> {
  return request(`/orchestrate/discovery/ideas/${ideaId}/simulation/lab`, {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export async function rebuildDiscoveryIdeaGraph(refresh: boolean = false): Promise<IdeaGraphSnapshot> {
  const suffix = refresh ? "?refresh=true" : "";
  return request(`/orchestrate/discovery/idea-graph/rebuild${suffix}`, {
    method: "POST",
  });
}

export async function getDiscoveryIdeaGraphSnapshots(limit: number = 20): Promise<IdeaGraphSnapshot[]> {
  const payload = await request<{ items: IdeaGraphSnapshot[] }>(`/orchestrate/discovery/idea-graph/snapshots?limit=${limit}`);
  return payload.items;
}

export async function getDiscoveryIdeaGraphSnapshot(graphId: string): Promise<IdeaGraphSnapshot> {
  return request(`/orchestrate/discovery/idea-graph/snapshots/${graphId}`);
}

export async function getDiscoveryIdeaGraph(ideaId: string): Promise<IdeaGraphContext> {
  return request(`/orchestrate/discovery/ideas/${ideaId}/idea-graph`);
}

export async function rebuildDiscoveryMemory(refresh: boolean = false): Promise<MemoryGraphSnapshot> {
  const suffix = refresh ? "?refresh=true" : "";
  return request(`/orchestrate/discovery/memory/rebuild${suffix}`, {
    method: "POST",
  });
}

export async function getDiscoveryMemorySnapshots(limit: number = 20): Promise<MemoryGraphSnapshot[]> {
  const payload = await request<{ items: MemoryGraphSnapshot[] }>(`/orchestrate/discovery/memory/snapshots?limit=${limit}`);
  return payload.items;
}

export async function getDiscoveryMemorySnapshot(snapshotId: string): Promise<MemoryGraphSnapshot> {
  return request(`/orchestrate/discovery/memory/snapshots/${snapshotId}`);
}

export async function getDiscoveryIdeaMemory(ideaId: string): Promise<InstitutionalMemoryContext> {
  return request(`/orchestrate/discovery/ideas/${ideaId}/memory`);
}

export async function queryDiscoveryMemory(body: MemoryQueryRequest): Promise<MemoryQueryResponse> {
  return request("/orchestrate/discovery/memory/query", {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export async function getDiscoveryDaemonStatus(): Promise<DiscoveryDaemonStatus> {
  return request("/orchestrate/discovery/daemon/status");
}

export async function controlDiscoveryDaemon(body: {
  action: "start" | "pause" | "resume" | "stop" | "tick" | "run_routine";
  routine_kind?: "hourly_refresh" | "daily_digest" | "overnight_queue";
}): Promise<DiscoveryDaemonStatus> {
  return request("/orchestrate/discovery/daemon/control", {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export async function getDiscoveryDaemonDigests(limit: number = 14): Promise<DiscoveryDailyDigest[]> {
  const payload = await request<{ items: DiscoveryDailyDigest[] }>(`/orchestrate/discovery/daemon/digests?limit=${limit}`);
  return payload.items;
}

export async function getDiscoveryDaemonRuns(limit: number = 20): Promise<DiscoveryDaemonRun[]> {
  const payload = await request<{ items: DiscoveryDaemonRun[] }>(`/orchestrate/discovery/daemon/runs?limit=${limit}`);
  return payload.items;
}

export async function getDiscoveryInboxFeed(
  limit: number = 50,
  status: "open" | "resolved" | "" = "open"
): Promise<DiscoveryInboxFeed> {
  const suffix = status ? `&status=${encodeURIComponent(status)}` : "";
  return request(`/orchestrate/discovery/inbox?limit=${limit}${suffix}`);
}

export async function getDiscoveryInbox(
  limit: number = 50,
  status: "open" | "resolved" | "" = "open"
): Promise<DiscoveryInboxItem[]> {
  const payload = await getDiscoveryInboxFeed(limit, status);
  return payload.items;
}

export async function getDiscoveryInboxItem(itemId: string): Promise<DiscoveryInboxItem> {
  return request(`/orchestrate/discovery/inbox/${itemId}`);
}

export async function actOnDiscoveryInboxItem(
  itemId: string,
  body: DiscoveryInboxActionRequest
): Promise<DiscoveryInboxItem> {
  return request(`/orchestrate/discovery/inbox/${itemId}/act`, {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export async function resolveDiscoveryInboxItem(
  itemId: string,
  status: "open" | "resolved" = "resolved"
): Promise<DiscoveryInboxItem> {
  return request(`/orchestrate/discovery/inbox/${itemId}/resolve`, {
    method: "POST",
    body: JSON.stringify({ status }),
  });
}

export async function getDiscoveryObservabilityEvals(limit: number = 100): Promise<DiscoveryEvaluationPack> {
  return request(`/orchestrate/observability/evals/discovery?limit=${limit}`);
}

export async function getDiscoveryObservabilityTraces(limit: number = 25): Promise<DiscoveryTraceSnapshot> {
  return request(`/orchestrate/observability/traces/discovery?limit=${limit}`);
}

export async function getDiscoveryIdeaTrace(ideaId: string): Promise<IdeaTraceBundle> {
  return request(`/orchestrate/observability/traces/discovery/${ideaId}`);
}

export async function getDiscoveryObservabilityScoreboard(): Promise<DiscoveryObservabilityScoreboard> {
  return request("/orchestrate/observability/scoreboards/discovery");
}

export async function getDebateReplay(sessionId: string): Promise<DebateReplaySession> {
  return request(`/orchestrate/observability/debate-replay/sessions/${sessionId}`);
}

export async function swipeDiscoveryIdea(
  ideaId: string,
  body: {
    action: "pass" | "maybe" | "yes" | "now";
    rationale?: string;
    actor?: string;
    revisit_after_hours?: number;
    metadata?: Record<string, unknown>;
  }
): Promise<IdeaSwipeResult> {
  return request(`/orchestrate/discovery/ideas/${ideaId}/swipe`, {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export async function getDiscoverySwipeQueue(limit: number = 20): Promise<SwipeQueueResponse> {
  return request(`/orchestrate/discovery/swipe-queue?limit=${limit}`);
}

export async function getDiscoveryMaybeQueue(limit: number = 20): Promise<MaybeQueueResponse> {
  return request(`/orchestrate/discovery/maybe-queue?limit=${limit}`);
}

export async function getDiscoveryPreferences(): Promise<FounderPreferenceProfile> {
  return request("/orchestrate/discovery/preferences");
}

export async function getDiscoveryIdeaChanges(ideaId: string): Promise<IdeaChangeRecord> {
  return request(`/orchestrate/discovery/ideas/${ideaId}/changes`);
}

export async function getRankingLeaderboard(limit: number = 50): Promise<RankingLeaderboardResponse> {
  return request(`/orchestrate/ranking/leaderboard?limit=${limit}`);
}

export async function getRankingNextPair(): Promise<NextPairResponse | null> {
  const payload = await request<{ pair?: NextPairResponse | null }>("/orchestrate/ranking/next-pair");
  return payload.pair ?? null;
}

export async function getRankingArchive(limitCells: number = 24): Promise<IdeaArchiveSnapshot> {
  return request(`/orchestrate/ranking/archive?limit_cells=${limitCells}`);
}

export async function compareRankingIdeas(body: {
  left_idea_id: string;
  right_idea_id: string;
  verdict: PairwiseVerdict;
  rationale?: string;
  judge_source?: RankingJudgeSource;
  judge_model?: string | null;
  judge_agent_id?: string | null;
  domain_key?: string | null;
  judge_confidence?: number;
  evidence_weight?: number;
  agent_importance_score?: number;
  metadata?: Record<string, unknown>;
}): Promise<PairwiseComparisonResponse> {
  return request("/orchestrate/ranking/compare", {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export async function resolveRankingFinals(body: {
  candidate_idea_ids?: string[];
  ballots: FinalVoteBallot[];
}): Promise<FinalVoteResult> {
  return request("/orchestrate/ranking/finals/resolve", {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export async function addDiscoveryObservation(
  ideaId: string,
  body: Omit<SourceObservation, "observation_id" | "idea_id" | "captured_at">
): Promise<SourceObservation> {
  return request(`/orchestrate/discovery/ideas/${ideaId}/observations`, {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export async function addDiscoveryValidationReport(
  ideaId: string,
  body: Omit<IdeaValidationReport, "report_id" | "idea_id" | "created_at" | "updated_at">
): Promise<IdeaValidationReport> {
  return request(`/orchestrate/discovery/ideas/${ideaId}/validation-reports`, {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export async function addDiscoveryDecision(
  ideaId: string,
  body: Omit<IdeaDecision, "decision_id" | "idea_id" | "created_at">
): Promise<IdeaDecision> {
  return request(`/orchestrate/discovery/ideas/${ideaId}/decisions`, {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export async function archiveDiscoveryIdea(
  ideaId: string,
  body: Pick<IdeaArchiveEntry, "reason" | "superseded_by_idea_id">
): Promise<IdeaArchiveEntry> {
  return request(`/orchestrate/discovery/ideas/${ideaId}/archive`, {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export async function addDiscoveryTimelineEvent(
  ideaId: string,
  body: Omit<DossierTimelineEvent, "event_id" | "created_at">
): Promise<DossierTimelineEvent> {
  return request(`/orchestrate/discovery/ideas/${ideaId}/timeline`, {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export async function upsertDiscoveryEvidenceBundle(
  ideaId: string,
  body: Pick<EvidenceBundleCandidate, "items" | "overall_confidence">
): Promise<EvidenceBundleCandidate> {
  return request(`/orchestrate/discovery/ideas/${ideaId}/evidence-bundle`, {
    method: "PUT",
    body: JSON.stringify(body),
  });
}

export async function upsertDiscoveryExecutionBriefCandidate(
  ideaId: string,
  body: Omit<ExecutionBriefCandidateRecord, "brief_id" | "idea_id" | "created_at" | "updated_at">
): Promise<ExecutionBriefCandidateRecord> {
  return request(`/orchestrate/discovery/ideas/${ideaId}/execution-brief-candidate`, {
    method: "PUT",
    body: JSON.stringify(body),
  });
}

export async function runResearchScan(body: {
  query: string;
  sources?: ResearchSource[];
  max_items_per_source?: number;
  freshness_window_hours?: number | null;
}): Promise<ResearchScanRun> {
  return request("/orchestrate/research/scan", {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export async function getResearchObservations(
  limit: number = 100,
  source?: ResearchSource,
  includeStale: boolean = false
): Promise<ResearchObservation[]> {
  const params = new URLSearchParams();
  params.set("limit", String(limit));
  if (source) params.set("source", source);
  if (includeStale) params.set("include_stale", "true");
  const payload = await request<{ items: ResearchObservation[] }>(`/orchestrate/research/observations?${params.toString()}`);
  return payload.items;
}

export async function searchResearchObservations(query: string, limit: number = 50): Promise<ResearchSearchResult> {
  const params = new URLSearchParams({ q: query, limit: String(limit) });
  return request(`/orchestrate/research/search?${params.toString()}`);
}

export async function getResearchDailyQueue(limit: number = 25): Promise<DailyQueueItem[]> {
  const payload = await request<{ items: DailyQueueItem[] }>(`/orchestrate/research/queue/daily?limit=${limit}`);
  return payload.items;
}

export async function getResearchRuns(limit: number = 50): Promise<ResearchScanRun[]> {
  const payload = await request<{ items: ResearchScanRun[] }>(`/orchestrate/research/runs?limit=${limit}`);
  return payload.items;
}

export async function exportResearchJsonl(limit: number = 200): Promise<string> {
  const res = await fetch(`${API_BASE}/orchestrate/research/exports/jsonl?limit=${limit}`);
  if (!res.ok) {
    throw new Error(`API error: ${res.status} ${res.statusText}`);
  }
  return res.text();
}

export async function exportResearchDailyQueueMarkdown(limit: number = 25): Promise<string> {
  const res = await fetch(`${API_BASE}/orchestrate/research/exports/daily-queue.md?limit=${limit}`);
  if (!res.ok) {
    throw new Error(`API error: ${res.status} ${res.statusText}`);
  }
  return res.text();
}

export async function analyzeRepoDigest(body: {
  source: string;
  branch?: string | null;
  include_patterns?: string[];
  exclude_patterns?: string[];
  issue_texts?: string[];
  issue_limit?: number;
  max_files?: number;
  hot_file_limit?: number;
  refresh?: boolean;
}): Promise<RepoDigestResult> {
  return request("/orchestrate/repo-digest/analyze", {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export async function getRepoDNAProfiles(limit: number = 50): Promise<RepoDNAProfile[]> {
  const payload = await request<{ items: RepoDNAProfile[] }>(`/orchestrate/repo-digest/profiles?limit=${limit}`);
  return payload.items;
}

export async function getRepoDNAProfile(profileId: string): Promise<RepoDNAProfile> {
  return request(`/orchestrate/repo-digest/profiles/${profileId}`);
}

export async function getRepoDigestResult(profileId: string): Promise<RepoDigestResult> {
  return request(`/orchestrate/repo-digest/results/${profileId}`);
}

export async function analyzeRepoGraph(body: {
  source: string;
  branch?: string | null;
  issue_texts?: string[];
  max_files?: number;
  refresh?: boolean;
  trigger?: "promoted" | "explicit" | "background";
}): Promise<RepoGraphResult> {
  return request("/orchestrate/repo-graph/analyze", {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export async function getRepoGraphResults(limit: number = 50): Promise<RepoGraphResult[]> {
  const payload = await request<{ items: RepoGraphResult[] }>(`/orchestrate/repo-graph/results?limit=${limit}`);
  return payload.items;
}

export async function getRepoGraphResult(graphId: string): Promise<RepoGraphResult> {
  return request(`/orchestrate/repo-graph/results/${graphId}`);
}

export async function getSession(id: string): Promise<Session> {
  return request(`/orchestrate/session/${id}`);
}

export async function deleteSession(id: string): Promise<{ status: string; deleted_session_ids: string[] }> {
  return request(`/orchestrate/session/${id}`, {
    method: "DELETE",
  });
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

export async function getConfiguredToolGuardrails(id: string): Promise<GuardrailScanReport> {
  return request(`/orchestrate/settings/tools/${id}/guardrails`);
}

export async function getGuardrailAudit(
  limit = 100,
  toolId?: string
): Promise<GuardrailAuditEvent[]> {
  const params = new URLSearchParams();
  params.set("limit", String(limit));
  if (toolId) {
    params.set("tool_id", toolId);
  }
  return request(`/orchestrate/guardrails/audit?${params.toString()}`);
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
