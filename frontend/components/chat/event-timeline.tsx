"use client";

import { ScrollArea } from "@/components/ui/scroll-area";
import type { SessionEvent } from "@/lib/types";

interface EventTimelineProps {
  events: SessionEvent[];
}

function formatTime(timestamp: number): string {
  return new Date(timestamp * 1000).toLocaleTimeString([], {
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  });
}

function formatEventLine(event: SessionEvent): string {
  const actor = event.agent_id ? `${event.agent_id} | ` : "";
  const detail = event.detail ? ` ${event.detail}` : "";
  const phase = event.phase ? ` | ${event.phase}` : "";
  const checkpoint = event.checkpoint_id ? ` | ${event.checkpoint_id}` : "";
  return `${actor}${event.title}${phase}${checkpoint}${detail}`.trim();
}

export function EventTimeline({ events }: EventTimelineProps) {
  return (
    <section className="rounded-[18px] border border-[#d6dbe6] bg-[#f8fafc] p-4 shadow-[0_10px_24px_-18px_rgba(17,48,105,0.18)]">
      <h2 className="text-[19px] font-medium tracking-[-0.03em] text-[#111111]">
        Execution Trace
      </h2>
      <div className="mt-3 rounded-[14px] border border-[#d6dbe6] bg-white">
        <ScrollArea className="h-[228px] px-4 py-3">
          <div className="space-y-4 font-mono text-[12px] leading-6 text-[#111111]">
            {events.map((event) => (
              <div key={event.id}>
                <span className="text-[#6b7280]">{formatTime(event.timestamp)}</span>
                {" | "}
                <span>{formatEventLine(event)}</span>
              </div>
            ))}
            {events.length === 0 ? (
              <div className="text-[#6b7280]">Trace will appear after the session starts.</div>
            ) : null}
          </div>
        </ScrollArea>
      </div>
    </section>
  );
}
