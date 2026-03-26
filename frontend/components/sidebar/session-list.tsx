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
  const isEmpty = !isLoading && sessions.length === 0;

  return (
    <div className="flex h-full w-[280px] flex-col border-r border-slate-200/70 bg-white/88 backdrop-blur-md dark:border-slate-800/80 dark:bg-slate-950/65">
      <div className="border-b border-slate-200/70 px-5 py-4 dark:border-slate-800/80">
        <div className="flex items-center justify-between">
          <div>
            <span className="text-[11px] font-semibold uppercase tracking-[0.22em] text-slate-500 dark:text-slate-400">
              Workspace
            </span>
            <p className="mt-1 text-sm font-medium text-slate-900 dark:text-slate-100">
              Сессии и ветки
            </p>
          </div>
          <Button
            variant="outline"
            size="sm"
            className="rounded-xl border-slate-200 bg-white text-xs shadow-sm dark:border-slate-700 dark:bg-slate-900"
            onClick={onNewSession}
            aria-label="Новая сессия"
          >
            <Plus className="mr-1.5 h-3.5 w-3.5" />
            Новая
          </Button>
        </div>
        <div className="mt-4 rounded-2xl border border-slate-200/80 bg-[linear-gradient(135deg,rgba(255,255,255,0.98),rgba(241,245,249,0.92))] px-4 py-3 shadow-[0_14px_30px_-24px_rgba(15,23,42,0.45)] dark:border-slate-800 dark:bg-[linear-gradient(135deg,rgba(15,23,42,0.92),rgba(15,23,42,0.76))]">
          <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-sky-700 dark:text-sky-300">
            Control Center
          </p>
          <p className="mt-1 text-[13px] leading-relaxed text-slate-700 dark:text-slate-300">
            Держи здесь основные прогоны, ветки от checkpoint и быстрый возврат к активным исследованиям.
          </p>
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
          <div className="mx-1 mt-2 rounded-3xl border border-dashed border-slate-300/80 bg-[linear-gradient(180deg,rgba(248,250,252,0.95),rgba(241,245,249,0.9))] px-5 py-6 text-center shadow-[0_16px_40px_-30px_rgba(15,23,42,0.4)] dark:border-slate-700 dark:bg-[linear-gradient(180deg,rgba(15,23,42,0.72),rgba(15,23,42,0.55))]">
            <p className="text-sm font-medium text-foreground">Пока нет сессий</p>
            <p className="mt-1.5 text-xs leading-relaxed text-muted-foreground/70">
              Создай первый запуск, выбери режим и посмотри, как агенты делят задачу между собой.
            </p>
            <Button
              variant="outline"
              size="sm"
              className="mt-4 rounded-xl border-slate-200 bg-white text-xs shadow-sm dark:border-slate-700 dark:bg-slate-900"
              onClick={onNewSession}
            >
              <Plus className="mr-1.5 h-3.5 w-3.5" />
              Первая сессия
            </Button>
          </div>
        )}
      </ScrollArea>
    </div>
  );
}
