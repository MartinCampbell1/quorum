"use client";

import { Plus } from "lucide-react";
import { Button } from "@/components/ui/button";
import { ScrollArea } from "@/components/ui/scroll-area";
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
    <div className="flex h-full w-60 flex-col border-r bg-background">
      <div className="flex items-center justify-between px-4 py-3.5">
        <span className="text-xs font-semibold uppercase tracking-widest text-muted-foreground/70">
          Сессии
        </span>
        <Button variant="ghost" size="icon-xs" onClick={onNewSession} aria-label="Новая сессия">
          <Plus className="h-3.5 w-3.5" />
        </Button>
      </div>
      <div className="h-px bg-border mx-3" />
      <ScrollArea className="flex-1 px-2 pt-2 pb-3">
        {isLoading && (
          <div className="px-3 py-8 text-center">
            <div className="inline-block h-1.5 w-1.5 rounded-full bg-muted-foreground/40 animate-pulse" />
          </div>
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
          <p className="px-3 py-10 text-center text-sm text-muted-foreground/60">
            Пока нет сессий
          </p>
        )}
      </ScrollArea>
    </div>
  );
}
