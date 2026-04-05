"use client";

import { useEffect, useRef, useState } from "react";
import { useSWRConfig } from "swr";
import { AlertCircle, Loader2, Play, SendHorizonal } from "lucide-react";

import { continueSession, controlSession, sendMessage } from "@/lib/api";
import { useLocale } from "@/lib/locale";
import type { Session } from "@/lib/types";
import { Button } from "@/components/ui/button";

interface InputBarProps {
  sessionId: string;
  status: Session["status"];
  pendingInstructions?: number;
  checkpointId?: string | null;
  continueCheckpointId?: string | null;
  parentSessionId?: string | null;
  runtimeState?: Session["runtime_state"];
  onForkSession?: (sessionId: string) => void;
  onOpenSession?: (sessionId: string) => void;
  onRefresh?: () => void;
  focusToken?: number;
}

export function InputBar({
  sessionId,
  status,
  pendingInstructions = 0,
  checkpointId,
  continueCheckpointId,
  parentSessionId,
  runtimeState,
  onForkSession,
  onOpenSession,
  onRefresh,
  focusToken = 0,
}: InputBarProps) {
  const { copy } = useLocale();
  const { mutate } = useSWRConfig();
  const [draft, setDraft] = useState("");
  const [isWorking, setIsWorking] = useState(false);
  const textareaRef = useRef<HTMLTextAreaElement | null>(null);
  const canQueueInstruction = runtimeState?.can_send_message ?? true;
  const canResume = runtimeState?.can_resume ?? true;
  const canBranchFromCheckpoint = runtimeState?.can_branch_from_checkpoint ?? Boolean(checkpointId);
  const canContinueConversation =
    runtimeState?.can_continue_conversation ?? Boolean(continueCheckpointId ?? checkpointId);
  const pausedActionsAvailable = canQueueInstruction || canResume || canBranchFromCheckpoint;
  const pausedNotice =
    (!canResume ? runtimeState?.reasons?.resume?.message : null) ??
    (!canQueueInstruction ? runtimeState?.reasons?.send_message?.message : null) ??
    (!canBranchFromCheckpoint ? runtimeState?.reasons?.branch_from_checkpoint?.message : null) ??
    null;
  const continueNotice =
    !canContinueConversation
      ? runtimeState?.reasons?.continue_conversation?.message ?? copy.monitor.noCheckpoints
      : null;

  useEffect(() => {
    if (!focusToken) return;
    textareaRef.current?.scrollIntoView({ behavior: "smooth", block: "center" });
    textareaRef.current?.focus();
  }, [focusToken]);

  async function queueInstruction() {
    if (!draft.trim()) return;
    setIsWorking(true);
    try {
      await sendMessage(sessionId, draft);
      setDraft("");
      await onRefresh?.();
    } finally {
      setIsWorking(false);
    }
  }

  async function resumeRun() {
    setIsWorking(true);
    try {
      await controlSession(sessionId, "resume", draft.trim() || undefined);
      setDraft("");
      await onRefresh?.();
    } finally {
      setIsWorking(false);
    }
  }

  async function forkFromCheckpoint() {
    if (!checkpointId) return;
    setIsWorking(true);
    try {
      const result = await controlSession(
        sessionId,
        "restart_from_checkpoint",
        draft.trim() || undefined,
        checkpointId
      );
      setDraft("");
      await onRefresh?.();
      if (result.new_session_id) {
        await mutate("/orchestrate/sessions");
        onForkSession?.(result.new_session_id);
      }
    } finally {
      setIsWorking(false);
    }
  }

  async function continueConversation() {
    if (!draft.trim()) return;
    if (!(continueCheckpointId ?? checkpointId)) return;
    setIsWorking(true);
    try {
      const result = await continueSession(sessionId, draft.trim());
      setDraft("");
      await onRefresh?.();
      if (result.new_session_id) {
        await mutate("/orchestrate/sessions");
        onForkSession?.(result.new_session_id);
      }
    } finally {
      setIsWorking(false);
    }
  }

  if (status === "paused") {
    return (
      <div className="border-t border-slate-200/70 bg-white/70 px-6 py-4 backdrop-blur-md dark:border-slate-800/70 dark:bg-slate-950/40">
        <div className="rounded-[26px] border border-orange-200/70 bg-[linear-gradient(135deg,rgba(255,251,235,0.94),rgba(255,247,237,0.9))] px-5 py-5 shadow-[0_24px_60px_-44px_rgba(249,115,22,0.45)] dark:border-orange-900/60 dark:bg-[linear-gradient(135deg,rgba(67,20,7,0.55),rgba(30,27,75,0.38))]">
          <div className="flex items-start gap-2.5">
            <AlertCircle className="mt-0.5 h-4 w-4 shrink-0 text-orange-600 dark:text-orange-400" />
            <div className="min-w-0 flex-1">
              <p className="text-[10px] font-semibold uppercase tracking-[0.2em] text-orange-700 dark:text-orange-300">
                {copy.input.checkpointControl}
              </p>
              <p className="mt-2 text-[14px] font-semibold text-foreground/90">
                {copy.input.sessionPaused}
              </p>
              <p className="mt-1 text-[12px] leading-relaxed text-muted-foreground/80">
                {copy.input.sessionPausedHint}
              </p>
              {pendingInstructions > 0 && (
                <p className="mt-1 text-[12px] text-orange-700 dark:text-orange-300">
                  {copy.input.queuedInstructions}: {pendingInstructions}
                </p>
              )}
              <textarea
                ref={textareaRef}
                value={draft}
                onChange={(e) => setDraft(e.target.value)}
                placeholder={copy.input.instructionPlaceholder}
                rows={3}
                disabled={!pausedActionsAvailable}
                className="mt-4 w-full resize-none rounded-2xl border border-orange-200/70 bg-white/85 px-4 py-3 text-sm text-foreground placeholder:text-muted-foreground/50 shadow-inner focus:outline-none focus:ring-2 focus:ring-orange-400/25 dark:border-orange-900/60 dark:bg-slate-950/50"
              />
              <div className="mt-4 flex flex-wrap gap-2">
                <Button
                  variant="outline"
                  size="sm"
                  className="rounded-full border-orange-200/80 bg-white/85 text-xs dark:border-orange-900/60 dark:bg-slate-950/40"
                  onClick={queueInstruction}
                  disabled={isWorking || !draft.trim() || !canQueueInstruction}
                >
                  {isWorking ? <Loader2 className="mr-1.5 h-3.5 w-3.5 animate-spin" /> : <SendHorizonal className="mr-1.5 h-3.5 w-3.5" />}
                  {copy.input.saveInstruction}
                </Button>
                <Button
                  size="sm"
                  className="rounded-full bg-slate-950 text-xs text-white hover:bg-slate-800 dark:bg-slate-100 dark:text-slate-950 dark:hover:bg-white"
                  onClick={resumeRun}
                  disabled={isWorking || !canResume}
                >
                  {isWorking ? <Loader2 className="mr-1.5 h-3.5 w-3.5 animate-spin" /> : <Play className="mr-1.5 h-3.5 w-3.5" />}
                  {draft.trim() ? copy.input.resumeWithInstruction : copy.input.resume}
                </Button>
                <Button
                  variant="secondary"
                  size="sm"
                  className="rounded-full text-xs"
                  onClick={forkFromCheckpoint}
                  disabled={isWorking || !checkpointId || !canBranchFromCheckpoint}
                >
                  {isWorking ? <Loader2 className="mr-1.5 h-3.5 w-3.5 animate-spin" /> : <Play className="mr-1.5 h-3.5 w-3.5" />}
                  {copy.input.newBranch}
                </Button>
              </div>
              {pausedNotice ? (
                <p className="mt-3 text-[12px] leading-5 text-orange-700 dark:text-orange-300">
                  {pausedNotice}
                </p>
              ) : null}
            </div>
          </div>
        </div>
      </div>
    );
  }

  if (["completed", "failed", "cancelled"].includes(status)) {
    if (!canContinueConversation && parentSessionId) {
      return (
        <div className="border-t border-slate-200/70 bg-white/70 px-6 py-4 backdrop-blur-md dark:border-slate-800/70 dark:bg-slate-950/40">
          <div className="rounded-[26px] border border-[#d6dbe6] bg-[linear-gradient(135deg,rgba(250,251,255,0.96),rgba(255,255,255,0.9))] px-5 py-5 shadow-[0_24px_60px_-44px_rgba(17,48,105,0.25)] dark:border-slate-800 dark:bg-[linear-gradient(135deg,rgba(15,23,42,0.72),rgba(2,6,23,0.5))]">
            <div className="flex items-start gap-2.5">
              <AlertCircle className="mt-0.5 h-4 w-4 shrink-0 text-slate-700 dark:text-slate-300" />
              <div className="min-w-0 flex-1">
                <p className="text-[10px] font-semibold uppercase tracking-[0.2em] text-[#6b7280] dark:text-slate-400">
                  {copy.input.teamContinue}
                </p>
                <p className="mt-2 text-[14px] font-semibold text-foreground/90">
                  {copy.input.openParentToContinue}
                </p>
                <p className="mt-2 text-[12px] leading-relaxed text-muted-foreground/80">
                  {copy.input.continueFromParentHint}
                </p>
                {continueNotice ? (
                  <p className="mt-3 text-[12px] leading-5 text-[#6b7280] dark:text-slate-400">
                    {continueNotice}
                  </p>
                ) : null}
                <div className="mt-4 flex flex-wrap gap-2">
                  <Button
                    type="button"
                    size="sm"
                    className="rounded-full bg-slate-950 text-xs text-white hover:bg-slate-800 dark:bg-slate-100 dark:text-slate-950 dark:hover:bg-white"
                    onClick={() => onOpenSession?.(parentSessionId)}
                  >
                    <Play className="mr-1.5 h-3.5 w-3.5" />
                    {copy.input.openParentSession}
                  </Button>
                </div>
              </div>
            </div>
          </div>
        </div>
      );
    }

    return (
      <div className="border-t border-slate-200/70 bg-white/70 px-6 py-4 backdrop-blur-md dark:border-slate-800/70 dark:bg-slate-950/40">
        <div className="rounded-[26px] border border-[#d6dbe6] bg-[linear-gradient(135deg,rgba(250,251,255,0.96),rgba(255,255,255,0.9))] px-5 py-5 shadow-[0_24px_60px_-44px_rgba(17,48,105,0.25)] dark:border-slate-800 dark:bg-[linear-gradient(135deg,rgba(15,23,42,0.72),rgba(2,6,23,0.5))]">
          <div className="flex items-start gap-2.5">
            <AlertCircle className="mt-0.5 h-4 w-4 shrink-0 text-slate-700 dark:text-slate-300" />
            <div className="min-w-0 flex-1">
              <p className="text-[10px] font-semibold uppercase tracking-[0.2em] text-[#6b7280] dark:text-slate-400">
                {copy.input.teamContinue}
              </p>
              <p className="mt-2 text-[14px] font-semibold text-foreground/90">
                {copy.input.teamContinueHint}
              </p>
              <textarea
                ref={textareaRef}
                value={draft}
                onChange={(e) => setDraft(e.target.value)}
                placeholder={copy.input.teamContinuePlaceholder}
                rows={3}
                disabled={!canContinueConversation}
                className="mt-4 w-full resize-none rounded-2xl border border-[#d6dbe6] bg-white/85 px-4 py-3 text-sm text-foreground placeholder:text-muted-foreground/50 shadow-inner focus:outline-none focus:ring-2 focus:ring-slate-400/20 dark:border-slate-800 dark:bg-slate-950/50"
              />
              <div className="mt-4 flex flex-wrap gap-2">
                <Button
                  size="sm"
                  className="rounded-full bg-slate-950 text-xs text-white hover:bg-slate-800 dark:bg-slate-100 dark:text-slate-950 dark:hover:bg-white"
                  onClick={continueConversation}
                  disabled={isWorking || !draft.trim() || !canContinueConversation}
                >
                  {isWorking ? <Loader2 className="mr-1.5 h-3.5 w-3.5 animate-spin" /> : <Play className="mr-1.5 h-3.5 w-3.5" />}
                  {copy.input.continueDiscussion}
                </Button>
                {!canContinueConversation ? (
                  <span className="self-center text-[12px] text-[#6b7280] dark:text-slate-400">
                    {continueNotice}
                  </span>
                ) : null}
              </div>
            </div>
          </div>
        </div>
      </div>
    );
  }

  return null;
}
