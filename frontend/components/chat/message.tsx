import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { AGENT_COLORS } from "@/lib/constants";
import type { Message as MessageType } from "@/lib/types";

interface MessageProps { message: MessageType; }

function resolveProvider(agentId: string): string {
  const l = agentId.toLowerCase();
  for (const k of ["claude", "codex", "gemini", "minimax", "user"]) if (l.includes(k)) return k;
  if (["director","proponent","critic","planner","synthesizer"].some(r => l.includes(r))) return "claude";
  if (["creator","opponent","worker"].some(r => l.includes(r))) return "codex";
  if (["judge","analyst"].some(r => l.includes(r))) return "gemini";
  return "system";
}

export function Message({ message }: MessageProps) {
  const provider = resolveProvider(message.agent_id);
  const color = AGENT_COLORS[provider] ?? AGENT_COLORS.system;

  return (
    <Card className="mb-3" style={{ borderLeftWidth: "3px", borderLeftColor: color }}>
      <CardContent className="p-4">
        <div className="flex items-center gap-2 mb-2">
          <div className="h-2 w-2 rounded-full" style={{ backgroundColor: color }} />
          <span className="font-mono text-xs font-medium" style={{ color }}>{message.agent_id}</span>
          {message.phase && <Badge variant="outline" className="text-[9px] px-1 py-0">{message.phase}</Badge>}
        </div>
        <p className="text-sm text-muted-foreground leading-relaxed whitespace-pre-wrap">{message.content}</p>
      </CardContent>
    </Card>
  );
}
