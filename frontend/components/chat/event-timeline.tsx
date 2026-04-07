"use client";

import { useMemo, useState } from "react";
import { AlertTriangle, ChevronDown, ChevronUp } from "lucide-react";
import useSWR from "swr";

import { ScrollArea } from "@/components/ui/scroll-area";
import { formatAgentDisplay, formatWorkspaceLabel, type RoleDisplayContext } from "@/lib/constants";
import { getSession } from "@/lib/api";
import { useLocale } from "@/lib/locale";
import type { AgentConfig, Message, Session, SessionEvent } from "@/lib/types";

import { RichText, extractReadableAgentText, sanitizeAgentText } from "./rich-text";

interface EventTimelineProps {
  events: SessionEvent[];
  mode?: string;
  scenarioId?: string | null;
  agents?: AgentConfig[];
  status?: Session["status"];
  parallelProgress?: Session["parallel_progress"];
  parallelChildren?: Session["parallel_children"];
}

interface ConversationPanelProps {
  sessionId: string;
  messages?: Message[];
  events?: SessionEvent[];
  mode?: string;
  scenarioId?: string | null;
  agents?: AgentConfig[];
  status?: Session["status"];
  parallelProgress?: Session["parallel_progress"];
  parallelChildren?: Session["parallel_children"];
  onOpenSession?: (sessionId: string) => void;
}

interface TimelineItem {
  id: string;
  timestamp: number;
  eyebrow: string;
  actor: string;
  title: string;
  detail: string;
  rawDetail: string;
  meta?: string;
  scopeLabel?: string;
}

interface ConversationMessageItem extends Message {
  cleanContent: string;
  rawContent: string;
  hasHiddenRuntimeDetails: boolean;
}

interface ParallelConversationThread {
  id: string;
  label: string;
  status: Session["status"];
  timestamp: number;
  preview: string;
  session: Session;
  messages: ConversationMessageItem[];
}

function formatTime(timestamp: number): string {
  return new Date(timestamp * 1000).toLocaleTimeString([], {
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  });
}

function truncateText(text: string, limit: number = 420): string {
  const normalized = text.replace(/\n{3,}/g, "\n\n").trim();
  if (normalized.length <= limit) {
    return normalized;
  }
  return `${normalized.slice(0, limit - 1)}...`;
}

function projectLabelForRole(role: string, agents: AgentConfig[] = []): string | null {
  const agent = agents.find((candidate) => candidate.role === role);
  return formatWorkspaceLabel(agent?.workspace_paths);
}

function displayActor(actor: string, context?: RoleDisplayContext, agents: AgentConfig[] = []): string {
  if (!actor || actor === "system" || actor === "user" || actor === "agent") {
    return actor || "agent";
  }
  return formatAgentDisplay(actor, {
    ...context,
    projectLabel: projectLabelForRole(actor, agents),
  });
}

function displayEventTitle(
  title: string,
  actor?: string,
  context?: RoleDisplayContext,
  agents: AgentConfig[] = []
): string {
  const normalized = String(title ?? "").trim();
  if (!normalized) return "";
  if (actor && normalized === actor) {
    return displayActor(actor, context, agents);
  }
  if (/^[a-z][a-z0-9_]*$/i.test(normalized) && normalized !== "system" && normalized !== "user") {
    return formatAgentDisplay(normalized, {
      ...context,
      projectLabel: projectLabelForRole(normalized, agents),
    });
  }
  return normalized;
}

function normalizeConversationMessage(message: Message): ConversationMessageItem {
  const rawContent = sanitizeAgentText(message.content);
  const cleanContent = extractReadableAgentText(message.content);
  return {
    ...message,
    rawContent,
    cleanContent,
    hasHiddenRuntimeDetails: Boolean(rawContent) && rawContent !== cleanContent,
  };
}

function meaningfulConversationMessages(messages: Message[] = []) {
  return messages
    .map(normalizeConversationMessage)
    .filter((message) => message.agent_id && (message.cleanContent.trim() || message.rawContent.trim()));
}

function buildExecutionItems(
  events: SessionEvent[],
  copy: ReturnType<typeof useLocale>["copy"],
  context?: RoleDisplayContext,
  agents: AgentConfig[] = [],
  options?: {
    scopeId?: string;
    scopeLabel?: string;
  }
): TimelineItem[] {
  return events
    .reduce<TimelineItem[]>((items, event) => {
      if (event.type === "agent_message") {
        return items;
      }

      if (event.type === "tool_call_started") {
        const rawDetail = sanitizeAgentText(event.detail || event.tool_name || event.title);
        const cleanDetail = extractReadableAgentText(rawDetail);
        items.push({
          id: `${options?.scopeId ?? "session"}-event-${event.id}`,
          timestamp: event.timestamp,
          eyebrow: copy.monitor.toolCall,
          actor: displayActor(event.agent_id ?? "agent", context, agents),
          title: event.tool_name ?? event.title,
          detail: cleanDetail || rawDetail,
          rawDetail,
          meta: event.phase || undefined,
          scopeLabel: options?.scopeLabel,
        });
        return items;
      }

      if (event.type === "tool_call_finished") {
        const elapsed = typeof event.elapsed_sec === "number" ? `${event.elapsed_sec}s` : "";
        const rawDetail = sanitizeAgentText(event.detail || event.title);
        const cleanDetail = extractReadableAgentText(rawDetail);
        items.push({
          id: `${options?.scopeId ?? "session"}-event-${event.id}`,
          timestamp: event.timestamp,
          eyebrow: copy.monitor.toolResult,
          actor: displayActor(event.agent_id ?? "agent", context, agents),
          title: event.tool_name ?? event.title,
          detail: cleanDetail || rawDetail,
          rawDetail,
          meta: [elapsed, event.success === false ? copy.monitor.failed : ""].filter(Boolean).join(" · ") || undefined,
          scopeLabel: options?.scopeLabel,
        });
        return items;
      }

      const rawDetail = sanitizeAgentText(event.detail || event.checkpoint_id || event.phase || "");
      const cleanDetail = extractReadableAgentText(rawDetail, { preferStructuredAnswer: true });
      items.push({
        id: `${options?.scopeId ?? "session"}-event-${event.id}`,
        timestamp: event.timestamp,
        eyebrow: copy.monitor.systemEvent,
        actor: displayActor(event.agent_id ?? "system", context, agents),
        title: displayEventTitle(event.title, event.agent_id, context, agents),
        detail: cleanDetail || rawDetail,
        rawDetail,
        meta: [event.phase, event.checkpoint_id].filter(Boolean).join(" · ") || undefined,
        scopeLabel: options?.scopeLabel,
      });
      return items;
    }, [])
    .sort((a, b) => b.timestamp - a.timestamp);
}

function latestFailure(events: SessionEvent[] = []) {
  return [...events]
    .reverse()
    .find((event) => event.type === "agent_failed" || event.type === "run_failed");
}

function hasActiveParallelTournamentParent({
  mode,
  status,
  parallelProgress,
  parallelChildren,
}: {
  mode?: string;
  status?: Session["status"];
  parallelProgress?: Session["parallel_progress"];
  parallelChildren?: Session["parallel_children"];
}) {
  return (
    mode === "tournament" &&
    status === "running" &&
    ((parallelProgress?.running ?? 0) > 0 ||
      (parallelChildren ?? []).some((child) => child.status === "running"))
  );
}

function conversationEyebrow(
  message: Message,
  copy: ReturnType<typeof useLocale>["copy"]
) {
  if (message.agent_id === "user") {
    return copy.monitor.userMessage;
  }

  return copy.monitor.agentMessage;
}

function useParallelChildSessions({
  mode,
  status,
  parallelChildren,
}: {
  mode?: string;
  status?: Session["status"];
  parallelChildren?: Session["parallel_children"];
}) {
  const childIds = useMemo(
    () =>
      mode === "tournament"
        ? [...new Set((parallelChildren ?? []).map((child) => child.id).filter(Boolean))]
        : [],
    [mode, parallelChildren]
  );

  const { data } = useSWR<Session[]>(
    childIds.length > 0 ? ["parallel-sessions", ...childIds] : null,
    () => Promise.all(childIds.map((id) => getSession(id))),
    {
      refreshInterval: status === "running" ? 1500 : 0,
    }
  );

  return data ?? [];
}

function buildParallelConversationThreads(
  childSessions: Session[],
  parallelChildren: Session["parallel_children"] = []
): ParallelConversationThread[] {
  const childLabels = new Map(parallelChildren.map((child) => [child.id, child.label]));
  const items: Array<ParallelConversationThread | null> = childSessions.map((session) => {
    const normalizedMessages = meaningfulConversationMessages(session.messages).filter((message) => message.agent_id !== "user");
    const participantMessages = normalizedMessages.filter((message) => message.agent_id !== "system");
    const transcriptMessages = participantMessages.length > 0 ? participantMessages : normalizedMessages;
    const latestTranscriptMessage = [...transcriptMessages]
      .reverse()
      .find((message) => message.cleanContent.trim() || message.rawContent.trim());
    const latestVerdict = [...transcriptMessages]
      .reverse()
      .find((message) => message.phase.includes("verdict") || message.agent_id === "judge");
    const resultPreview =
      extractReadableAgentText(session.result ?? "", { preferStructuredAnswer: true }) ||
      sanitizeAgentText(session.result ?? "");
    const preview = latestVerdict?.cleanContent || latestTranscriptMessage?.cleanContent || resultPreview;

    if (!preview.trim() && transcriptMessages.length === 0) {
      return null;
    }

    return {
      id: session.id,
      label: childLabels.get(session.id) ?? session.parallel_label ?? session.id,
      status: session.status,
      timestamp: latestVerdict?.timestamp ?? latestTranscriptMessage?.timestamp ?? session.created_at,
      preview: truncateText(preview, 320),
      session,
      messages: transcriptMessages,
    };
  });

  return items
    .filter((item): item is ParallelConversationThread => item !== null)
    .sort((left, right) => {
      const leftRunning = left.status === "running" ? 1 : 0;
      const rightRunning = right.status === "running" ? 1 : 0;
      if (leftRunning !== rightRunning) {
        return rightRunning - leftRunning;
      }
      return right.timestamp - left.timestamp;
    });
}

function ConversationMessageCard({
  message,
  copy,
  roleContext,
  agents,
}: {
  message: ConversationMessageItem;
  copy: ReturnType<typeof useLocale>["copy"];
  roleContext: RoleDisplayContext;
  agents: AgentConfig[];
}) {
  const [expanded, setExpanded] = useState(false);
  const [showRaw, setShowRaw] = useState(false);
  const canExpandMessage = message.cleanContent.length > 420;
  const visibleContent = canExpandMessage && !expanded ? truncateText(message.cleanContent, 420) : message.cleanContent;
  const displayContent = visibleContent || copy.monitor.rawConversationHidden;

  return (
    <div className="rounded-[14px] border border-[#e5e7eb] bg-[#fbfcff] px-4 py-4 dark:border-slate-800 dark:bg-slate-900/80">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="flex min-w-0 flex-wrap items-center gap-2">
          <span className="rounded-full border border-[#d6dbe6] bg-white px-2.5 py-1 text-[10px] uppercase tracking-[0.14em] text-[#6b7280] dark:border-slate-700 dark:bg-slate-950 dark:text-slate-400">
            {conversationEyebrow(message, copy)}
          </span>
          <span className="text-[12px] font-medium text-[#111111] dark:text-slate-100">
            {displayActor(message.agent_id, roleContext, agents)}
          </span>
          {message.phase ? (
            <span className="text-[11px] uppercase tracking-[0.12em] text-[#8b94a7] dark:text-slate-500">
              {message.phase.replace(/_/g, " ")}
            </span>
          ) : null}
        </div>
        <div className="text-[11px] text-[#6b7280] dark:text-slate-500">{formatTime(message.timestamp)}</div>
      </div>

      <div className="mt-3 rounded-[12px] border border-[#e5e7eb] bg-white px-4 py-4 dark:border-slate-800 dark:bg-slate-950">
        {canExpandMessage && !expanded ? (
          <p className="whitespace-pre-line text-[14px] leading-7 text-[#273142] dark:text-slate-300">{displayContent}</p>
        ) : (
          <RichText text={displayContent} />
        )}
      </div>

      {canExpandMessage || message.hasHiddenRuntimeDetails ? (
        <div className="mt-3 flex flex-wrap gap-2">
          {canExpandMessage ? (
            <button
              type="button"
              onClick={() => setExpanded((value) => !value)}
              className="rounded-full border border-[#d6dbe6] bg-white px-3 py-1 text-[11px] uppercase tracking-[0.14em] text-[#6b7280] dark:border-slate-800 dark:bg-slate-950 dark:text-slate-400"
            >
              {expanded ? copy.monitor.hideMessage : copy.monitor.showFullMessage}
            </button>
          ) : null}
          {message.hasHiddenRuntimeDetails ? (
            <button
              type="button"
              onClick={() => setShowRaw((value) => !value)}
              className="rounded-full border border-[#d6dbe6] bg-white px-3 py-1 text-[11px] uppercase tracking-[0.14em] text-[#6b7280] dark:border-slate-800 dark:bg-slate-950 dark:text-slate-400"
            >
              {showRaw ? copy.monitor.hideRawDetails : copy.monitor.showRawDetails}
            </button>
          ) : null}
        </div>
      ) : null}

      {message.hasHiddenRuntimeDetails && showRaw ? (
        <div className="mt-3 rounded-[12px] border border-[#d6dbe6] bg-white px-4 py-3 dark:border-slate-800 dark:bg-slate-950">
          <pre className="max-h-56 overflow-auto whitespace-pre-wrap break-words text-[12px] leading-5 text-[#273142] dark:text-slate-300">
            {message.rawContent}
          </pre>
        </div>
      ) : null}
    </div>
  );
}

function ParallelConversationCard({
  thread,
  copy,
  onOpenSession,
}: {
  thread: ParallelConversationThread;
  copy: ReturnType<typeof useLocale>["copy"];
  onOpenSession?: (sessionId: string) => void;
}) {
  const [expanded, setExpanded] = useState(thread.status === "running");
  const roleContext = useMemo<RoleDisplayContext>(
    () => ({ mode: thread.session.mode, scenarioId: thread.session.active_scenario }),
    [thread.session.active_scenario, thread.session.mode]
  );

  return (
    <div className="rounded-[14px] border border-[#e5e7eb] bg-[#fbfcff] px-4 py-4 dark:border-slate-800 dark:bg-slate-900/80">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="flex min-w-0 flex-wrap items-center gap-2">
          <span className="rounded-full border border-[#d6dbe6] bg-white px-2.5 py-1 text-[10px] uppercase tracking-[0.14em] text-[#6b7280] dark:border-slate-700 dark:bg-slate-950 dark:text-slate-400">
            {thread.label}
          </span>
          <span className="rounded-full border border-[#d6dbe6] bg-white px-2.5 py-1 text-[10px] uppercase tracking-[0.14em] text-[#6b7280] dark:border-slate-700 dark:bg-slate-950 dark:text-slate-400">
            {copy.statuses[thread.status as keyof typeof copy.statuses] ?? thread.status}
          </span>
        </div>
        <div className="text-[11px] text-[#6b7280] dark:text-slate-500">{formatTime(thread.timestamp)}</div>
      </div>

      <div className="mt-3 rounded-[12px] border border-[#e5e7eb] bg-white px-4 py-4 dark:border-slate-800 dark:bg-slate-950">
        <RichText text={thread.preview} />
      </div>

      <div className="mt-3 flex flex-wrap gap-2">
        {thread.messages.length > 0 ? (
          <button
            type="button"
            onClick={() => setExpanded((value) => !value)}
            className="rounded-full border border-[#d6dbe6] bg-white px-3 py-1 text-[11px] uppercase tracking-[0.14em] text-[#6b7280] dark:border-slate-800 dark:bg-slate-950 dark:text-slate-400"
          >
            {expanded ? copy.monitor.hideTranscript : copy.monitor.showTranscript}
          </button>
        ) : null}
        {onOpenSession ? (
          <button
            type="button"
            onClick={() => onOpenSession(thread.id)}
            className="rounded-full border border-[#d6dbe6] bg-white px-3 py-1 text-[11px] uppercase tracking-[0.14em] text-[#6b7280] dark:border-slate-800 dark:bg-slate-950 dark:text-slate-400"
          >
            {copy.monitor.openChildSession}
          </button>
        ) : null}
      </div>

      {expanded ? (
        <div className="mt-3 space-y-3">
          {thread.messages.map((message) => (
            <ConversationMessageCard
              key={`parallel-message-${thread.id}-${message.agent_id}-${message.timestamp}-${message.phase}`}
              message={message}
              copy={copy}
              roleContext={roleContext}
              agents={thread.session.agents}
            />
          ))}
        </div>
      ) : null}
    </div>
  );
}

function EventTimelineCard({
  item,
  copy,
}: {
  item: TimelineItem;
  copy: ReturnType<typeof useLocale>["copy"];
}) {
  const [expanded, setExpanded] = useState(false);
  const [showRaw, setShowRaw] = useState(false);
  const canExpand = item.detail.length > 260;
  const hasHiddenRuntimeDetails = Boolean(item.rawDetail) && item.rawDetail !== item.detail;
  const visibleDetail = canExpand && !expanded ? truncateText(item.detail, 260) : item.detail;

  return (
    <div className="rounded-[14px] border border-[#e5e7eb] bg-[#fbfcff] px-4 py-3 dark:border-slate-800 dark:bg-slate-900/80">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="flex min-w-0 flex-wrap items-center gap-2">
          <span className="rounded-full border border-[#d6dbe6] bg-white px-2.5 py-1 text-[10px] uppercase tracking-[0.14em] text-[#6b7280] dark:border-slate-700 dark:bg-slate-950 dark:text-slate-400">
            {item.eyebrow}
          </span>
          {item.scopeLabel ? (
            <span className="rounded-full border border-[#d6dbe6] bg-white px-2.5 py-1 text-[10px] uppercase tracking-[0.14em] text-[#6b7280] dark:border-slate-700 dark:bg-slate-950 dark:text-slate-400">
              {item.scopeLabel}
            </span>
          ) : null}
          <span className="text-[12px] font-medium text-[#111111] dark:text-slate-100">{item.actor}</span>
          {item.meta ? (
            <span className="text-[11px] uppercase tracking-[0.12em] text-[#8b94a7] dark:text-slate-500">
              {item.meta}
            </span>
          ) : null}
        </div>
        <div className="text-[11px] text-[#6b7280] dark:text-slate-500">{formatTime(item.timestamp)}</div>
      </div>

      <div className="mt-2 text-[14px] font-medium tracking-[-0.03em] text-[#111111] dark:text-slate-100">
        {item.title}
      </div>

      {item.detail ? (
        <div className="mt-2 rounded-[12px] border border-[#e5e7eb] bg-white px-3 py-3 dark:border-slate-800 dark:bg-slate-950">
          {canExpand && !expanded ? (
            <div className="text-[12px] leading-6 text-[#273142] dark:text-slate-300">{visibleDetail}</div>
          ) : (
            <RichText text={visibleDetail} className="text-[13px] leading-6" />
          )}
        </div>
      ) : null}

      {canExpand || hasHiddenRuntimeDetails ? (
        <div className="mt-3 flex flex-wrap gap-2">
          {canExpand ? (
            <button
              type="button"
              onClick={() => setExpanded((value) => !value)}
              className="rounded-full border border-[#d6dbe6] bg-white px-3 py-1 text-[11px] uppercase tracking-[0.14em] text-[#6b7280] dark:border-slate-800 dark:bg-slate-950 dark:text-slate-400"
            >
              {expanded ? copy.monitor.hideMessage : copy.monitor.showFullMessage}
            </button>
          ) : null}
          {hasHiddenRuntimeDetails ? (
            <button
              type="button"
              onClick={() => setShowRaw((value) => !value)}
              className="rounded-full border border-[#d6dbe6] bg-white px-3 py-1 text-[11px] uppercase tracking-[0.14em] text-[#6b7280] dark:border-slate-800 dark:bg-slate-950 dark:text-slate-400"
            >
              {showRaw ? copy.monitor.hideRawDetails : copy.monitor.showRawDetails}
            </button>
          ) : null}
        </div>
      ) : null}

      {hasHiddenRuntimeDetails && showRaw ? (
        <div className="mt-3 rounded-[12px] border border-[#d6dbe6] bg-white px-4 py-3 dark:border-slate-800 dark:bg-slate-950">
          <pre className="max-h-56 overflow-auto whitespace-pre-wrap break-words text-[12px] leading-5 text-[#273142] dark:text-slate-300">
            {item.rawDetail}
          </pre>
        </div>
      ) : null}
    </div>
  );
}

export function ConversationPanel({
  sessionId,
  messages = [],
  events = [],
  mode,
  scenarioId,
  agents = [],
  status,
  parallelProgress,
  parallelChildren,
  onOpenSession,
}: ConversationPanelProps) {
  const { copy } = useLocale();
  const shouldAutoExpand =
    !status || (!["completed", "failed", "cancelled"].includes(status) && messages.length <= 6);
  const [manualExpanded, setManualExpanded] = useState<boolean | null>(null);
  const expanded = manualExpanded ?? shouldAutoExpand;
  const roleContext = useMemo<RoleDisplayContext>(() => ({ mode, scenarioId }), [mode, scenarioId]);
  const visibleMessages = useMemo(() => meaningfulConversationMessages(messages), [messages]);
  const failure = useMemo(() => latestFailure(events), [events]);
  const showParallelHint = hasActiveParallelTournamentParent({
    mode,
    status,
    parallelProgress,
    parallelChildren,
  });
  const parallelChildSessions = useParallelChildSessions({
    mode,
    status,
    parallelChildren,
  });
  const parallelThreads = useMemo(
    () => buildParallelConversationThreads(parallelChildSessions, parallelChildren),
    [parallelChildSessions, parallelChildren]
  );
  const canToggleHistory = visibleMessages.length > 3;
  const hiddenCount = expanded ? 0 : Math.max(0, visibleMessages.length - 3);
  const renderedMessages = expanded ? visibleMessages : visibleMessages.slice(-3);
  void sessionId;

  return (
    <section className="rounded-[18px] border border-[#d6dbe6] bg-[#f8fafc] p-4 shadow-[0_10px_24px_-18px_rgba(17,48,105,0.18)] dark:border-slate-800 dark:bg-slate-950/60 dark:shadow-none">
      <div className="flex items-center justify-between gap-3">
        <h2 className="text-[19px] font-medium tracking-[-0.03em] text-[#111111] dark:text-slate-100">
          {copy.monitor.conversation}
        </h2>
        {canToggleHistory ? (
          <button
            type="button"
            onClick={() => setManualExpanded((value) => !(value ?? shouldAutoExpand))}
            className="inline-flex items-center gap-1 rounded-full border border-[#d6dbe6] bg-white px-3 py-1 text-[11px] uppercase tracking-[0.14em] text-[#6b7280] dark:border-slate-800 dark:bg-slate-900 dark:text-slate-400"
          >
            {expanded ? <ChevronUp className="h-3.5 w-3.5" /> : <ChevronDown className="h-3.5 w-3.5" />}
            {expanded ? copy.monitor.hideEarlierMessages : `${copy.monitor.showEarlierMessages} ${hiddenCount}`}
          </button>
        ) : null}
      </div>

      <div className="mt-3 rounded-[14px] border border-[#d6dbe6] bg-white px-4 py-3 dark:border-slate-800 dark:bg-slate-950/70">
        <div className="space-y-3">
          {failure ? (
            <div className="rounded-[14px] border border-amber-200 bg-amber-50 px-4 py-3 text-amber-900 dark:border-amber-900/70 dark:bg-amber-950/30 dark:text-amber-100">
              <div className="flex items-start gap-2">
                <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" />
                <div>
                  <div className="text-[11px] uppercase tracking-[0.16em] text-amber-700 dark:text-amber-300">
                    {copy.monitor.agentFailure}
                  </div>
                  <div className="mt-1 text-[14px] font-medium">
                    {failure.title}
                  </div>
                  {failure.detail ? (
                    <div className="mt-2 text-[13px] leading-6 text-amber-900/80 dark:text-amber-100/80">
                      {failure.detail}
                    </div>
                  ) : null}
                </div>
              </div>
            </div>
          ) : null}

          {renderedMessages.map((message) => (
            <ConversationMessageCard
              key={`message-${message.agent_id}-${message.timestamp}-${message.phase}`}
              message={message}
              copy={copy}
              roleContext={roleContext}
              agents={agents}
            />
          ))}

          {parallelThreads.length > 0 ? (
            <div className="space-y-3 border-t border-[#e5e7eb] pt-3 dark:border-slate-800">
              <div className="text-[11px] uppercase tracking-[0.16em] text-[#7b8190] dark:text-slate-500">
                {copy.monitor.parallelConversations}
              </div>
              {parallelThreads.map((thread) => (
                <ParallelConversationCard
                  key={thread.id}
                  thread={thread}
                  copy={copy}
                  onOpenSession={onOpenSession}
                />
              ))}
            </div>
          ) : null}

          {visibleMessages.length === 0 && !failure && parallelThreads.length === 0 ? (
            <div className="text-[14px] text-[#6b7280] dark:text-slate-500">
              {showParallelHint ? copy.monitor.parallelConversationHint : copy.monitor.noConversationYet}
            </div>
          ) : null}
        </div>
      </div>
    </section>
  );
}

export function EventTimeline({
  events,
  mode,
  scenarioId,
  agents = [],
  status,
  parallelProgress,
  parallelChildren,
}: EventTimelineProps) {
  const { copy } = useLocale();
  const roleContext = useMemo<RoleDisplayContext>(() => ({ mode, scenarioId }), [mode, scenarioId]);
  const parentItems = useMemo(
    () => buildExecutionItems(events, copy, roleContext, agents, { scopeId: "parent" }),
    [agents, copy, events, roleContext]
  );
  const parallelChildSessions = useParallelChildSessions({
    mode,
    status,
    parallelChildren,
  });
  const parallelItems = useMemo(() => {
    const childLabels = new Map((parallelChildren ?? []).map((child) => [child.id, child.label]));
    return parallelChildSessions.flatMap((session) =>
      buildExecutionItems(
        session.events ?? [],
        copy,
        { mode: session.mode, scenarioId: session.active_scenario },
        session.agents,
        {
          scopeId: session.id,
          scopeLabel: childLabels.get(session.id) ?? session.parallel_label ?? session.id,
        }
      ).slice(0, 12)
    );
  }, [copy, parallelChildSessions, parallelChildren]);
  const items = useMemo(
    () => [...parentItems, ...parallelItems].sort((left, right) => right.timestamp - left.timestamp).slice(0, 80),
    [parallelItems, parentItems]
  );
  const showParallelHint = hasActiveParallelTournamentParent({
    mode,
    status,
    parallelProgress,
    parallelChildren,
  });
  const [expanded, setExpanded] = useState(false);
  const canToggleTrace = items.length > 6;
  const visibleItems = expanded ? items : items.slice(0, 6);
  const hiddenCount = expanded ? 0 : Math.max(0, items.length - 6);

  return (
    <section className="rounded-[18px] border border-[#d6dbe6] bg-[#f8fafc] p-4 shadow-[0_10px_24px_-18px_rgba(17,48,105,0.18)] dark:border-slate-800 dark:bg-slate-950/60 dark:shadow-none">
      <div className="flex items-center justify-between gap-3">
        <h2 className="text-[19px] font-medium tracking-[-0.03em] text-[#111111] dark:text-slate-100">
          {copy.monitor.executionTrace}
        </h2>
        {canToggleTrace ? (
          <button
            type="button"
            onClick={() => setExpanded((value) => !value)}
            className="inline-flex items-center gap-1 rounded-full border border-[#d6dbe6] bg-white px-3 py-1 text-[11px] uppercase tracking-[0.14em] text-[#6b7280] dark:border-slate-800 dark:bg-slate-900 dark:text-slate-400"
          >
            {expanded ? <ChevronUp className="h-3.5 w-3.5" /> : <ChevronDown className="h-3.5 w-3.5" />}
            {expanded ? copy.monitor.hideTrace : `${copy.monitor.showTrace} ${hiddenCount}`}
          </button>
        ) : null}
      </div>
      <div className="mt-3 rounded-[14px] border border-[#d6dbe6] bg-white dark:border-slate-800 dark:bg-slate-950/70">
        {showParallelHint && parallelItems.length === 0 ? (
          <div className="border-b border-[#e5e7eb] px-4 py-3 text-[13px] leading-6 text-[#6b7280] dark:border-slate-800 dark:text-slate-400">
            {copy.monitor.parallelTraceHint}
          </div>
        ) : null}
        {expanded ? (
          <ScrollArea className="h-[320px] px-4 py-3">
            <div className="space-y-3">
              {visibleItems.map((item) => (
                <EventTimelineCard
                  key={item.id}
                  item={item}
                  copy={copy}
                />
              ))}
              {items.length === 0 ? (
                <div className="text-[14px] text-[#6b7280] dark:text-slate-500">{copy.monitor.traceEmpty}</div>
              ) : null}
            </div>
          </ScrollArea>
        ) : (
          <div className="px-4 py-3">
            <div className="space-y-3">
              {visibleItems.map((item) => (
                <EventTimelineCard
                  key={item.id}
                  item={item}
                  copy={copy}
                />
              ))}
              {items.length === 0 ? (
                <div className="text-[14px] text-[#6b7280] dark:text-slate-500">{copy.monitor.traceEmpty}</div>
              ) : null}
            </div>
          </div>
        )}
      </div>
    </section>
  );
}
