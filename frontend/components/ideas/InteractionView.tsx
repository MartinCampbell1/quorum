"use client";

import type { MarketSimulationReport } from "@/lib/types";


function percent(value: number): string {
  return `${Math.round(value * 100)}%`;
}

export function InteractionView({
  report,
  text,
}: {
  report: MarketSimulationReport;
  text: Record<string, string>;
}) {
  const recentActions = report.run_state.agent_actions.slice(-18).reverse();

  return (
    <div className="grid gap-4 xl:grid-cols-[minmax(0,0.95fr)_minmax(0,1.05fr)]">
      <div className="rounded-[24px] border border-[#d6dbe6] bg-white/95 p-5 dark:border-slate-800 dark:bg-slate-950/60">
        <div className="text-[15px] font-semibold tracking-[-0.03em] text-[#111111] dark:text-slate-100">{text.roundsTitle}</div>
        <div className="mt-4 space-y-3">
          {report.run_state.round_summaries.map((round) => (
            <div key={round.round_id} className="rounded-[16px] border border-[#d6dbe6] bg-[#fbfcff] px-4 py-4 dark:border-slate-800 dark:bg-slate-900/60">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <div className="text-[13px] font-semibold text-[#111111] dark:text-slate-100">
                  {text.round} {round.round_index}
                </div>
                <div className="text-[11px] text-[#6b7280] dark:text-slate-400">
                  adoption {percent(round.adoption_rate)} · retention {percent(round.retention_rate)}
                </div>
              </div>
              <div className="mt-3 grid gap-2 md:grid-cols-2">
                {round.key_events.map((event, index) => (
                  <div key={`${round.round_id}-${index}`} className="rounded-[14px] bg-white px-3 py-2 text-[12px] leading-6 dark:bg-slate-950/70">
                    {event}
                  </div>
                ))}
              </div>
              <div className="mt-3 text-[12px] leading-6 text-[#6b7280] dark:text-slate-400">
                {text.objections}: {round.top_objections.join(", ") || "none"}
              </div>
            </div>
          ))}
        </div>
      </div>

      <div className="rounded-[24px] border border-[#d6dbe6] bg-white/95 p-5 dark:border-slate-800 dark:bg-slate-950/60">
        <div className="text-[15px] font-semibold tracking-[-0.03em] text-[#111111] dark:text-slate-100">{text.interactionsTitle}</div>
        <div className="mt-4 space-y-3">
          {recentActions.map((action) => (
            <div key={action.action_id} className="rounded-[16px] border border-[#d6dbe6] bg-[#fbfcff] px-4 py-4 dark:border-slate-800 dark:bg-slate-900/60">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <div className="text-[13px] font-semibold text-[#111111] dark:text-slate-100">
                  {action.segment} · {action.action_type}
                </div>
                <div className="text-[11px] text-[#6b7280] dark:text-slate-400">
                  {text.round} {action.round_index} · {action.channel}
                </div>
              </div>
              <div className="mt-2 text-[12px] leading-6 text-[#111111] dark:text-slate-100">
                {action.summary}
              </div>
              <div className="mt-2 text-[11px] text-[#6b7280] dark:text-slate-400">
                {action.adoption_stage_before} → {action.adoption_stage_after} · influence {action.influence_delta.toFixed(2)} · pain relief {action.pain_relief_delta.toFixed(2)}
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
