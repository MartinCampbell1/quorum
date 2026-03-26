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

  return (
    <div className="flex h-screen overflow-hidden bg-background">
      <IconBar activeView={view} onViewChange={setView} />
      <SessionList
        activeSessionId={activeSessionId}
        onSelectSession={(id) => { setActiveSessionId(id); setShowWizard(false); }}
        onNewSession={() => { setShowWizard(true); setActiveSessionId(null); }}
      />
      <main className="flex-1 flex flex-col min-w-0">
        {showWizard ? (
          <Wizard onSessionCreated={(id) => { setActiveSessionId(id); setShowWizard(false); }} />
        ) : activeSessionId ? (
          <ChatView sessionId={activeSessionId} />
        ) : (
          <div className="flex h-full items-center justify-center text-sm text-muted-foreground">
            Select a session or create a new one
          </div>
        )}
      </main>
    </div>
  );
}
