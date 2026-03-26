"use client";

import { useEffect, useRef } from "react";
import { EventTimeline } from "./event-timeline";
import { useSessionEvents } from "@/hooks/use-session-events";
import { useSession } from "@/hooks/use-session";
import { ChatHeader } from "./chat-header";
import { Message } from "./message";
import { InputBar } from "./input-bar";

interface ChatViewProps {
  sessionId: string;
  onForkSession?: (sessionId: string) => void;
}

export function ChatView({ sessionId, onForkSession }: ChatViewProps) {
  const { session, isLoading, refresh } = useSession(sessionId);
  const bottomRef = useRef<HTMLDivElement>(null);
  const { events } = useSessionEvents(session?.id ?? null, session?.events ?? [], refresh);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [session?.messages.length]);

  if (isLoading || !session) {
    return (
      <div className="flex h-full items-center justify-center">
        <div className="flex items-center gap-2.5 text-muted-foreground">
          <div className="h-1.5 w-1.5 rounded-full bg-muted-foreground/40 animate-pulse" />
          <span className="text-[13px]">Загрузка сессии...</span>
        </div>
      </div>
    );
  }

  return (
    <div className="flex h-full flex-col bg-[#faf8ff] dark:bg-transparent">
      <ChatHeader session={session} onRefresh={refresh} />
      <div className="min-h-0 flex-1 px-6 py-5">
        <div className="grid h-full gap-5 xl:grid-cols-[minmax(0,1.65fr)_minmax(20rem,26rem)]">
          <div className="min-h-0 overflow-hidden rounded-[18px] border border-[#e2e8f0] bg-white shadow-[0_4px_6px_-1px_rgba(17,48,105,0.04),0_2px_4px_-1px_rgba(17,48,105,0.02)] dark:border-slate-800/80 dark:bg-[linear-gradient(180deg,rgba(15,23,42,0.86),rgba(2,6,23,0.82))]">
            <div className="h-full overflow-y-auto px-6 py-5">
              {session.messages.length === 0 && ["running", "pause_requested"].includes(session.status) && (
                <div className="flex h-full items-center justify-center">
                  <div className="flex items-center gap-3 rounded-full border border-sky-200/80 bg-white/80 px-4 py-2 text-slate-600 shadow-sm dark:border-sky-900/60 dark:bg-slate-900/70 dark:text-slate-300">
                    <div className="relative flex h-3 w-3 items-center justify-center">
                      <div
                        className="h-2 w-2 rounded-full bg-sky-500"
                        style={{ animation: "pulse-dot 1.5s ease-in-out infinite" }}
                      />
                      <div className="absolute h-3 w-3 rounded-full bg-sky-500/20" />
                    </div>
                    <span className="text-[13px] font-medium">
                      {session.status === "pause_requested" ? "Ожидаем безопасную паузу..." : "Агенты работают..."}
                    </span>
                  </div>
                </div>
              )}
              {session.messages.map((msg, i) => (
                <Message key={i} message={msg} />
              ))}
              <div ref={bottomRef} />
            </div>
          </div>
          <div className="min-h-0">
            <EventTimeline
              events={events}
              activeNode={session.active_node}
              pendingInstructions={session.pending_instructions}
            />
          </div>
        </div>
      </div>
      <InputBar
        sessionId={session.id}
        status={session.status}
        pendingInstructions={session.pending_instructions}
        currentCheckpointId={session.current_checkpoint_id}
        onForkSession={onForkSession}
        onRefresh={refresh}
      />
    </div>
  );
}
