"use client";

import {
  AlertTriangle,
  Bot,
  CheckCircle2,
  CircleStop,
  Flag,
  PauseCircle,
  PlayCircle,
  Waypoints,
} from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { ScrollArea } from "@/components/ui/scroll-area";
import { cn } from "@/lib/utils";
import type { SessionEvent } from "@/lib/types";

interface EventTimelineProps {
  events: SessionEvent[];
  activeNode?: string | null;
  pendingInstructions?: number;
}

const EVENT_STYLES: Record<
  string,
  {
    icon: typeof Bot;
    accent: string;
    tone: string;
  }
> = {
  run_started: {
    icon: Flag,
    accent: "text-sky-700 dark:text-sky-300",
    tone: "border-sky-500/20 bg-sky-500/5",
  },
  branch_started: {
    icon: Flag,
    accent: "text-indigo-700 dark:text-indigo-300",
    tone: "border-indigo-500/20 bg-indigo-500/5",
  },
  checkpoint_created: {
    icon: Waypoints,
    accent: "text-violet-700 dark:text-violet-300",
    tone: "border-violet-500/20 bg-violet-500/5",
  },
  agent_message: {
    icon: Bot,
    accent: "text-foreground/80",
    tone: "border-border/70 bg-background",
  },
  instruction_queued: {
    icon: PauseCircle,
    accent: "text-amber-700 dark:text-amber-300",
    tone: "border-amber-500/20 bg-amber-500/5",
  },
  instruction_applied: {
    icon: PlayCircle,
    accent: "text-emerald-700 dark:text-emerald-300",
    tone: "border-emerald-500/20 bg-emerald-500/5",
  },
  pause_requested: {
    icon: PauseCircle,
    accent: "text-amber-700 dark:text-amber-300",
    tone: "border-amber-500/20 bg-amber-500/5",
  },
  run_paused: {
    icon: PauseCircle,
    accent: "text-orange-700 dark:text-orange-300",
    tone: "border-orange-500/20 bg-orange-500/5",
  },
  run_resumed: {
    icon: PlayCircle,
    accent: "text-emerald-700 dark:text-emerald-300",
    tone: "border-emerald-500/20 bg-emerald-500/5",
  },
  cancel_requested: {
    icon: CircleStop,
    accent: "text-amber-700 dark:text-amber-300",
    tone: "border-amber-500/20 bg-amber-500/5",
  },
  run_cancelled: {
    icon: CircleStop,
    accent: "text-zinc-700 dark:text-zinc-300",
    tone: "border-zinc-500/20 bg-zinc-500/5",
  },
  run_completed: {
    icon: CheckCircle2,
    accent: "text-emerald-700 dark:text-emerald-300",
    tone: "border-emerald-500/20 bg-emerald-500/5",
  },
  run_failed: {
    icon: AlertTriangle,
    accent: "text-red-700 dark:text-red-300",
    tone: "border-red-500/20 bg-red-500/5",
  },
};

function formatTime(timestamp: number): string {
  return new Date(timestamp * 1000).toLocaleTimeString([], {
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  });
}

function summarizeDetail(detail: string): string {
  if (!detail) {
    return "";
  }
  return detail.length > 260 ? `${detail.slice(0, 257)}...` : detail;
}

export function EventTimeline({
  events,
  activeNode = null,
  pendingInstructions = 0,
}: EventTimelineProps) {
  return (
    <Card className="h-full overflow-hidden rounded-[18px] border border-[#e2e8f0] bg-white shadow-[0_4px_6px_-1px_rgba(17,48,105,0.04),0_2px_4px_-1px_rgba(17,48,105,0.02)] dark:border-slate-800/80 dark:bg-[linear-gradient(180deg,rgba(15,23,42,0.94),rgba(2,6,23,0.9))]">
      <CardHeader className="border-b border-[#e2e8f0]/70 pb-4 dark:border-slate-800/70">
        <div className="flex items-start justify-between gap-3">
          <div>
            <CardTitle className="text-sm tracking-tight text-[#09090b] dark:text-white">Execution Trace</CardTitle>
            <p className="mt-1 text-[12px] leading-relaxed text-[#445d99] dark:text-slate-300">
              Контрольные точки, статусы и сообщения агентов в реальном времени.
            </p>
          </div>
          <Badge variant="outline" className="border-[#e2e8f0] bg-white text-[10px] font-normal shadow-none dark:border-slate-800 dark:bg-slate-900">
            {events.length} events
          </Badge>
        </div>
        <div className="flex flex-wrap gap-2 pt-1">
          {activeNode && (
            <Badge variant="outline" className="border-[#e2e8f0] bg-white text-[10px] font-normal dark:border-slate-800 dark:bg-slate-900">
              next: {activeNode}
            </Badge>
          )}
          {pendingInstructions > 0 && (
            <Badge variant="outline" className="border-[#e2e8f0] bg-white text-[10px] font-normal text-orange-700 dark:border-slate-800 dark:bg-slate-900 dark:text-orange-300">
              queued: {pendingInstructions}
            </Badge>
          )}
        </div>
      </CardHeader>
      <CardContent className="min-h-0 flex-1 px-0 pb-0">
        <ScrollArea className="h-[calc(100vh-16.5rem)] px-4 pb-4">
          {events.length === 0 ? (
            <div className="px-1 py-6 text-[12px] leading-relaxed text-muted-foreground">
              События появятся после старта сессии.
            </div>
          ) : (
            <div className="relative space-y-3 py-4">
              <div className="absolute bottom-0 left-[14px] top-4 w-px bg-[linear-gradient(180deg,rgba(152,177,242,0.38),rgba(17,48,105,0.08))] dark:bg-[linear-gradient(180deg,rgba(71,85,105,0.58),rgba(15,23,42,0.08))]" />
              {events.map((event) => {
                const style = EVENT_STYLES[event.type] ?? EVENT_STYLES.agent_message;
                const Icon = style.icon;
                return (
                  <div key={event.id} className="relative pl-9">
                    <div
                      className={cn("absolute left-0 top-3 flex h-7 w-7 items-center justify-center rounded-full border bg-white dark:bg-slate-950", style.tone)}
                    >
                      <Icon className={cn("h-3.5 w-3.5", style.accent)} />
                    </div>
                    <div className={cn("rounded-[14px] border px-4 py-3 shadow-[0_4px_6px_-1px_rgba(17,48,105,0.04),0_2px_4px_-1px_rgba(17,48,105,0.02)]", style.tone)}>
                      <div className="flex items-start justify-between gap-3">
                        <div className="min-w-0">
                          <p className="text-[12px] font-medium text-foreground/90">
                            {event.title}
                          </p>
                          {event.agent_id && (
                            <p className="mt-1 text-[11px] uppercase tracking-[0.14em] text-muted-foreground">
                              {event.agent_id}
                            </p>
                          )}
                        </div>
                        <span className="shrink-0 font-mono text-[10px] text-muted-foreground">
                          {formatTime(event.timestamp)}
                        </span>
                      </div>
                      {event.detail && (
                        <p className="mt-2 whitespace-pre-wrap text-[12px] leading-relaxed text-foreground/75">
                          {summarizeDetail(event.detail)}
                        </p>
                      )}
                      <div className="mt-3 flex flex-wrap gap-2">
                        <Badge variant="outline" className="text-[10px] font-normal">
                          {event.type}
                        </Badge>
                        {event.phase && (
                          <Badge variant="outline" className="text-[10px] font-normal">
                            {event.phase}
                          </Badge>
                        )}
                        {event.checkpoint_id && (
                          <Badge variant="outline" className="text-[10px] font-normal">
                            {event.checkpoint_id}
                          </Badge>
                        )}
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </ScrollArea>
      </CardContent>
    </Card>
  );
}
