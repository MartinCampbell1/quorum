"use client";

import { useState } from "react";
import { Circle, Search, UserCircle2 } from "lucide-react";
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
    <div className="flex h-screen overflow-hidden bg-[#faf8ff] text-foreground dark:bg-[linear-gradient(180deg,#0f172a_0%,#020617_100%)]">
      <IconBar activeView={view} onViewChange={handleViewChange} />
      <SessionList
        activeSessionId={activeSessionId}
        onSelectSession={handleSelectSession}
        onNewSession={handleNewSession}
      />
      <main className="relative flex min-w-0 flex-1 flex-col overflow-hidden bg-[#faf8ff] dark:bg-transparent">
        <div className="flex h-[72px] items-center justify-between border-b border-[#e2e8f0]/70 bg-white/82 px-7 backdrop-blur-md dark:border-slate-800/80 dark:bg-slate-950/45">
          <div className="relative w-full max-w-xl">
            <Search className="pointer-events-none absolute left-4 top-1/2 h-4 w-4 -translate-y-1/2 text-[#445d99]/80 dark:text-slate-400" />
            <input
              readOnly
              value=""
              placeholder="Search"
              className="h-10 w-full rounded-[14px] border border-[#98b1f2]/28 bg-white px-11 text-sm text-[#09090b] outline-none placeholder:text-[#445d99]/65 dark:border-slate-700 dark:bg-slate-900/80 dark:text-white"
            />
          </div>
          <div className="ml-6 flex shrink-0 items-center gap-4 text-sm text-[#09090b] dark:text-slate-200">
            <div className="flex items-center gap-2">
              <span className="whitespace-nowrap text-[13px] text-[#09090b]/80 dark:text-slate-300">Localhost Status: Connected</span>
              <Circle className="h-2.5 w-2.5 fill-current text-[#4a5167] dark:text-emerald-400" />
            </div>
            <button className="flex h-9 w-9 items-center justify-center rounded-full border border-[#e2e8f0] bg-white text-[#09090b] dark:border-slate-700 dark:bg-slate-900 dark:text-white">
              <UserCircle2 className="h-5 w-5" />
            </button>
          </div>
        </div>
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
