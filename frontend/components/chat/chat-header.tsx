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
    <div className="flex items-center gap-3 border-b px-6 py-3.5 bg-background">
      {Icon && (
        <div className="flex h-7 w-7 items-center justify-center rounded-md bg-muted">
          <Icon className="h-3.5 w-3.5 text-muted-foreground" />
        </div>
      )}
      <span className="text-[13px] font-medium truncate flex-1">
        {session.task.slice(0, 80)}
      </span>
      <Badge variant="outline" className="text-[10px] font-normal">
        {MODE_LABELS[session.mode]}
      </Badge>
      <Badge
        variant="outline"
        className={cn(
          "text-[10px] font-normal",
          session.status === "running" && "border-green-500/30 text-green-600 dark:text-green-400",
          session.status === "pause_requested" && "border-amber-500/30 text-amber-600 dark:text-amber-400",
          session.status === "paused" && "border-orange-500/30 text-orange-600 dark:text-orange-400",
          session.status === "cancel_requested" && "border-amber-500/30 text-amber-600 dark:text-amber-400",
          session.status === "cancelled" && "border-zinc-500/30 text-zinc-600 dark:text-zinc-400",
          session.status === "completed" && "border-blue-500/30 text-blue-600 dark:text-blue-400",
          session.status === "failed" && "border-red-500/30 text-red-600 dark:text-red-400"
        )}
      >
        {session.status}
      </Badge>
      {session.elapsed_sec !== null && (
        <span className="font-mono text-[10px] text-muted-foreground/60 tabular-nums">
          {session.elapsed_sec}s
        </span>
      )}
      {session.current_checkpoint_id && (
        <Badge variant="outline" className="text-[10px] font-normal">
          {session.current_checkpoint_id}
        </Badge>
      )}
      {session.status === "running" && (
        <Button variant="outline" size="sm" className="text-xs" onClick={handlePause} disabled={isWorking}>
          {isWorking ? <Loader2 className="mr-1.5 h-3.5 w-3.5 animate-spin" /> : <Pause className="mr-1.5 h-3.5 w-3.5" />}
          Пауза
        </Button>
      )}
      {session.status === "paused" && (
        <Button variant="outline" size="sm" className="text-xs" onClick={handleResume} disabled={isWorking}>
          {isWorking ? <Loader2 className="mr-1.5 h-3.5 w-3.5 animate-spin" /> : <Play className="mr-1.5 h-3.5 w-3.5" />}
          Продолжить
        </Button>
      )}
      {["running", "pause_requested", "paused"].includes(session.status) && (
        <Button variant="ghost" size="sm" className="text-xs text-muted-foreground" onClick={handleCancel} disabled={isWorking}>
          <Square className="mr-1.5 h-3.5 w-3.5" />
          Стоп
        </Button>
      )}
    </div>
  );
}
