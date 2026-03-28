"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { Folder, Globe, HardDrive, Loader2, Sparkles, TerminalSquare } from "lucide-react";

import { Button } from "@/components/ui/button";
import { controlSession } from "@/lib/api";
import { useLocale } from "@/lib/locale";
import { useSession } from "@/hooks/use-session";
import { useSessionEvents } from "@/hooks/use-session-events";
import type { AttachedToolDetail } from "@/lib/types";

import { ChatHeader } from "./chat-header";
import { CheckpointPanel } from "./checkpoint-panel";
import { ConversationPanel, EventTimeline } from "./event-timeline";
import { InputBar } from "./input-bar";
import { TopologyPanel } from "./topology-panel";

interface ChatViewProps {
  sessionId: string;
  onForkSession?: (sessionId: string) => void;
  onOpenHome?: () => void;
  onOpenSessions?: () => void;
}

function ToolIcon({ tool }: { tool: AttachedToolDetail }) {
  if (tool.icon === "🔍" || tool.id.includes("search")) return <Globe className="h-7 w-7 text-[#7b8190]" />;
  if (tool.icon === "🧠" || tool.id.includes("perplexity")) return <Sparkles className="h-7 w-7 text-[#7b8190]" />;
  if (tool.icon === "⚡" || tool.icon === "🐍" || tool.id.includes("shell") || tool.id.includes("code")) {
    return <TerminalSquare className="h-7 w-7 text-[#7b8190]" />;
  }
  if (tool.icon === "📊") return <HardDrive className="h-7 w-7 text-[#7b8190]" />;
  return <Folder className="h-7 w-7 text-[#7b8190]" />;
}

function TaskSummaryCard({ task }: { task: string }) {
  const { copy } = useLocale();
  const [expanded, setExpanded] = useState(false);
  const preview = task.length > 220 ? `${task.slice(0, 219)}…` : task;

  return (
    <section className="rounded-[18px] border border-[#d6dbe6] bg-white p-4 shadow-[0_10px_24px_-18px_rgba(17,48,105,0.18)] dark:border-slate-800 dark:bg-slate-950/60 dark:shadow-none">
      <div className="flex items-center justify-between gap-3">
        <h2 className="text-[19px] font-medium tracking-[-0.03em] text-[#111111] dark:text-slate-100">
          {copy.monitor.sessionTask}
        </h2>
        {task.length > 220 ? (
          <button
            type="button"
            onClick={() => setExpanded((value) => !value)}
            className="rounded-full border border-[#d6dbe6] bg-white px-3 py-1 text-[11px] uppercase tracking-[0.14em] text-[#6b7280] dark:border-slate-800 dark:bg-slate-900 dark:text-slate-400"
          >
            {expanded ? copy.monitor.collapseTask : copy.monitor.expandTask}
          </button>
        ) : null}
      </div>
      <div className="mt-3 rounded-[14px] border border-[#e5e7eb] bg-[#fbfcff] px-4 py-3 text-[14px] leading-7 text-[#273142] dark:border-slate-800 dark:bg-slate-900/80 dark:text-slate-300">
        {expanded ? task : preview}
      </div>
    </section>
  );
}

export function ChatView({
  sessionId,
  onForkSession,
  onOpenHome,
  onOpenSessions,
}: ChatViewProps) {
  const { copy } = useLocale();
  const { session, isLoading, refresh } = useSession(sessionId);
  const { events } = useSessionEvents(session?.id ?? null, session?.events ?? []);
  const [isWorking, setIsWorking] = useState(false);
  const [selectedCheckpointId, setSelectedCheckpointId] = useState<string | null>(null);
  const trackedSessionIdRef = useRef<string | null>(null);
  const trackedCurrentCheckpointRef = useRef<string | null>(null);
  const currentSessionId = session?.id ?? null;
  const currentCheckpointId = session?.current_checkpoint_id ?? null;

  const activeConnections = useMemo(() => {
    if (!session) return [];
    if (session.attached_tools?.length) return session.attached_tools;
    return Array.from(
      new Set(session.attached_tool_ids?.length ? session.attached_tool_ids : session.agents.flatMap((agent) => agent.tools ?? []))
    ).map((toolId) => ({
      id: toolId,
      name: toolId,
      transport: "unknown",
      subtitle: copy.monitor.genericConnection,
      icon: "folder",
      capability: "native" as const,
    }));
  }, [session, copy.monitor.genericConnection]);

  useEffect(() => {
    if (!currentSessionId) return;
    if (trackedSessionIdRef.current !== currentSessionId) {
      trackedSessionIdRef.current = currentSessionId;
      trackedCurrentCheckpointRef.current = currentCheckpointId;
      setSelectedCheckpointId(currentCheckpointId);
      return;
    }

    setSelectedCheckpointId((selected) => {
      if (selected === null || selected === trackedCurrentCheckpointRef.current) {
        return currentCheckpointId;
      }
      return selected;
    });
    trackedCurrentCheckpointRef.current = currentCheckpointId;
  }, [currentCheckpointId, currentSessionId]);

  async function handlePrimaryAction() {
    if (!session) return;
    setIsWorking(true);
    try {
      if (session.status === "paused") {
        await controlSession(session.id, "resume");
      } else if (["running", "pause_requested", "cancel_requested"].includes(session.status)) {
        await controlSession(session.id, "cancel");
      } else if (selectedCheckpointId ?? session.current_checkpoint_id) {
        const result = await controlSession(
          session.id,
          "restart_from_checkpoint",
          "",
          selectedCheckpointId ?? session.current_checkpoint_id ?? undefined
        );
        if (result.new_session_id) {
          onForkSession?.(result.new_session_id);
        }
      } else {
        onOpenHome?.();
      }
      await refresh();
    } finally {
      setIsWorking(false);
    }
  }

  function handleExport() {
    if (!session) return;
    const blob = new Blob([JSON.stringify(session, null, 2)], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = `${session.id}.json`;
    anchor.click();
    URL.revokeObjectURL(url);
  }

  function primaryLabel() {
    if (!session) return copy.monitor.stopSession;
    if (session.status === "paused") return copy.monitor.resumeSession;
    if (["running", "pause_requested", "cancel_requested"].includes(session.status)) return copy.monitor.stopSession;
    if (selectedCheckpointId ?? session.current_checkpoint_id) return copy.monitor.restartBranch;
    return copy.monitor.newSession;
  }

  if (isLoading || !session) {
    return (
      <div className="flex h-full items-center justify-center bg-[#f6f7fb] dark:bg-[#05070c]">
        <div className="text-[14px] text-[#6b7280] dark:text-slate-500">{copy.monitor.loading}</div>
      </div>
    );
  }

  return (
    <div className="flex h-full flex-col bg-[#f6f7fb] dark:bg-[#05070c]">
      <ChatHeader
        session={session}
        onOpenHome={onOpenHome}
        onOpenSessions={onOpenSessions}
      />

      <div className="min-h-0 flex-1 overflow-y-auto px-6 pb-6">
        <div className="grid gap-4 xl:grid-cols-[minmax(0,1fr)_356px]">
          <div className="space-y-4">
            <TaskSummaryCard task={session.task} />
            <TopologyPanel session={session} />
            <ConversationPanel key={session.id} sessionId={session.id} messages={session.messages} events={events} />
            <EventTimeline events={events} />
          </div>

          <div className="flex flex-col gap-4">
            <CheckpointPanel
              session={session}
              selectedCheckpointId={selectedCheckpointId}
              onSelectCheckpoint={setSelectedCheckpointId}
              onForkSession={onForkSession}
              onRefresh={refresh}
            />
            <section className="rounded-[18px] border border-[#d6dbe6] bg-white p-4 shadow-[0_10px_24px_-18px_rgba(17,48,105,0.18)] dark:border-slate-800 dark:bg-slate-950/60 dark:shadow-none">
              <h2 className="text-[19px] font-medium tracking-[-0.03em] text-[#111111] dark:text-slate-100">
                {copy.monitor.activeConnections}
              </h2>
              <div className="mt-4 space-y-4">
                {activeConnections.map((tool) => (
                  <div
                    key={tool.id}
                    className="rounded-[16px] border border-[#d6dbe6] bg-white px-4 py-4 dark:border-slate-800 dark:bg-slate-900/80"
                  >
                    <div className="flex items-start gap-3">
                      <div className="mt-1">
                        <ToolIcon tool={tool} />
                      </div>
                      <div>
                        <div className="text-[18px] font-medium tracking-[-0.03em] text-[#111111] dark:text-slate-100">
                          {tool.name}
                        </div>
                        <div className="mt-2 text-[14px] text-[#6b7280] dark:text-slate-400">
                          {tool.subtitle}
                        </div>
                        <div className="mt-2 inline-flex rounded-full border border-[#d6dbe6] bg-[#fafbff] px-2.5 py-1 text-[10px] uppercase tracking-[0.14em] text-[#6b7280] dark:border-slate-800 dark:bg-slate-900 dark:text-slate-400">
                          {tool.capability}
                        </div>
                      </div>
                    </div>
                  </div>
                ))}
                {activeConnections.length === 0 ? (
                  <div className="rounded-[16px] border border-[#d6dbe6] bg-white px-4 py-4 text-[14px] text-[#6b7280] dark:border-slate-800 dark:bg-slate-900/80 dark:text-slate-400">
                    {copy.monitor.noActiveConnections}
                  </div>
                ) : null}
              </div>
            </section>

            <div className="mt-auto rounded-[18px] border border-[#d6dbe6] bg-white p-4 dark:border-slate-800 dark:bg-slate-950/60">
              <div className="flex gap-3">
                <Button
                  type="button"
                  onClick={handlePrimaryAction}
                  disabled={isWorking}
                  className="h-[46px] flex-1 rounded-[12px] bg-black text-[15px] font-medium text-white hover:bg-black/92"
                >
                  {isWorking ? (
                    <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                  ) : null}
                  {primaryLabel()}
                </Button>
                <Button
                  type="button"
                  variant="outline"
                  onClick={handleExport}
                  className="h-[46px] flex-1 rounded-[12px] border-[#111111] bg-white text-[15px] font-medium text-[#111111] dark:border-slate-700 dark:bg-slate-950 dark:text-slate-100 dark:hover:bg-slate-900"
                >
                  {copy.monitor.exportResults}
                </Button>
              </div>
            </div>
          </div>
        </div>

        <InputBar
          sessionId={session.id}
          status={session.status}
          pendingInstructions={session.pending_instructions}
          checkpointId={selectedCheckpointId ?? session.current_checkpoint_id}
          continueCheckpointId={session.current_checkpoint_id}
          onForkSession={onForkSession}
          onRefresh={refresh}
        />
      </div>
    </div>
  );
}
