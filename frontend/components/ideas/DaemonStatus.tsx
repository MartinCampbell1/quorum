"use client";

import { useEffect, useState } from "react";
import { Activity, AlertTriangle, Loader2, PauseCircle, PlayCircle, RefreshCcw, TimerReset } from "lucide-react";

import { Button } from "@/components/ui/button";
import { controlDiscoveryDaemon, getDiscoveryDaemonStatus } from "@/lib/api";
import { useLocale } from "@/lib/locale";
import type { DiscoveryDaemonStatus as DiscoveryDaemonStatusPayload, DiscoveryRoutineState } from "@/lib/types";


function formatTimestamp(value?: string | null): string {
  if (!value) return "pending";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "pending";
  return date.toLocaleString();
}

function RoutineRow({
  item,
  busy,
  onRun,
}: {
  item: DiscoveryRoutineState;
  busy: boolean;
  onRun: (routineKind: DiscoveryRoutineState["routine_kind"]) => void;
}) {
  return (
    <div className="rounded-[18px] border border-[#d6dbe6] bg-[#fbfcff] px-4 py-4 dark:border-slate-800 dark:bg-slate-900/60">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <div className="text-[14px] font-semibold tracking-[-0.03em] text-[#111111] dark:text-slate-100">
            {item.label}
          </div>
          <div className="mt-1 text-[11px] text-[#6b7280] dark:text-slate-400">
            every {item.cadence_minutes}m / next {formatTimestamp(item.next_due_at)}
          </div>
        </div>
        <Button type="button" variant="outline" size="sm" onClick={() => onRun(item.routine_kind)} disabled={busy} className="h-8 rounded-full text-[11px]">
          {busy ? <Loader2 className="mr-1 h-3.5 w-3.5 animate-spin" /> : <TimerReset className="mr-1 h-3.5 w-3.5" />}
          Run now
        </Button>
      </div>
      <div className="mt-3 flex flex-wrap gap-2 text-[10px] uppercase tracking-[0.14em] text-[#6b7280] dark:text-slate-500">
        <span className="rounded-full border border-[#d6dbe6] bg-white px-2 py-1 dark:border-slate-800 dark:bg-slate-950/70">
          {item.last_status}
        </span>
        <span className="rounded-full border border-[#d6dbe6] bg-white px-2 py-1 dark:border-slate-800 dark:bg-slate-950/70">
          max {item.max_ideas}
        </span>
        <span className="rounded-full border border-[#d6dbe6] bg-white px-2 py-1 dark:border-slate-800 dark:bg-slate-950/70">
          budget ${item.budget_limit_usd.toFixed(2)}
        </span>
      </div>
      <div className="mt-3 text-[12px] leading-6 text-[#4b5563] dark:text-slate-300">
        {item.summary || "The daemon has not written a routine summary yet."}
      </div>
    </div>
  );
}

export function DaemonStatus() {
  const { locale } = useLocale();
  const text =
    locale === "ru"
      ? {
          title: "Daemon status",
          subtitle: "24/7 discovery loops, fresh-session policy и health alerts для offline refresh.",
          start: "Запустить",
          pause: "Пауза",
          resume: "Продолжить",
          stop: "Стоп",
          tick: "Прогнать due routines",
          loading: "Считываю daemon state…",
          error: "Не удалось загрузить daemon status.",
          fresh: "Fresh session policy",
          inbox: "Open inbox",
          heartbeat: "Worker heartbeat",
          alerts: "Alerts",
          routines: "Routines",
          recentRuns: "Recent runs",
          emptyRuns: "Пока нет daemon runs.",
          noAlerts: "Сейчас health alerts нет.",
        }
      : {
          title: "Daemon status",
          subtitle: "24/7 discovery loops, fresh-session policy, and health alerts for offline refresh work.",
          start: "Start",
          pause: "Pause",
          resume: "Resume",
          stop: "Stop",
          tick: "Run due routines",
          loading: "Loading daemon state…",
          error: "Failed to load daemon status.",
          fresh: "Fresh session policy",
          inbox: "Open inbox",
          heartbeat: "Worker heartbeat",
          alerts: "Alerts",
          routines: "Routines",
          recentRuns: "Recent runs",
          emptyRuns: "No daemon runs have landed yet.",
          noAlerts: "No daemon health alerts right now.",
        };

  const [status, setStatus] = useState<DiscoveryDaemonStatusPayload | null>(null);
  const [loading, setLoading] = useState(true);
  const [busyKey, setBusyKey] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function load(showLoader: boolean = false) {
    if (showLoader) setLoading(true);
    setError(null);
    try {
      setStatus(await getDiscoveryDaemonStatus());
    } catch (nextError) {
      setError(nextError instanceof Error ? nextError.message : text.error);
    } finally {
      setLoading(false);
    }
  }

  async function handleControl(action: "start" | "pause" | "resume" | "stop" | "tick" | "run_routine", routineKind?: DiscoveryRoutineState["routine_kind"]) {
    const key = routineKind ? `${action}:${routineKind}` : action;
    setBusyKey(key);
    setError(null);
    try {
      const next = await controlDiscoveryDaemon({ action, routine_kind: routineKind });
      setStatus(next);
    } catch (nextError) {
      setError(nextError instanceof Error ? nextError.message : text.error);
    } finally {
      setBusyKey(null);
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
            <Activity className="h-5 w-5" />
            {text.title}
          </div>
          <div className="mt-2 max-w-3xl text-[13px] leading-6 text-[#6b7280] dark:text-slate-400">
            {text.subtitle}
          </div>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <Button type="button" variant="outline" size="sm" onClick={() => void load(true)} className="h-8 rounded-full text-[11px]">
            {loading ? <Loader2 className="mr-1 h-3.5 w-3.5 animate-spin" /> : <RefreshCcw className="mr-1 h-3.5 w-3.5" />}
            Refresh
          </Button>
          {status?.mode === "running" ? (
            <Button type="button" variant="outline" size="sm" onClick={() => void handleControl("pause")} disabled={busyKey === "pause"} className="h-8 rounded-full text-[11px]">
              {busyKey === "pause" ? <Loader2 className="mr-1 h-3.5 w-3.5 animate-spin" /> : <PauseCircle className="mr-1 h-3.5 w-3.5" />}
              {text.pause}
            </Button>
          ) : (
            <Button
              type="button"
              size="sm"
              onClick={() => void handleControl(status?.mode === "paused" ? "resume" : "start")}
              disabled={busyKey === "start" || busyKey === "resume"}
              className="h-8 rounded-full bg-black text-[11px] text-white hover:bg-black/90"
            >
              {busyKey === "start" || busyKey === "resume" ? <Loader2 className="mr-1 h-3.5 w-3.5 animate-spin" /> : <PlayCircle className="mr-1 h-3.5 w-3.5" />}
              {status?.mode === "paused" ? text.resume : text.start}
            </Button>
          )}
          <Button type="button" variant="outline" size="sm" onClick={() => void handleControl("tick")} disabled={busyKey === "tick"} className="h-8 rounded-full text-[11px]">
            {busyKey === "tick" ? <Loader2 className="mr-1 h-3.5 w-3.5 animate-spin" /> : <TimerReset className="mr-1 h-3.5 w-3.5" />}
            {text.tick}
          </Button>
          <Button type="button" variant="outline" size="sm" onClick={() => void handleControl("stop")} disabled={busyKey === "stop"} className="h-8 rounded-full text-[11px]">
            {busyKey === "stop" ? <Loader2 className="mr-1 h-3.5 w-3.5 animate-spin" /> : <PauseCircle className="mr-1 h-3.5 w-3.5" />}
            {text.stop}
          </Button>
        </div>
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
      ) : !status ? null : (
        <>
          <div className="mt-5 grid gap-3 md:grid-cols-2 xl:grid-cols-4">
            <div className="rounded-[18px] border border-[#d6dbe6] bg-[#fbfcff] px-4 py-4 dark:border-slate-800 dark:bg-slate-900/60">
              <div className="text-[11px] uppercase tracking-[0.14em] text-[#6b7280] dark:text-slate-500">Mode</div>
              <div className="mt-2 text-[28px] font-semibold tracking-[-0.04em] text-[#111111] dark:text-slate-100">{status.mode}</div>
            </div>
            <div className="rounded-[18px] border border-[#d6dbe6] bg-[#fbfcff] px-4 py-4 dark:border-slate-800 dark:bg-slate-900/60">
              <div className="text-[11px] uppercase tracking-[0.14em] text-[#6b7280] dark:text-slate-500">{text.fresh}</div>
              <div className="mt-2 text-[14px] font-semibold tracking-[-0.03em] text-[#111111] dark:text-slate-100">{status.fresh_session_policy}</div>
            </div>
            <div className="rounded-[18px] border border-[#d6dbe6] bg-[#fbfcff] px-4 py-4 dark:border-slate-800 dark:bg-slate-900/60">
              <div className="text-[11px] uppercase tracking-[0.14em] text-[#6b7280] dark:text-slate-500">{text.inbox}</div>
              <div className="mt-2 text-[28px] font-semibold tracking-[-0.04em] text-[#111111] dark:text-slate-100">{status.inbox_pending_count}</div>
            </div>
            <div className="rounded-[18px] border border-[#d6dbe6] bg-[#fbfcff] px-4 py-4 dark:border-slate-800 dark:bg-slate-900/60">
              <div className="text-[11px] uppercase tracking-[0.14em] text-[#6b7280] dark:text-slate-500">{text.heartbeat}</div>
              <div className="mt-2 text-[13px] leading-6 text-[#111111] dark:text-slate-100">{formatTimestamp(status.worker_heartbeat_at)}</div>
            </div>
          </div>

          <div className="mt-5 grid gap-4 xl:grid-cols-[minmax(0,1.05fr)_minmax(320px,0.95fr)]">
            <div>
              <div className="flex items-center gap-2 text-[11px] uppercase tracking-[0.14em] text-[#6b7280] dark:text-slate-500">
                <TimerReset className="h-3.5 w-3.5" />
                {text.routines}
              </div>
              <div className="mt-3 space-y-3">
                {status.routines.map((item) => (
                  <RoutineRow
                    key={item.routine_kind}
                    item={item}
                    busy={busyKey === `run_routine:${item.routine_kind}`}
                    onRun={(routineKind) => void handleControl("run_routine", routineKind)}
                  />
                ))}
              </div>
            </div>

            <div className="space-y-4">
              <div className="rounded-[20px] border border-[#d6dbe6] bg-[#fbfcff] px-4 py-4 dark:border-slate-800 dark:bg-slate-900/60">
                <div className="flex items-center gap-2 text-[11px] uppercase tracking-[0.14em] text-[#6b7280] dark:text-slate-500">
                  <AlertTriangle className="h-3.5 w-3.5" />
                  {text.alerts}
                </div>
                <div className="mt-3 space-y-2">
                  {status.alerts.length === 0 ? (
                    <div className="rounded-[14px] bg-white px-3 py-3 text-[12px] leading-6 text-[#4b5563] dark:bg-slate-950/70 dark:text-slate-300">
                      {text.noAlerts}
                    </div>
                  ) : (
                    status.alerts.map((alert) => (
                      <div key={alert.alert_id} className="rounded-[14px] bg-white px-3 py-3 dark:bg-slate-950/70">
                        <div className="text-[12px] font-semibold uppercase tracking-[0.12em] text-rose-700 dark:text-rose-300">{alert.severity}</div>
                        <div className="mt-1 text-[13px] font-medium text-[#111111] dark:text-slate-100">{alert.title}</div>
                        <div className="mt-1 text-[12px] leading-6 text-[#4b5563] dark:text-slate-300">{alert.detail}</div>
                      </div>
                    ))
                  )}
                </div>
              </div>

              <div className="rounded-[20px] border border-[#d6dbe6] bg-[#fbfcff] px-4 py-4 dark:border-slate-800 dark:bg-slate-900/60">
                <div className="text-[11px] uppercase tracking-[0.14em] text-[#6b7280] dark:text-slate-500">{text.recentRuns}</div>
                <div className="mt-3 space-y-2">
                  {status.recent_runs.length === 0 ? (
                    <div className="rounded-[14px] bg-white px-3 py-3 text-[12px] leading-6 text-[#4b5563] dark:bg-slate-950/70 dark:text-slate-300">
                      {text.emptyRuns}
                    </div>
                  ) : (
                    status.recent_runs.slice(0, 6).map((run) => (
                      <div key={run.run_id} className="rounded-[14px] bg-white px-3 py-3 dark:bg-slate-950/70">
                        <div className="flex items-center justify-between gap-3">
                          <div className="text-[13px] font-medium text-[#111111] dark:text-slate-100">{run.routine_kind}</div>
                          <div className="text-[10px] uppercase tracking-[0.14em] text-[#6b7280] dark:text-slate-400">{run.status}</div>
                        </div>
                        <div className="mt-1 text-[12px] leading-6 text-[#4b5563] dark:text-slate-300">{run.summary}</div>
                      </div>
                    ))
                  )}
                </div>
              </div>
            </div>
          </div>
        </>
      )}
    </section>
  );
}
