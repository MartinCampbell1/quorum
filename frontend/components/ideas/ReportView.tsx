"use client";

import type { ComponentType } from "react";
import { Activity, ArrowUpRight, Gauge, TrendingUp, Users } from "lucide-react";

import type { MarketSimulationReport } from "@/lib/types";


function percent(value: number): string {
  return `${Math.round(value * 100)}%`;
}

export function ReportView({
  report,
  cached,
  text,
}: {
  report: MarketSimulationReport;
  cached: boolean;
  text: Record<string, string>;
}) {
  const deltaRank = report.ranking_delta.rank_score_delta ?? 0;
  const deltaBelief = report.ranking_delta.belief_score_delta ?? 0;
  return (
    <div className="space-y-4">
      <div className="rounded-[24px] border border-[#d6dbe6] bg-white/95 p-5 dark:border-slate-800 dark:bg-slate-950/60">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <div className="text-[18px] font-semibold tracking-[-0.04em] text-[#111111] dark:text-slate-100">
              {report.executive_summary}
            </div>
            <div className="mt-2 text-[13px] leading-6 text-[#6b7280] dark:text-slate-400">
              {text.verdict}: <span className="font-medium text-[#111111] dark:text-slate-100">{report.verdict}</span>
            </div>
          </div>
          {cached ? (
            <span className="rounded-full border border-[#d6dbe6] bg-[#fafbff] px-3 py-1 text-[10px] uppercase tracking-[0.14em] text-[#6b7280] dark:border-slate-800 dark:bg-slate-900 dark:text-slate-400">
              {text.cached}
            </span>
          ) : null}
        </div>

        <div className="mt-5 grid gap-3 md:grid-cols-3 xl:grid-cols-6">
          <MetricCard icon={Users} label={text.adoption} value={percent(report.adoption_rate)} />
          <MetricCard icon={Activity} label={text.retention} value={percent(report.retention_rate)} />
          <MetricCard icon={TrendingUp} label={text.virality} value={percent(report.virality_score)} />
          <MetricCard icon={Gauge} label={text.painRelief} value={percent(report.pain_relief_score)} />
          <MetricCard icon={Gauge} label={text.fit} value={percent(report.market_fit_score)} />
          <MetricCard icon={ArrowUpRight} label={text.priority} value={percent(report.build_priority_score)} />
        </div>

        <div className="mt-5 grid gap-4 xl:grid-cols-2">
          <ListCard title={text.segments} items={report.strongest_segments} />
          <ListCard title={text.weakSegments} items={report.weakest_segments} />
          <ListCard title={text.channels} items={report.channel_findings} />
          <ListCard title={text.objections} items={report.key_objections} />
        </div>

        <div className="mt-5 rounded-[18px] border border-[#d6dbe6] bg-[#fbfcff] p-4 dark:border-slate-800 dark:bg-slate-900/60">
          <div className="text-[11px] uppercase tracking-[0.14em] text-[#6b7280] dark:text-slate-500">{text.rankingDelta}</div>
          <div className="mt-3 grid gap-3 md:grid-cols-2">
            <div className="rounded-[14px] bg-white px-4 py-3 text-[13px] dark:bg-slate-950/70">
              Rank delta: <span className="font-semibold">{deltaRank >= 0 ? "+" : ""}{deltaRank.toFixed(3)}</span>
            </div>
            <div className="rounded-[14px] bg-white px-4 py-3 text-[13px] dark:bg-slate-950/70">
              Belief delta: <span className="font-semibold">{deltaBelief >= 0 ? "+" : ""}{deltaBelief.toFixed(3)}</span>
            </div>
          </div>
        </div>

        <div className="mt-5 grid gap-4 xl:grid-cols-2">
          {report.report_outline.map((section) => (
            <ListCard key={section.title} title={section.title} items={section.bullets} />
          ))}
          <ListCard title={text.actions} items={report.recommended_actions} />
        </div>
      </div>
    </div>
  );
}

function MetricCard({
  icon: Icon,
  label,
  value,
}: {
  icon: ComponentType<{ className?: string }>;
  label: string;
  value: string;
}) {
  return (
    <div className="rounded-[18px] border border-[#d6dbe6] bg-[#fbfcff] px-4 py-4 dark:border-slate-800 dark:bg-slate-900/60">
      <div className="flex items-center gap-2 text-[11px] uppercase tracking-[0.14em] text-[#6b7280] dark:text-slate-500">
        <Icon className="h-3.5 w-3.5" />
        {label}
      </div>
      <div className="mt-2 text-[24px] font-semibold tracking-[-0.04em] text-[#111111] dark:text-slate-100">
        {value}
      </div>
    </div>
  );
}

function ListCard({ title, items }: { title: string; items: string[] }) {
  return (
    <div className="rounded-[18px] border border-[#d6dbe6] bg-[#fbfcff] px-4 py-4 dark:border-slate-800 dark:bg-slate-900/60">
      <div className="text-[11px] uppercase tracking-[0.14em] text-[#6b7280] dark:text-slate-500">{title}</div>
      <div className="mt-3 space-y-2">
        {items.length > 0 ? (
          items.map((item, index) => (
            <div key={`${title}-${index}-${item}`} className="rounded-[14px] bg-white px-3 py-2 text-[12px] leading-6 dark:bg-slate-950/70">
              {item}
            </div>
          ))
        ) : (
          <div className="rounded-[14px] bg-white px-3 py-2 text-[12px] leading-6 text-[#6b7280] dark:bg-slate-950/70 dark:text-slate-400">
            None yet.
          </div>
        )}
      </div>
    </div>
  );
}
