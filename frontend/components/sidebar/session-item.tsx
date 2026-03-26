import { Badge } from "@/components/ui/badge";
import { MODE_ICONS } from "@/lib/constants";
import { cn } from "@/lib/utils";
import type { SessionSummary } from "@/lib/types";

interface SessionItemProps {
  session: SessionSummary;
  isActive: boolean;
  onClick: () => void;
}

function timeAgo(ts: number): string {
  const diff = Math.floor(Date.now() / 1000 - ts);
  if (diff < 60) return "now";
  if (diff < 3600) return `${Math.floor(diff / 60)}m`;
  if (diff < 86400) return `${Math.floor(diff / 3600)}h`;
  return `${Math.floor(diff / 86400)}d`;
}

export function SessionItem({ session, isActive, onClick }: SessionItemProps) {
  const Icon = MODE_ICONS[session.mode];
  return (
    <button
      onClick={onClick}
      className={cn(
        "w-full rounded-md px-3 py-2 text-left transition-colors cursor-pointer mb-0.5",
        isActive ? "bg-accent" : "hover:bg-accent/50"
      )}
    >
      <div className="flex items-center gap-2">
        {Icon && <Icon className="h-3 w-3 text-muted-foreground shrink-0" />}
        <span className={cn("truncate text-xs", isActive ? "font-medium" : "text-muted-foreground")}>
          {session.task.slice(0, 30)}
        </span>
      </div>
      <div className="mt-1 pl-5 flex items-center gap-2">
        <span className="font-mono text-[10px] text-muted-foreground">{timeAgo(session.created_at)}</span>
        <Badge variant="outline" className="text-[9px] px-1 py-0">{session.status}</Badge>
      </div>
    </button>
  );
}
