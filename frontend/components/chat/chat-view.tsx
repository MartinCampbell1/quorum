"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { useSWRConfig } from "swr";
import { Folder, Globe, HardDrive, Loader2, Sparkles, TerminalSquare } from "lucide-react";

import { Button } from "@/components/ui/button";
import {
  controlSession,
  exportExecutionBrief,
  getAutopilotLaunchPresets,
  prepareTournamentFromSession,
  sendExecutionBriefToAutopilot,
} from "@/lib/api";
import { useLocale } from "@/lib/locale";
import { useSession } from "@/hooks/use-session";
import { useSessionEvents } from "@/hooks/use-session-events";
import type { AttachedToolDetail, AutopilotLaunchPreset, Session } from "@/lib/types";
import { saveWizardDraft } from "@/components/wizard/wizard";

import { ChatHeader } from "./chat-header";
import { CheckpointPanel } from "./checkpoint-panel";
import { ConversationPanel, EventTimeline } from "./event-timeline";
import { InputBar } from "./input-bar";
import { RichText, extractReadableAgentText, hasToolMarkup, sanitizeAgentText } from "./rich-text";
import { TopologyPanel } from "./topology-panel";

interface ChatViewProps {
  sessionId: string;
  onForkSession?: (sessionId: string) => void;
  onOpenHome?: () => void;
  onOpenDraftWizard?: () => void;
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

function truncateText(text: string, limit: number = 160) {
  const normalized = text.replace(/\s+/g, " ").trim();
  if (normalized.length <= limit) {
    return normalized;
  }
  return `${normalized.slice(0, limit - 1)}…`;
}

function SessionResultPanel({ session }: { session: Session }) {
  const { copy } = useLocale();
  const judgeRole = session.agents.find((agent) => agent.role === "judge")?.role;
  const rawVerdict =
    [...session.messages]
      .reverse()
      .find((message) => message.agent_id === judgeRole && message.phase === "verdict")?.content ??
    session.result;
  const visibleVerdict = extractReadableAgentText(rawVerdict, { preferStructuredAnswer: true });
  const hasHiddenRuntimeDetails =
    hasToolMarkup(rawVerdict) || sanitizeAgentText(rawVerdict) !== visibleVerdict;

  if (!sanitizeAgentText(rawVerdict)) {
    return null;
  }

  const title = session.mode === "debate" ? copy.monitor.finalVerdict : copy.monitor.finalResult;

  return (
    <section className="rounded-[18px] border border-[#d6dbe6] bg-white p-5 shadow-[0_10px_24px_-18px_rgba(17,48,105,0.18)] dark:border-slate-800 dark:bg-slate-950/60 dark:shadow-none">
      <div className="flex flex-wrap items-center gap-2">
        <span className="rounded-full border border-[#d6dbe6] bg-[#fbfcff] px-3 py-1 text-[10px] uppercase tracking-[0.16em] text-[#6b7280] dark:border-slate-800 dark:bg-slate-900 dark:text-slate-400">
          {copy.statuses[session.status]}
        </span>
        {judgeRole ? (
          <span className="rounded-full border border-[#d6dbe6] bg-[#fbfcff] px-3 py-1 text-[10px] uppercase tracking-[0.16em] text-[#6b7280] dark:border-slate-800 dark:bg-slate-900 dark:text-slate-400">
            {copy.monitor.judgeVerdict}
          </span>
        ) : null}
        {hasHiddenRuntimeDetails ? (
          <span className="rounded-full border border-[#d6dbe6] bg-[#fbfcff] px-3 py-1 text-[10px] uppercase tracking-[0.16em] text-[#6b7280] dark:border-slate-800 dark:bg-slate-900 dark:text-slate-400">
            {copy.monitor.hiddenRuntimeDetails}
          </span>
        ) : null}
      </div>
      <h2 className="mt-3 text-[22px] font-medium tracking-[-0.03em] text-[#111111] dark:text-slate-100">
        {title}
      </h2>
      <div className="mt-4 rounded-[16px] border border-[#e5e7eb] bg-[#fbfcff] px-5 py-5 dark:border-slate-800 dark:bg-slate-900/70">
        <RichText text={visibleVerdict || copy.monitor.finalAnswerFallback} className="text-[15px] leading-8" />
      </div>
    </section>
  );
}

function assessLastInstruction(session: Session, copy: ReturnType<typeof useLocale>["copy"]) {
  const latestInstruction = [...session.messages]
    .reverse()
    .find((message) => message.agent_id === "user" && sanitizeAgentText(message.content));

  if (!latestInstruction) {
    return {
      tone: "neutral" as const,
      statusLabel: copy.monitor.lastInstructionNone,
      explanation: copy.monitor.lastInstructionNoneHint,
      preview: "",
    };
  }

  const responsesAfterInstruction = session.messages.filter(
    (message) =>
      message.timestamp >= latestInstruction.timestamp &&
      message.agent_id !== "user" &&
      Boolean(extractReadableAgentText(message.content))
  );

  if (
    responsesAfterInstruction.length > 0 ||
    (["completed", "failed", "cancelled"].includes(session.status) &&
      Boolean(extractReadableAgentText(session.result, { preferStructuredAnswer: true })))
  ) {
    return {
      tone: "answered" as const,
      statusLabel: copy.monitor.lastInstructionAnswered,
      explanation: copy.monitor.lastInstructionAnsweredHint,
      preview: sanitizeAgentText(latestInstruction.content),
    };
  }

  if (
    (session.pending_instructions ?? 0) > 0 ||
    ["running", "pause_requested", "cancel_requested", "paused"].includes(session.status)
  ) {
    return {
      tone: "pending" as const,
      statusLabel: copy.monitor.lastInstructionPending,
      explanation: copy.monitor.lastInstructionPendingHint,
      preview: sanitizeAgentText(latestInstruction.content),
    };
  }

  return {
    tone: "unanswered" as const,
    statusLabel: copy.monitor.lastInstructionNotAnswered,
    explanation: copy.monitor.lastInstructionNotAnsweredHint,
    preview: sanitizeAgentText(latestInstruction.content),
  };
}

function LastInstructionPanel({ session }: { session: Session }) {
  const { copy } = useLocale();
  const assessment = useMemo(() => assessLastInstruction(session, copy), [session, copy]);
  const [expanded, setExpanded] = useState(false);
  const preview = assessment.preview;
  const canExpand = preview.length > 160;
  const visiblePreview = expanded ? preview : truncateText(preview, 160);

  const toneClassName =
    assessment.tone === "answered"
      ? "border-emerald-200 bg-emerald-50 text-emerald-700 dark:border-emerald-900/60 dark:bg-emerald-950/30 dark:text-emerald-300"
      : assessment.tone === "pending"
        ? "border-amber-200 bg-amber-50 text-amber-700 dark:border-amber-900/60 dark:bg-amber-950/30 dark:text-amber-300"
        : assessment.tone === "unanswered"
          ? "border-rose-200 bg-rose-50 text-rose-700 dark:border-rose-900/60 dark:bg-rose-950/30 dark:text-rose-300"
          : "border-[#d6dbe6] bg-[#fbfcff] text-[#6b7280] dark:border-slate-800 dark:bg-slate-900 dark:text-slate-400";

  return (
    <section className="rounded-[18px] border border-[#d6dbe6] bg-white p-4 shadow-[0_10px_24px_-18px_rgba(17,48,105,0.18)] dark:border-slate-800 dark:bg-slate-950/60 dark:shadow-none">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <div className="text-[10px] uppercase tracking-[0.16em] text-[#6b7280] dark:text-slate-400">
            {copy.monitor.lastInstructionStatus}
          </div>
          <h3 className="mt-2 text-[18px] font-medium tracking-[-0.03em] text-[#111111] dark:text-slate-100">
            {assessment.statusLabel}
          </h3>
        </div>
        <span className={`rounded-full border px-3 py-1 text-[10px] uppercase tracking-[0.16em] ${toneClassName}`}>
          {assessment.statusLabel}
        </span>
      </div>

      <p className="mt-3 text-[14px] leading-6 text-[#4b5563] dark:text-slate-300">{assessment.explanation}</p>

      {preview ? (
        <div className="mt-3 rounded-[14px] border border-[#e5e7eb] bg-[#fbfcff] px-4 py-3 dark:border-slate-800 dark:bg-slate-900/70">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <span className="text-[10px] uppercase tracking-[0.16em] text-[#6b7280] dark:text-slate-400">
              {copy.monitor.instructionPreview}
            </span>
            {canExpand ? (
              <button
                type="button"
                onClick={() => setExpanded((value) => !value)}
                className="rounded-full border border-[#d6dbe6] bg-white px-3 py-1 text-[11px] uppercase tracking-[0.14em] text-[#6b7280] dark:border-slate-800 dark:bg-slate-950 dark:text-slate-400"
              >
                {expanded ? copy.monitor.hideInstruction : copy.monitor.showFullInstruction}
              </button>
            ) : null}
          </div>
          <p className="mt-2 text-[13px] leading-6 text-[#273142] dark:text-slate-300">{visiblePreview}</p>
        </div>
      ) : null}
    </section>
  );
}

function latestRuntimeRecoveredEvent(session: Session) {
  return [...(session.events ?? [])].reverse().find((event) => event.type === "runtime_recovered");
}

export function ChatView({
  sessionId,
  onForkSession,
  onOpenHome,
  onOpenDraftWizard,
  onOpenSessions,
}: ChatViewProps) {
  const { copy } = useLocale();
  const { mutate } = useSWRConfig();
  const { session, isLoading, refresh } = useSession(sessionId);
  const { events } = useSessionEvents(session?.id ?? null, session?.events ?? []);
  const [isWorking, setIsWorking] = useState(false);
  const [isExportingBrief, setIsExportingBrief] = useState(false);
  const [isPreparingTournament, setIsPreparingTournament] = useState(false);
  const [isSendingToAutopilot, setIsSendingToAutopilot] = useState(false);
  const [isLaunchingInAutopilot, setIsLaunchingInAutopilot] = useState(false);
  const [autopilotLaunchPresets, setAutopilotLaunchPresets] = useState<AutopilotLaunchPreset[]>([]);
  const [selectedLaunchPresetId, setSelectedLaunchPresetId] = useState("team");
  const [bridgeStatus, setBridgeStatus] = useState<string | null>(null);
  const [selectedCheckpointId, setSelectedCheckpointId] = useState<string | null>(null);
  const [composerFocusToken, setComposerFocusToken] = useState(0);
  const trackedSessionIdRef = useRef<string | null>(null);
  const trackedCurrentCheckpointRef = useRef<string | null>(null);
  const currentSessionId = session?.id ?? null;
  const currentCheckpointId = session?.current_checkpoint_id ?? null;
  const isParallelChild = Boolean(session?.parallel_parent_id);
  const canPrepareTournament = session?.active_scenario === "portfolio_pivot_lab";
  const runtimeRecoveredEvent = useMemo(() => (session ? latestRuntimeRecoveredEvent(session) : null), [session]);
  const canRecoveryContinue = Boolean(session?.runtime_state?.can_continue_conversation);
  const canRecoveryBranch = Boolean(session?.runtime_state?.can_branch_from_checkpoint);
  const showRecoveryActions =
    session?.status === "failed" &&
    Boolean(runtimeRecoveredEvent) &&
    (canRecoveryContinue || canRecoveryBranch);

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
    getAutopilotLaunchPresets()
      .then((presets) => {
        setAutopilotLaunchPresets(presets);
        if (presets.length === 0) return;
        const recommended = session?.mode === "tournament" || session?.mode === "debate" ? "team" : "fast";
        const fallback = presets[0]?.id ?? "fast";
        const preferred = presets.some((preset) => preset.id === recommended) ? recommended : fallback;
        setSelectedLaunchPresetId((current) =>
          presets.some((preset) => preset.id === current) ? current : preferred
        );
      })
      .catch(() => {});
  }, [session?.mode]);

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
          await mutate("/orchestrate/sessions");
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

  async function handleExport() {
    if (!session) return;
    setIsExportingBrief(true);
    setBridgeStatus(null);
    try {
      const exported = await exportExecutionBrief(session.id);
      const blob = new Blob([JSON.stringify(exported.brief, null, 2)], { type: "application/json" });
      const url = URL.createObjectURL(blob);
      const anchor = document.createElement("a");
      anchor.href = url;
      anchor.download = `${session.id}-execution-brief.json`;
      anchor.click();
      URL.revokeObjectURL(url);
      setBridgeStatus(copy.monitor.briefExported);
    } catch (error) {
      setBridgeStatus(error instanceof Error ? error.message : "Execution Brief export failed.");
    } finally {
      setIsExportingBrief(false);
    }
  }

  async function handleSendToAutopilot() {
    if (!session) return;
    setIsSendingToAutopilot(true);
    setBridgeStatus(null);
    try {
      const response = await sendExecutionBriefToAutopilot(session.id, {});
      const projectName =
        typeof response.autopilot?.project_name === "string" && response.autopilot.project_name
          ? ` ${response.autopilot.project_name}`
          : "";
      setBridgeStatus(`${copy.monitor.briefSent}${projectName}`.trim());
    } catch (error) {
      setBridgeStatus(error instanceof Error ? error.message : "Autopilot bridge failed.");
    } finally {
      setIsSendingToAutopilot(false);
    }
  }

  async function handleLaunchInAutopilot() {
    if (!session) return;
    setIsLaunchingInAutopilot(true);
    setBridgeStatus(null);
    try {
      const preset = autopilotLaunchPresets.find((item) => item.id === selectedLaunchPresetId);
      const response = await sendExecutionBriefToAutopilot(session.id, {
        priority: session.mode === "tournament" ? "high" : "normal",
        launch: true,
        launch_profile: preset?.launch_profile ?? { preset: selectedLaunchPresetId },
      });
      const projectName =
        typeof response.autopilot?.project_name === "string" && response.autopilot.project_name
          ? ` ${response.autopilot.project_name}`
          : "";
      setBridgeStatus(`${copy.monitor.launchedInAutopilot}${projectName}`.trim());
    } catch (error) {
      setBridgeStatus(error instanceof Error ? error.message : "Autopilot launch failed.");
    } finally {
      setIsLaunchingInAutopilot(false);
    }
  }

  async function handlePrepareTournament() {
    if (!session) return;
    setIsPreparingTournament(true);
    setBridgeStatus(null);
    try {
      const response = await prepareTournamentFromSession(session.id);
      saveWizardDraft({
        step: 2,
        selectedScenarioId: response.tournament.scenario_id,
        agents: response.tournament.agents,
        workspacePresetIds: [],
        workspacePaths: response.tournament.workspace_paths,
        taskDraft: response.tournament.task,
        launchConfig: {
          max_rounds: response.tournament.recommended_max_rounds,
          execution_mode: response.tournament.recommended_execution_mode,
        },
      });
      setBridgeStatus(`${copy.monitor.tournamentPrepared} ${response.tournament.contestants.length}`.trim());
      onOpenDraftWizard?.();
    } catch (error) {
      setBridgeStatus(error instanceof Error ? error.message : "Tournament preparation failed.");
    } finally {
      setIsPreparingTournament(false);
    }
  }

  async function handleRecoveryBranch() {
    if (!session?.current_checkpoint_id) return;
    setIsWorking(true);
    try {
      const result = await controlSession(
        session.id,
        "restart_from_checkpoint",
        "",
        session.current_checkpoint_id
      );
      await refresh();
      if (result.new_session_id) {
        await mutate("/orchestrate/sessions");
        onForkSession?.(result.new_session_id);
      }
    } finally {
      setIsWorking(false);
    }
  }

  function handleRecoveryContinue() {
    setComposerFocusToken((value) => value + 1);
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
            {showRecoveryActions ? (
              <section className="rounded-[18px] border border-amber-200 bg-[linear-gradient(135deg,rgba(255,251,235,0.96),rgba(255,247,237,0.9))] p-4 shadow-[0_10px_24px_-18px_rgba(180,83,9,0.2)] dark:border-amber-900/60 dark:bg-[linear-gradient(135deg,rgba(67,20,7,0.55),rgba(30,27,75,0.38))] dark:shadow-none">
                <div className="text-[10px] font-semibold uppercase tracking-[0.16em] text-amber-700 dark:text-amber-300">
                  {copy.monitor.runtimeRecoveredActionsTitle}
                </div>
                <div className="mt-2 text-[15px] font-medium text-[#111111] dark:text-slate-100">
                  {copy.monitor.runtimeRecoveredActionsHint.replace("{checkpoint}", session.current_checkpoint_id ?? "checkpoint")}
                </div>
                <div className="mt-2 text-[13px] leading-6 text-[#6b7280] dark:text-slate-400">
                  {runtimeRecoveredEvent?.detail}
                </div>
                <div className="mt-4 flex flex-wrap gap-2">
                  {session.runtime_state?.can_continue_conversation ? (
                    <Button
                      type="button"
                      onClick={handleRecoveryContinue}
                      className="h-[42px] rounded-[12px] bg-black px-4 text-[13px] font-medium text-white hover:bg-black/92"
                    >
                      {copy.monitor.continueFromCurrentCheckpoint}
                    </Button>
                  ) : null}
                  {session.runtime_state?.can_branch_from_checkpoint && session.current_checkpoint_id ? (
                    <Button
                      type="button"
                      variant="outline"
                      onClick={handleRecoveryBranch}
                      disabled={isWorking}
                      className="h-[42px] rounded-[12px] border-[#111111] bg-white px-4 text-[13px] font-medium text-[#111111] dark:border-slate-700 dark:bg-slate-950 dark:text-slate-100 dark:hover:bg-slate-900"
                    >
                      {isWorking ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : null}
                      {copy.monitor.branchFromCurrentCheckpoint.replace("{checkpoint}", session.current_checkpoint_id ?? "checkpoint")}
                    </Button>
                  ) : null}
                </div>
              </section>
            ) : null}
            <TopologyPanel session={session} onOpenSession={onForkSession} />
            <SessionResultPanel session={session} />
            <LastInstructionPanel session={session} />
            <ConversationPanel
              key={session.id}
              sessionId={session.id}
              messages={session.messages}
              events={events}
              mode={session.mode}
              scenarioId={session.active_scenario}
              agents={session.agents}
              status={session.status}
              parallelProgress={session.parallel_progress}
              parallelChildren={session.parallel_children}
              onOpenSession={onForkSession}
            />
            <EventTimeline
              events={events}
              mode={session.mode}
              scenarioId={session.active_scenario}
              agents={session.agents}
              status={session.status}
              parallelProgress={session.parallel_progress}
              parallelChildren={session.parallel_children}
            />
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
              {isParallelChild ? (
                <div className="rounded-[14px] border border-[#d6dbe6] bg-[#fafbff] px-4 py-4 text-[13px] leading-6 text-[#6b7280] dark:border-slate-800 dark:bg-slate-900/80 dark:text-slate-400">
                  <div>{copy.monitor.managedByParent}</div>
                  <div className="mt-2">{copy.monitor.managedByParentHint}</div>
                </div>
              ) : (
                <div className="flex flex-col gap-3">
                  {autopilotLaunchPresets.length > 0 ? (
                    <div className="rounded-[14px] border border-[#d6dbe6] bg-[#fafbff] px-4 py-4 dark:border-slate-800 dark:bg-slate-900/80">
                      <div className="text-[11px] font-semibold uppercase tracking-[0.14em] text-[#6b7280] dark:text-slate-500">
                        {copy.monitor.autopilotLaunchMode}
                      </div>
                      <div className="mt-3 flex flex-wrap gap-2">
                        {autopilotLaunchPresets.map((preset) => (
                          <button
                            key={preset.id}
                            type="button"
                            onClick={() => setSelectedLaunchPresetId(preset.id)}
                            className={`rounded-full border px-3 py-1.5 text-[11px] transition-colors ${
                              selectedLaunchPresetId === preset.id
                                ? "border-black bg-black text-white dark:border-slate-100 dark:bg-slate-100 dark:text-slate-950"
                                : "border-[#d6dbe6] bg-white text-[#4b5563] hover:text-[#111111] dark:border-slate-800 dark:bg-slate-950 dark:text-slate-400 dark:hover:text-slate-100"
                            }`}
                          >
                            {preset.label}
                          </button>
                        ))}
                      </div>
                      {autopilotLaunchPresets.find((preset) => preset.id === selectedLaunchPresetId)?.description ? (
                        <div className="mt-3 text-[12px] leading-6 text-[#4b5563] dark:text-slate-400">
                          {autopilotLaunchPresets.find((preset) => preset.id === selectedLaunchPresetId)?.description}
                        </div>
                      ) : null}
                    </div>
                  ) : null}
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
                  <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
                    <Button
                      type="button"
                      variant="outline"
                      onClick={handleExport}
                      disabled={isExportingBrief || isPreparingTournament || isSendingToAutopilot || isLaunchingInAutopilot}
                      className="h-[46px] rounded-[12px] border-[#111111] bg-white text-[15px] font-medium text-[#111111] dark:border-slate-700 dark:bg-slate-950 dark:text-slate-100 dark:hover:bg-slate-900"
                    >
                      {isExportingBrief ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : null}
                      {copy.monitor.exportBrief}
                    </Button>
                    {canPrepareTournament ? (
                      <Button
                        type="button"
                        variant="outline"
                        onClick={handlePrepareTournament}
                        disabled={isExportingBrief || isPreparingTournament || isSendingToAutopilot || isLaunchingInAutopilot}
                        className="h-[46px] rounded-[12px] border-[#111111] bg-white text-[15px] font-medium text-[#111111] dark:border-slate-700 dark:bg-slate-950 dark:text-slate-100 dark:hover:bg-slate-900"
                      >
                        {isPreparingTournament ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : null}
                        {copy.monitor.prepareTournament}
                      </Button>
                    ) : null}
                    <Button
                      type="button"
                      variant="outline"
                      onClick={handleLaunchInAutopilot}
                      disabled={isExportingBrief || isPreparingTournament || isSendingToAutopilot || isLaunchingInAutopilot}
                      className="h-[46px] rounded-[12px] border-[#111111] bg-white text-[15px] font-medium text-[#111111] dark:border-slate-700 dark:bg-slate-950 dark:text-slate-100 dark:hover:bg-slate-900"
                    >
                      {isLaunchingInAutopilot ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : null}
                      {copy.monitor.launchInAutopilot}
                    </Button>
                    <Button
                      type="button"
                      variant="outline"
                      onClick={handleSendToAutopilot}
                      disabled={isExportingBrief || isPreparingTournament || isSendingToAutopilot || isLaunchingInAutopilot}
                      className="h-[46px] rounded-[12px] border-[#111111] bg-white text-[15px] font-medium text-[#111111] dark:border-slate-700 dark:bg-slate-950 dark:text-slate-100 dark:hover:bg-slate-900"
                    >
                      {isSendingToAutopilot ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : null}
                      {copy.monitor.sendToAutopilot}
                    </Button>
                  </div>
                  {bridgeStatus ? (
                    <div className="rounded-[14px] border border-[#d6dbe6] bg-[#fafbff] px-4 py-3 text-[13px] leading-6 text-[#4b5563] dark:border-slate-800 dark:bg-slate-900/80 dark:text-slate-300">
                      {bridgeStatus}
                    </div>
                  ) : null}
                </div>
              )}
            </div>
          </div>
        </div>

        {!isParallelChild ? (
          <InputBar
            sessionId={session.id}
            status={session.status}
            pendingInstructions={session.pending_instructions}
            checkpointId={selectedCheckpointId ?? session.current_checkpoint_id}
            continueCheckpointId={session.current_checkpoint_id}
            parentSessionId={session.forked_from}
            runtimeState={session.runtime_state}
            onForkSession={onForkSession}
            onOpenSession={onForkSession}
            onRefresh={refresh}
            focusToken={composerFocusToken}
          />
        ) : null}
      </div>
    </div>
  );
}
