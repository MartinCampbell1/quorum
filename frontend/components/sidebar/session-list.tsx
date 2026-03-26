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
    <div
      className="flex h-full w-[220px] flex-col"
      style={{ background: "#0e0e0e", borderRight: "1px solid #1a1a1a" }}
    >
      <div className="flex items-center justify-between px-4 py-4">
        <span className="text-[10px] font-mono font-medium uppercase tracking-[0.1em]" style={{ color: "#555" }}>
          Sessions
        </span>
        <button
          onClick={onNewSession}
          className="flex h-6 w-6 items-center justify-center rounded-md transition-all cursor-pointer hover:bg-[#1a1a1a]"
          style={{ color: "#555" }}
          aria-label="New session"
        >
          <Plus size={13} strokeWidth={2} />
        </button>
      </div>
      <div className="flex-1 overflow-y-auto px-2 pb-2">
        {isLoading && (
          <div className="px-3 py-4 text-[12px]" style={{ color: "#444" }}>Loading...</div>
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
          <div className="px-3 py-12 text-center">
            <p className="text-[12px]" style={{ color: "#444" }}>No sessions yet</p>
            <p className="text-[11px] mt-1" style={{ color: "#333" }}>Create one to get started</p>
          </div>
        )}
      </div>
    </div>
  );
}
