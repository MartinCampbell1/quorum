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

export function SessionList({
  activeSessionId,
  onSelectSession,
  onNewSession,
}: SessionListProps) {
  const { sessions, isLoading } = useSessions();
  const isEmpty = !isLoading && sessions.length === 0;

  return (
    <aside className="flex h-full w-[228px] flex-col border-r border-[#e6e8ee] bg-white">
      <div className="border-b border-[#e6e8ee] px-4 py-3">
        <div className="relative">
          <Search className="pointer-events-none absolute left-3.5 top-1/2 h-4 w-4 -translate-y-1/2 text-[#09090b]/55" />
          <input
            readOnly
            value=""
            placeholder="Search"
            className="h-10 w-full rounded-[10px] border border-[#d9dde7] bg-white px-10 text-[13px] outline-none placeholder:text-[#09090b]/45"
          />
        </div>
        <div className="mt-5 flex items-center justify-between">
          <span className="text-[11px] font-medium uppercase tracking-[0.14em] text-[#09090b]">
            Сессии
          </span>
          <button
            type="button"
            aria-label="Новая сессия"
            onClick={onNewSession}
            className="flex h-7 w-7 items-center justify-center rounded-full text-[#09090b] transition-colors hover:bg-[#f5f6fa]"
          >
            <Plus className="h-4 w-4 stroke-[1.9]" />
          </button>
        </div>
      </div>

      <ScrollArea className="flex-1 px-3 py-3">
        {isLoading ? (
          <div className="px-4 py-8 text-[13px] text-[#09090b]/42">Загрузка...</div>
        ) : null}

        {sessions.map((session) => (
          <SessionItem
            key={session.id}
            session={session}
            isActive={session.id === activeSessionId}
            onClick={() => onSelectSession(session.id)}
          />
        ))}

        {isEmpty ? (
          <div className="px-4 py-10 text-[14px] leading-8 text-[#09090b]/78">
            Пока нет сессий
          </div>
        ) : null}
      </ScrollArea>

      <div className="mt-auto px-4 pb-5 pt-3">
        <Button
          type="button"
          variant="outline"
          className="h-10 w-full rounded-[12px] border-[#d9dde7] bg-white text-[14px] font-medium text-[#09090b] shadow-none hover:bg-[#f7f7fa]"
        >
          2 Issues
        </Button>
      </div>
    </aside>
  );
}
