"use client";

import { Plus, Search } from "lucide-react";
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
  const isEmpty = !isLoading && sessions.length === 0;

  return (
    <div className="flex h-full w-[260px] flex-col border-r border-[#e2e8f0]/75 bg-[#fcfcff] dark:border-slate-800/80 dark:bg-slate-950/65">
      <div className="border-b border-[#e2e8f0]/75 px-4 py-4 dark:border-slate-800/80">
        <div className="relative">
          <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-[#445d99]/70 dark:text-slate-400" />
          <input
            readOnly
            value=""
            placeholder="Search"
            className="h-10 w-full rounded-[12px] border border-[#e2e8f0] bg-white px-10 text-sm text-[#09090b] placeholder:text-[#445d99]/65 dark:border-slate-800 dark:bg-slate-900/80 dark:text-white"
          />
        </div>
        <div className="flex items-center justify-between">
          <div>
            <span className="mt-4 block text-[11px] font-semibold uppercase tracking-[0.22em] text-[#445d99] dark:text-slate-400">
              СЕССИИ
            </span>
          </div>
          <Button
            variant="ghost"
            size="sm"
            className="mt-4 rounded-xl border border-transparent px-2 text-xs text-[#09090b] hover:bg-[#f2f3ff] dark:text-slate-100 dark:hover:bg-slate-900"
            onClick={onNewSession}
            aria-label="Новая сессия"
          >
            <Plus className="h-4 w-4" />
          </Button>
        </div>
      </div>
      <ScrollArea className="flex-1 px-3 py-3">
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
        {isEmpty && (
          <div className="px-4 py-8 text-center">
            <p className="text-sm font-medium text-foreground">Пока нет сессий</p>
            <Button
              variant="outline"
              size="sm"
              className="mt-4 rounded-xl border-[#e2e8f0] bg-white text-xs dark:border-slate-800 dark:bg-slate-900"
              onClick={onNewSession}
            >
              <Plus className="mr-1.5 h-3.5 w-3.5" />
              Создать
            </Button>
          </div>
        )}
      </ScrollArea>
    </div>
  );
}
