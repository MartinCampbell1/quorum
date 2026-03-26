"use client";

import { Plus } from "lucide-react";
import { useSessions } from "@/hooks/use-sessions";
import { SessionItem } from "./session-item";

interface SessionListProps {
  activeSessionId: string | null;
  onSelectSession: (id: string) => void;
  onNewSession: () => void;
}

export function SessionList({
  activeSessionId,
  onSelectSession,
  onNewSession,
}: SessionListProps) {
  const { sessions, isLoading } = useSessions();

  return (
    <div className="flex h-full w-60 flex-col border-r border-border bg-bg-secondary">
      <div className="flex items-center justify-between px-4 py-3">
        <span className="text-[10px] font-semibold uppercase tracking-widest text-text-muted">
          Sessions
        </span>
        <button
          onClick={onNewSession}
          className="flex h-6 w-6 items-center justify-center rounded-md bg-bg-card text-text-muted hover:bg-accent hover:text-white transition-colors cursor-pointer"
          aria-label="New session"
        >
          <Plus size={14} />
        </button>
      </div>
      <div className="flex-1 overflow-y-auto px-2 pb-2">
        {isLoading && (
          <div className="px-3 py-4 text-xs text-text-muted">Loading...</div>
        )}
        {sessions.map((s) => (
          <SessionItem
            key={s.id}
            session={s}
            isActive={s.id === activeSessionId}
            onClick={() => onSelectSession(s.id)}
          />
        ))}
        {!isLoading && sessions.length === 0 && (
          <div className="px-3 py-8 text-center text-xs text-text-muted">
            No sessions yet
          </div>
        )}
      </div>
    </div>
  );
}
