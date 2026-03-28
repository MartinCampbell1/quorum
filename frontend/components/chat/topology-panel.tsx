"use client";

import {
  AlertTriangle,
  ArrowRight,
  Folder,
  Globe,
  HardDrive,
  LoaderCircle,
  PauseCircle,
  Sparkles,
  TerminalSquare,
  type LucideIcon,
} from "lucide-react";

import { formatAgentDisplay, formatWorkspaceLabel } from "@/lib/constants";
import { useLocale } from "@/lib/locale";
import type { AttachedToolDetail, Message, Session, SessionEvent } from "@/lib/types";

import { useTopologyFlowGraph } from "./topology-layout";
import {
  latestRoundLabel,
  tournamentRoundLabel,
} from "./topology-model";
import { TopologyFlowStage } from "./topology-stage";

interface TopologyPanelProps {
  session: Session;
  onOpenSession?: (sessionId: string) => void;
}

const RUNTIME_WARNING_PREFIX_RE = /^(?:MCP issues detected\. Run \/mcp list for status\.\s*)+/i;

function sanitizeMessageContent(text?: string | null) {
  return String(text ?? "").replace(RUNTIME_WARNING_PREFIX_RE, "").trim();
}

function humanizeTool(tool: string) {
  return tool
    .replace(/_/g, " ")
    .replace(/\b\w/g, (char) => char.toUpperCase());
}

function formatSessionRole(session: Session, role: string) {
  const agent = session.agents.find((candidate) => candidate.role === role);
  return formatAgentDisplay(role, {
    mode: session.mode,
    scenarioId: session.active_scenario,
    projectLabel: formatWorkspaceLabel(agent?.workspace_paths),
  });
}

function displayActor(session: Session, actor?: string | null) {
  const normalized = String(actor ?? "").trim();
  if (!normalized || normalized === "system" || normalized === "user" || normalized === "agent") {
    return normalized || "agent";
  }
  return formatSessionRole(session, normalized);
}

function resolveToolIcon(tool: string, detail?: AttachedToolDetail): LucideIcon {
  if (detail?.icon === "🔍" || tool.includes("search")) return Globe;
  if (detail?.icon === "🧠" || tool.includes("perplexity")) return Sparkles;
  if (detail?.icon === "⚡" || detail?.icon === "🐍" || tool.includes("shell") || tool.includes("code")) return TerminalSquare;
  if (detail?.icon === "📊") return HardDrive;
  return Folder;
}

function latestMessage(messages: Message[], agentId: string, phasePrefix?: string) {
  return [...messages]
    .reverse()
    .find((message) => message.agent_id === agentId && (!phasePrefix || message.phase.startsWith(phasePrefix)));
}

function latestMessageText(messages: Message[], agentId: string, phasePrefix?: string) {
  return sanitizeMessageContent(latestMessage(messages, agentId, phasePrefix)?.content);
}

function latestEvent(
  events: SessionEvent[] = [],
  type: string,
  predicate?: (event: SessionEvent) => boolean
) {
  return [...events].reverse().find((event) => event.type === type && (!predicate || predicate(event)));
}

function recentEvents(events: SessionEvent[] = [], type: string, limit: number = 3) {
  return events.filter((event) => event.type === type).slice(-limit).reverse();
}

function latestStatusEvent(session: Session) {
  return [...(session.events ?? [])]
    .reverse()
    .find((event) => Boolean(event.status) || ["runtime_recovered", "run_failed", "run_started"].includes(event.type));
}

function sanitizeSummaryText(text?: string | null, limit: number = 320) {
  const normalized = (text ?? "").replace(/\r\n/g, "\n").trim();
  if (!normalized) {
    return "";
  }

  const withoutTrace = normalized.includes("Traceback")
    ? normalized.slice(0, normalized.indexOf("Traceback")).trim()
    : normalized;
  const flattened = withoutTrace
    .split("\n")
    .map((line) => line.trim())
    .filter(Boolean)
    .join(" ");

  if (flattened.length <= limit) {
    return flattened;
  }

  return `${flattened.slice(0, limit - 1)}…`;
}

function latestFailureEvent(session: Session) {
  return [...(session.events ?? [])]
    .reverse()
    .find((event) => event.type === "agent_failed" || event.type === "run_failed");
}

function summarizedResult(session: Session, fallback: string) {
  if (session.status === "failed" || session.status === "cancelled") {
    return (
      sanitizeSummaryText(latestFailureEvent(session)?.detail) ||
      sanitizeSummaryText(latestFailureEvent(session)?.title) ||
      sanitizeSummaryText(latestStatusEvent(session)?.detail) ||
      sanitizeSummaryText(session.result) ||
      fallback
    );
  }

  return sanitizeSummaryText(session.result) || fallback;
}

function resolveSessionStateSnapshot(session: Session, copy: ReturnType<typeof useLocale>["copy"]) {
  const latestStatus = latestStatusEvent(session);

  if (session.status === "completed") {
    return {
      tone: "completed" as const,
      title: copy.monitor.stateTitles.completed,
      detail: latestStatus?.detail || copy.monitor.stateDetails.completed,
    };
  }

  if (session.status === "failed") {
    return {
      tone: "failed" as const,
      title: latestStatus?.title || copy.monitor.stateTitles.failed,
      detail: latestStatus?.detail || copy.monitor.stateDetails.failed,
    };
  }

  if (session.status === "paused") {
    return {
      tone: "paused" as const,
      title: copy.monitor.stateTitles.paused,
      detail:
        latestStatus?.detail ||
        (session.current_checkpoint_id
          ? `${copy.monitor.stateDetails.paused} ${copy.monitor.signalLabels.checkpoint}: ${session.current_checkpoint_id}.`
          : copy.monitor.stateDetails.paused),
    };
  }

  if (session.status === "cancelled") {
    return {
      tone: "cancelled" as const,
      title: copy.monitor.stateTitles.cancelled,
      detail: latestStatus?.detail || copy.monitor.stateDetails.cancelled,
    };
  }

  if (session.status === "running" && session.messages.length === 0 && (session.events?.length ?? 0) <= 1) {
    return {
      tone: "waiting" as const,
      title: copy.monitor.stateTitles.waiting,
      detail: latestStatus?.detail || copy.monitor.stateDetails.waiting,
    };
  }

  return null;
}

function shellTitle(session: Session, copy: ReturnType<typeof useLocale>["copy"]) {
  if (session.mode === "board") return copy.monitor.topologyTitles.board;
  if (session.mode === "democracy") return copy.monitor.topologyTitles.democracy;
  if (session.mode === "debate" || session.mode === "tournament_match") return copy.monitor.topologyTitles.debate;
  if (session.mode === "creator_critic") return copy.monitor.topologyTitles.creator_critic;
  if (session.mode === "map_reduce") return copy.monitor.topologyTitles.map_reduce;
  if (session.mode === "dictator") return copy.monitor.topologyTitles.dictator;
  if (session.mode === "tournament") return copy.monitor.topologyTitles.tournament;
  return copy.monitor.topologyTitles.default;
}

function latestSignal(session: Session) {
  return [...(session.events ?? [])]
    .reverse()
    .find((event) =>
      [
        "tool_call_started",
        "tool_call_finished",
        "vote_recorded",
        "round_started",
        "round_completed",
        "chunk_completed",
      ].includes(event.type)
    );
}

function resolveActiveEdgeIds(session: Session, edgeIds: string[]): Set<string> {
  const signal = latestSignal(session);
  if (!signal) {
    return new Set();
  }

  if ((signal.type === "tool_call_started" || signal.type === "tool_call_finished") && signal.agent_id) {
    const direct = edgeIds.find((edgeId) => edgeId.endsWith(`->agent:${signal.agent_id}`) || edgeId.startsWith(`hub->agent:${signal.agent_id}`));
    if (direct) {
      return new Set([direct]);
    }
  }

  if (signal.type === "vote_recorded" && signal.agent_id) {
    return new Set([`agent:${signal.agent_id}->hub`]);
  }

  if (signal.type === "chunk_completed" && signal.agent_id) {
    return new Set([`agent:${signal.agent_id}->synth`]);
  }

  if (signal.type === "round_started" || signal.type === "round_completed") {
    if (session.mode === "board") {
      return new Set(session.agents.map((agent) => `hub->agent:${agent.role}`));
    }

    if (session.mode === "democracy") {
      return new Set(session.agents.map((agent) => `agent:${agent.role}->hub`));
    }

    if (session.mode === "debate" || session.mode === "tournament_match") {
      const proponent = session.agents[0]?.role ?? "proponent";
      const opponent = session.agents[1]?.role ?? "opponent";
      return new Set(["debate:judge", `agent:${proponent}->agent:${opponent}`]);
    }

    if (session.mode === "creator_critic") {
      const creator = session.agents[0]?.role;
      const critic = session.agents[1]?.role;
      return new Set(
        [
          creator ? `task->agent:${creator}` : null,
          creator ? `agent:${creator}->draft` : null,
          critic ? `draft->agent:${critic}` : null,
          critic ? `agent:${critic}->feedback` : null,
          creator ? `feedback->agent:${creator}` : null,
        ].filter((edgeId): edgeId is string => Boolean(edgeId))
      );
    }

    if (session.mode === "dictator") {
      return new Set(session.agents.slice(1).map((agent) => `agent:${session.agents[0]?.role}->agent:${agent.role}`));
    }

    if (session.mode === "map_reduce") {
      const planner = session.agents[0]?.role;
      const workers = session.agents.slice(1, -1).map((agent) => agent.role);
      return new Set(
        [
          planner ? `task->agent:${planner}` : null,
          ...workers.map((role) => (planner ? `agent:${planner}->agent:${role}` : null)),
          ...workers.map((role) => `agent:${role}->synth`),
        ].filter((edgeId): edgeId is string => Boolean(edgeId))
      );
    }

    if (session.mode === "tournament") {
      return new Set(
        edgeIds.filter((edgeId) => edgeId.includes("match:") || edgeId.includes("playin:") || edgeId.endsWith("->hub"))
      );
    }
  }

  return new Set();
}

function signalCards(session: Session, copy: ReturnType<typeof useLocale>["copy"]) {
  const latestToolEvent =
    latestEvent(session.events ?? [], "tool_call_finished") ??
    latestEvent(session.events ?? [], "tool_call_started");
  const terminal = ["completed", "failed", "cancelled"].includes(session.status);
  const activeNodeValue = terminal
    ? copy.monitor.terminalNode
    : session.active_node || copy.monitor.idle;
  const liveToolValue = terminal
    ? copy.monitor.executionFinished
    : latestToolEvent?.tool_name || latestToolEvent?.detail || copy.monitor.noToolActivity;

  return [
    {
      label: copy.monitor.signalLabels.activeNode,
      value: activeNodeValue,
    },
    {
      label: copy.monitor.signalLabels.checkpoint,
      value: session.current_checkpoint_id || copy.monitor.pending,
    },
    {
      label: copy.monitor.signalLabels.liveTool,
      value: liveToolValue,
    },
  ];
}

interface LiveExchangeItem {
  id: string;
  timestamp: number;
  channel: string;
  title: string;
  from: string;
  to: string;
  preview: string;
  raw: string;
  meta: string[];
}

interface TournamentRoundSnapshot {
  round: number;
  aArg?: string;
  bArg?: string;
  verdict?: string;
}

interface TournamentMatchSnapshot {
  key: string;
  tournamentRound: number;
  matchIndex: number;
  badge: string;
  contestantARole?: string;
  contestantBRole?: string;
  contestantA?: string;
  contestantB?: string;
  rounds: TournamentRoundSnapshot[];
  latestJudgeNote?: string;
  completionSummary?: string;
  latestTimestamp: number;
}

interface TournamentProgressSnapshot {
  matches: TournamentMatchSnapshot[];
  completedMatches: TournamentMatchSnapshot[];
  currentMatch: TournamentMatchSnapshot | null;
  focusMatch: TournamentMatchSnapshot | null;
  reachedLabel: string;
  focusStepLabel: string;
  focusDetail: string;
}

const TOURNAMENT_PHASE_RE = /^tournament_r(\d+)_m(\d+)_(?:round_(\d+)_(a|b|verdict)|match_\d+_complete|round_complete)$/;
const ADVANCE_SUMMARY_RE = /^Round\s+\d+,\s+match\s+\d+:\s+(.+?)\s+advances over\s+(.+?)\.\s*$/i;

function normalizeExchangeText(text: string) {
  return text.replace(/\r\n/g, "\n").trim();
}

function compactExchangeText(text: string, limit: number = 132) {
  const normalized = text.replace(/\s+/g, " ").trim();
  if (normalized.length <= limit) {
    return normalized;
  }

  return `${normalized.slice(0, limit - 1)}…`;
}

function formatExchangePayload(text: string) {
  const normalized = normalizeExchangeText(text);
  if (!normalized) {
    return "";
  }

  try {
    return JSON.stringify(JSON.parse(normalized), null, 2);
  } catch {
    return normalized;
  }
}

function nextPowerOfTwoAtLeast(value: number) {
  let power = 1;
  while (power < value) {
    power *= 2;
  }
  return power;
}

function tournamentStageLabel(totalEntrants: number, tournamentRound: number) {
  let participants = nextPowerOfTwoAtLeast(Math.max(totalEntrants, 2));
  for (let index = 1; index < tournamentRound; index += 1) {
    participants = Math.max(2, participants / 2);
  }
  return tournamentRoundLabel(participants);
}

function tournamentMatchBadge(
  copy: ReturnType<typeof useLocale>["copy"],
  totalEntrants: number,
  tournamentRound: number,
  matchIndex: number
) {
  return `${tournamentStageLabel(totalEntrants, tournamentRound)} · ${copy.monitor.matchLabel} ${matchIndex}`;
}

function ensureTournamentDebateRound(match: TournamentMatchSnapshot, roundNumber: number) {
  let round = match.rounds.find((candidate) => candidate.round === roundNumber);
  if (!round) {
    round = { round: roundNumber };
    match.rounds.push(round);
  }
  return round;
}

function describeTournamentMatchStep(
  match: TournamentMatchSnapshot | null,
  copy: ReturnType<typeof useLocale>["copy"],
  sessionStatus: Session["status"]
) {
  if (!match) {
    return copy.monitor.noMatchYet;
  }
  if (match.completionSummary) {
    return copy.statuses.completed;
  }
  const latestRound = match.rounds.at(-1);
  if (!latestRound?.aArg) {
    return copy.monitor.noMatchYet;
  }
  if (!latestRound.bArg) {
    return copy.monitor.awaitingSecondContestant;
  }
  if (!latestRound.verdict) {
    return sessionStatus === "failed" ? copy.monitor.judgeStep : copy.monitor.awaitingJudgeDecision;
  }
  return copy.monitor.advancingBracket;
}

function buildTournamentProgress(
  session: Session,
  copy: ReturnType<typeof useLocale>["copy"]
): TournamentProgressSnapshot {
  const totalEntrants = Math.max(session.agents.length - 1, 2);
  const matches = new Map<string, TournamentMatchSnapshot>();

  for (const message of [...session.messages].sort((left, right) => left.timestamp - right.timestamp)) {
    const phase = String(message.phase ?? "").trim();
    const parsed = TOURNAMENT_PHASE_RE.exec(phase);
    if (!parsed) {
      continue;
    }

    const tournamentRound = Number(parsed[1]);
    const matchIndex = Number(parsed[2]);
    const key = `${tournamentRound}:${matchIndex}`;
    const content = sanitizeMessageContent(message.content);
    let match = matches.get(key);
    if (!match) {
      match = {
        key,
        tournamentRound,
        matchIndex,
        badge: tournamentMatchBadge(copy, totalEntrants, tournamentRound, matchIndex),
        rounds: [],
        latestTimestamp: message.timestamp,
      };
      matches.set(key, match);
    }

    match.latestTimestamp = Math.max(match.latestTimestamp, message.timestamp);
    const debateRoundNumber = parsed[3] ? Number(parsed[3]) : 0;
    const phaseKind = parsed[4];

    if (debateRoundNumber > 0 && phaseKind) {
      const debateRound = ensureTournamentDebateRound(match, debateRoundNumber);
      if (phaseKind === "a") {
        debateRound.aArg = content;
        match.contestantARole = message.agent_id;
        match.contestantA = displayActor(session, message.agent_id);
      } else if (phaseKind === "b") {
        debateRound.bArg = content;
        match.contestantBRole = message.agent_id;
        match.contestantB = displayActor(session, message.agent_id);
      } else {
        debateRound.verdict = content;
        match.latestJudgeNote = content;
      }
      continue;
    }

    match.completionSummary = content;
  }

  const orderedMatches = [...matches.values()].sort((left, right) =>
    left.tournamentRound === right.tournamentRound
      ? left.matchIndex - right.matchIndex
      : left.tournamentRound - right.tournamentRound
  );
  const currentMatch = [...orderedMatches].reverse().find((match) => !match.completionSummary) ?? null;
  const focusMatch = currentMatch ?? orderedMatches.at(-1) ?? null;
  const failure = latestFailureEvent(session);
  const focusDetail =
    session.status === "failed" && currentMatch && failure
      ? sanitizeSummaryText(failure.detail, 560) || sanitizeSummaryText(failure.title, 560)
      : focusMatch?.latestJudgeNote || focusMatch?.completionSummary || "";

  return {
    matches: orderedMatches,
    completedMatches: orderedMatches.filter((match) => Boolean(match.completionSummary)),
    currentMatch,
    focusMatch,
    reachedLabel: focusMatch?.badge ?? copy.monitor.noMatchYet,
    focusStepLabel: describeTournamentMatchStep(focusMatch, copy, session.status),
    focusDetail,
  };
}

function parseAdvanceSummary(summary?: string | null) {
  const match = ADVANCE_SUMMARY_RE.exec(String(summary ?? "").trim());
  if (!match) {
    return null;
  }
  return {
    winner: match[1].trim(),
    loser: match[2].trim(),
  };
}

function buildLiveExchange(session: Session, copy: ReturnType<typeof useLocale>["copy"]): LiveExchangeItem[] {
  return (session.events ?? [])
    .filter((event) => ["tool_call_started", "tool_call_finished", "vote_recorded", "round_completed", "chunk_completed"].includes(event.type))
    .map((event) => {
      const raw = formatExchangePayload(event.detail || event.tool_name || event.title);
      return {
        id: `event-${event.id}`,
        timestamp: event.timestamp,
        channel:
          event.type === "tool_call_started"
            ? copy.monitor.toolCall
            : event.type === "tool_call_finished"
              ? copy.monitor.toolResult
              : event.title,
        title: event.tool_name ?? event.title,
        from: displayActor(session, event.agent_id) || copy.monitor.sharedContexts.default,
        to: event.tool_name ?? copy.monitor.sharedContexts.default,
        preview: compactExchangeText(raw || event.title),
        raw,
        meta: [
          event.phase,
          typeof event.round === "number" && event.round > 0 ? `R${event.round}` : null,
          typeof event.elapsed_sec === "number" ? `${event.elapsed_sec.toFixed(1)}s` : null,
          event.success === false ? copy.monitor.failed : null,
        ].filter((value): value is string => Boolean(value)),
      };
    })
    .sort((a, b) => b.timestamp - a.timestamp)
    .slice(0, 3);
}

function SessionStateBanner({ session }: { session: Session }) {
  const { copy } = useLocale();
  const snapshot = resolveSessionStateSnapshot(session, copy);

  if (!snapshot) {
    return null;
  }

  const Icon =
    snapshot.tone === "waiting"
      ? LoaderCircle
      : snapshot.tone === "paused"
        ? PauseCircle
        : snapshot.tone === "completed"
          ? Sparkles
          : AlertTriangle;
  const toneClasses =
    snapshot.tone === "completed"
      ? "border-emerald-200 bg-emerald-50/90 text-emerald-900 dark:border-emerald-900/70 dark:bg-emerald-950/30 dark:text-emerald-100"
      : snapshot.tone === "failed"
      ? "border-amber-200 bg-amber-50/90 text-amber-900 dark:border-amber-900/70 dark:bg-amber-950/30 dark:text-amber-100"
      : snapshot.tone === "paused"
        ? "border-sky-200 bg-sky-50/90 text-sky-900 dark:border-sky-900/70 dark:bg-sky-950/30 dark:text-sky-100"
        : snapshot.tone === "cancelled"
          ? "border-slate-200 bg-slate-100/90 text-slate-800 dark:border-slate-800 dark:bg-slate-900/80 dark:text-slate-200"
          : "border-violet-200 bg-violet-50/90 text-violet-900 dark:border-violet-900/70 dark:bg-violet-950/30 dark:text-violet-100";

  return (
    <div className={`rounded-[16px] border px-4 py-3 ${toneClasses}`}>
      <div className="flex items-start gap-3">
        <div className="mt-0.5 rounded-full border border-current/15 bg-white/60 p-2 text-current dark:bg-slate-950/20">
          <Icon className={`h-4 w-4 ${snapshot.tone === "waiting" ? "animate-spin" : ""}`} />
        </div>
        <div className="min-w-0">
          <div className="text-[10px] font-semibold uppercase tracking-[0.18em] text-current/80">
            {copy.statuses[session.status]}
          </div>
          <div className="mt-1 text-[15px] font-semibold tracking-[-0.03em] text-current">
            {snapshot.title}
          </div>
          <div className="mt-1 text-[13px] leading-6 text-current/80">
            {snapshot.detail}
          </div>
        </div>
      </div>
    </div>
  );
}

function ConnectionCanvas({ session }: { session: Session }) {
  const { copy } = useLocale();
  const flowGraph = useTopologyFlowGraph(session, copy);
  const flowViewKey = `${session.id}:${session.mode}:${flowGraph.nodes
    .map((node) => `${node.id}:${node.position.x}:${node.position.y}:${node.data.kind}:${node.data.dimensions.width}:${node.data.dimensions.height}`)
    .join("|")}`;
  const activeEdgeIds = resolveActiveEdgeIds(session, flowGraph.edges.map((edge) => edge.id));
  const activeSignal = latestSignal(session);
  const activeAgentId = activeSignal?.agent_id;
  const cards = signalCards(session, copy);
  const exchanges = buildLiveExchange(session, copy);

  return (
    <div className="overflow-hidden rounded-[20px] border border-[#d6dbe6] bg-white dark:border-slate-800 dark:bg-slate-950/70">
      <div className="absolute inset-x-0 top-0 h-[96px] bg-[radial-gradient(circle_at_top,rgba(226,231,247,0.58),rgba(255,255,255,0))]" />
      <TopologyFlowStage
        graph={flowGraph}
        viewKey={flowViewKey}
        activeAgentId={activeAgentId}
        activeEdgeIds={activeEdgeIds}
      />

      <div className="border-t border-[#e6e8ee] bg-white p-4 dark:border-slate-800 dark:bg-slate-950/70">
        <div className="rounded-[18px] border border-[#d6dbe6] bg-[#fafbff] p-4 dark:border-slate-800 dark:bg-slate-900/80">
          <div className="text-[11px] uppercase tracking-[0.16em] text-[#7b8190] dark:text-slate-500">{copy.monitor.liveExchange}</div>
          {exchanges.length > 0 ? (
            <div className="mt-3 space-y-3">
              {exchanges.map((exchange) => (
                <div key={exchange.id} className="rounded-[14px] border border-[#d6dbe6] bg-white px-3 py-3 dark:border-slate-800 dark:bg-slate-950/70">
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <div className="flex min-w-0 flex-wrap items-center gap-2">
                      <span className="rounded-full border border-[#d6dbe6] bg-[#fafbff] px-2.5 py-1 text-[10px] uppercase tracking-[0.14em] text-[#6b7280] dark:border-slate-700 dark:bg-slate-900 dark:text-slate-400">
                        {exchange.channel}
                      </span>
                      <span className="text-[12px] font-medium tracking-[-0.02em] text-[#111111] dark:text-slate-100">{exchange.title}</span>
                    </div>
                    <div className="text-[10px] text-[#9aa3b2] dark:text-slate-500">
                      {new Date(exchange.timestamp * 1000).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" })}
                    </div>
                  </div>
                  <div className="mt-2 text-[13px] font-medium tracking-[-0.02em] text-[#111111] dark:text-slate-100">
                    {exchange.from} <span className="text-[#9aa3b2]">→</span> {exchange.to}
                  </div>
                  {exchange.meta.length > 0 ? (
                    <div className="mt-2 flex flex-wrap gap-2">
                      {exchange.meta.map((meta) => (
                        <span
                          key={`${exchange.id}-${meta}`}
                          className="rounded-full border border-[#e5e7eb] bg-[#fbfcff] px-2.5 py-1 text-[10px] uppercase tracking-[0.12em] text-[#7b8190] dark:border-slate-800 dark:bg-slate-900 dark:text-slate-400"
                        >
                          {meta}
                        </span>
                      ))}
                    </div>
                  ) : null}
                  <div className="mt-2 text-[12px] leading-5 text-[#475569] dark:text-slate-400">{exchange.preview}</div>
                  <pre className="mt-2 max-h-[132px] overflow-auto whitespace-pre-wrap break-words rounded-[12px] border border-[#e5e7eb] bg-[#fbfcff] px-3 py-2 font-mono text-[11px] leading-5 text-[#344054] dark:border-slate-800 dark:bg-slate-950 dark:text-slate-300">
                    {exchange.raw || exchange.preview}
                  </pre>
                </div>
              ))}
            </div>
          ) : (
            <div className="mt-3 rounded-[14px] border border-[#d6dbe6] bg-white px-3 py-4 text-[13px] text-[#6b7280] dark:border-slate-800 dark:bg-slate-950/60 dark:text-slate-400">
              {copy.monitor.noExchangeYet}
            </div>
          )}
        </div>

        <div className="mt-4 flex flex-wrap gap-2">
          {cards.map((card) => (
            <div key={card.label} className="rounded-full border border-[#d6dbe6] bg-[#fafbff] px-3 py-1.5 dark:border-slate-800 dark:bg-slate-900/80">
              <span className="text-[10px] uppercase tracking-[0.14em] text-[#7b8190] dark:text-slate-500">{card.label}</span>
              <span className="ml-2 text-[12px] font-medium tracking-[-0.02em] text-[#111111] dark:text-slate-100">{card.value}</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

function AgentPill({
  label,
  subtitle,
  accent,
}: {
  label: string;
  subtitle: string;
  accent?: string;
}) {
  return (
    <div className="rounded-[16px] border border-[#d6dbe6] bg-white px-4 py-3 dark:border-slate-800 dark:bg-slate-950/70">
      <div className="flex items-center justify-between gap-3">
        <div className="text-[16px] font-medium tracking-[-0.03em] text-[#111111] dark:text-slate-100">{label}</div>
        {accent ? (
          <div className="rounded-full border border-[#d6dbe6] bg-[#fafbff] px-2.5 py-1 text-[10px] uppercase tracking-[0.14em] text-[#6b7280] dark:border-slate-700 dark:bg-slate-900 dark:text-slate-400">
            {accent}
          </div>
        ) : null}
      </div>
      <div className="mt-1 text-[13px] leading-5 text-[#6b7280] dark:text-slate-400">{subtitle}</div>
    </div>
  );
}

function GenericView({ session }: { session: Session }) {
  const { copy } = useLocale();
  const orchestrator = session.agents[0] ?? null;
  const workers = session.agents.slice(1, 3);
  const upperWorker = workers[0] ?? null;
  const lowerWorker = workers[1] ?? null;
  const upperTools = (upperWorker?.tools ?? []).slice(0, 2);
  const lowerTools = (lowerWorker?.tools ?? []).slice(0, 1);
  const attachedDetails = new Map((session.attached_tools ?? []).map((tool) => [tool.id, tool]));

  return (
    <div className="relative min-h-[360px] rounded-[18px] border border-[#d6dbe6] bg-white dark:border-slate-800 dark:bg-slate-950/70">
      <svg className="absolute inset-0 h-full w-full" viewBox="0 0 940 360" preserveAspectRatio="none">
        <path d="M110 180 C 180 180, 210 180, 270 180" fill="none" stroke="#9ca3af" strokeWidth="2.2" />
        <path d="M328 180 C 430 180, 470 80, 620 80" fill="none" stroke="#9ca3af" strokeWidth="2.2" />
        <path d="M328 180 C 430 180, 470 260, 620 260" fill="none" stroke="#9ca3af" strokeWidth="2.2" />
        <path d="M698 88 C 740 88, 760 48, 810 48" fill="none" stroke="#9ca3af" strokeWidth="2.2" />
        <path d="M698 108 C 740 108, 760 148, 810 148" fill="none" stroke="#9ca3af" strokeWidth="2.2" />
        <path d="M698 268 C 740 268, 760 268, 810 268" fill="none" stroke="#9ca3af" strokeWidth="2.2" />
      </svg>

      <div className="absolute left-[46px] top-[150px] flex flex-col items-center">
        <div className="flex h-[74px] w-[74px] items-center justify-center rounded-[14px] border border-[#d1d5db] bg-white">
          <Folder className="h-9 w-9 text-[#9ca3af]" />
        </div>
        <div className="mt-3 text-center text-[20px] leading-tight text-[#111111]">
          {copy.monitor.taskInput}
        </div>
      </div>

      {orchestrator ? (
        <div className="absolute left-[184px] top-[150px] flex flex-col items-center">
          <div className="flex h-[74px] w-[74px] items-center justify-center rounded-[14px] border border-[#d1d5db] bg-white text-[44px] font-semibold text-[#6b7280]">
            {orchestrator.provider[0]?.toUpperCase() ?? "A"}
          </div>
          <div className="mt-3 text-center text-[20px] leading-tight text-[#111111]">
            {orchestrator.provider}
            <br />
            ({formatSessionRole(session, orchestrator.role)})
          </div>
        </div>
      ) : null}

      {upperWorker ? (
        <div className="absolute left-[590px] top-[28px] flex flex-col items-center">
          <div className="flex h-[74px] w-[74px] items-center justify-center rounded-[14px] border border-[#d1d5db] bg-white text-[44px] font-semibold text-[#6b7280]">
            {upperWorker.provider[0]?.toUpperCase() ?? "A"}
          </div>
          <div className="mt-3 text-center text-[20px] leading-tight text-[#111111]">
            {upperWorker.provider}
            <br />
            ({formatSessionRole(session, upperWorker.role)})
          </div>
        </div>
      ) : null}

      {lowerWorker ? (
        <div className="absolute left-[590px] top-[232px] flex flex-col items-center">
          <div className="flex h-[74px] w-[74px] items-center justify-center rounded-[14px] border border-[#d1d5db] bg-white text-[44px] font-semibold text-[#6b7280]">
            {lowerWorker.provider[0]?.toUpperCase() ?? "A"}
          </div>
          <div className="mt-3 text-center text-[20px] leading-tight text-[#111111]">
            {lowerWorker.provider}
            <br />
            ({formatSessionRole(session, lowerWorker.role)})
          </div>
        </div>
      ) : null}

      {upperTools.map((tool, index) => {
        const detail = attachedDetails.get(tool);
        const Icon = resolveToolIcon(tool, detail);
        return (
          <div
            key={`upper-${tool}-${index}`}
            className="absolute flex flex-col items-center"
            style={{ left: "804px", top: `${index === 0 ? 16 : 132}px` }}
          >
            <div className="flex h-[68px] w-[68px] items-center justify-center rounded-[14px] border border-[#d1d5db] bg-white">
              <Icon className="h-8 w-8 text-[#7b8190]" />
            </div>
            <div className="mt-2 text-center text-[18px] leading-tight text-[#111111]">
              {detail?.name ?? humanizeTool(tool)}
            </div>
          </div>
        );
      })}

      {lowerTools.map((tool, index) => {
        const detail = attachedDetails.get(tool);
        const Icon = resolveToolIcon(tool, detail);
        return (
          <div
            key={`lower-${tool}-${index}`}
            className="absolute flex flex-col items-center"
            style={{ left: "804px", top: `${index === 0 ? 236 : 152}px` }}
          >
            <div className="flex h-[68px] w-[68px] items-center justify-center rounded-[14px] border border-[#d1d5db] bg-white">
              <Icon className="h-8 w-8 text-[#7b8190]" />
            </div>
            <div className="mt-2 text-center text-[18px] leading-tight text-[#111111]">
              {detail?.name ?? humanizeTool(tool)}
            </div>
          </div>
        );
      })}
    </div>
  );
}

function BoardView({ session }: { session: Session }) {
  const { copy } = useLocale();
  const directors = session.agents.slice(0, 3);
  const events = session.events ?? [];
  const roundLabel = latestRoundLabel(events);
  const latestDecision = latestEvent(events, "round_completed");

  return (
    <div className="grid gap-4 rounded-[18px] border border-[#d6dbe6] bg-white p-5 dark:border-slate-800 dark:bg-slate-950/70 lg:grid-cols-[repeat(3,minmax(0,1fr))]">
      {directors.map((director) => (
        <AgentPill
          key={director.role}
          label={formatSessionRole(session, director.role)}
          subtitle={
            latestEvent(events, "vote_recorded", (event) => event.agent_id === director.role)?.detail ||
            latestMessageText(session.messages, director.role).slice(0, 160) ||
            copy.monitor.waitingBoardPosition
          }
          accent={roundLabel ?? undefined}
        />
      ))}
      <div className="rounded-[16px] border border-[#d6dbe6] bg-[#fafbff] px-4 py-4 lg:col-span-3 dark:border-slate-800 dark:bg-slate-900/80">
        <div className="text-[11px] uppercase tracking-[0.16em] text-[#7b8190] dark:text-slate-500">{copy.monitor.consensusState}</div>
        <div className="mt-2 text-[16px] leading-7 text-[#111111] dark:text-slate-100">
          {sanitizeSummaryText(latestDecision?.detail) || summarizedResult(session, copy.monitor.waitingBoardPosition)}
        </div>
      </div>
    </div>
  );
}

function DemocracyView({ session }: { session: Session }) {
  const { copy } = useLocale();
  const events = session.events ?? [];
  const roundLabel = latestRoundLabel(events);
  const latestMajority = latestEvent(events, "round_completed");

  return (
    <div className="grid gap-4 rounded-[18px] border border-[#d6dbe6] bg-white p-5 dark:border-slate-800 dark:bg-slate-950/70 lg:grid-cols-[repeat(3,minmax(0,1fr))]">
      {session.agents.map((agent) => (
        <AgentPill
          key={agent.role}
          label={formatSessionRole(session, agent.role)}
          subtitle={
            latestEvent(events, "vote_recorded", (event) => event.agent_id === agent.role)?.detail ||
            latestMessageText(session.messages, agent.role).replace(/^Vote:\s*/i, "").slice(0, 140) ||
            copy.monitor.waitingVote
          }
          accent={roundLabel ?? undefined}
        />
      ))}
      <div className="rounded-[16px] border border-[#d6dbe6] bg-[#fafbff] px-4 py-4 lg:col-span-3 dark:border-slate-800 dark:bg-slate-900/80">
        <div className="text-[11px] uppercase tracking-[0.16em] text-[#7b8190] dark:text-slate-500">{copy.monitor.majorityState}</div>
        <div className="mt-2 text-[16px] leading-7 text-[#111111] dark:text-slate-100">
          {sanitizeSummaryText(latestMajority?.detail) || summarizedResult(session, copy.monitor.noMajorityYet)}
        </div>
      </div>
    </div>
  );
}

function DebateView({ session }: { session: Session }) {
  const { copy } = useLocale();
  const [proponent, opponent, judge] = session.agents;
  const events = session.events ?? [];
  const roundLabel = latestRoundLabel(events);
  const latestVerdict = latestEvent(events, "round_completed");

  return (
    <div className="grid gap-4 rounded-[18px] border border-[#d6dbe6] bg-white p-5 dark:border-slate-800 dark:bg-slate-950/70 lg:grid-cols-[minmax(0,1fr)_48px_minmax(0,1fr)]">
      <AgentPill
        label={formatSessionRole(session, proponent?.role ?? "proponent")}
        subtitle={proponent ? latestMessageText(session.messages, proponent.role).slice(0, 180) || copy.monitor.awaitingArgument : "—"}
        accent={roundLabel ?? undefined}
      />
      <div className="flex items-center justify-center text-[#9ca3af]">
        <ArrowRight className="h-6 w-6" />
      </div>
      <AgentPill
        label={formatSessionRole(session, opponent?.role ?? "opponent")}
        subtitle={opponent ? latestMessageText(session.messages, opponent.role).slice(0, 180) || copy.monitor.awaitingRebuttal : "—"}
        accent={roundLabel ?? undefined}
      />
      <div className="rounded-[16px] border border-[#d6dbe6] bg-[#fafbff] px-4 py-4 lg:col-span-3 dark:border-slate-800 dark:bg-slate-900/80">
        <div className="text-[11px] uppercase tracking-[0.16em] text-[#7b8190] dark:text-slate-500">{copy.monitor.judgeVerdict}</div>
        <div className="mt-2 text-[16px] leading-7 text-[#111111] dark:text-slate-100">
          {sanitizeSummaryText(latestVerdict?.detail) ||
            (judge
              ? sanitizeSummaryText(latestMessageText(session.messages, judge.role)) ||
                summarizedResult(session, copy.monitor.noVerdictYet)
              : summarizedResult(session, copy.monitor.noVerdictYet))}
        </div>
      </div>
    </div>
  );
}

function CreatorCriticView({ session }: { session: Session }) {
  const { copy } = useLocale();
  const iterations = session.messages.filter((message) => message.phase.startsWith("version_") || message.phase.startsWith("critique_"));

  return (
    <div className="rounded-[18px] border border-[#d6dbe6] bg-white p-5 dark:border-slate-800 dark:bg-slate-950/70">
      <div className="space-y-3">
        {iterations.map((message) => (
          <div key={`${message.agent_id}-${message.timestamp}`} className="rounded-[16px] border border-[#d6dbe6] bg-[#fafbff] px-4 py-3 dark:border-slate-800 dark:bg-slate-900/80">
            <div className="text-[11px] uppercase tracking-[0.16em] text-[#7b8190] dark:text-slate-500">
              {displayActor(session, message.agent_id)} · {message.phase.replace(/_/g, " ")}
            </div>
            <div className="mt-2 text-[14px] leading-6 text-[#111111] dark:text-slate-100">{sanitizeMessageContent(message.content)}</div>
          </div>
        ))}
        {iterations.length === 0 ? (
          <div className="rounded-[16px] border border-[#d6dbe6] bg-[#fafbff] px-4 py-4 text-[14px] text-[#6b7280] dark:border-slate-800 dark:bg-slate-900/80 dark:text-slate-400">
            {copy.monitor.iterationsHint}
          </div>
        ) : null}
      </div>
    </div>
  );
}

function MapReduceView({ session }: { session: Session }) {
  const { copy } = useLocale();
  const planner = session.agents[0];
  const workers = session.agents.slice(1, -1);
  const synthesizer = session.agents[session.agents.length - 1];
  const chunkEvents = recentEvents(session.events ?? [], "chunk_completed", 4);

  return (
    <div className="grid gap-4 rounded-[18px] border border-[#d6dbe6] bg-white p-5 dark:border-slate-800 dark:bg-slate-950/70 lg:grid-cols-[minmax(0,1fr)_minmax(0,1.4fr)_minmax(0,1fr)]">
      <AgentPill
        label={formatSessionRole(session, planner?.role ?? "planner")}
        subtitle={planner ? latestMessageText(session.messages, planner.role) || copy.monitor.plannerPreparing : "—"}
      />
      <div className="space-y-3 rounded-[16px] border border-[#d6dbe6] bg-[#fafbff] px-4 py-4 dark:border-slate-800 dark:bg-slate-900/80">
        <div className="text-[11px] uppercase tracking-[0.16em] text-[#7b8190] dark:text-slate-500">{copy.monitor.workers}</div>
        {workers.map((worker) => (
          <div key={worker.role} className="rounded-[14px] border border-[#d6dbe6] bg-white px-3 py-3 dark:border-slate-800 dark:bg-slate-950/70">
            <div className="text-[14px] font-medium text-[#111111] dark:text-slate-100">{formatSessionRole(session, worker.role)}</div>
            <div className="mt-1 text-[12px] leading-5 text-[#6b7280] dark:text-slate-400">
              {latestEvent(session.events ?? [], "chunk_completed", (event) => event.agent_id === worker.role)?.detail ||
                latestMessageText(session.messages, worker.role).slice(0, 120) ||
                copy.monitor.waitingChunkOutput}
            </div>
          </div>
        ))}
        {chunkEvents.length > 0 ? (
          <div className="space-y-2 rounded-[14px] border border-dashed border-[#d6dbe6] bg-white px-3 py-3 dark:border-slate-700 dark:bg-slate-950/70">
            <div className="text-[11px] uppercase tracking-[0.16em] text-[#7b8190] dark:text-slate-500">{copy.monitor.recentChunks}</div>
            {chunkEvents.map((event) => (
              <div key={event.id} className="text-[12px] leading-5 text-[#6b7280] dark:text-slate-400">
                <span className="font-medium text-[#111111] dark:text-slate-100">{displayActor(session, event.agent_id || "worker")}</span>
                {" · "}
                {event.detail}
              </div>
            ))}
          </div>
        ) : null}
      </div>
      <AgentPill
        label={formatSessionRole(session, synthesizer?.role ?? "synthesizer")}
        subtitle={
          synthesizer
            ? sanitizeSummaryText(latestMessageText(session.messages, synthesizer.role)) ||
              summarizedResult(session, copy.monitor.synthesisPending)
            : "—"
        }
      />
    </div>
  );
}

function DictatorView({ session }: { session: Session }) {
  const { copy } = useLocale();
  const dictator = session.agents[0];
  const workers = session.agents.slice(1, 4);
  const events = session.events ?? [];
  const latestDirective = latestEvent(events, "round_started");

  return (
    <div className="grid gap-4 rounded-[18px] border border-[#d6dbe6] bg-white p-5 dark:border-slate-800 dark:bg-slate-950/70 lg:grid-cols-[minmax(0,1fr)_minmax(0,1.6fr)]">
      <div className="rounded-[16px] border border-[#d6dbe6] bg-[#fafbff] px-4 py-4 dark:border-slate-800 dark:bg-slate-900/80">
        <div className="text-[11px] uppercase tracking-[0.16em] text-[#7b8190] dark:text-slate-500">{copy.monitor.dictatorInstruction}</div>
        <div className="mt-2 text-[16px] font-medium tracking-[-0.03em] text-[#111111] dark:text-slate-100">
          {formatSessionRole(session, dictator?.role ?? "dictator")}
        </div>
        <div className="mt-2 text-[14px] leading-6 text-[#6b7280] dark:text-slate-400">
          {latestDirective?.detail || latestMessageText(session.messages, dictator?.role ?? "").slice(0, 240) || copy.monitor.idle}
        </div>
      </div>
      <div className="space-y-3">
        {workers.map((worker) => (
          <AgentPill
            key={worker.role}
            label={formatSessionRole(session, worker.role)}
            subtitle={latestMessageText(session.messages, worker.role).slice(0, 160) || copy.monitor.waitingWorkerResult}
          />
        ))}
        <div className="rounded-[16px] border border-[#d6dbe6] bg-[#fafbff] px-4 py-4 dark:border-slate-800 dark:bg-slate-900/80">
          <div className="text-[11px] uppercase tracking-[0.16em] text-[#7b8190] dark:text-slate-500">{copy.monitor.dictatorDecision}</div>
          <div className="mt-2 text-[16px] leading-7 text-[#111111] dark:text-slate-100">
            {sanitizeSummaryText(latestEvent(events, "round_completed")?.detail) || summarizedResult(session, copy.monitor.idle)}
          </div>
        </div>
      </div>
    </div>
  );
}

function TournamentSequentialView({ session }: { session: Session }) {
  const { copy } = useLocale();
  const progress = buildTournamentProgress(session, copy);
  const focusTitle =
    session.status === "failed" && progress.currentMatch
      ? copy.monitor.failedAt
      : progress.currentMatch
        ? copy.monitor.currentMatch
        : copy.monitor.matchResult;

  return (
    <div className="grid gap-4 rounded-[18px] border border-[#d6dbe6] bg-white p-5 dark:border-slate-800 dark:bg-slate-950/70">
      <div className="grid gap-3 lg:grid-cols-3">
        <div className="rounded-[16px] border border-[#d6dbe6] bg-[#fafbff] px-4 py-4 dark:border-slate-800 dark:bg-slate-900/80">
          <div className="text-[11px] uppercase tracking-[0.16em] text-[#7b8190] dark:text-slate-500">{copy.monitor.reachedMatch}</div>
          <div className="mt-2 text-[18px] font-medium tracking-[-0.03em] text-[#111111] dark:text-slate-100">
            {progress.reachedLabel}
          </div>
        </div>
        <div className="rounded-[16px] border border-[#d6dbe6] bg-[#fafbff] px-4 py-4 dark:border-slate-800 dark:bg-slate-900/80">
          <div className="text-[11px] uppercase tracking-[0.16em] text-[#7b8190] dark:text-slate-500">{copy.monitor.completedMatches}</div>
          <div className="mt-2 text-[18px] font-medium tracking-[-0.03em] text-[#111111] dark:text-slate-100">
            {progress.completedMatches.length}
          </div>
        </div>
        <div className="rounded-[16px] border border-[#d6dbe6] bg-[#fafbff] px-4 py-4 dark:border-slate-800 dark:bg-slate-900/80">
          <div className="text-[11px] uppercase tracking-[0.16em] text-[#7b8190] dark:text-slate-500">
            {session.status === "failed" && progress.currentMatch ? copy.monitor.failedAt : copy.monitor.currentStep}
          </div>
          <div className="mt-2 text-[18px] font-medium tracking-[-0.03em] text-[#111111] dark:text-slate-100">
            {progress.focusStepLabel}
          </div>
        </div>
      </div>

      <div className="rounded-[16px] border border-[#d6dbe6] bg-[#fafbff] px-4 py-4 dark:border-slate-800 dark:bg-slate-900/80">
        <div className="flex flex-wrap items-center gap-2">
          <div className="text-[11px] uppercase tracking-[0.16em] text-[#7b8190] dark:text-slate-500">{focusTitle}</div>
          {progress.focusMatch ? (
            <span className="rounded-full border border-[#d6dbe6] bg-white px-2.5 py-1 text-[10px] uppercase tracking-[0.14em] text-[#6b7280] dark:border-slate-700 dark:bg-slate-950 dark:text-slate-400">
              {progress.focusMatch.badge}
            </span>
          ) : null}
        </div>
        {progress.focusMatch ? (
          <div className="mt-3 grid gap-3 lg:grid-cols-[minmax(0,1fr)_48px_minmax(0,1fr)] lg:items-center">
            <AgentPill
              label={progress.focusMatch.contestantA || copy.monitor.noMatchYet}
              subtitle={
                progress.focusMatch.rounds.at(-1)?.aArg?.slice(0, 180) ||
                copy.monitor.noMatchYet
              }
              accent={progress.focusMatch.badge}
            />
            <div className="flex items-center justify-center text-[18px] font-bold tracking-[-0.04em] text-[#9aa3b2] dark:text-slate-500">
              {copy.monitor.vsLabel}
            </div>
            <AgentPill
              label={progress.focusMatch.contestantB || copy.monitor.awaitingSecondContestant}
              subtitle={
                progress.focusMatch.rounds.at(-1)?.bArg?.slice(0, 180) ||
                copy.monitor.awaitingSecondContestant
              }
              accent={progress.focusStepLabel}
            />
          </div>
        ) : null}
        <div className="mt-3 text-[15px] leading-7 text-[#111111] dark:text-slate-100">
          {progress.focusDetail || copy.monitor.noMatchYet}
        </div>
      </div>

      <div className="rounded-[16px] border border-[#d6dbe6] bg-[#fafbff] px-4 py-4 dark:border-slate-800 dark:bg-slate-900/80">
        <div className="text-[11px] uppercase tracking-[0.16em] text-[#7b8190] dark:text-slate-500">{copy.monitor.completedMatchesList}</div>
        {progress.completedMatches.length > 0 ? (
          <div className="mt-3 space-y-3">
            {progress.completedMatches.map((match) => {
              const summary = parseAdvanceSummary(match.completionSummary);
              return (
                <div
                  key={match.key}
                  className="rounded-[14px] border border-[#d6dbe6] bg-white px-4 py-3 dark:border-slate-800 dark:bg-slate-950/70"
                >
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <span className="rounded-full border border-[#d6dbe6] bg-[#fafbff] px-2.5 py-1 text-[10px] uppercase tracking-[0.14em] text-[#6b7280] dark:border-slate-700 dark:bg-slate-900 dark:text-slate-400">
                      {match.badge}
                    </span>
                    {summary ? (
                      <span className="text-[13px] font-medium tracking-[-0.02em] text-[#111111] dark:text-slate-100">
                        {summary.winner}
                      </span>
                    ) : null}
                  </div>
                  <div className="mt-2 text-[13px] leading-6 text-[#475569] dark:text-slate-400">
                    {match.completionSummary}
                  </div>
                </div>
              );
            })}
          </div>
        ) : (
          <div className="mt-3 rounded-[14px] border border-[#d6dbe6] bg-white px-3 py-4 text-[13px] text-[#6b7280] dark:border-slate-800 dark:bg-slate-950/60 dark:text-slate-400">
            {copy.monitor.noCompletedMatches}
          </div>
        )}
      </div>
      {session.status === "completed" ? (
        <div className="rounded-[16px] border border-[#d6dbe6] bg-[#fafbff] px-4 py-4 dark:border-slate-800 dark:bg-slate-900/80">
          <div className="text-[11px] uppercase tracking-[0.16em] text-[#7b8190] dark:text-slate-500">{copy.monitor.matchResult}</div>
          <div className="mt-2 text-[16px] leading-7 text-[#111111] dark:text-slate-100">
            {summarizedResult(session, copy.monitor.noMatchYet)}
          </div>
        </div>
      ) : null}
    </div>
  );
}

function TournamentParallelView({
  session,
  onOpenSession,
}: {
  session: Session;
  onOpenSession?: (sessionId: string) => void;
}) {
  const { copy } = useLocale();
  const progress = session.parallel_progress ?? {};
  const children = session.parallel_children ?? [];
  const stageLabel = progress.stage_label || copy.monitor.noMatchYet;

  return (
    <div className="grid gap-4 rounded-[18px] border border-[#d6dbe6] bg-white p-5 dark:border-slate-800 dark:bg-slate-950/70">
      <div className="grid gap-3 lg:grid-cols-4">
        <div className="rounded-[16px] border border-[#d6dbe6] bg-[#fafbff] px-4 py-4 dark:border-slate-800 dark:bg-slate-900/80">
          <div className="text-[11px] uppercase tracking-[0.16em] text-[#7b8190] dark:text-slate-500">{copy.monitor.parallelStage}</div>
          <div className="mt-2 text-[18px] font-medium tracking-[-0.03em] text-[#111111] dark:text-slate-100">
            {stageLabel}
          </div>
        </div>
        <div className="rounded-[16px] border border-[#d6dbe6] bg-[#fafbff] px-4 py-4 dark:border-slate-800 dark:bg-slate-900/80">
          <div className="text-[11px] uppercase tracking-[0.16em] text-[#7b8190] dark:text-slate-500">{copy.monitor.completedMatches}</div>
          <div className="mt-2 text-[18px] font-medium tracking-[-0.03em] text-[#111111] dark:text-slate-100">
            {progress.completed ?? 0} / {progress.total ?? children.length}
          </div>
        </div>
        <div className="rounded-[16px] border border-[#d6dbe6] bg-[#fafbff] px-4 py-4 dark:border-slate-800 dark:bg-slate-900/80">
          <div className="text-[11px] uppercase tracking-[0.16em] text-[#7b8190] dark:text-slate-500">{copy.monitor.runningMatches}</div>
          <div className="mt-2 text-[18px] font-medium tracking-[-0.03em] text-[#111111] dark:text-slate-100">
            {progress.running ?? 0}
          </div>
        </div>
        <div className="rounded-[16px] border border-[#d6dbe6] bg-[#fafbff] px-4 py-4 dark:border-slate-800 dark:bg-slate-900/80">
          <div className="text-[11px] uppercase tracking-[0.16em] text-[#7b8190] dark:text-slate-500">{copy.monitor.failedMatches}</div>
          <div className="mt-2 text-[18px] font-medium tracking-[-0.03em] text-[#111111] dark:text-slate-100">
            {progress.failed ?? 0}
          </div>
        </div>
      </div>

      <div className="rounded-[16px] border border-[#d6dbe6] bg-[#fafbff] px-4 py-4 dark:border-slate-800 dark:bg-slate-900/80">
        <div className="text-[11px] uppercase tracking-[0.16em] text-[#7b8190] dark:text-slate-500">{copy.monitor.parallelChildren}</div>
        {children.length > 0 ? (
          <div className="mt-3 grid gap-3 lg:grid-cols-2">
            {children.map((child) => (
              <div
                key={child.id}
                className="rounded-[14px] border border-[#d6dbe6] bg-white px-4 py-3 dark:border-slate-800 dark:bg-slate-950/70"
              >
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <div className="min-w-0">
                    <div className="text-[13px] font-medium tracking-[-0.02em] text-[#111111] dark:text-slate-100">
                      {child.label}
                    </div>
                    <div className="mt-1 text-[11px] text-[#6b7280] dark:text-slate-400">
                      {child.stage} · {child.slot_key}
                    </div>
                  </div>
                  <span className="rounded-full border border-[#d6dbe6] bg-[#fafbff] px-2.5 py-1 text-[10px] uppercase tracking-[0.14em] text-[#6b7280] dark:border-slate-700 dark:bg-slate-900 dark:text-slate-400">
                    {copy.statuses[child.status as keyof typeof copy.statuses] ?? child.status}
                  </span>
                </div>
                {child.winner_label ? (
                  <div className="mt-2 text-[12px] leading-5 text-[#475569] dark:text-slate-400">
                    {copy.monitor.matchResult}: {child.winner_label}
                  </div>
                ) : null}
                {onOpenSession ? (
                  <button
                    type="button"
                    onClick={() => onOpenSession(child.id)}
                    className="mt-3 rounded-full border border-[#d6dbe6] bg-white px-3 py-1.5 text-[11px] font-medium text-[#111111] transition-colors hover:bg-[#f6f7fb] dark:border-slate-700 dark:bg-slate-950 dark:text-slate-100 dark:hover:bg-slate-900"
                  >
                    {copy.monitor.openChildSession}
                  </button>
                ) : null}
              </div>
            ))}
          </div>
        ) : (
          <div className="mt-3 rounded-[14px] border border-[#d6dbe6] bg-white px-3 py-4 text-[13px] text-[#6b7280] dark:border-slate-800 dark:bg-slate-950/60 dark:text-slate-400">
            {copy.monitor.noMatchYet}
          </div>
        )}
      </div>

      {session.status === "completed" || session.status === "failed" ? (
        <div className="rounded-[16px] border border-[#d6dbe6] bg-[#fafbff] px-4 py-4 dark:border-slate-800 dark:bg-slate-900/80">
          <div className="text-[11px] uppercase tracking-[0.16em] text-[#7b8190] dark:text-slate-500">{copy.monitor.finalResult}</div>
          <div className="mt-2 text-[16px] leading-7 text-[#111111] dark:text-slate-100">
            {summarizedResult(session, copy.monitor.noMatchYet)}
          </div>
        </div>
      ) : null}
    </div>
  );
}

function TournamentMatchView({ session }: { session: Session }) {
  const { copy } = useLocale();

  return (
    <div className="space-y-4">
      <div className="rounded-[16px] border border-[#d6dbe6] bg-[#fafbff] px-4 py-4 dark:border-slate-800 dark:bg-slate-900/80">
        <div className="flex flex-wrap items-center gap-2">
          {session.parallel_stage ? (
            <span className="rounded-full border border-[#d6dbe6] bg-white px-2.5 py-1 text-[10px] uppercase tracking-[0.14em] text-[#6b7280] dark:border-slate-700 dark:bg-slate-950 dark:text-slate-400">
              {session.parallel_stage}
            </span>
          ) : null}
          {session.parallel_slot_key ? (
            <span className="rounded-full border border-[#d6dbe6] bg-white px-2.5 py-1 text-[10px] uppercase tracking-[0.14em] text-[#6b7280] dark:border-slate-700 dark:bg-slate-950 dark:text-slate-400">
              {session.parallel_slot_key}
            </span>
          ) : null}
        </div>
        <div className="mt-3 text-[16px] font-medium tracking-[-0.03em] text-[#111111] dark:text-slate-100">
          {session.parallel_label ?? copy.monitor.currentMatch}
        </div>
        <div className="mt-1 text-[13px] leading-6 text-[#6b7280] dark:text-slate-400">
          {copy.monitor.managedByParent}
        </div>
      </div>
      <DebateView session={session} />
    </div>
  );
}

function TournamentView({
  session,
  onOpenSession,
}: {
  session: Session;
  onOpenSession?: (sessionId: string) => void;
}) {
  const executionMode = session.parallel_progress?.execution_mode;
  const hasParallelChildren = (session.parallel_children?.length ?? 0) > 0;
  if (executionMode === "parallel" || hasParallelChildren) {
    return <TournamentParallelView session={session} onOpenSession={onOpenSession} />;
  }
  return <TournamentSequentialView session={session} />;
}

export function TopologyPanel({ session, onOpenSession }: TopologyPanelProps) {
  const { copy } = useLocale();
  let content = <GenericView session={session} />;
  if (session.mode === "board") content = <BoardView session={session} />;
  else if (session.mode === "democracy") content = <DemocracyView session={session} />;
  else if (session.mode === "debate") content = <DebateView session={session} />;
  else if (session.mode === "tournament_match") content = <TournamentMatchView session={session} />;
  else if (session.mode === "creator_critic") content = <CreatorCriticView session={session} />;
  else if (session.mode === "map_reduce") content = <MapReduceView session={session} />;
  else if (session.mode === "dictator") content = <DictatorView session={session} />;
  else if (session.mode === "tournament") content = <TournamentView session={session} onOpenSession={onOpenSession} />;

  return (
    <section className="rounded-[18px] border border-[#d6dbe6] bg-white p-4 shadow-[0_10px_24px_-18px_rgba(17,48,105,0.18)] dark:border-slate-800 dark:bg-slate-950/60 dark:shadow-none">
      <h2 className="text-[19px] font-medium tracking-[-0.03em] text-[#111111] dark:text-slate-100">
        {shellTitle(session, copy)}
      </h2>
      <div className="mt-5 space-y-4">
        <SessionStateBanner session={session} />
        <ConnectionCanvas session={session} />
        {content}
      </div>
    </section>
  );
}
