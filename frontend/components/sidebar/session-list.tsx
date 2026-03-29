"use client";

import { Plus, Search } from "lucide-react";

import { ScrollArea } from "@/components/ui/scroll-area";
import { useLocale } from "@/lib/locale";
import { useSessions } from "@/hooks/use-sessions";
import { cn } from "@/lib/utils";

import { SessionItem } from "./session-item";

interface SessionListProps {
  activeSessionId: string | null;
  onSelectSession: (id: string) => void;
  onNewSession: () => void;
  collapsed?: boolean;
}

export function SessionList({
  activeSessionId,
  onSelectSession,
  onNewSession,
  collapsed = false,
}: SessionListProps) {
  const { copy } = useLocale();
  const { sessions, isLoading } = useSessions();
  const isEmpty = !isLoading && sessions.length === 0;

  return (
    <aside
      className={cn(
        "flex h-full flex-col overflow-hidden border-r border-[#e6e8ee] bg-white transition-[width,opacity] duration-200 dark:border-slate-800/80 dark:bg-[#0b0f17]",
        collapsed ? "w-0 border-r-0 opacity-0" : "w-[228px] opacity-100"
      )}
    >
      <div className="border-b border-[#e6e8ee] px-4 py-3 dark:border-slate-800/80">
        <div className="relative">
          <Search className="pointer-events-none absolute left-3.5 top-1/2 h-4 w-4 -translate-y-1/2 text-[#09090b]/55 dark:text-slate-500" />
          <input
            readOnly
            value=""
            placeholder={copy.shell.searchPlaceholder}
            className="h-10 w-full rounded-[10px] border border-[#d9dde7] bg-white px-10 text-[13px] outline-none placeholder:text-[#09090b]/45 dark:border-slate-800 dark:bg-slate-950/60 dark:text-slate-100 dark:placeholder:text-slate-500"
          />
        </div>
        <div className="mt-5 flex items-center justify-between">
          <span className="text-[11px] font-medium uppercase tracking-[0.14em] text-[#09090b] dark:text-slate-300">
            {copy.shell.sessions}
          </span>
          <button
            type="button"
            aria-label={copy.shell.newSession}
            onClick={onNewSession}
            className="flex h-7 w-7 items-center justify-center rounded-full text-[#09090b] transition-colors hover:bg-[#f5f6fa] dark:text-slate-100 dark:hover:bg-slate-800/70"
          >
            <Plus className="h-4 w-4 stroke-[1.9]" />
          </button>
        </div>
      </div>

      <ScrollArea className="min-h-0 flex-1 px-3 py-3">
        {isLoading ? (
          <div className="px-4 py-8 text-[13px] text-[#09090b]/42 dark:text-slate-500">{copy.shell.loading}</div>
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
          <div className="px-4 py-10 text-[14px] leading-8 text-[#09090b]/78 dark:text-slate-400">
            {copy.shell.noSessions}
          </div>
        ) : null}
      </ScrollArea>

    </aside>
  );
}
