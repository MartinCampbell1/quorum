import { Badge } from "@/components/common/badge";
import { MODE_ICONS } from "@/lib/constants";
import type { SessionSummary } from "@/lib/types";

interface SessionItemProps {
  session: SessionSummary;
  isActive: boolean;
  onClick: () => void;
}

function timeAgo(ts: number): string {
  const diff = Math.floor(Date.now() / 1000 - ts);
  if (diff < 60) return "just now";
  if (diff < 3600) return `${Math.floor(diff / 60)}m ago`;
  if (diff < 86400) return `${Math.floor(diff / 3600)}h ago`;
  return `${Math.floor(diff / 86400)}d ago`;
}

export function SessionItem({ session, isActive, onClick }: SessionItemProps) {
  const Icon = MODE_ICONS[session.mode];
  return (
    <button
      onClick={onClick}
      className={`w-full rounded-lg px-3 py-2.5 text-left transition-colors cursor-pointer ${
        isActive
          ? "bg-bg-card border-l-2 border-l-accent"
          : "hover:bg-bg-card/50"
      }`}
    >
      <div className="flex items-center gap-2">
        {Icon && <Icon size={12} className="text-text-muted flex-shrink-0" />}
        <span className="truncate text-xs font-medium text-text-primary">
          {session.task.slice(0, 40)}
        </span>
      </div>
      <div className="mt-1 flex items-center gap-2">
        <span className="font-mono text-[10px] text-text-muted">
          {timeAgo(session.created_at)}
        </span>
        <Badge
          label={session.status}
          variant={
            session.status === "completed"
              ? "success"
              : session.status === "failed"
                ? "error"
                : "accent"
          }
        />
      </div>
    </button>
  );
}
