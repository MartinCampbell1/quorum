"use client";

import { Loader2, Sparkles } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { useLocale } from "@/lib/locale";
import type { DiscoveryInboxItem, IdeaDossier } from "@/lib/types";

interface DossierInboxCardProps {
  item: DiscoveryInboxItem | null;
  dossier: IdeaDossier | null;
  loading?: boolean;
}

export function DossierInboxCard({ item, dossier, loading = false }: DossierInboxCardProps) {
  const { locale } = useLocale();
  const text =
    locale === "ru"
      ? {
          empty: "Выбери review item слева, чтобы открыть dossier preview.",
          loading: "Подтягиваю dossier preview…",
          summary: "Summary",
          evidence: "Evidence",
          validation: "Validation",
          simulation: "Simulation",
          handoff: "Handoff",
          trace: "Raw trace",
          none: "Пока пусто.",
        }
      : {
          empty: "Pick a review item to open its dossier preview.",
          loading: "Loading dossier preview…",
          summary: "Summary",
          evidence: "Evidence",
          validation: "Validation",
          simulation: "Simulation",
          handoff: "Handoff",
          trace: "Raw trace",
          none: "Nothing is attached yet.",
        };

  if (!item) {
    return (
      <aside className="rounded-[24px] border border-dashed border-[#d6dbe6] bg-[#fbfcff] px-5 py-5 text-[13px] leading-6 text-[#6b7280] dark:border-slate-800 dark:bg-slate-900/60 dark:text-slate-400">
        {text.empty}
      </aside>
    );
  }

  if (loading) {
    return (
      <aside className="rounded-[24px] border border-[#d6dbe6] bg-white/90 px-5 py-5 text-[13px] text-[#4b5563] dark:border-slate-800 dark:bg-slate-950/60 dark:text-slate-300">
        <div className="flex items-center gap-3">
          <Loader2 className="h-4 w-4 animate-spin" />
          {text.loading}
        </div>
      </aside>
    );
  }

  return (
    <aside className="rounded-[24px] border border-[#d6dbe6] bg-white/90 p-5 shadow-[0_16px_38px_-28px_rgba(17,48,105,0.22)] dark:border-slate-800 dark:bg-slate-950/60 dark:shadow-none">
      <div className="flex items-start justify-between gap-3">
        <div>
          <div className="flex items-center gap-2 text-[18px] font-semibold tracking-[-0.03em] text-[#111111] dark:text-slate-100">
            <Sparkles className="h-4.5 w-4.5" />
            {item.title}
          </div>
          <div className="mt-2 flex flex-wrap gap-2">
            <Badge variant="secondary" className="rounded-full bg-[#eef2f8] text-[#475569] dark:bg-slate-800 dark:text-slate-300">
              {item.subject_kind}
            </Badge>
            {item.dossier_preview ? (
              <Badge variant="secondary" className="rounded-full bg-[#f8f2e8] text-[#8b5e1a] dark:bg-amber-950/40 dark:text-amber-200">
                {item.dossier_preview.latest_stage}
              </Badge>
            ) : null}
          </div>
        </div>
        <div className="text-right text-[11px] uppercase tracking-[0.14em] text-[#6b7280] dark:text-slate-500">
          {item.aging_bucket}
        </div>
      </div>

      <div className="mt-4 grid gap-4">
        <section className="rounded-[18px] border border-[#d6dbe6] bg-[#fbfcff] px-4 py-4 dark:border-slate-800 dark:bg-slate-900/60">
          <div className="text-[10px] uppercase tracking-[0.14em] text-[#6b7280] dark:text-slate-500">{text.summary}</div>
          <div className="mt-2 text-[13px] leading-6 text-[#374151] dark:text-slate-300">
            {item.interrupt?.description || item.dossier_preview?.idea_summary || item.detail}
          </div>
        </section>

        <section className="rounded-[18px] border border-[#d6dbe6] bg-[#fbfcff] px-4 py-4 dark:border-slate-800 dark:bg-slate-900/60">
          <div className="text-[10px] uppercase tracking-[0.14em] text-[#6b7280] dark:text-slate-500">{text.evidence}</div>
          <div className="mt-2 space-y-2 text-[13px] leading-6 text-[#374151] dark:text-slate-300">
            {(item.dossier_preview?.evidence.observations.length
              ? item.dossier_preview.evidence.observations
              : dossier?.observations.slice(-3).reverse().map((entry) => entry.raw_text) ?? []
            )
              .slice(0, 3)
              .map((line) => (
                <div key={line} className="rounded-[14px] bg-white px-3 py-2 dark:bg-slate-950/70">
                  {line}
                </div>
              ))}
            {!item.dossier_preview?.evidence.observations.length && !dossier?.observations.length ? (
              <div className="text-[#6b7280] dark:text-slate-400">{text.none}</div>
            ) : null}
          </div>
        </section>

        <section className="grid gap-4 md:grid-cols-2">
          <div className="rounded-[18px] border border-[#d6dbe6] bg-[#fbfcff] px-4 py-4 dark:border-slate-800 dark:bg-slate-900/60">
            <div className="text-[10px] uppercase tracking-[0.14em] text-[#6b7280] dark:text-slate-500">{text.validation}</div>
            <div className="mt-2 text-[13px] leading-6 text-[#374151] dark:text-slate-300">
              {item.dossier_preview?.debate_summary
                || dossier?.validation_reports.slice(-1)[0]?.summary
                || text.none}
            </div>
          </div>
          <div className="rounded-[18px] border border-[#d6dbe6] bg-[#fbfcff] px-4 py-4 dark:border-slate-800 dark:bg-slate-900/60">
            <div className="text-[10px] uppercase tracking-[0.14em] text-[#6b7280] dark:text-slate-500">{text.simulation}</div>
            <div className="mt-2 text-[13px] leading-6 text-[#374151] dark:text-slate-300">
              {item.dossier_preview?.simulation_summary
                || dossier?.simulation_report?.summary_headline
                || dossier?.market_simulation_report?.executive_summary
                || text.none}
            </div>
          </div>
        </section>

        <section className="rounded-[18px] border border-[#d6dbe6] bg-[#fbfcff] px-4 py-4 dark:border-slate-800 dark:bg-slate-900/60">
          <div className="text-[10px] uppercase tracking-[0.14em] text-[#6b7280] dark:text-slate-500">{text.handoff}</div>
          <div className="mt-2 text-[13px] leading-6 text-[#374151] dark:text-slate-300">
            {item.dossier_preview?.handoff_summary
              || dossier?.execution_brief_candidate?.prd_summary
              || dossier?.execution_brief_candidate?.title
              || text.none}
          </div>
        </section>

        <details className="rounded-[18px] border border-[#d6dbe6] bg-[#fbfcff] px-4 py-4 dark:border-slate-800 dark:bg-slate-900/60">
          <summary className="cursor-pointer text-[10px] font-semibold uppercase tracking-[0.14em] text-[#6b7280] dark:text-slate-500">
            {text.trace}
          </summary>
          <pre className="mt-3 overflow-x-auto rounded-[14px] bg-white px-3 py-3 text-[12px] leading-6 text-[#374151] dark:bg-slate-950/70 dark:text-slate-300">
            {JSON.stringify(item.dossier_preview?.raw_trace ?? {}, null, 2)}
          </pre>
        </details>
      </div>
    </aside>
  );
}
