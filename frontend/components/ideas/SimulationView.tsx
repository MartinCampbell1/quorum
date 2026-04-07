"use client";

import { useEffect, useMemo, useState } from "react";
import { BarChart3, Loader2 } from "lucide-react";

import { getDiscoveryIdeas, getDiscoveryMarketSimulation, runDiscoveryMarketSimulation } from "@/lib/api";
import { useLocale } from "@/lib/locale";
import type { IdeaCandidate, MarketSimulationReport } from "@/lib/types";

import { InteractionView } from "./InteractionView";
import { ReportView } from "./ReportView";
import { SimulationRunView } from "./SimulationRunView";


function sortIdeas(items: IdeaCandidate[]): IdeaCandidate[] {
  return [...items]
    .filter((idea) => idea.validation_state !== "archived")
    .sort((left, right) => {
      const delta = right.rank_score - left.rank_score;
      if (delta !== 0) return delta;
      return String(right.updated_at).localeCompare(String(left.updated_at));
    });
}

export function SimulationView() {
  const { locale } = useLocale();
  const text =
    locale === "ru"
      ? {
          title: "Market Simulation Lab",
          subtitle: "Heavy sandbox for adoption, retention, virality and objection pressure before build approval.",
          loadingIdeas: "Собираю идеи для market sandbox…",
          loadingReport: "Загружаю последний market report…",
          empty: "Сначала добавь идеи в discovery pipeline.",
          noReport: "У этой идеи ещё нет market simulation report.",
          candidates: "Кандидаты",
          population: "Популяция",
          rounds: "Раунды",
          refresh: "Обновить",
          run: "Запустить market lab",
          state: "Состояние",
          cached: "Последний market run пришёл из cache.",
          verdict: "Вердикт",
          adoption: "Adoption",
          retention: "Retention",
          virality: "Virality",
          painRelief: "Pain relief",
          fit: "Market fit",
          priority: "Build priority",
          segments: "Сильные сегменты",
          weakSegments: "Слабые сегменты",
          channels: "Channel findings",
          objections: "Ключевые возражения",
          rankingDelta: "Ranking delta",
          actions: "Recommended actions",
          roundsTitle: "Round summaries",
          interactionsTitle: "Interaction log",
          round: "Раунд",
        }
      : {
          title: "Market Simulation Lab",
          subtitle: "Run a heavier sandbox for adoption, retention, virality, and objection pressure before build approval.",
          loadingIdeas: "Loading ideas for the market sandbox…",
          loadingReport: "Loading the latest market report…",
          empty: "Add ideas to the discovery pipeline first.",
          noReport: "This idea does not have a market simulation report yet.",
          candidates: "Candidates",
          population: "Population",
          rounds: "Rounds",
          refresh: "Refresh",
          run: "Run market lab",
          state: "State",
          cached: "The latest market run came from cache.",
          verdict: "Verdict",
          adoption: "Adoption",
          retention: "Retention",
          virality: "Virality",
          painRelief: "Pain relief",
          fit: "Market fit",
          priority: "Build priority",
          segments: "Strong segments",
          weakSegments: "Weak segments",
          channels: "Channel findings",
          objections: "Key objections",
          rankingDelta: "Ranking delta",
          actions: "Recommended actions",
          roundsTitle: "Round summaries",
          interactionsTitle: "Interaction log",
          round: "Round",
        };

  const [ideas, setIdeas] = useState<IdeaCandidate[]>([]);
  const [selectedIdeaId, setSelectedIdeaId] = useState<string | null>(null);
  const [populationSize, setPopulationSize] = useState(60);
  const [roundCount, setRoundCount] = useState(4);
  const [report, setReport] = useState<MarketSimulationReport | null>(null);
  const [loadingIdeas, setLoadingIdeas] = useState(true);
  const [loadingReport, setLoadingReport] = useState(false);
  const [running, setRunning] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [cached, setCached] = useState(false);

  const sortedIdeas = useMemo(() => sortIdeas(ideas), [ideas]);
  const selectedIdea = sortedIdeas.find((idea) => idea.idea_id === selectedIdeaId) ?? sortedIdeas[0] ?? null;

  async function loadIdeas(showLoader: boolean = false) {
    if (showLoader) {
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
      const nextReport = await getDiscoveryMarketSimulation(ideaId);
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
      const result = await runDiscoveryMarketSimulation(selectedIdea.idea_id, {
        population_size: populationSize,
        round_count: roundCount,
      });
      setReport(result.report);
      setCached(result.cached);
      setIdeas((current) => current.map((idea) => (idea.idea_id === result.idea.idea_id ? result.idea : idea)));
    } catch (nextError) {
      setError(nextError instanceof Error ? nextError.message : "Failed to run market simulation.");
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
      <div className="flex items-start gap-2 text-[20px] font-semibold tracking-[-0.04em] text-[#111111] dark:text-slate-100">
        <BarChart3 className="mt-0.5 h-5 w-5" />
        <div>
          <div>{text.title}</div>
          <div className="mt-2 max-w-3xl text-[13px] font-normal leading-6 text-[#6b7280] dark:text-slate-400">
            {text.subtitle}
          </div>
        </div>
      </div>

      <div className="mt-5 grid gap-4 xl:grid-cols-[360px_minmax(0,1fr)]">
        <SimulationRunView
          ideas={sortedIdeas}
          selectedIdeaId={selectedIdea?.idea_id ?? null}
          onSelectIdea={setSelectedIdeaId}
          populationSize={populationSize}
          onPopulationSize={setPopulationSize}
          roundCount={roundCount}
          onRoundCount={setRoundCount}
          loadingIdeas={loadingIdeas}
          running={running}
          onRefresh={() => void loadIdeas(true)}
          onRun={() => void handleRun()}
          text={text}
        />

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
              <div className="flex items-center gap-2">
                <Loader2 className="h-4 w-4 animate-spin" />
                {text.loadingReport}
              </div>
            </div>
          ) : report ? (
            <>
              <ReportView report={report} cached={cached} text={text} />
              <InteractionView report={report} text={text} />
            </>
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
