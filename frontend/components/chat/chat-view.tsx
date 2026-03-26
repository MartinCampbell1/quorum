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
  const { session, isLoading } = useSession(sessionId);
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [session?.messages.length]);

  if (isLoading || !session) {
    return (
      <div className="flex h-full items-center justify-center text-sm text-text-muted">
        Loading session...
      </div>
    );
  }

  return (
    <div className="flex flex-col h-full">
      <ChatHeader session={session} />
      <div className="flex-1 overflow-y-auto px-5 py-4">
        {session.messages.length === 0 && session.status === "running" && (
          <div className="flex h-full items-center justify-center text-sm text-text-muted">
            <div className="flex items-center gap-2">
              <div className="h-2 w-2 rounded-full bg-accent animate-pulse" />
              Agents are working...
            </div>
          </div>
        )}
        {session.messages.map((msg, i) => (
          <Message key={i} message={msg} />
        ))}
        <div ref={bottomRef} />
      </div>
      <InputBar
        sessionId={sessionId}
        disabled={session.status !== "running"}
      />
    </div>
  );
}
