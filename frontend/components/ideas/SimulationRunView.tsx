"use client";

import { Loader2, PlayCircle, RefreshCcw, Users } from "lucide-react";

import { Button } from "@/components/ui/button";
import type { IdeaCandidate } from "@/lib/types";


const POPULATION_OPTIONS = [24, 40, 60, 90, 120];
const ROUND_OPTIONS = [2, 3, 4, 5, 6];

export function SimulationRunView({
  ideas,
  selectedIdeaId,
  onSelectIdea,
  populationSize,
  onPopulationSize,
  roundCount,
  onRoundCount,
  loadingIdeas,
  running,
  onRefresh,
  onRun,
  text,
}: {
  ideas: IdeaCandidate[];
  selectedIdeaId: string | null;
  onSelectIdea: (ideaId: string) => void;
  populationSize: number;
  onPopulationSize: (value: number) => void;
  roundCount: number;
  onRoundCount: (value: number) => void;
  loadingIdeas: boolean;
  running: boolean;
  onRefresh: () => void;
  onRun: () => void;
  text: Record<string, string>;
}) {
  return (
    <div className="space-y-4">
      <div className="rounded-[22px] border border-[#d6dbe6] bg-[#fbfcff] p-4 dark:border-slate-800 dark:bg-slate-900/60">
        <div className="flex items-center gap-2 text-[13px] font-semibold tracking-[-0.02em] text-[#111111] dark:text-slate-100">
          <Users className="h-4 w-4" />
          {text.candidates}
        </div>
        <div className="mt-4 space-y-3">
          {loadingIdeas ? (
            <div className="rounded-[16px] bg-white px-4 py-4 text-[13px] text-[#4b5563] dark:bg-slate-950/70 dark:text-slate-300">
              {text.loadingIdeas}
            </div>
          ) : ideas.length === 0 ? (
            <div className="rounded-[16px] bg-white px-4 py-4 text-[13px] leading-6 text-[#6b7280] dark:bg-slate-950/70 dark:text-slate-400">
              {text.empty}
            </div>
          ) : (
            ideas.slice(0, 8).map((idea) => {
              const active = selectedIdeaId === idea.idea_id;
              return (
                <button
                  key={idea.idea_id}
                  type="button"
                  onClick={() => onSelectIdea(idea.idea_id)}
                  className={`w-full rounded-[16px] border px-4 py-3 text-left transition-colors ${
                    active
                      ? "border-black bg-black text-white dark:border-slate-100 dark:bg-slate-100 dark:text-slate-950"
                      : "border-[#d6dbe6] bg-white text-[#111111] dark:border-slate-800 dark:bg-slate-950/70 dark:text-slate-100"
                  }`}
                >
                  <div className="text-[14px] font-semibold tracking-[-0.03em]">{idea.title}</div>
                  <div className={`mt-1 text-[11px] leading-5 ${active ? "text-white/80 dark:text-slate-800" : "text-[#6b7280] dark:text-slate-400"}`}>
                    {text.state}: {idea.simulation_state} · rank {Math.round(idea.rank_score * 100)}%
                  </div>
                  <div className={`mt-2 text-[11px] leading-5 ${active ? "text-white/80 dark:text-slate-800" : "text-[#6b7280] dark:text-slate-400"}`}>
                    {idea.topic_tags.length ? idea.topic_tags.join(", ") : idea.source}
                  </div>
                </button>
              );
            })
          )}
        </div>
      </div>

      <div className="rounded-[22px] border border-[#d6dbe6] bg-[#fbfcff] p-4 dark:border-slate-800 dark:bg-slate-900/60">
        <div className="text-[11px] uppercase tracking-[0.14em] text-[#6b7280] dark:text-slate-500">{text.population}</div>
        <div className="mt-3 flex flex-wrap gap-2">
          {POPULATION_OPTIONS.map((count) => (
            <button
              key={count}
              type="button"
              onClick={() => onPopulationSize(count)}
              className={`rounded-full border px-3 py-1.5 text-[11px] transition-colors ${
                populationSize === count
                  ? "border-black bg-black text-white dark:border-slate-100 dark:bg-slate-100 dark:text-slate-950"
                  : "border-[#d6dbe6] bg-white text-[#4b5563] dark:border-slate-800 dark:bg-slate-950 dark:text-slate-400"
              }`}
            >
              {count}
            </button>
          ))}
        </div>

        <div className="mt-5 text-[11px] uppercase tracking-[0.14em] text-[#6b7280] dark:text-slate-500">{text.rounds}</div>
        <div className="mt-3 flex flex-wrap gap-2">
          {ROUND_OPTIONS.map((count) => (
            <button
              key={count}
              type="button"
              onClick={() => onRoundCount(count)}
              className={`rounded-full border px-3 py-1.5 text-[11px] transition-colors ${
                roundCount === count
                  ? "border-black bg-black text-white dark:border-slate-100 dark:bg-slate-100 dark:text-slate-950"
                  : "border-[#d6dbe6] bg-white text-[#4b5563] dark:border-slate-800 dark:bg-slate-950 dark:text-slate-400"
              }`}
            >
              {count}
            </button>
          ))}
        </div>

        <div className="mt-5 flex flex-wrap gap-2">
          <Button type="button" variant="outline" size="sm" onClick={onRefresh} className="h-8 rounded-full text-[11px]">
            {loadingIdeas ? <Loader2 className="mr-1 h-3.5 w-3.5 animate-spin" /> : <RefreshCcw className="mr-1 h-3.5 w-3.5" />}
            {text.refresh}
          </Button>
          <Button type="button" size="sm" onClick={onRun} disabled={!selectedIdeaId || running} className="h-8 rounded-full bg-black text-[11px] text-white hover:bg-black/90">
            {running ? <Loader2 className="mr-1 h-3.5 w-3.5 animate-spin" /> : <PlayCircle className="mr-1 h-3.5 w-3.5" />}
            {text.run}
          </Button>
        </div>
      </div>
    </div>
  );
}
