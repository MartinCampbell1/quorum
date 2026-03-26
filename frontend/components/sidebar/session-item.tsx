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
        "group mb-2 w-full rounded-2xl border px-3.5 py-3 text-left transition-all duration-200 cursor-pointer",
        isActive
          ? "border-slate-900 bg-slate-950 text-white shadow-[0_18px_40px_-28px_rgba(15,23,42,0.88)] dark:border-slate-200 dark:bg-slate-100 dark:text-slate-950"
          : "border-slate-200/80 bg-white/80 hover:-translate-y-0.5 hover:border-slate-300 hover:bg-white hover:shadow-[0_16px_32px_-28px_rgba(15,23,42,0.5)] dark:border-slate-800 dark:bg-slate-900/65 dark:hover:border-slate-700"
      )}
    >
      <div className="flex items-center gap-2.5">
        {Icon && (
          <Icon className={cn(
            "h-3.5 w-3.5 shrink-0 transition-colors",
            isActive ? "text-current" : "text-muted-foreground"
          )} />
        )}
        <span className={cn(
          "truncate text-sm leading-tight",
          isActive ? "font-medium text-current" : "text-foreground/78 dark:text-slate-200"
        )}>
          {session.task.slice(0, 40)}
        </span>
      </div>
      <div className="mt-2 pl-6 flex items-center gap-2">
        <span className={cn("font-mono text-[11px]", isActive ? "text-current/58" : "text-muted-foreground/60")}>
          {timeAgo(session.created_at)}
        </span>
        <Badge
          variant="outline"
          className={cn(
            "text-[10px] px-1.5 py-0 font-normal backdrop-blur-sm",
            isActive && "border-current/10 bg-current/5 text-current/75",
            !isActive && session.status === "running" && "border-green-500/30 text-green-600 dark:text-green-400",
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
