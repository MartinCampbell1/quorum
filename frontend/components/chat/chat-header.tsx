import { Badge } from "@/components/ui/badge";
import { MODE_LABELS, MODE_ICONS } from "@/lib/constants";
import { cn } from "@/lib/utils";
import type { Session } from "@/lib/types";

interface ChatHeaderProps {
  session: Session;
}

export function ChatHeader({ session }: ChatHeaderProps) {
  const Icon = MODE_ICONS[session.mode];

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
    </div>
  );
}
