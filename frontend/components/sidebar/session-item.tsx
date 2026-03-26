import { Badge } from "@/components/ui/badge";
import { MODE_ICONS } from "@/lib/constants";
import { cn } from "@/lib/utils";
import type { SessionSummary } from "@/lib/types";

interface SessionItemProps {
  session: SessionSummary;
  isActive: boolean;
  onClick: () => void;
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

function timeAgo(ts: number): string {
  const diff = Math.floor(Date.now() / 1000 - ts);
  if (diff < 60) return "сейчас";
  if (diff < 3600) return `${Math.floor(diff / 60)} мин`;
  if (diff < 86400) return `${Math.floor(diff / 3600)} ч`;
  return `${Math.floor(diff / 86400)} д`;
}

export function SessionItem({ session, isActive, onClick }: SessionItemProps) {
  const Icon = MODE_ICONS[session.mode];

  return (
    <button
      onClick={onClick}
      className={cn(
        "group w-full rounded-lg px-3 py-2.5 text-left transition-all duration-150 cursor-pointer mb-0.5",
        isActive
          ? "bg-accent shadow-sm"
          : "hover:bg-accent/50"
      )}
    >
      <div className="flex items-center gap-2.5">
        {Icon && (
          <Icon className={cn(
            "h-3.5 w-3.5 shrink-0 transition-colors",
            isActive ? "text-foreground" : "text-muted-foreground"
          )} />
        )}
        <span className={cn(
          "truncate text-sm leading-tight",
          isActive ? "font-medium text-foreground" : "text-muted-foreground"
        )}>
          {session.task.slice(0, 40)}
        </span>
      </div>
      <div className="mt-1.5 pl-6 flex items-center gap-2">
        <span className="font-mono text-[11px] text-muted-foreground/60">
          {timeAgo(session.created_at)}
        </span>
        <Badge
          variant="outline"
          className={cn(
            "text-[10px] px-1.5 py-0 font-normal",
            session.status === "running" && "border-green-500/30 text-green-600 dark:text-green-400",
            session.status === "pause_requested" && "border-amber-500/30 text-amber-600 dark:text-amber-400",
            session.status === "paused" && "border-orange-500/30 text-orange-600 dark:text-orange-400",
            session.status === "cancel_requested" && "border-amber-500/30 text-amber-600 dark:text-amber-400",
            session.status === "cancelled" && "border-zinc-500/30 text-zinc-600 dark:text-zinc-400",
            session.status === "failed" && "border-red-500/30 text-red-600 dark:text-red-400"
          )}
        >
          {STATUS_LABELS[session.status] ?? session.status}
        </Badge>
      </div>
    </button>
  );
}
