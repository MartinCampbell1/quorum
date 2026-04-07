"use client";

import { useEffect, useState } from "react";
import { Activity, Gauge, Loader2, Radar, RefreshCcw } from "lucide-react";

import { Button } from "@/components/ui/button";
import { getDiscoveryObservabilityScoreboard, getDiscoveryObservabilityTraces } from "@/lib/api";
import { useLocale } from "@/lib/locale";
import type { DiscoveryObservabilityScoreboard, DiscoveryTraceSnapshot, IdeaTraceBundle } from "@/lib/types";

function formatMetric(value: number, unit: string): string {
  if (unit === "ratio") return `${Math.round(value * 100)}%`;
  if (unit === "usd") return `$${value.toFixed(2)}`;
  if (unit === "seconds") return `${value.toFixed(1)}s`;
  return value.toFixed(value >= 10 ? 0 : 2);
}

function MetricCard({
  label,
  value,
  detail,
  unit,
}: {
  label: string;
  value: number;
  detail: string;
  unit: string;
}) {
  return (
    <div className="rounded-[18px] border border-[#d6dbe6] bg-[#fbfcff] px-4 py-4 dark:border-slate-800 dark:bg-slate-900/60">
      <div className="text-[11px] uppercase tracking-[0.14em] text-[#6b7280] dark:text-slate-500">{label}</div>
      <div className="mt-2 text-[28px] font-semibold tracking-[-0.04em] text-[#111111] dark:text-slate-100">
        {formatMetric(value, unit)}
      </div>
      <div className="mt-2 text-[12px] leading-6 text-[#6b7280] dark:text-slate-400">{detail}</div>
    </div>
  );
}

function TraceRow({ item }: { item: IdeaTraceBundle }) {
  const steps = item.steps.slice(-3).reverse();
  return (
    <div className="rounded-[18px] border border-[#d6dbe6] bg-[#fbfcff] px-4 py-4 dark:border-slate-800 dark:bg-slate-900/60">
      <div className="flex items-center justify-between gap-3">
        <div className="min-w-0">
          <div className="truncate text-[14px] font-semibold tracking-[-0.03em] text-[#111111] dark:text-slate-100">
            {item.title}
          </div>
          <div className="mt-1 text-[11px] text-[#6b7280] dark:text-slate-400">
            {item.latest_stage} · {item.steps.length} trace steps
          </div>
        </div>
        <div className="rounded-full border border-[#d6dbe6] bg-white px-2.5 py-1 text-[10px] font-semibold uppercase tracking-[0.14em] text-[#6b7280] dark:border-slate-800 dark:bg-slate-950 dark:text-slate-400">
          {item.linked_session_ids.length} sessions
        </div>
      </div>
      <div className="mt-3 space-y-2">
        {steps.map((step) => (
          <div key={step.trace_id} className="rounded-[14px] bg-white px-3 py-2 text-[12px] leading-6 text-[#4b5563] dark:bg-slate-950/70 dark:text-slate-300">
            <div className="font-medium text-[#111111] dark:text-slate-100">
              {step.title}
            </div>
            <div className="mt-1">{step.detail || step.trace_kind}</div>
          </div>
        ))}
      </div>
    </div>
  );
}

export function DiscoveryScoreboard() {
  const { locale } = useLocale();
  const text =
    locale === "ru"
      ? {
          title: "Discovery observability",
          subtitle: "Quality, evals, trace coverage и protocol regressions для всего founder discovery lane.",
          refresh: "Обновить",
          loading: "Собираю observability scoreboard…",
          error: "Не удалось загрузить observability scoreboard.",
          highlights: "Highlights",
          regressions: "Protocol regressions",
          strongest: "Strongest ideas",
          weakest: "Watchlist",
          traces: "Recent traces",
          empty: "Пока данных мало, чтобы показать observability surface.",
          sessions: "sessions",
          invalid: "invalid",
          cache: "cache",
        }
      : {
          title: "Discovery observability",
          subtitle: "Quality, evals, trace coverage, and protocol regressions across the founder discovery lane.",
          refresh: "Refresh",
          loading: "Loading the observability scoreboard…",
          error: "Failed to load the observability scoreboard.",
          highlights: "Highlights",
          regressions: "Protocol regressions",
          strongest: "Strongest ideas",
          weakest: "Watchlist",
          traces: "Recent traces",
          empty: "Not enough data has landed yet to render observability clearly.",
          sessions: "sessions",
          invalid: "invalid",
          cache: "cache",
        };

  const [scoreboard, setScoreboard] = useState<DiscoveryObservabilityScoreboard | null>(null);
  const [traces, setTraces] = useState<DiscoveryTraceSnapshot | null>(null);
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
      const [nextScoreboard, nextTraces] = await Promise.all([
        getDiscoveryObservabilityScoreboard(),
        getDiscoveryObservabilityTraces(6),
      ]);
      setScoreboard(nextScoreboard);
      setTraces(nextTraces);
    } catch (nextError) {
      setError(nextError instanceof Error ? nextError.message : text.error);
    } finally {
      setLoading(false);
      setRefreshing(false);
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
            <Radar className="h-5 w-5" />
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
      ) : !scoreboard ? (
        <div className="mt-5 rounded-[20px] border border-dashed border-[#d6dbe6] bg-[#fbfcff] px-4 py-6 text-[13px] leading-6 text-[#6b7280] dark:border-slate-800 dark:bg-slate-900/60 dark:text-slate-400">
          {text.empty}
        </div>
      ) : (
        <>
          <div className="mt-5 grid gap-3 md:grid-cols-2 xl:grid-cols-4">
            {scoreboard.metrics.slice(0, 4).map((metric) => (
              <MetricCard key={metric.key} label={metric.label} value={metric.value} detail={metric.detail} unit={metric.unit} />
            ))}
          </div>

          <div className="mt-5 grid gap-4 xl:grid-cols-[minmax(0,1.05fr)_minmax(320px,0.95fr)]">
            <div className="space-y-4">
              <div className="rounded-[20px] border border-[#d6dbe6] bg-[#fbfcff] px-4 py-4 dark:border-slate-800 dark:bg-slate-900/60">
                <div className="flex items-center gap-2 text-[11px] uppercase tracking-[0.14em] text-[#6b7280] dark:text-slate-500">
                  <Activity className="h-3.5 w-3.5" />
                  {text.highlights}
                </div>
                <div className="mt-3 space-y-2 text-[13px] leading-6 text-[#4b5563] dark:text-slate-300">
                  {scoreboard.highlights.map((item) => (
                    <div key={item} className="rounded-[14px] bg-white px-3 py-2 dark:bg-slate-950/70">
                      {item}
                    </div>
                  ))}
                </div>
              </div>

              <div className="grid gap-4 xl:grid-cols-2">
                <div className="rounded-[20px] border border-[#d6dbe6] bg-[#fbfcff] px-4 py-4 dark:border-slate-800 dark:bg-slate-900/60">
                  <div className="text-[11px] uppercase tracking-[0.14em] text-[#6b7280] dark:text-slate-500">{text.strongest}</div>
                  <div className="mt-3 space-y-2">
                    {scoreboard.strongest_ideas.map((item) => (
                      <div key={item.idea_id} className="rounded-[14px] bg-white px-3 py-2 dark:bg-slate-950/70">
                        <div className="text-[13px] font-medium text-[#111111] dark:text-slate-100">{item.title}</div>
                        <div className="mt-1 text-[12px] text-[#6b7280] dark:text-slate-400">{Math.round(item.overall_health * 100)} health</div>
                      </div>
                    ))}
                  </div>
                </div>

                <div className="rounded-[20px] border border-[#d6dbe6] bg-[#fbfcff] px-4 py-4 dark:border-slate-800 dark:bg-slate-900/60">
                  <div className="text-[11px] uppercase tracking-[0.14em] text-[#6b7280] dark:text-slate-500">{text.weakest}</div>
                  <div className="mt-3 space-y-2">
                    {scoreboard.weakest_ideas.map((item) => (
                      <div key={item.idea_id} className="rounded-[14px] bg-white px-3 py-2 dark:bg-slate-950/70">
                        <div className="text-[13px] font-medium text-[#111111] dark:text-slate-100">{item.title}</div>
                        <div className="mt-1 text-[12px] text-[#6b7280] dark:text-slate-400">
                          {item.flags.slice(0, 2).join(" · ") || `${Math.round(item.overall_health * 100)} health`}
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              </div>

              <div className="space-y-3">
                <div className="flex items-center gap-2 text-[11px] uppercase tracking-[0.14em] text-[#6b7280] dark:text-slate-500">
                  <Gauge className="h-3.5 w-3.5" />
                  {text.traces}
                </div>
                {(traces?.traces ?? []).slice(0, 3).map((item) => (
                  <TraceRow key={item.idea_id} item={item} />
                ))}
              </div>
            </div>

            <div className="rounded-[20px] border border-[#d6dbe6] bg-[#fbfcff] px-4 py-4 dark:border-slate-800 dark:bg-slate-900/60">
              <div className="text-[11px] uppercase tracking-[0.14em] text-[#6b7280] dark:text-slate-500">{text.regressions}</div>
              <div className="mt-3 space-y-3">
                {scoreboard.protocol_regressions.slice(0, 6).map((item) => (
                  <div key={`${item.mode}-${item.protocol_key}`} className="rounded-[14px] bg-white px-3 py-3 dark:bg-slate-950/70">
                    <div className="text-[13px] font-medium text-[#111111] dark:text-slate-100">
                      {item.protocol_key}
                    </div>
                    <div className="mt-1 text-[12px] leading-6 text-[#6b7280] dark:text-slate-400">
                      {item.mode} · {item.session_count} {text.sessions} · {Math.round(item.invalid_transition_rate * 100)}% {text.invalid} · {Math.round(item.cache_hit_rate * 100)}% {text.cache}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </>
      )}
    </section>
  );
}
