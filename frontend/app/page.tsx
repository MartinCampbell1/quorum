"use client";

import { useState } from "react";
import { IconBar } from "@/components/sidebar/icon-bar";
import { SessionList } from "@/components/sidebar/session-list";
import { Wizard } from "@/components/wizard/wizard";
import { ChatView } from "@/components/chat/chat-view";
import { HistoryView } from "@/components/history-view";
import { SettingsView } from "@/components/settings-view";

type View = "chat" | "history" | "settings";

export default function Home() {
  const [view, setView] = useState<View>("chat");
  const [activeSessionId, setActiveSessionId] = useState<string | null>(null);
  const [showWizard, setShowWizard] = useState(true);

  function handleViewChange(v: View) {
    setView(v);
    if (v === "chat") {
      if (!activeSessionId) {
        setShowWizard(true);
      }
    }
  }

  function handleSelectSession(id: string) {
    setActiveSessionId(id);
    setShowWizard(false);
    setView("chat");
  }

  function handleNewSession() {
    setShowWizard(true);
    setActiveSessionId(null);
    setView("chat");
  }

  return (
    <div className="flex h-screen overflow-hidden bg-background">
      <IconBar activeView={view} onViewChange={handleViewChange} />
      <SessionList
        activeSessionId={activeSessionId}
        onSelectSession={handleSelectSession}
        onNewSession={handleNewSession}
      />
      <main className="flex-1 flex flex-col min-w-0 bg-[#f5f5f4]  dark:bg-muted/20">
        {view === "history" ? (
          <HistoryView onSelectSession={handleSelectSession} />
        ) : view === "settings" ? (
          <SettingsView />
        ) : showWizard ? (
          <Wizard onSessionCreated={(id) => { setActiveSessionId(id); setShowWizard(false); }} />
        ) : activeSessionId ? (
          <ChatView sessionId={activeSessionId} onForkSession={handleSelectSession} />
        ) : (
          <div className="flex h-full items-center justify-center">
            <div className="text-center">
              <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-muted mx-auto mb-3">
                <span className="font-semibold text-sm text-muted-foreground">Q</span>
              </div>
              <p className="text-[13px] text-muted-foreground/60">
                Выберите сессию или создайте новую
              </p>
            </div>
          </div>
        )}
      </main>
    </div>
  );
}
