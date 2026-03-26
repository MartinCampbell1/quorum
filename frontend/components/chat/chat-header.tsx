import { useState } from "react";
import { Loader2, Pause, Play, Square } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { controlSession } from "@/lib/api";
import { MODE_LABELS, MODE_ICONS } from "@/lib/constants";
import { cn } from "@/lib/utils";
import type { Session } from "@/lib/types";

interface ChatHeaderProps {
  session: Session;
  onRefresh?: () => void;
}

export function ChatHeader({ session, onRefresh }: ChatHeaderProps) {
  const Icon = MODE_ICONS[session.mode];
  const [isWorking, setIsWorking] = useState(false);
  const statusTone = cn(
    "border-slate-200/80 bg-white/80 text-slate-700 dark:border-slate-800 dark:bg-slate-900/70 dark:text-slate-300",
    session.status === "running" && "border-emerald-200 bg-emerald-50 text-emerald-700 dark:border-emerald-900/60 dark:bg-emerald-950/30 dark:text-emerald-300",
    session.status === "pause_requested" && "border-amber-200 bg-amber-50 text-amber-700 dark:border-amber-900/60 dark:bg-amber-950/30 dark:text-amber-300",
    session.status === "paused" && "border-orange-200 bg-orange-50 text-orange-700 dark:border-orange-900/60 dark:bg-orange-950/30 dark:text-orange-300",
    session.status === "cancel_requested" && "border-amber-200 bg-amber-50 text-amber-700 dark:border-amber-900/60 dark:bg-amber-950/30 dark:text-amber-300",
    session.status === "cancelled" && "border-zinc-200 bg-zinc-50 text-zinc-700 dark:border-zinc-800 dark:bg-zinc-950/30 dark:text-zinc-300",
    session.status === "completed" && "border-sky-200 bg-sky-50 text-sky-700 dark:border-sky-900/60 dark:bg-sky-950/30 dark:text-sky-300",
    session.status === "failed" && "border-rose-200 bg-rose-50 text-rose-700 dark:border-rose-900/60 dark:bg-rose-950/30 dark:text-rose-300"
  );

  async function handlePause() {
    setIsWorking(true);
    try {
      await controlSession(session.id, "pause");
      await onRefresh?.();
    } finally {
      setIsWorking(false);
    }
  }

  async function handleResume() {
    setIsWorking(true);
    try {
      await controlSession(session.id, "resume");
      await onRefresh?.();
    } finally {
      setIsWorking(false);
    }
  }

  async function handleCancel() {
    setIsWorking(true);
    try {
      await controlSession(session.id, "cancel");
      await onRefresh?.();
    } finally {
      setIsWorking(false);
    }
  }

  return (
    <div className="border-b border-slate-200/70 bg-white/75 px-6 py-4 backdrop-blur-md dark:border-slate-800/70 dark:bg-slate-950/45">
      <div className="flex flex-wrap items-center gap-3">
        <div className="flex min-w-0 flex-1 items-center gap-3">
          {Icon && (
            <div className="flex h-11 w-11 items-center justify-center rounded-2xl border border-slate-200/80 bg-[linear-gradient(135deg,rgba(255,255,255,0.96),rgba(241,245,249,0.92))] shadow-sm dark:border-slate-800 dark:bg-[linear-gradient(135deg,rgba(15,23,42,0.94),rgba(30,41,59,0.72))]">
              <Icon className="h-4 w-4 text-slate-600 dark:text-slate-300" />
            </div>
          )}
          <div className="min-w-0">
            <p className="text-[10px] font-semibold uppercase tracking-[0.2em] text-[#445d99] dark:text-sky-300">
              Session Monitor
            </p>
            <p className="mt-1 truncate text-sm font-semibold text-slate-950 dark:text-slate-50">
              {session.task}
            </p>
          </div>
        </div>

        <div className="flex flex-wrap items-center gap-2">
          <Badge variant="outline" className="border-slate-200/80 bg-white/85 text-[10px] font-medium text-slate-600 dark:border-slate-800 dark:bg-slate-900/70 dark:text-slate-300">
            {MODE_LABELS[session.mode]}
          </Badge>
          <Badge variant="outline" className={cn("text-[10px] font-medium", statusTone)}>
            {session.status}
          </Badge>
          {session.elapsed_sec !== null && (
            <div className="rounded-full border border-slate-200/80 bg-white/85 px-3 py-1 font-mono text-[10px] tabular-nums text-slate-500 dark:border-slate-800 dark:bg-slate-900/70 dark:text-slate-400">
              {session.elapsed_sec}s
            </div>
          )}
          {session.current_checkpoint_id && (
            <div className="rounded-full border border-slate-200/80 bg-white/85 px-3 py-1 font-mono text-[10px] text-slate-500 dark:border-slate-800 dark:bg-slate-900/70 dark:text-slate-400">
              {session.current_checkpoint_id}
            </div>
          )}
        </div>

        <div className="ml-auto flex items-center gap-2">
          {session.status === "running" && (
            <Button variant="outline" size="sm" className="rounded-full border-slate-200/80 bg-white/85 text-xs dark:border-slate-800 dark:bg-slate-900/70" onClick={handlePause} disabled={isWorking}>
              {isWorking ? <Loader2 className="mr-1.5 h-3.5 w-3.5 animate-spin" /> : <Pause className="mr-1.5 h-3.5 w-3.5" />}
              Пауза
            </Button>
          )}
          {session.status === "paused" && (
            <Button size="sm" className="rounded-full bg-slate-950 text-xs text-white hover:bg-slate-800 dark:bg-slate-100 dark:text-slate-950 dark:hover:bg-white" onClick={handleResume} disabled={isWorking}>
              {isWorking ? <Loader2 className="mr-1.5 h-3.5 w-3.5 animate-spin" /> : <Play className="mr-1.5 h-3.5 w-3.5" />}
              Продолжить
            </Button>
          )}
          {["running", "pause_requested", "paused"].includes(session.status) && (
            <Button variant="ghost" size="sm" className="rounded-full text-xs text-muted-foreground" onClick={handleCancel} disabled={isWorking}>
              <Square className="mr-1.5 h-3.5 w-3.5" />
              Стоп
            </Button>
          )}
        </div>
      </div>
    </div>
  );
}
