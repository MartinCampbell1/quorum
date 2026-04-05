"use client";

import { useEffect, useState } from "react";
import { GitBranch, Loader2, PlayCircle, RefreshCcw } from "lucide-react";

import { Button } from "@/components/ui/button";
import { getDebateReplay, getSessions } from "@/lib/api";
import { useLocale } from "@/lib/locale";
import type { DebateReplaySession, SessionSummary } from "@/lib/types";

function formatDelta(createdAt: number, timestamp: number): string {
  if (!timestamp || !createdAt) return "t+0s";
  const delta = Math.max(0, timestamp - createdAt);
  return `t+${delta.toFixed(delta >= 10 ? 0 : 1)}s`;
}

export function DebateReplayCard() {
  const { locale } = useLocale();
  const text =
    locale === "ru"
      ? {
          title: "Debate replay",
          subtitle: "Replay surface для generation/debate/runtime traces по последним quorum sessions.",
          loading: "Собираю replay surface…",
          error: "Не удалось загрузить replay surface.",
          refresh: "Обновить",
          empty: "Пока нет сессий с replayable history.",
          timeline: "Timeline",
          participants: "Участники",
          invalid: "invalid",
        }
      : {
          title: "Debate replay",
          subtitle: "Replay surface for generation, debate, and runtime traces from recent Quorum sessions.",
          loading: "Loading the replay surface…",
          error: "Failed to load the replay surface.",
          refresh: "Refresh",
          empty: "No sessions with replayable history yet.",
          timeline: "Timeline",
          participants: "Participants",
          invalid: "invalid",
        };

  const [sessions, setSessions] = useState<SessionSummary[]>([]);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [replay, setReplay] = useState<DebateReplaySession | null>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function load(showLoader: boolean) {
    if (showLoader) {
      setLoading(true);
    } else {
      setRefreshing(true);
    }
    setError(null);
    try {
      const nextSessions = await getSessions();
      setSessions(nextSessions.slice(0, 6));
      const chosenId = selectedId ?? nextSessions[0]?.id ?? null;
      setSelectedId(chosenId);
      if (chosenId) {
        setReplay(await getDebateReplay(chosenId));
      } else {
        setReplay(null);
      }
    } catch (nextError) {
      setError(nextError instanceof Error ? nextError.message : text.error);
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }

  async function handleSelect(sessionId: string) {
    setSelectedId(sessionId);
    setError(null);
    try {
      setReplay(await getDebateReplay(sessionId));
    } catch (nextError) {
      setError(nextError instanceof Error ? nextError.message : text.error);
    }
  }

  useEffect(() => {
    void load(true);
  }, []);

  return (
    <section className="rounded-[28px] border border-[#d6dbe6] bg-white/90 p-5 shadow-[0_16px_38px_-28px_rgba(17,48,105,0.22)] dark:border-slate-800 dark:bg-slate-950/60 dark:shadow-none">
      <div className="flex flex-col gap-4 xl:flex-row xl:items-start xl:justify-between">
        <div>
          <div className="flex items-center gap-2 text-[20px] font-semibold tracking-[-0.04em] text-[#111111] dark:text-slate-100">
            <PlayCircle className="h-5 w-5" />
            {text.title}
          </div>
          <div className="mt-2 max-w-3xl text-[13px] leading-6 text-[#6b7280] dark:text-slate-400">
            {text.subtitle}
          </div>
        </div>
        <Button type="button" variant="outline" size="sm" onClick={() => void load(false)} className="h-8 rounded-full text-[11px]">
          {refreshing ? <Loader2 className="mr-1 h-3.5 w-3.5 animate-spin" /> : <RefreshCcw className="mr-1 h-3.5 w-3.5" />}
          {text.refresh}
        </Button>
      </div>

      {loading ? (
        <div className="mt-5 flex items-center gap-3 rounded-[20px] border border-[#d6dbe6] bg-[#fbfcff] px-4 py-5 text-[13px] text-[#4b5563] dark:border-slate-800 dark:bg-slate-900/60 dark:text-slate-300">
          <Loader2 className="h-4 w-4 animate-spin" />
          {text.loading}
        </div>
      ) : error ? (
        <div className="mt-5 rounded-[20px] border border-rose-200 bg-rose-50 px-4 py-5 text-[13px] text-rose-700 dark:border-rose-900/60 dark:bg-rose-950/40 dark:text-rose-300">
          {error}
        </div>
      ) : !replay ? (
        <div className="mt-5 rounded-[20px] border border-dashed border-[#d6dbe6] bg-[#fbfcff] px-4 py-6 text-[13px] leading-6 text-[#6b7280] dark:border-slate-800 dark:bg-slate-900/60 dark:text-slate-400">
          {text.empty}
        </div>
      ) : (
        <div className="mt-5 grid gap-4 xl:grid-cols-[280px_minmax(0,1fr)]">
          <div className="space-y-3">
            {sessions.map((session) => (
              <button
                key={session.id}
                type="button"
                onClick={() => void handleSelect(session.id)}
                className={`w-full rounded-[18px] border px-4 py-3 text-left transition ${
                  session.id === selectedId
                    ? "border-[#111111] bg-[#111111] text-white dark:border-slate-200 dark:bg-slate-100 dark:text-slate-950"
                    : "border-[#d6dbe6] bg-[#fbfcff] text-[#111111] dark:border-slate-800 dark:bg-slate-900/60 dark:text-slate-100"
                }`}
              >
                <div className="truncate text-[13px] font-medium">{session.task}</div>
                <div className="mt-1 text-[11px] opacity-80">{session.mode} · {session.status}</div>
              </button>
            ))}
          </div>

          <div className="space-y-4">
            <div className="rounded-[20px] border border-[#d6dbe6] bg-[#fbfcff] px-4 py-4 dark:border-slate-800 dark:bg-slate-900/60">
              <div className="flex flex-wrap items-center gap-2 text-[11px] uppercase tracking-[0.14em] text-[#6b7280] dark:text-slate-500">
                <GitBranch className="h-3.5 w-3.5" />
                {replay.mode}
                <span>·</span>
                <span>{replay.timeline.length} steps</span>
                <span>·</span>
                <span>{replay.invalid_transition_count} {text.invalid}</span>
              </div>
              <div className="mt-3 text-[14px] font-semibold tracking-[-0.03em] text-[#111111] dark:text-slate-100">
                {replay.task}
              </div>
              <div className="mt-2 text-[12px] leading-6 text-[#6b7280] dark:text-slate-400">
                {text.participants}: {replay.participants.map((item) => `${item.role} (${item.provider})`).join(", ")}
              </div>
            </div>

            <div className="rounded-[20px] border border-[#d6dbe6] bg-[#fbfcff] px-4 py-4 dark:border-slate-800 dark:bg-slate-900/60">
              <div className="text-[11px] uppercase tracking-[0.14em] text-[#6b7280] dark:text-slate-500">{text.timeline}</div>
              <div className="mt-3 space-y-2">
                {replay.timeline.slice(-8).reverse().map((item) => (
                  <div key={item.replay_id} className="rounded-[14px] bg-white px-3 py-3 dark:bg-slate-950/70">
                    <div className="flex items-center justify-between gap-3">
                      <div className="text-[13px] font-medium text-[#111111] dark:text-slate-100">{item.title}</div>
                      <div className="text-[11px] text-[#6b7280] dark:text-slate-400">
                        {formatDelta(replay.created_at, item.timestamp)}
                      </div>
                    </div>
                    <div className="mt-1 text-[12px] leading-6 text-[#4b5563] dark:text-slate-300">
                      {item.detail || item.kind}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </div>
      )}
    </section>
  );
}
