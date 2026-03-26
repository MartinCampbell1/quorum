import { Badge } from "@/components/common/badge";
import { MODE_LABELS, MODE_ICONS } from "@/lib/constants";
import type { Session } from "@/lib/types";

interface ChatHeaderProps {
  session: Session;
}

export function ChatHeader({ session }: ChatHeaderProps) {
  const Icon = MODE_ICONS[session.mode];
  const statusVariant =
    session.status === "completed"
      ? "success"
      : session.status === "failed"
        ? "error"
        : "accent";

  return (
    <div className="flex items-center gap-3 border-b border-border px-5 py-3">
      {Icon && <Icon size={14} className="text-text-muted" />}
      <span className="text-sm font-semibold text-text-primary truncate">
        {session.task.slice(0, 60)}
      </span>
      <Badge label={MODE_LABELS[session.mode] ?? session.mode} />
      <Badge label={session.status} variant={statusVariant} />
      {session.elapsed_sec !== null && (
        <span className="ml-auto font-mono text-[10px] text-text-muted">
          {session.elapsed_sec}s
        </span>
      )}
    </div>
  );
}
