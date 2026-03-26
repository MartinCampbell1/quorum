"use client";

import { Badge } from "@/components/ui/badge";
import { Clock } from "lucide-react";
import { MODE_LABELS, MODE_ICONS } from "@/lib/constants";
import { useSessions } from "@/hooks/use-sessions";
import { cn } from "@/lib/utils";

interface HistoryViewProps {
  onSelectSession: (id: string) => void;
}

function timeAgo(ts: number): string {
  const diff = Math.floor(Date.now() / 1000 - ts);
  if (diff < 60) return "только что";
  if (diff < 3600) return `${Math.floor(diff / 60)} мин назад`;
  if (diff < 86400) return `${Math.floor(diff / 3600)} ч назад`;
  return `${Math.floor(diff / 86400)} д назад`;
}

const STATUS_LABELS: Record<string, string> = {
  running: "работает",
  pause_requested: "ставим на паузу",
  paused: "на паузе",
  cancel_requested: "останавливаем",
  cancelled: "остановлено",
  completed: "готово",
  failed: "ошибка",
};

export function HistoryView({ onSelectSession }: HistoryViewProps) {
  const { sessions, isLoading } = useSessions();

  return (
    <div className="flex flex-col h-full">
      <div className="border-b bg-background px-8 py-4">
        <h2 className="text-lg font-semibold tracking-tight">История сессий</h2>
        <p className="text-sm text-muted-foreground mt-0.5">
          {sessions.length} {sessions.length === 1 ? "сессия" : sessions.length < 5 ? "сессии" : "сессий"}
        </p>
      </div>
      <div className="flex-1 overflow-y-auto px-8 py-4">
        {isLoading ? (
          <div className="flex items-center justify-center py-20">
            <div className="h-1.5 w-1.5 rounded-full bg-muted-foreground/40 animate-pulse" />
          </div>
        ) : sessions.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-20 text-muted-foreground">
            <Clock className="h-8 w-8 mb-3 opacity-30" />
            <p className="text-sm">Пока нет сессий</p>
          </div>
        ) : (
          <div className="space-y-2 max-w-2xl">
            {sessions.map((s) => {
              const Icon = MODE_ICONS[s.mode];
              return (
                <button
                  key={s.id}
                  onClick={() => onSelectSession(s.id)}
                  className="w-full flex items-center gap-4 rounded-xl border border-border p-4 text-left transition-all hover:shadow-sm hover:border-foreground/20 cursor-pointer group"
                >
                  <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-muted text-muted-foreground group-hover:bg-foreground/10 transition-colors">
                    {Icon && <Icon size={16} strokeWidth={1.5} />}
                  </div>
                  <div className="flex-1 min-w-0">
                    <p className="text-sm font-medium truncate">{s.task}</p>
                    <div className="flex items-center gap-2 mt-1">
                      <span className="text-[11px] text-muted-foreground/60 font-mono">{timeAgo(s.created_at)}</span>
                      <Badge variant="outline" className="text-[10px] px-1.5 py-0 font-normal">
                        {MODE_LABELS[s.mode]}
                      </Badge>
                    </div>
                  </div>
                  <Badge
                    variant="outline"
                    className={cn(
                      "text-[10px] px-1.5 py-0 font-normal shrink-0",
                      s.status === "running" && "border-green-500/30 text-green-600",
                      s.status === "pause_requested" && "border-amber-500/30 text-amber-600",
                      s.status === "paused" && "border-orange-500/30 text-orange-600",
                      s.status === "cancel_requested" && "border-amber-500/30 text-amber-600",
                      s.status === "cancelled" && "border-zinc-500/30 text-zinc-600",
                      s.status === "completed" && "border-foreground/20 text-foreground/50",
                      s.status === "failed" && "border-red-500/30 text-red-600"
                    )}
                  >
                    {STATUS_LABELS[s.status] ?? s.status}
                  </Badge>
                </button>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}
