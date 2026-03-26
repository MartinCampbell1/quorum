"use client";

import { useEffect, useRef } from "react";
import { useSession } from "@/hooks/use-session";
import { ChatHeader } from "./chat-header";
import { Message } from "./message";
import { InputBar } from "./input-bar";

interface ChatViewProps {
  sessionId: string;
}

export function ChatView({ sessionId }: ChatViewProps) {
  const { session, isLoading, refresh } = useSession(sessionId);
  const bottomRef = useRef<HTMLDivElement>(null);

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
    <div className="flex flex-col h-full bg-muted/10">
      <ChatHeader session={session} onRefresh={refresh} />
      <div className="flex-1 overflow-y-auto px-6 py-5">
        {session.messages.length === 0 && ["running", "pause_requested"].includes(session.status) && (
          <div className="flex h-full items-center justify-center">
            <div className="flex items-center gap-2.5 text-muted-foreground">
              <div
                className="h-2 w-2 rounded-full bg-foreground/30"
                style={{ animation: "pulse-dot 1.5s ease-in-out infinite" }}
              />
              <span className="text-[13px]">
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
      <InputBar
        sessionId={session.id}
        status={session.status}
        pendingInstructions={session.pending_instructions}
        onRefresh={refresh}
      />
    </div>
  );
}
