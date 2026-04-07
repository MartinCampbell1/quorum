"use client";

import { useState } from "react";
import { Circle, Search, UserCircle2 } from "lucide-react";

import { ChatView } from "@/components/chat/chat-view";
import { FounderOsBoard } from "@/components/founder-os/founder-os-board";
import { SettingsView } from "@/components/settings-view";
import { HistoryView } from "@/components/history-view";
import { IconBar } from "@/components/sidebar/icon-bar";
import { SessionList } from "@/components/sidebar/session-list";
import { clearWizardDraft, Wizard } from "@/components/wizard/wizard";
import { LocaleProvider, useLocale } from "@/lib/locale";

type View = "chat" | "founderos" | "history" | "settings";

function BrandMark() {
  return (
    <svg
      viewBox="0 0 28 28"
      aria-hidden="true"
      className="h-7 w-7 text-[#09090b] dark:text-slate-100"
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

function HomeShell() {
  const { locale, setLocale, copy } = useLocale();
  const [view, setView] = useState<View>("chat");
  const [activeSessionId, setActiveSessionId] = useState<string | null>(null);
  const [showWizard, setShowWizard] = useState(true);
  const [isSessionListCollapsed, setIsSessionListCollapsed] = useState(false);
  const [resumeWizardDraft, setResumeWizardDraft] = useState(false);
  const [wizardVersion, setWizardVersion] = useState(0);

  function openFreshWizard() {
    clearWizardDraft();
    setResumeWizardDraft(false);
    setActiveSessionId(null);
    setShowWizard(true);
    setView("chat");
    setWizardVersion((value) => value + 1);
  }

  function openDraftWizard() {
    setResumeWizardDraft(true);
    setActiveSessionId(null);
    setShowWizard(true);
    setView("chat");
    setWizardVersion((value) => value + 1);
  }

  function handleViewChange(nextView: View) {
    setView(nextView);
    if (nextView === "chat" && !activeSessionId) {
      setShowWizard(true);
      if (!resumeWizardDraft) {
        setWizardVersion((value) => value + 1);
      }
    }
  }

  function handleSelectSession(id: string) {
    clearWizardDraft();
    setResumeWizardDraft(false);
    setActiveSessionId(id);
    setShowWizard(false);
    setView("chat");
  }

  function handleNewSession() {
    openFreshWizard();
  }

  function handleOpenHome() {
    openFreshWizard();
  }

  function handleDeleteSession(id: string) {
    if (activeSessionId !== id) {
      return;
    }
    clearWizardDraft();
    setResumeWizardDraft(false);
    setActiveSessionId(null);
    setShowWizard(false);
    setView("chat");
  }

  const isMonitorView = view === "chat" && !showWizard && !!activeSessionId;
  const shellView: View = view;

  return (
    <div className="flex h-screen flex-col overflow-hidden bg-[#f6f7fb] text-slate-950 dark:bg-[#06080d] dark:text-slate-100">
      <header className="flex h-[70px] shrink-0 items-center border-b border-[#e6e8ee] bg-white/95 px-6 backdrop-blur-sm dark:border-slate-800/80 dark:bg-[#0b0f17]/95">
        <div className="flex w-[300px] shrink-0 items-center gap-4">
          <BrandMark />
          <div className="text-[17px] font-semibold tracking-[-0.03em]">
            {copy.shell.appTitle}
          </div>
        </div>
        <div className="flex flex-1 justify-center px-6">
          <div className="relative w-full max-w-[450px]">
            <Search className="pointer-events-none absolute left-4 top-1/2 h-4 w-4 -translate-y-1/2 text-[#09090b]/55 dark:text-slate-500" />
            <input
              readOnly
              value=""
              placeholder={copy.shell.searchPlaceholder}
              className="h-10 w-full rounded-[12px] border border-[#d9dde7] bg-white px-11 text-[13px] outline-none placeholder:text-[#09090b]/45 dark:border-slate-800 dark:bg-slate-950/60 dark:text-slate-100 dark:placeholder:text-slate-500"
            />
          </div>
        </div>
        <div className="flex w-[340px] shrink-0 items-center justify-end gap-4">
          <div className="inline-flex rounded-[12px] border border-[#d9dde7] bg-white p-1 dark:border-slate-800 dark:bg-slate-950/60">
            {(["ru", "en"] as const).map((item) => (
              <button
                key={item}
                type="button"
                onClick={() => setLocale(item)}
                className={`rounded-[8px] px-2.5 py-1 text-[12px] font-medium uppercase tracking-[0.08em] ${
                  locale === item
                    ? "bg-[#111111] text-white dark:bg-slate-100 dark:text-slate-950"
                    : "text-[#6b7280] dark:text-slate-400"
                }`}
              >
                {item}
              </button>
            ))}
          </div>
          <div className="flex items-center gap-2 text-[13px] text-[#09090b]/88 dark:text-slate-300">
            <span>{copy.shell.localhostStatus}</span>
            <Circle className="h-2.5 w-2.5 fill-current text-[#4b5563] dark:text-emerald-400" />
          </div>
          <button
            aria-label={copy.shell.account}
            className="flex h-10 w-10 items-center justify-center rounded-full border border-[#d9dde7] bg-white text-[#09090b] dark:border-slate-800 dark:bg-slate-950/60 dark:text-slate-100"
          >
            <UserCircle2 className="h-5 w-5" />
          </button>
        </div>
      </header>

      <div className="flex min-h-0 flex-1">
        <IconBar
          activeView={shellView}
          onViewChange={handleViewChange}
          sessionsCollapsed={isSessionListCollapsed}
          onToggleSessions={() => setIsSessionListCollapsed((value) => !value)}
        />
        <SessionList
          activeSessionId={activeSessionId}
          onSelectSession={handleSelectSession}
          onNewSession={handleNewSession}
          onDeleteSession={handleDeleteSession}
          collapsed={isSessionListCollapsed}
        />
        <main className="min-w-0 flex-1 overflow-hidden bg-[#f6f7fb] dark:bg-[#05070c]">
          {view === "history" ? (
            <HistoryView onSelectSession={handleSelectSession} />
          ) : view === "founderos" ? (
            <FounderOsBoard
              onSelectSession={handleSelectSession}
              onOpenDraftWizard={() => {
                setResumeWizardDraft(true);
                setActiveSessionId(null);
                setShowWizard(true);
                setView("chat");
                setWizardVersion((value) => value + 1);
              }}
            />
          ) : view === "settings" ? (
            <SettingsView />
          ) : showWizard ? (
            <Wizard
              key={wizardVersion}
              resumeDraft={resumeWizardDraft}
              onSessionCreated={(id) => {
                clearWizardDraft();
                setResumeWizardDraft(false);
                setActiveSessionId(id);
                setShowWizard(false);
              }}
              onOpenSettings={() => {
                setResumeWizardDraft(true);
                setView("settings");
              }}
            />
          ) : isMonitorView && activeSessionId ? (
            <ChatView
              sessionId={activeSessionId}
              onForkSession={handleSelectSession}
              onOpenHome={handleOpenHome}
              onOpenDraftWizard={openDraftWizard}
              onOpenSessions={handleOpenHome}
            />
          ) : (
            <div className="flex h-full items-center justify-center">
              <div className="text-center text-[13px] text-[#09090b]/52 dark:text-slate-500">{copy.shell.noSessionSelected}</div>
            </div>
          )}
        </main>
      </div>
    </div>
  );
}

export default function Home() {
  return (
    <LocaleProvider>
      <HomeShell />
    </LocaleProvider>
  );
}
