"use client";

import { useMemo, useState } from "react";
import { AlertTriangle, ChevronDown, ChevronUp } from "lucide-react";

import { ScrollArea } from "@/components/ui/scroll-area";
import { useLocale } from "@/lib/locale";
import type { Message, SessionEvent } from "@/lib/types";

interface EventTimelineProps {
  events: SessionEvent[];
}

interface ConversationPanelProps {
  sessionId: string;
  messages?: Message[];
  events?: SessionEvent[];
}

interface TimelineItem {
  id: string;
  timestamp: number;
  eyebrow: string;
  actor: string;
  title: string;
  detail: string;
  meta?: string;
}

function formatTime(timestamp: number): string {
  return new Date(timestamp * 1000).toLocaleTimeString([], {
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  });
}

function compactDetail(text: string, limit: number = 180): string {
  const normalized = text.replace(/\s+/g, " ").trim();
  if (normalized.length <= limit) {
    return normalized;
  }
  return `${normalized.slice(0, limit - 1)}…`;
}

function buildExecutionItems(
  events: SessionEvent[],
  copy: ReturnType<typeof useLocale>["copy"]
): TimelineItem[] {
  return events
    .map((event) => {
      if (event.type === "tool_call_started") {
        return {
          id: `event-${event.id}`,
          timestamp: event.timestamp,
          eyebrow: copy.monitor.toolCall,
          actor: event.agent_id ?? "agent",
          title: event.tool_name ?? event.title,
          detail: compactDetail(event.detail || event.tool_name || event.title),
          meta: event.phase || undefined,
        };
      }

      if (event.type === "tool_call_finished") {
        const elapsed = typeof event.elapsed_sec === "number" ? `${event.elapsed_sec}s` : "";
        return {
          id: `event-${event.id}`,
          timestamp: event.timestamp,
          eyebrow: copy.monitor.toolResult,
          actor: event.agent_id ?? "agent",
          title: event.tool_name ?? event.title,
          detail: compactDetail(event.detail || event.title),
          meta: [elapsed, event.success === false ? copy.monitor.failed : ""].filter(Boolean).join(" · ") || undefined,
        };
      }

      return {
        id: `event-${event.id}`,
        timestamp: event.timestamp,
        eyebrow: copy.monitor.systemEvent,
        actor: event.agent_id ?? "system",
        title: event.title,
        detail: compactDetail(event.detail || event.checkpoint_id || event.phase || ""),
        meta: [event.phase, event.checkpoint_id].filter(Boolean).join(" · ") || undefined,
      };
    })
    .sort((a, b) => b.timestamp - a.timestamp)
    .slice(0, 28);
}

function latestFailure(events: SessionEvent[] = []) {
  return [...events]
    .reverse()
    .find((event) => event.type === "agent_failed" || event.type === "run_failed");
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

export function ConversationPanel({
  sessionId,
  messages = [],
  events = [],
}: ConversationPanelProps) {
  const { copy } = useLocale();
  const [expanded, setExpanded] = useState(false);
  void sessionId;

  const visibleMessages = useMemo(
    () => messages.filter((message) => message.agent_id && message.content.trim()),
    [messages]
  );
  const failure = useMemo(() => latestFailure(events), [events]);
  const hiddenCount = Math.max(0, visibleMessages.length - 4);
  const renderedMessages = expanded ? visibleMessages : visibleMessages.slice(-4);

  return (
    <section className="rounded-[18px] border border-[#d6dbe6] bg-[#f8fafc] p-4 shadow-[0_10px_24px_-18px_rgba(17,48,105,0.18)] dark:border-slate-800 dark:bg-slate-950/60 dark:shadow-none">
      <div className="flex items-center justify-between gap-3">
        <h2 className="text-[19px] font-medium tracking-[-0.03em] text-[#111111] dark:text-slate-100">
          {copy.monitor.conversation}
        </h2>
        {hiddenCount > 0 ? (
          <button
            type="button"
            onClick={() => setExpanded((value) => !value)}
            className="inline-flex items-center gap-1 rounded-full border border-[#d6dbe6] bg-white px-3 py-1 text-[11px] uppercase tracking-[0.14em] text-[#6b7280] dark:border-slate-800 dark:bg-slate-900 dark:text-slate-400"
          >
            {expanded ? <ChevronUp className="h-3.5 w-3.5" /> : <ChevronDown className="h-3.5 w-3.5" />}
            {expanded ? copy.monitor.hideEarlierMessages : `${copy.monitor.showEarlierMessages} ${hiddenCount}`}
          </button>
        ) : null}
      </div>

      <div className="mt-3 rounded-[14px] border border-[#d6dbe6] bg-white dark:border-slate-800 dark:bg-slate-950/70">
        <ScrollArea className="h-[324px] px-4 py-3">
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
              <div
                key={`message-${message.agent_id}-${message.timestamp}-${message.phase}`}
                className="rounded-[14px] border border-[#e5e7eb] bg-[#fbfcff] px-4 py-3 dark:border-slate-800 dark:bg-slate-900/80"
              >
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <div className="flex min-w-0 flex-wrap items-center gap-2">
                    <span className="rounded-full border border-[#d6dbe6] bg-white px-2.5 py-1 text-[10px] uppercase tracking-[0.14em] text-[#6b7280] dark:border-slate-700 dark:bg-slate-950 dark:text-slate-400">
                      {conversationEyebrow(message, copy)}
                    </span>
                    <span className="text-[12px] font-medium text-[#111111] dark:text-slate-100">{message.agent_id}</span>
                    {message.phase ? (
                      <span className="text-[11px] uppercase tracking-[0.12em] text-[#8b94a7] dark:text-slate-500">
                        {message.phase.replace(/_/g, " ")}
                      </span>
                    ) : null}
                  </div>
                  <div className="text-[11px] text-[#6b7280] dark:text-slate-500">{formatTime(message.timestamp)}</div>
                </div>
                <div className="mt-3 whitespace-pre-wrap break-words rounded-[12px] border border-[#e5e7eb] bg-white px-3 py-3 text-[13px] leading-6 text-[#273142] dark:border-slate-800 dark:bg-slate-950 dark:text-slate-300">
                  {message.content}
                </div>
              </div>
            ))}

            {visibleMessages.length === 0 && !failure ? (
              <div className="text-[14px] text-[#6b7280] dark:text-slate-500">{copy.monitor.noConversationYet}</div>
            ) : null}
          </div>
        </ScrollArea>
      </div>
    </section>
  );
}

export function EventTimeline({ events }: EventTimelineProps) {
  const { copy } = useLocale();
  const items = buildExecutionItems(events, copy);

  return (
    <section className="rounded-[18px] border border-[#d6dbe6] bg-[#f8fafc] p-4 shadow-[0_10px_24px_-18px_rgba(17,48,105,0.18)] dark:border-slate-800 dark:bg-slate-950/60 dark:shadow-none">
      <h2 className="text-[19px] font-medium tracking-[-0.03em] text-[#111111] dark:text-slate-100">
        {copy.monitor.executionTrace}
      </h2>
      <div className="mt-3 rounded-[14px] border border-[#d6dbe6] bg-white dark:border-slate-800 dark:bg-slate-950/70">
        <ScrollArea className="h-[252px] px-4 py-3">
          <div className="space-y-3">
            {items.map((item) => (
              <div
                key={item.id}
                className="rounded-[14px] border border-[#e5e7eb] bg-[#fbfcff] px-4 py-3 dark:border-slate-800 dark:bg-slate-900/80"
              >
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <div className="flex min-w-0 flex-wrap items-center gap-2">
                    <span className="rounded-full border border-[#d6dbe6] bg-white px-2.5 py-1 text-[10px] uppercase tracking-[0.14em] text-[#6b7280] dark:border-slate-700 dark:bg-slate-950 dark:text-slate-400">
                      {item.eyebrow}
                    </span>
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
                  <div className="mt-2 rounded-[12px] border border-[#e5e7eb] bg-white px-3 py-2 font-mono text-[12px] leading-6 text-[#273142] dark:border-slate-800 dark:bg-slate-950 dark:text-slate-300">
                    {item.detail}
                  </div>
                ) : null}
              </div>
            ))}
            {items.length === 0 ? (
              <div className="text-[14px] text-[#6b7280] dark:text-slate-500">{copy.monitor.traceEmpty}</div>
            ) : null}
          </div>
        </ScrollArea>
      </div>
    </section>
  );
}
