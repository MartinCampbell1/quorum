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

import { useLocale } from "@/lib/locale";
import type { AttachedToolDetail, Message, Session, SessionEvent } from "@/lib/types";

import { useTopologyFlowGraph } from "./topology-layout";
import {
  buildTournamentStructure,
  latestRoundLabel,
} from "./topology-model";
import { TopologyFlowStage } from "./topology-stage";

interface TopologyPanelProps {
  session: Session;
}

function humanizeTool(tool: string) {
  return tool
    .replace(/_/g, " ")
    .replace(/\b\w/g, (char) => char.toUpperCase());
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
  if (session.mode === "debate") return copy.monitor.topologyTitles.debate;
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

    if (session.mode === "debate") {
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

  return [
    {
      label: copy.monitor.signalLabels.activeNode,
      value: session.active_node || copy.monitor.idle,
    },
    {
      label: copy.monitor.signalLabels.checkpoint,
      value: session.current_checkpoint_id || copy.monitor.pending,
    },
    {
      label: copy.monitor.signalLabels.liveTool,
      value: latestToolEvent?.tool_name || latestToolEvent?.detail || copy.monitor.noToolActivity,
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
        from: event.agent_id ?? copy.monitor.sharedContexts.default,
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
    snapshot.tone === "waiting" ? LoaderCircle : snapshot.tone === "paused" ? PauseCircle : AlertTriangle;
  const toneClasses =
    snapshot.tone === "failed"
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
            ({orchestrator.role})
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
            ({upperWorker.role})
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
            ({lowerWorker.role})
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
          label={director.role}
          subtitle={
            latestEvent(events, "vote_recorded", (event) => event.agent_id === director.role)?.detail ||
            latestMessage(session.messages, director.role)?.content?.slice(0, 160) ||
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
          label={agent.role}
          subtitle={
            latestEvent(events, "vote_recorded", (event) => event.agent_id === agent.role)?.detail ||
            latestMessage(session.messages, agent.role)?.content?.replace(/^Vote:\s*/i, "").slice(0, 140) ||
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
        label={proponent?.role ?? "proponent"}
        subtitle={proponent ? latestMessage(session.messages, proponent.role)?.content?.slice(0, 180) || copy.monitor.awaitingArgument : "—"}
        accent={roundLabel ?? undefined}
      />
      <div className="flex items-center justify-center text-[#9ca3af]">
        <ArrowRight className="h-6 w-6" />
      </div>
      <AgentPill
        label={opponent?.role ?? "opponent"}
        subtitle={opponent ? latestMessage(session.messages, opponent.role)?.content?.slice(0, 180) || copy.monitor.awaitingRebuttal : "—"}
        accent={roundLabel ?? undefined}
      />
      <div className="rounded-[16px] border border-[#d6dbe6] bg-[#fafbff] px-4 py-4 lg:col-span-3 dark:border-slate-800 dark:bg-slate-900/80">
        <div className="text-[11px] uppercase tracking-[0.16em] text-[#7b8190] dark:text-slate-500">{copy.monitor.judgeVerdict}</div>
        <div className="mt-2 text-[16px] leading-7 text-[#111111] dark:text-slate-100">
          {sanitizeSummaryText(latestVerdict?.detail) ||
            (judge
              ? sanitizeSummaryText(latestMessage(session.messages, judge.role)?.content) ||
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
              {message.agent_id} · {message.phase.replace(/_/g, " ")}
            </div>
            <div className="mt-2 text-[14px] leading-6 text-[#111111] dark:text-slate-100">{message.content}</div>
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
        label={planner?.role ?? "planner"}
        subtitle={planner ? latestMessage(session.messages, planner.role)?.content || copy.monitor.plannerPreparing : "—"}
      />
      <div className="space-y-3 rounded-[16px] border border-[#d6dbe6] bg-[#fafbff] px-4 py-4 dark:border-slate-800 dark:bg-slate-900/80">
        <div className="text-[11px] uppercase tracking-[0.16em] text-[#7b8190] dark:text-slate-500">{copy.monitor.workers}</div>
        {workers.map((worker) => (
          <div key={worker.role} className="rounded-[14px] border border-[#d6dbe6] bg-white px-3 py-3 dark:border-slate-800 dark:bg-slate-950/70">
            <div className="text-[14px] font-medium text-[#111111] dark:text-slate-100">{worker.role}</div>
            <div className="mt-1 text-[12px] leading-5 text-[#6b7280] dark:text-slate-400">
              {latestEvent(session.events ?? [], "chunk_completed", (event) => event.agent_id === worker.role)?.detail ||
                latestMessage(session.messages, worker.role)?.content?.slice(0, 120) ||
                copy.monitor.waitingChunkOutput}
            </div>
          </div>
        ))}
        {chunkEvents.length > 0 ? (
          <div className="space-y-2 rounded-[14px] border border-dashed border-[#d6dbe6] bg-white px-3 py-3 dark:border-slate-700 dark:bg-slate-950/70">
            <div className="text-[11px] uppercase tracking-[0.16em] text-[#7b8190] dark:text-slate-500">{copy.monitor.recentChunks}</div>
            {chunkEvents.map((event) => (
              <div key={event.id} className="text-[12px] leading-5 text-[#6b7280] dark:text-slate-400">
                <span className="font-medium text-[#111111] dark:text-slate-100">{event.agent_id || "worker"}</span>
                {" · "}
                {event.detail}
              </div>
            ))}
          </div>
        ) : null}
      </div>
      <AgentPill
        label={synthesizer?.role ?? "synthesizer"}
        subtitle={
          synthesizer
            ? sanitizeSummaryText(latestMessage(session.messages, synthesizer.role)?.content) ||
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
          {dictator?.role ?? "dictator"}
        </div>
        <div className="mt-2 text-[14px] leading-6 text-[#6b7280] dark:text-slate-400">
          {latestDirective?.detail || latestMessage(session.messages, dictator?.role ?? "")?.content?.slice(0, 240) || copy.monitor.idle}
        </div>
      </div>
      <div className="space-y-3">
        {workers.map((worker) => (
          <AgentPill
            key={worker.role}
            label={worker.role}
            subtitle={latestMessage(session.messages, worker.role)?.content?.slice(0, 160) || copy.monitor.waitingWorkerResult}
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

function TournamentView({ session }: { session: Session }) {
  const { copy } = useLocale();
  const structure = buildTournamentStructure(session.agents);
  const events = session.events ?? [];
  const roundLabel = latestRoundLabel(events) ?? structure.mainRoundLabels[0];
  const directAccent = structure.playInMatchCount > 0 ? structure.mainRoundLabels[0] ?? roundLabel : roundLabel;
  const directEntries = structure.slots.filter((slot): slot is Extract<(typeof structure.slots)[number], { kind: "direct" }> => slot.kind === "direct");
  const playInEntries = structure.slots.filter((slot): slot is Extract<(typeof structure.slots)[number], { kind: "playin" }> => slot.kind === "playin");

  return (
    <div className="grid gap-4 rounded-[18px] border border-[#d6dbe6] bg-white p-5 dark:border-slate-800 dark:bg-slate-950/70">
      {playInEntries.map((slot) => {
        const [a, b] = slot.pair;
        return (
          <div
            key={`playin-${slot.slotIndex}`}
            className="grid grid-cols-[minmax(0,1fr)_48px_minmax(0,1fr)] items-center gap-2 rounded-[16px] border border-[#d6dbe6] bg-[#fafbff] px-4 py-4 dark:border-slate-800 dark:bg-slate-900/80"
          >
            <AgentPill
              label={a.role}
              subtitle={latestMessage(session.messages, a.role)?.content?.slice(0, 120) || copy.monitor.noMatchYet}
              accent="PLAY-IN"
            />
            <div className="flex items-center justify-center text-[18px] font-bold tracking-[-0.04em] text-[#9aa3b2] dark:text-slate-500">
              {copy.monitor.vsLabel}
            </div>
            <AgentPill
              label={b.role}
              subtitle={latestMessage(session.messages, b.role)?.content?.slice(0, 120) || copy.monitor.noMatchYet}
              accent="PLAY-IN"
            />
          </div>
        );
      })}
      {directEntries.length > 0 ? (
        <div className="grid gap-3 rounded-[16px] border border-[#d6dbe6] bg-[#fafbff] px-4 py-4 dark:border-slate-800 dark:bg-slate-900/80 lg:grid-cols-2">
          {directEntries.map((slot) => (
            <AgentPill
              key={`seeded-${slot.agent.role}`}
              label={slot.agent.role}
              subtitle={latestMessage(session.messages, slot.agent.role)?.content?.slice(0, 140) || copy.monitor.seededForward}
              accent={directAccent ?? undefined}
            />
          ))}
        </div>
      ) : null}
      <div className="rounded-[16px] border border-[#d6dbe6] bg-[#fafbff] px-4 py-4 dark:border-slate-800 dark:bg-slate-900/80">
        <div className="text-[11px] uppercase tracking-[0.16em] text-[#7b8190] dark:text-slate-500">{copy.monitor.matchResult}</div>
        <div className="mt-2 text-[16px] leading-7 text-[#111111] dark:text-slate-100">
          {sanitizeSummaryText(latestEvent(events, "round_completed")?.detail) || summarizedResult(session, copy.monitor.noMatchYet)}
        </div>
      </div>
    </div>
  );
}

export function TopologyPanel({ session }: TopologyPanelProps) {
  const { copy } = useLocale();
  let content = <GenericView session={session} />;
  if (session.mode === "board") content = <BoardView session={session} />;
  else if (session.mode === "democracy") content = <DemocracyView session={session} />;
  else if (session.mode === "debate") content = <DebateView session={session} />;
  else if (session.mode === "creator_critic") content = <CreatorCriticView session={session} />;
  else if (session.mode === "map_reduce") content = <MapReduceView session={session} />;
  else if (session.mode === "dictator") content = <DictatorView session={session} />;
  else if (session.mode === "tournament") content = <TournamentView session={session} />;

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
