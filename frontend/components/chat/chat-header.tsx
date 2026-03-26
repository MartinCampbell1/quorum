import { ChevronDown, UserCircle2 } from "lucide-react";

import type { Session } from "@/lib/types";

interface ChatHeaderProps {
  session: Session;
  onOpenHome?: () => void;
  onOpenSessions?: () => void;
}

export function ChatHeader({ session, onOpenHome, onOpenSessions }: ChatHeaderProps) {
  const title = session.task.length > 56 ? `${session.task.slice(0, 56)}…` : session.task;

  return (
    <div className="flex items-center justify-between px-6 py-4">
      <div>
        <div className="text-[22px] font-medium tracking-[-0.03em] text-[#111111]">
          Premium Session Monitor - White Edition: {title}
        </div>
        <div className="mt-1 flex items-center gap-3 text-[11px] uppercase tracking-[0.14em] text-[#6b7280]">
          <span>{session.mode}</span>
          {session.active_scenario ? <span>scenario: {session.active_scenario}</span> : null}
          {session.forked_from ? <span>branch of {session.forked_from}</span> : null}
        </div>
      </div>
      <div className="flex items-center gap-5">
        <button
          type="button"
          onClick={onOpenHome}
          className="rounded-[10px] bg-[#edf0f5] px-4 py-2 text-[18px] text-[#111111]"
        >
          Home
        </button>
        <button type="button" className="text-[18px] text-[#6b7280]">
          Agents
        </button>
        <button
          type="button"
          onClick={onOpenSessions}
          className="text-[18px] text-[#6b7280]"
        >
          Sessions
        </button>
        <button
          type="button"
          className="flex h-10 w-10 items-center justify-center rounded-full bg-[#eef1f5] text-[#6b7280]"
        >
          <UserCircle2 className="h-6 w-6" />
        </button>
        <ChevronDown className="h-5 w-5 text-[#6b7280]" />
      </div>
    </div>
  );
}
