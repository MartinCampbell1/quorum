"use client";

import { BadgeDollarSign, Lightbulb, MessagesSquare, TrendingUp, Users, type LucideIcon } from "lucide-react";

import { useLocale } from "@/lib/locale";
import type { SimulationFeedbackReport } from "@/lib/types";


function percent(value: number): string {
  return `${Math.round(value * 100)}%`;
}

export function SimulationSummary({
  report,
  cached = false,
}: {
  report: SimulationFeedbackReport;
  cached?: boolean;
}) {
  const { locale } = useLocale();
  const text =
    locale === "ru"
      ? {
          cached: "cache hit",
          support: "Поддержка",
          resonance: "Резонанс",
          purchase: "Purchase intent",
          personas: "Персон",
          verdict: "Вердикт",
          strongSegments: "Сильные сегменты",
          positives: "Позитивные сигналы",
          objections: "Возражения",
          asks: "Что хотят увидеть",
          gtm: "GTM signals",
          pricing: "Pricing",
          quotes: "Representative quotes",
          actions: "Next actions",
          cost: "Стоимость",
        }
      : {
          cached: "cache hit",
          support: "Support",
          resonance: "Resonance",
          purchase: "Purchase intent",
          personas: "Personas",
          verdict: "Verdict",
          strongSegments: "Strong segments",
          positives: "Positive signals",
          objections: "Objections",
          asks: "What they want",
          gtm: "GTM signals",
          pricing: "Pricing",
          quotes: "Representative quotes",
          actions: "Next actions",
          cost: "Cost",
        };

  return (
    <div className="rounded-[24px] border border-[#d6dbe6] bg-white/95 p-5 dark:border-slate-800 dark:bg-slate-950/60">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <div className="text-[18px] font-semibold tracking-[-0.04em] text-[#111111] dark:text-slate-100">
            {report.summary_headline}
          </div>
          <div className="mt-2 text-[13px] leading-6 text-[#6b7280] dark:text-slate-400">
            {text.verdict}: <span className="font-medium text-[#111111] dark:text-slate-100">{report.verdict}</span>
          </div>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          {cached ? (
            <span className="rounded-full border border-[#d6dbe6] bg-[#fafbff] px-3 py-1 text-[10px] uppercase tracking-[0.14em] text-[#6b7280] dark:border-slate-800 dark:bg-slate-900 dark:text-slate-400">
              {text.cached}
            </span>
          ) : null}
          <span className="rounded-full border border-[#d6dbe6] bg-[#fafbff] px-3 py-1 text-[10px] uppercase tracking-[0.14em] text-[#6b7280] dark:border-slate-800 dark:bg-slate-900 dark:text-slate-400">
            {report.run.engine}
          </span>
        </div>
      </div>

      <div className="mt-5 grid gap-3 md:grid-cols-3 xl:grid-cols-6">
        <MetricCard icon={TrendingUp} label={text.support} value={percent(report.support_ratio)} />
        <MetricCard icon={Lightbulb} label={text.resonance} value={percent(report.average_resonance)} />
        <MetricCard icon={BadgeDollarSign} label={text.purchase} value={percent(report.average_purchase_intent)} />
        <MetricCard icon={Users} label={text.personas} value={String(report.run.persona_count)} />
        <MetricCard icon={MessagesSquare} label={text.cost} value={`$${report.run.estimated_cost_usd.toFixed(4)}`} />
        <MetricCard icon={Users} label={text.verdict} value={report.verdict} />
      </div>

      <div className="mt-5 grid gap-4 xl:grid-cols-[minmax(0,1.1fr)_minmax(0,0.9fr)]">
        <div className="space-y-4">
          <StringListCard title={text.strongSegments} items={report.strongest_segments} />
          <StringListCard title={text.positives} items={report.positive_signals} />
          <StringListCard title={text.objections} items={report.objections} />
          <StringListCard title={text.asks} items={report.desired_capabilities} />
        </div>
        <div className="space-y-4">
          <StringListCard title={text.gtm} items={report.go_to_market_signals} />
          <StringListCard title={text.pricing} items={report.pricing_signals} />
          <StringListCard title={text.quotes} items={report.sample_quotes} />
          <StringListCard title={text.actions} items={report.recommended_actions} />
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
  icon: LucideIcon;
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

function StringListCard({ title, items }: { title: string; items: string[] }) {
  return (
    <div className="rounded-[18px] border border-[#d6dbe6] bg-[#fbfcff] px-4 py-4 dark:border-slate-800 dark:bg-slate-900/60">
      <div className="text-[11px] uppercase tracking-[0.14em] text-[#6b7280] dark:text-slate-500">{title}</div>
      <div className="mt-3 space-y-2">
        {items.length > 0 ? (
          items.map((item, index) => (
            <div
              key={`${title}-${index}-${item}`}
              className="rounded-[14px] bg-white px-3 py-2 text-[12px] leading-6 text-[#111111] dark:bg-slate-950/70 dark:text-slate-100"
            >
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
