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
    <div className="flex h-screen overflow-hidden bg-[radial-gradient(circle_at_top_left,_rgba(148,163,184,0.18),_transparent_22%),linear-gradient(180deg,_#f8fafc_0%,_#f1f5f9_100%)] text-foreground dark:bg-[radial-gradient(circle_at_top_left,_rgba(30,41,59,0.55),_transparent_20%),linear-gradient(180deg,_#020617_0%,_#0f172a_100%)]">
      <IconBar activeView={view} onViewChange={handleViewChange} />
      <SessionList
        activeSessionId={activeSessionId}
        onSelectSession={handleSelectSession}
        onNewSession={handleNewSession}
      />
      <main className="relative flex min-w-0 flex-1 flex-col overflow-hidden bg-white/65 backdrop-blur-[2px] dark:bg-slate-950/30">
        <div className="pointer-events-none absolute inset-0 bg-[linear-gradient(135deg,rgba(255,255,255,0.4)_0%,transparent_38%),radial-gradient(circle_at_top_right,rgba(14,165,233,0.08),transparent_22%)] dark:bg-[linear-gradient(135deg,rgba(15,23,42,0.28)_0%,transparent_38%),radial-gradient(circle_at_top_right,rgba(56,189,248,0.1),transparent_22%)]" />
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
