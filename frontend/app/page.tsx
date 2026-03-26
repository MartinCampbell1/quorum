"use client";

import { useState } from "react";
import { IconBar } from "@/components/sidebar/icon-bar";
import { SessionList } from "@/components/sidebar/session-list";
import { Wizard } from "@/components/wizard/wizard";
import { ChatView } from "@/components/chat/chat-view";

type View = "chat" | "history" | "settings";

export default function Home() {
  const [view, setView] = useState<View>("chat");
  const [activeSessionId, setActiveSessionId] = useState<string | null>(null);
  const [showWizard, setShowWizard] = useState(true);

  function handleSessionCreated(id: string) {
    setActiveSessionId(id);
    setShowWizard(false);
  }

  function handleNewSession() {
    setShowWizard(true);
    setActiveSessionId(null);
  }

  function handleSelectSession(id: string) {
    setActiveSessionId(id);
    setShowWizard(false);
  }

  return (
    <div className="flex h-screen overflow-hidden">
      <IconBar activeView={view} onViewChange={setView} />
      <SessionList
        activeSessionId={activeSessionId}
        onSelectSession={handleSelectSession}
        onNewSession={handleNewSession}
      />
      <main className="flex-1 flex flex-col min-w-0">
        {showWizard ? (
          <Wizard onSessionCreated={handleSessionCreated} />
        ) : activeSessionId ? (
          <ChatView sessionId={activeSessionId} />
        ) : (
          <div className="flex h-full items-center justify-center text-sm text-text-muted">
            Select a session or create a new one
          </div>
        )}
      </main>
    </div>
  );
}
