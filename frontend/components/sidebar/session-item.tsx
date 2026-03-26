import { MODE_ICONS } from "@/lib/constants";
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
      className="w-full rounded-lg px-3 py-2 text-left transition-colors cursor-pointer mb-0.5"
      style={{ background: isActive ? "#161616" : "transparent" }}
    >
      <div className="flex items-center gap-2">
        {Icon && <Icon size={12} strokeWidth={1.5} style={{ color: "#555" }} />}
        <span
          className="truncate text-[13px]"
          style={{ color: isActive ? "#ccc" : "#888", fontWeight: isActive ? 500 : 400 }}
        >
          {session.task.slice(0, 30)}
        </span>
      </div>
      <div className="mt-1 pl-5 flex items-center gap-2">
        <span className="font-mono text-[10px]" style={{ color: "#444" }}>
          {timeAgo(session.created_at)}
        </span>
        <span className="font-mono text-[10px] uppercase" style={{ color: "#555" }}>
          {session.status}
        </span>
      </div>
    </button>
  );
}
