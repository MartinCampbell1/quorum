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
  onRefresh?: () => void;
}

export function InputBar({ sessionId, status, pendingInstructions = 0, onRefresh }: InputBarProps) {
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

  if (status === "paused") {
    return (
      <div className="border-t bg-background px-6 py-3.5">
        <div className="rounded-xl border border-orange-500/20 bg-orange-50/60 px-4 py-4 dark:bg-orange-950/20">
          <div className="flex items-start gap-2.5">
            <AlertCircle className="mt-0.5 h-4 w-4 shrink-0 text-orange-600 dark:text-orange-400" />
            <div className="min-w-0 flex-1">
              <p className="text-[13px] font-medium text-foreground/90">
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
                className="mt-3 w-full rounded-xl border border-border bg-background px-3 py-2.5 text-sm text-foreground placeholder:text-muted-foreground/50 resize-none focus:outline-none focus:ring-2 focus:ring-ring/30"
              />
              <div className="mt-3 flex flex-wrap gap-2">
                <Button
                  variant="outline"
                  size="sm"
                  className="text-xs"
                  onClick={queueInstruction}
                  disabled={isWorking || !draft.trim()}
                >
                  {isWorking ? <Loader2 className="mr-1.5 h-3.5 w-3.5 animate-spin" /> : <SendHorizonal className="mr-1.5 h-3.5 w-3.5" />}
                  Сохранить инструкцию
                </Button>
                <Button
                  size="sm"
                  className="text-xs"
                  onClick={resumeRun}
                  disabled={isWorking}
                >
                  {isWorking ? <Loader2 className="mr-1.5 h-3.5 w-3.5 animate-spin" /> : <Play className="mr-1.5 h-3.5 w-3.5" />}
                  {draft.trim() ? "Продолжить с инструкцией" : "Продолжить"}
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
    <div className="border-t bg-background px-6 py-3.5">
      <div className="flex items-start gap-2.5 rounded-lg border border-dashed border-border/70 bg-muted/20 px-4 py-3">
        <AlertCircle className="mt-0.5 h-4 w-4 shrink-0 text-muted-foreground/70" />
        <div className="min-w-0">
          <p className="text-[13px] font-medium text-foreground/80">{title}</p>
          <p className="mt-1 text-[12px] leading-relaxed text-muted-foreground/70">{body}</p>
        </div>
      </div>
    </div>
  );
}
