"use client";

import { useEffect, useMemo, useState } from "react";
import { FlaskConical, Loader2, PlayCircle, RefreshCcw, Users } from "lucide-react";

import { Button } from "@/components/ui/button";
import { getDiscoveryIdeas, getDiscoverySimulation, runDiscoverySimulation } from "@/lib/api";
import { useLocale } from "@/lib/locale";
import type { IdeaCandidate, SimulationFeedbackReport } from "@/lib/types";

import { SimulationSummary } from "./SimulationSummary";


const PERSONA_COUNTS = [10, 12, 16, 24, 32, 48];

function sortIdeas(items: IdeaCandidate[]): IdeaCandidate[] {
  return [...items]
    .filter((idea) => idea.validation_state !== "archived")
    .sort((left, right) => {
      const scoreDelta = right.rank_score - left.rank_score;
      if (scoreDelta !== 0) return scoreDelta;
      return String(right.updated_at).localeCompare(String(left.updated_at));
    });
}

export function PersonaLab() {
  const { locale } = useLocale();
  const text =
    locale === "ru"
      ? {
          title: "Persona Lab",
          subtitle: "Cheap synthetic focus group before debate-heavy build decisions or handoff.",
          refresh: "Обновить",
          run: "Прогнать симуляцию",
          loadingIdeas: "Собираю discovery ideas…",
          loadingReport: "Загружаю simulation report…",
          empty: "Сначала добавь идеи в discovery pipeline, чтобы запустить virtual users.",
          noReport: "У выбранной идеи ещё нет simulation report.",
          candidates: "Кандидаты",
          personas: "Персоны",
          state: "Состояние",
          tags: "Теги",
          source: "Источник",
          cached: "Последний запуск был взят из cache.",
        }
      : {
          title: "Persona Lab",
          subtitle: "Run a cheap synthetic focus group before debate-heavy build decisions or handoff.",
          refresh: "Refresh",
          run: "Run simulation",
          loadingIdeas: "Loading discovery ideas…",
          loadingReport: "Loading the simulation report…",
          empty: "Add ideas to the discovery pipeline first to run virtual users.",
          noReport: "The selected idea does not have a simulation report yet.",
          candidates: "Candidates",
          personas: "Personas",
          state: "State",
          tags: "Tags",
          source: "Source",
          cached: "The latest run was returned from cache.",
        };

  const [ideas, setIdeas] = useState<IdeaCandidate[]>([]);
  const [selectedIdeaId, setSelectedIdeaId] = useState<string | null>(null);
  const [personaCount, setPersonaCount] = useState<number>(12);
  const [report, setReport] = useState<SimulationFeedbackReport | null>(null);
  const [loadingIdeas, setLoadingIdeas] = useState(true);
  const [loadingReport, setLoadingReport] = useState(false);
  const [running, setRunning] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [cached, setCached] = useState(false);

  const sortedIdeas = useMemo(() => sortIdeas(ideas), [ideas]);
  const selectedIdea = sortedIdeas.find((idea) => idea.idea_id === selectedIdeaId) ?? sortedIdeas[0] ?? null;

  async function loadIdeas(showSpinner: boolean = false) {
    if (showSpinner) {
      setLoadingIdeas(true);
    }
    setError(null);
    try {
      const nextIdeas = await getDiscoveryIdeas(24);
      setIdeas(nextIdeas);
      if (!selectedIdeaId && nextIdeas.length > 0) {
        setSelectedIdeaId(sortIdeas(nextIdeas)[0]?.idea_id ?? null);
      }
    } catch (nextError) {
      setError(nextError instanceof Error ? nextError.message : "Failed to load ideas.");
    } finally {
      setLoadingIdeas(false);
    }
  }

  async function loadReport(ideaId: string) {
    setLoadingReport(true);
    setCached(false);
    try {
      const nextReport = await getDiscoverySimulation(ideaId);
      setReport(nextReport);
    } catch {
      setReport(null);
    } finally {
      setLoadingReport(false);
    }
  }

  async function handleRun() {
    if (!selectedIdea) return;
    setRunning(true);
    setError(null);
    try {
      const result = await runDiscoverySimulation(selectedIdea.idea_id, {
        persona_count: personaCount,
        max_rounds: 3,
      });
      setReport(result.report);
      setCached(result.cached);
      setIdeas((current) =>
        current.map((idea) => (idea.idea_id === result.idea.idea_id ? result.idea : idea))
      );
    } catch (nextError) {
      setError(nextError instanceof Error ? nextError.message : "Failed to run simulation.");
    } finally {
      setRunning(false);
    }
  }

  useEffect(() => {
    void loadIdeas(true);
  }, []);

  useEffect(() => {
    if (!selectedIdea?.idea_id) {
      setReport(null);
      return;
    }
    void loadReport(selectedIdea.idea_id);
  }, [selectedIdea?.idea_id]);

  return (
    <section className="rounded-[28px] border border-[#d6dbe6] bg-white/90 p-5 shadow-[0_16px_38px_-28px_rgba(17,48,105,0.22)] dark:border-slate-800 dark:bg-slate-950/60 dark:shadow-none">
      <div className="flex flex-col gap-4 xl:flex-row xl:items-start xl:justify-between">
        <div>
          <div className="flex items-center gap-2 text-[20px] font-semibold tracking-[-0.04em] text-[#111111] dark:text-slate-100">
            <FlaskConical className="h-5 w-5" />
            {text.title}
          </div>
          <div className="mt-2 max-w-3xl text-[13px] leading-6 text-[#6b7280] dark:text-slate-400">
            {text.subtitle}
          </div>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <Button type="button" variant="outline" size="sm" onClick={() => void loadIdeas(true)} className="h-8 rounded-full text-[11px]">
            {loadingIdeas ? <Loader2 className="mr-1 h-3.5 w-3.5 animate-spin" /> : <RefreshCcw className="mr-1 h-3.5 w-3.5" />}
            {text.refresh}
          </Button>
          <Button
            type="button"
            size="sm"
            onClick={() => void handleRun()}
            disabled={!selectedIdea || running}
            className="h-8 rounded-full bg-black text-[11px] text-white hover:bg-black/90"
          >
            {running ? <Loader2 className="mr-1 h-3.5 w-3.5 animate-spin" /> : <PlayCircle className="mr-1 h-3.5 w-3.5" />}
            {text.run}
          </Button>
        </div>
      </div>

      <div className="mt-5 grid gap-4 xl:grid-cols-[360px_minmax(0,1fr)]">
        <div className="space-y-4">
          <div className="rounded-[20px] border border-[#d6dbe6] bg-[#fbfcff] p-4 dark:border-slate-800 dark:bg-slate-900/60">
            <div className="text-[11px] uppercase tracking-[0.14em] text-[#6b7280] dark:text-slate-500">
              {text.personas}
            </div>
            <div className="mt-3 flex flex-wrap gap-2">
              {PERSONA_COUNTS.map((count) => (
                <button
                  key={count}
                  type="button"
                  onClick={() => setPersonaCount(count)}
                  className={`rounded-full border px-3 py-1.5 text-[11px] transition-colors ${
                    personaCount === count
                      ? "border-black bg-black text-white dark:border-slate-100 dark:bg-slate-100 dark:text-slate-950"
                      : "border-[#d6dbe6] bg-white text-[#4b5563] dark:border-slate-800 dark:bg-slate-950 dark:text-slate-400"
                  }`}
                >
                  {count}
                </button>
              ))}
            </div>
          </div>

          <div className="rounded-[20px] border border-[#d6dbe6] bg-[#fbfcff] p-4 dark:border-slate-800 dark:bg-slate-900/60">
            <div className="flex items-center gap-2 text-[13px] font-semibold tracking-[-0.02em] text-[#111111] dark:text-slate-100">
              <Users className="h-4 w-4" />
              {text.candidates}
            </div>

            <div className="mt-4 space-y-3">
              {loadingIdeas ? (
                <div className="rounded-[16px] bg-white px-4 py-4 text-[13px] text-[#4b5563] dark:bg-slate-950/70 dark:text-slate-300">
                  {text.loadingIdeas}
                </div>
              ) : sortedIdeas.length === 0 ? (
                <div className="rounded-[16px] bg-white px-4 py-4 text-[13px] leading-6 text-[#6b7280] dark:bg-slate-950/70 dark:text-slate-400">
                  {text.empty}
                </div>
              ) : (
                sortedIdeas.slice(0, 8).map((idea) => {
                  const active = idea.idea_id === selectedIdea?.idea_id;
                  return (
                    <button
                      key={idea.idea_id}
                      type="button"
                      onClick={() => setSelectedIdeaId(idea.idea_id)}
                      className={`w-full rounded-[16px] border px-4 py-3 text-left transition-colors ${
                        active
                          ? "border-black bg-black text-white dark:border-slate-100 dark:bg-slate-100 dark:text-slate-950"
                          : "border-[#d6dbe6] bg-white text-[#111111] dark:border-slate-800 dark:bg-slate-950/70 dark:text-slate-100"
                      }`}
                    >
                      <div className="text-[14px] font-semibold tracking-[-0.03em]">{idea.title}</div>
                      <div className={`mt-1 text-[11px] leading-5 ${active ? "text-white/80 dark:text-slate-800" : "text-[#6b7280] dark:text-slate-400"}`}>
                        {text.state}: {idea.simulation_state} · {text.source}: {idea.source}
                      </div>
                      <div className={`mt-2 text-[11px] leading-5 ${active ? "text-white/80 dark:text-slate-800" : "text-[#6b7280] dark:text-slate-400"}`}>
                        {text.tags}: {idea.topic_tags.length ? idea.topic_tags.join(", ") : "none"}
                      </div>
                    </button>
                  );
                })
              )}
            </div>
          </div>
        </div>

        <div className="space-y-4">
          {error ? (
            <div className="rounded-[20px] border border-rose-200 bg-rose-50 px-4 py-5 text-[13px] text-rose-700 dark:border-rose-900/60 dark:bg-rose-950/40 dark:text-rose-300">
              {error}
            </div>
          ) : null}
          {cached ? (
            <div className="rounded-[18px] border border-[#d6dbe6] bg-[#fbfcff] px-4 py-3 text-[12px] leading-6 text-[#4b5563] dark:border-slate-800 dark:bg-slate-900/60 dark:text-slate-300">
              {text.cached}
            </div>
          ) : null}
          {loadingReport ? (
            <div className="rounded-[20px] border border-[#d6dbe6] bg-[#fbfcff] px-4 py-5 text-[13px] text-[#4b5563] dark:border-slate-800 dark:bg-slate-900/60 dark:text-slate-300">
              {text.loadingReport}
            </div>
          ) : report ? (
            <SimulationSummary report={report} cached={cached} />
          ) : (
            <div className="rounded-[20px] border border-dashed border-[#d6dbe6] bg-[#fbfcff] px-4 py-6 text-[13px] leading-6 text-[#6b7280] dark:border-slate-800 dark:bg-slate-900/60 dark:text-slate-400">
              {text.noReport}
            </div>
          )}
        </div>
      </div>
    </section>
  );
}
