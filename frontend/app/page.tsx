"use client";

import { useState } from "react";
import { Circle, Search, UserCircle2 } from "lucide-react";

import { ChatView } from "@/components/chat/chat-view";
import { SettingsView } from "@/components/settings-view";
import { HistoryView } from "@/components/history-view";
import { IconBar } from "@/components/sidebar/icon-bar";
import { SessionList } from "@/components/sidebar/session-list";
import { Wizard } from "@/components/wizard/wizard";

type View = "chat" | "history" | "settings";

function BrandMark() {
  return (
    <svg
      viewBox="0 0 28 28"
      aria-hidden="true"
      className="h-7 w-7 text-[#09090b]"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.9"
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      <path d="M14 3 6.7 8.2 10.2 22h7.6L21.3 8.2 14 3Z" />
      <path d="m9.2 10.2 4.8 4.1 4.8-4.1" />
      <path d="m11.3 21 2.7-6 2.7 6" />
    </svg>
  );
}

export default function Home() {
  const [view, setView] = useState<View>("chat");
  const [activeSessionId, setActiveSessionId] = useState<string | null>(null);
  const [showWizard, setShowWizard] = useState(true);

  function handleViewChange(nextView: View) {
    setView(nextView);
    if (nextView === "chat" && !activeSessionId) {
      setShowWizard(true);
    }
  }

  function handleSelectSession(id: string) {
    setActiveSessionId(id);
    setShowWizard(false);
    setView("chat");
  }

  function handleNewSession() {
    setActiveSessionId(null);
    setShowWizard(true);
    setView("chat");
  }

  function handleOpenHome() {
    setActiveSessionId(null);
    setShowWizard(true);
    setView("chat");
  }

  const isMonitorView = view === "chat" && !showWizard && !!activeSessionId;
  const shellView: View = showWizard ? "settings" : view;

  if (isMonitorView && activeSessionId) {
    return (
      <div className="h-screen overflow-hidden bg-white text-[#09090b]">
        <ChatView
          sessionId={activeSessionId}
          onForkSession={handleSelectSession}
          onOpenHome={handleOpenHome}
          onOpenSessions={handleOpenHome}
        />
      </div>
    );
  }

  return (
    <div className="flex h-screen flex-col overflow-hidden bg-white text-[#09090b]">
      <header className="flex h-[70px] shrink-0 items-center border-b border-[#e6e8ee] bg-white px-6">
        <div className="flex w-[300px] shrink-0 items-center gap-4">
          <BrandMark />
          <div className="text-[17px] font-semibold tracking-[-0.03em]">
            AGENT ORCHESTRATOR
          </div>
        </div>
        <div className="flex flex-1 justify-center px-6">
          <div className="relative w-full max-w-[450px]">
            <Search className="pointer-events-none absolute left-4 top-1/2 h-4 w-4 -translate-y-1/2 text-[#09090b]/55" />
            <input
              readOnly
              value=""
              placeholder="Search"
              className="h-10 w-full rounded-[12px] border border-[#d9dde7] bg-white px-11 text-[13px] outline-none placeholder:text-[#09090b]/45"
            />
          </div>
        </div>
        <div className="flex w-[300px] shrink-0 items-center justify-end gap-4">
          <div className="flex items-center gap-2 text-[13px] text-[#09090b]/88">
            <span>Localhost Status: Connected</span>
            <Circle className="h-2.5 w-2.5 fill-current text-[#4b5563]" />
          </div>
          <button className="flex h-10 w-10 items-center justify-center rounded-full border border-[#d9dde7] bg-white text-[#09090b]">
            <UserCircle2 className="h-5 w-5" />
          </button>
        </div>
      </header>

      <div className="flex min-h-0 flex-1">
        <IconBar activeView={shellView} onViewChange={handleViewChange} />
        <SessionList
          activeSessionId={activeSessionId}
          onSelectSession={handleSelectSession}
          onNewSession={handleNewSession}
        />
        <main className="min-w-0 flex-1 overflow-hidden bg-white">
          {view === "history" ? (
            <HistoryView onSelectSession={handleSelectSession} />
          ) : view === "settings" ? (
            <SettingsView />
          ) : showWizard ? (
            <Wizard
              onSessionCreated={(id) => {
                setActiveSessionId(id);
                setShowWizard(false);
              }}
            />
          ) : (
            <div className="flex h-full items-center justify-center">
              <div className="text-center text-[13px] text-[#09090b]/52">
                Выберите сессию или создайте новую.
              </div>
            </div>
          )}
        </main>
      </div>
    </div>
  );
}
