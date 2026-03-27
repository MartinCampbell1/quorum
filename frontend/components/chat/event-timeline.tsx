"use client";

import { ScrollArea } from "@/components/ui/scroll-area";
import { useLocale } from "@/lib/locale";
import type { Message, SessionEvent } from "@/lib/types";

interface EventTimelineProps {
  events: SessionEvent[];
  messages?: Message[];
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

function compactDetail(text: string, limit: number = 220): string {
  const normalized = text.replace(/\s+/g, " ").trim();
  if (normalized.length <= limit) {
    return normalized;
  }
  return `${normalized.slice(0, limit - 1)}…`;
}

function buildTimelineItems(
  events: SessionEvent[],
  messages: Message[],
  copy: ReturnType<typeof useLocale>["copy"]
): TimelineItem[] {
  const eventItems: TimelineItem[] = events.map((event) => {
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
  });

  const messageItems: TimelineItem[] = messages.map((message) => ({
    id: `message-${message.agent_id}-${message.timestamp}-${message.phase}`,
    timestamp: message.timestamp,
    eyebrow: copy.monitor.agentMessage,
    actor: message.agent_id,
    title: message.phase.replace(/_/g, " "),
    detail: compactDetail(message.content, 260),
  }));

  return [...eventItems, ...messageItems]
    .sort((a, b) => b.timestamp - a.timestamp)
    .slice(0, 28);
}

export function EventTimeline({ events, messages = [] }: EventTimelineProps) {
  const { copy } = useLocale();
  const items = buildTimelineItems(events, messages, copy);

  return (
    <section className="rounded-[18px] border border-[#d6dbe6] bg-[#f8fafc] p-4 shadow-[0_10px_24px_-18px_rgba(17,48,105,0.18)]">
      <h2 className="text-[19px] font-medium tracking-[-0.03em] text-[#111111]">
        {copy.monitor.executionTrace}
      </h2>
      <div className="mt-3 rounded-[14px] border border-[#d6dbe6] bg-white">
        <ScrollArea className="h-[252px] px-4 py-3">
          <div className="space-y-3">
            {items.map((item) => (
              <div
                key={item.id}
                className="rounded-[14px] border border-[#e5e7eb] bg-[#fbfcff] px-4 py-3"
              >
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <div className="flex min-w-0 flex-wrap items-center gap-2">
                    <span className="rounded-full border border-[#d6dbe6] bg-white px-2.5 py-1 text-[10px] uppercase tracking-[0.14em] text-[#6b7280]">
                      {item.eyebrow}
                    </span>
                    <span className="text-[12px] font-medium text-[#111111]">{item.actor}</span>
                    {item.meta ? (
                      <span className="text-[11px] uppercase tracking-[0.12em] text-[#8b94a7]">
                        {item.meta}
                      </span>
                    ) : null}
                  </div>
                  <div className="text-[11px] text-[#6b7280]">{formatTime(item.timestamp)}</div>
                </div>
                <div className="mt-2 text-[14px] font-medium tracking-[-0.03em] text-[#111111]">
                  {item.title}
                </div>
                {item.detail ? (
                  <div className="mt-2 rounded-[12px] border border-[#e5e7eb] bg-white px-3 py-2 font-mono text-[12px] leading-6 text-[#273142]">
                    {item.detail}
                  </div>
                ) : null}
              </div>
            ))}
            {items.length === 0 ? (
              <div className="text-[14px] text-[#6b7280]">{copy.monitor.traceEmpty}</div>
            ) : null}
          </div>
        </ScrollArea>
      </div>
    </section>
  );
}
