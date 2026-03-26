import { Badge } from "@/components/ui/badge";
import { Separator } from "@/components/ui/separator";
import { MODE_LABELS, MODE_ICONS } from "@/lib/constants";
import type { Session } from "@/lib/types";

interface ChatHeaderProps { session: Session; }

export function ChatHeader({ session }: ChatHeaderProps) {
  const Icon = MODE_ICONS[session.mode];
  return (
    <div className="flex items-center gap-3 border-b px-5 py-3">
      {Icon && <Icon className="h-4 w-4 text-muted-foreground" />}
      <span className="text-sm font-semibold truncate">{session.task.slice(0, 60)}</span>
      <Badge variant="outline">{MODE_LABELS[session.mode]}</Badge>
      <Badge variant={session.status === "completed" ? "default" : session.status === "failed" ? "destructive" : "secondary"}>
        {session.status}
      </Badge>
      {session.elapsed_sec !== null && (
        <span className="ml-auto font-mono text-[10px] text-muted-foreground">{session.elapsed_sec}s</span>
      )}
    </div>
  );
}
