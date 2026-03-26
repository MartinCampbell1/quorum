"use client";

import { useState } from "react";
import { AlertCircle, Loader2, Play, SendHorizonal } from "lucide-react";

import { controlSession, sendMessage } from "@/lib/api";
import type { Session } from "@/lib/types";
import { Button } from "@/components/ui/button";

interface InputBarProps {
  sessionId: string;
  status: Session["status"];
  pendingInstructions?: number;
  currentCheckpointId?: string | null;
  onForkSession?: (sessionId: string) => void;
  onRefresh?: () => void;
}

export function InputBar({
  sessionId,
  status,
  pendingInstructions = 0,
  currentCheckpointId,
  onForkSession,
  onRefresh,
}: InputBarProps) {
  const [draft, setDraft] = useState("");
  const [isWorking, setIsWorking] = useState(false);

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
    if (!currentCheckpointId) return;
    setIsWorking(true);
    try {
      const result = await controlSession(
        sessionId,
        "restart_from_checkpoint",
        draft.trim() || undefined,
        currentCheckpointId
      );
      setDraft("");
      await onRefresh?.();
      if (result.new_session_id) {
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
                Checkpoint Control
              </p>
              <p className="mt-2 text-[14px] font-semibold text-foreground/90">
                Сессия остановлена на checkpoint.
              </p>
              <p className="mt-1 text-[12px] leading-relaxed text-muted-foreground/80">
                Добавь инструкцию, если хочешь скорректировать следующий шаг, или просто продолжи выполнение.
              </p>
              {pendingInstructions > 0 && (
                <p className="mt-1 text-[12px] text-orange-700 dark:text-orange-300">
                  В очереди инструкций: {pendingInstructions}
                </p>
              )}
              <textarea
                value={draft}
                onChange={(e) => setDraft(e.target.value)}
                placeholder="Например: проверь гипотезу глубже и опирайся на последние новости по BTC"
                rows={3}
                className="mt-4 w-full resize-none rounded-2xl border border-orange-200/70 bg-white/85 px-4 py-3 text-sm text-foreground placeholder:text-muted-foreground/50 shadow-inner focus:outline-none focus:ring-2 focus:ring-orange-400/25 dark:border-orange-900/60 dark:bg-slate-950/50"
              />
              <div className="mt-4 flex flex-wrap gap-2">
                <Button
                  variant="outline"
                  size="sm"
                  className="rounded-full border-orange-200/80 bg-white/85 text-xs dark:border-orange-900/60 dark:bg-slate-950/40"
                  onClick={queueInstruction}
                  disabled={isWorking || !draft.trim()}
                >
                  {isWorking ? <Loader2 className="mr-1.5 h-3.5 w-3.5 animate-spin" /> : <SendHorizonal className="mr-1.5 h-3.5 w-3.5" />}
                  Сохранить инструкцию
                </Button>
                <Button
                  size="sm"
                  className="rounded-full bg-slate-950 text-xs text-white hover:bg-slate-800 dark:bg-slate-100 dark:text-slate-950 dark:hover:bg-white"
                  onClick={resumeRun}
                  disabled={isWorking}
                >
                  {isWorking ? <Loader2 className="mr-1.5 h-3.5 w-3.5 animate-spin" /> : <Play className="mr-1.5 h-3.5 w-3.5" />}
                  {draft.trim() ? "Продолжить с инструкцией" : "Продолжить"}
                </Button>
                <Button
                  variant="secondary"
                  size="sm"
                  className="rounded-full text-xs"
                  onClick={forkFromCheckpoint}
                  disabled={isWorking || !currentCheckpointId}
                >
                  {isWorking ? <Loader2 className="mr-1.5 h-3.5 w-3.5 animate-spin" /> : <Play className="mr-1.5 h-3.5 w-3.5" />}
                  Новая ветка
                </Button>
              </div>
            </div>
          </div>
        </div>
      </div>
    );
  }

  let title = "Сессия только для наблюдения.";
  let body = "Здесь будет доступен ввод, когда прогон остановится на checkpoint или завершится поддержка live control.";

  if (status === "running") {
    title = "Идёт выполнение.";
    body = "Можно нажать «Пауза» в заголовке. Система остановится после текущего узла, а не посреди шага.";
  } else if (status === "pause_requested") {
    title = "Пауза запрошена.";
    body = "Текущий узел должен завершиться, после этого сессия перейдёт в paused и примет инструкцию.";
  } else if (status === "cancel_requested") {
    title = "Остановка запрошена.";
    body = "Сессия завершится на ближайшем безопасном checkpoint.";
  }

  return (
    <div className="border-t border-slate-200/70 bg-white/70 px-6 py-4 backdrop-blur-md dark:border-slate-800/70 dark:bg-slate-950/40">
      <div className="flex items-start gap-3 rounded-[22px] border border-dashed border-slate-200/80 bg-[linear-gradient(135deg,rgba(255,255,255,0.85),rgba(248,250,252,0.82))] px-4 py-4 dark:border-slate-800/80 dark:bg-[linear-gradient(135deg,rgba(15,23,42,0.72),rgba(2,6,23,0.64))]">
        <AlertCircle className="mt-0.5 h-4 w-4 shrink-0 text-muted-foreground/70" />
        <div className="min-w-0">
          <p className="text-[10px] font-semibold uppercase tracking-[0.2em] text-slate-500 dark:text-slate-400">
            Session Notes
          </p>
          <p className="mt-1 text-[13px] font-medium text-foreground/80">{title}</p>
          <p className="mt-1 text-[12px] leading-relaxed text-muted-foreground/70">{body}</p>
        </div>
      </div>
    </div>
  );
}
