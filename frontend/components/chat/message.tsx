import { Badge } from "@/components/ui/badge";
import { AGENT_COLORS } from "@/lib/constants";
import type { Message as MessageType } from "@/lib/types";

interface MessageProps {
  message: MessageType;
}

function resolveProvider(agentId: string): string {
  const l = agentId.toLowerCase();
  for (const k of ["claude", "codex", "gemini", "minimax", "user"]) {
    if (l.includes(k)) return k;
  }
  if (["director", "proponent", "critic", "planner", "synthesizer"].some(r => l.includes(r))) return "claude";
  if (["creator", "opponent", "worker"].some(r => l.includes(r))) return "codex";
  if (["judge", "analyst"].some(r => l.includes(r))) return "gemini";
  return "system";
}

export function Message({ message }: MessageProps) {
  const provider = resolveProvider(message.agent_id);
  const color = AGENT_COLORS[provider] ?? AGENT_COLORS.system;

  return (
    <div
      className="mb-3 overflow-hidden rounded-[24px] border border-slate-200/80 bg-[linear-gradient(180deg,rgba(255,255,255,0.94),rgba(248,250,252,0.9))] px-5 py-4 shadow-[0_18px_55px_-42px_rgba(15,23,42,0.5)] transition-shadow hover:shadow-[0_22px_70px_-42px_rgba(15,23,42,0.56)] dark:border-slate-800/80 dark:bg-[linear-gradient(180deg,rgba(15,23,42,0.82),rgba(2,6,23,0.78))]"
      style={{ boxShadow: `inset 3px 0 0 0 ${color}` }}
    >
      <div className="mb-3 flex items-center gap-2">
        <div className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full border border-slate-200/80 bg-white/85 dark:border-slate-800 dark:bg-slate-900/70">
          <div
            className="h-2.5 w-2.5 rounded-full"
            style={{ backgroundColor: color }}
          />
        </div>
        <span className="font-mono text-[11px] font-semibold" style={{ color }}>
          {message.agent_id}
        </span>
        {message.phase && (
          <Badge variant="outline" className="border-slate-200/80 bg-white/80 px-2 py-0 text-[9px] font-normal text-muted-foreground dark:border-slate-800 dark:bg-slate-900/60">
            {message.phase}
          </Badge>
        )}
      </div>
      <p className="whitespace-pre-wrap pl-9 text-[13px] leading-relaxed text-foreground/80">
        {message.content}
      </p>
    </div>
  );
}
