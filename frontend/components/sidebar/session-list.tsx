"use client";

import { Plus } from "lucide-react";
import { Button } from "@/components/ui/button";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Separator } from "@/components/ui/separator";
import { useSessions } from "@/hooks/use-sessions";
import { SessionItem } from "./session-item";

interface SessionListProps {
  activeSessionId: string | null;
  onSelectSession: (id: string) => void;
  onNewSession: () => void;
}

export function SessionList({ activeSessionId, onSelectSession, onNewSession }: SessionListProps) {
  const { sessions, isLoading } = useSessions();

  return (
    <div className="flex h-full w-56 flex-col border-r bg-sidebar">
      <div className="flex items-center justify-between px-4 py-3">
        <span className="text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">Sessions</span>
        <Button variant="ghost" size="icon" className="h-6 w-6" onClick={onNewSession}>
          <Plus className="h-3.5 w-3.5" />
        </Button>
      </div>
      <Separator />
      <ScrollArea className="flex-1 px-2 py-2">
        {isLoading && <p className="px-3 py-4 text-xs text-muted-foreground">Loading...</p>}
        {sessions.map((s) => (
          <SessionItem key={s.id} session={s} isActive={s.id === activeSessionId} onClick={() => onSelectSession(s.id)} />
        ))}
        {!isLoading && sessions.length === 0 && (
          <p className="px-3 py-8 text-center text-xs text-muted-foreground">No sessions yet</p>
        )}
      </ScrollArea>
    </div>
  );
}
