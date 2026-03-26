import { AGENT_COLORS } from "@/lib/constants";
import type { Message as MessageType } from "@/lib/types";

interface MessageProps {
  message: MessageType;
}

function resolveProvider(agentId: string): string {
  const lower = agentId.toLowerCase();
  for (const key of ["claude", "codex", "gemini", "minimax", "user"]) {
    if (lower.includes(key)) return key;
  }
  if (["director", "proponent", "critic", "planner", "synthesizer"].some((r) => lower.includes(r)))
    return "claude";
  if (["creator", "opponent", "worker"].some((r) => lower.includes(r)))
    return "codex";
  if (["judge", "analyst"].some((r) => lower.includes(r)))
    return "gemini";
  return "system";
}

export function Message({ message }: MessageProps) {
  const provider = resolveProvider(message.agent_id);
  const color = AGENT_COLORS[provider] ?? AGENT_COLORS.system;

  return (
    <div
      className="rounded-xl bg-bg-card border border-border px-4 py-3 mb-3"
      style={{ borderLeftWidth: "2px", borderLeftColor: color }}
    >
      <div className="flex items-center gap-2 mb-1.5">
        <div
          className="h-1.5 w-1.5 rounded-full flex-shrink-0"
          style={{ backgroundColor: color }}
        />
        <span
          className="font-mono text-[11px] font-medium"
          style={{ color }}
        >
          {message.agent_id}
        </span>
        {message.phase && (
          <span className="font-mono text-[10px] text-text-muted">
            {message.phase}
          </span>
        )}
      </div>
      <div className="text-sm text-text-secondary leading-relaxed whitespace-pre-wrap">
        {message.content}
      </div>
    </div>
  );
}
