"use client";

import { useEffect, useState } from "react";
import { Gauge, GitBranchPlus, Loader2, RefreshCcw, ShieldCheck, Swords, Trophy } from "lucide-react";

import { PairwiseVote } from "@/components/ideas/PairwiseVote";
import { Button } from "@/components/ui/button";
import { getRankingArchive, getRankingLeaderboard, getRankingNextPair } from "@/lib/api";
import { useLocale } from "@/lib/locale";
import type {
  IdeaArchiveSnapshot,
  NextPairResponse,
  PairwiseComparisonResponse,
  RankingLeaderboardResponse,
  RankedIdeaRecord,
} from "@/lib/types";

function percent(value: number): string {
  return `${Math.round(value * 100)}%`;
}

function RankRow({ item }: { item: RankedIdeaRecord }) {
  return (
    <div className="grid gap-3 rounded-[18px] border border-[#d6dbe6] bg-[#fbfcff] px-4 py-4 dark:border-slate-800 dark:bg-slate-900/60 lg:grid-cols-[64px_minmax(0,1.4fr)_120px_120px_130px_130px]">
      <div className="flex items-center">
        <div className="rounded-full border border-[#d6dbe6] bg-white px-3 py-1 text-[11px] font-semibold tracking-[0.04em] text-[#111111] dark:border-slate-800 dark:bg-slate-950 dark:text-slate-100">
          #{item.rank_position}
        </div>
      </div>
      <div className="min-w-0">
        <div className="truncate text-[15px] font-semibold tracking-[-0.03em] text-[#111111] dark:text-slate-100">
          {item.idea.title}
        </div>
        <div className="mt-1 truncate text-[12px] leading-6 text-[#6b7280] dark:text-slate-400">
          {item.idea.summary || item.idea.thesis || item.idea.description || item.idea.source}
        </div>
      </div>
      <div>
        <div className="text-[10px] uppercase tracking-[0.14em] text-[#6b7280] dark:text-slate-500">Rating</div>
        <div className="mt-1 text-[15px] font-semibold tracking-[-0.03em] text-[#111111] dark:text-slate-100">
          {item.rating.toFixed(1)}
        </div>
      </div>
      <div>
        <div className="text-[10px] uppercase tracking-[0.14em] text-[#6b7280] dark:text-slate-500">Merit</div>
        <div className="mt-1 text-[15px] font-semibold tracking-[-0.03em] text-[#111111] dark:text-slate-100">
          {percent(item.merit_score)}
        </div>
      </div>
      <div>
        <div className="text-[10px] uppercase tracking-[0.14em] text-[#6b7280] dark:text-slate-500">Record</div>
        <div className="mt-1 text-[15px] font-semibold tracking-[-0.03em] text-[#111111] dark:text-slate-100">
          {item.wins}-{item.losses}-{item.ties}
        </div>
      </div>
      <div>
        <div className="text-[10px] uppercase tracking-[0.14em] text-[#6b7280] dark:text-slate-500">Stability</div>
        <div className="mt-1 text-[15px] font-semibold tracking-[-0.03em] text-[#111111] dark:text-slate-100">
          {percent(item.stability_score)}
        </div>
      </div>
    </div>
  );
}

export function RankBoard() {
  const { locale } = useLocale();
  const text =
    locale === "ru"
      ? {
          title: "Rank board",
          subtitle: "Elo + merit kernel, adaptive next pair и believability judging поверх discovery ideas.",
          refresh: "Обновить",
          loading: "Собираю ranking board…",
          error: "Не удалось загрузить ranking board.",
          empty: "Пока нет активных идей для ранжирования.",
          archive: "Evolution archive",
          archiveEmpty: "Архив MAP-Elites появится после первых сравнений и хотя бы одной занятой ниши.",
          generation: "Поколение",
          niches: "Ниши",
          coverage: "Покрытие",
          qd: "QD score",
          checkpoints: "Чекпойнты",
          topCells: "Лучшие ниши",
          promptProfiles: "Prompt profiles",
          recommendations: "Следующие ходы",
          noRecommendations: "Пока нет evolutionary-рекомендаций.",
          fit: "Фит",
          novelty: "Новизна",
          uses: "исп.",
          compsShort: "сравн.",
          comps: "Сравнения",
          reliability: "Надёжность",
          stability: "Стабильность ранга",
          volatility: "Волатильность",
          judges: "Believability judges",
          noJudges: "Пока нет judge-профилей. Они появятся после первых pairwise сравнений.",
          ci: "Средний CI",
          pool: "Идей в пуле",
        }
      : {
          title: "Rank board",
          subtitle: "Elo + merit kernel, adaptive next pair selection, and believability judging on top of discovery ideas.",
          refresh: "Refresh",
          loading: "Loading the ranking board…",
          error: "Failed to load the ranking board.",
          empty: "There are no active ideas to rank yet.",
          archive: "Evolution archive",
          archiveEmpty: "The MAP-Elites archive will appear after the first comparisons populate at least one niche.",
          generation: "Generation",
          niches: "Niches",
          coverage: "Coverage",
          qd: "QD score",
          checkpoints: "Checkpoints",
          topCells: "Top niches",
          promptProfiles: "Prompt profiles",
          recommendations: "Next moves",
          noRecommendations: "No evolutionary recommendations yet.",
          fit: "Fit",
          novelty: "Novelty",
          uses: "uses",
          compsShort: "comps",
          comps: "Comparisons",
          reliability: "Reliability",
          stability: "Rank stability",
          volatility: "Volatility",
          judges: "Believability judges",
          noJudges: "Judge profiles will appear after the first pairwise comparisons land.",
          ci: "Avg CI",
          pool: "Ideas in pool",
        };

  const [leaderboard, setLeaderboard] = useState<RankingLeaderboardResponse | null>(null);
  const [nextPair, setNextPair] = useState<NextPairResponse | null>(null);
  const [archive, setArchive] = useState<IdeaArchiveSnapshot | null>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function loadArchive() {
    try {
      const nextArchive = await getRankingArchive(8);
      setArchive(nextArchive);
    } catch {
      // Keep the board responsive even if the archive refresh lags behind compare writes.
    }
  }

  async function loadBoard(showLoader: boolean) {
    if (showLoader) {
      setLoading(true);
    } else {
      setRefreshing(true);
    }
    setError(null);
    try {
      const [nextLeaderboard, nextPairCandidate, nextArchive] = await Promise.all([
        getRankingLeaderboard(12),
        getRankingNextPair(),
        getRankingArchive(8),
      ]);
      setLeaderboard(nextLeaderboard);
      setNextPair(nextPairCandidate);
      setArchive(nextArchive);
    } catch (nextError) {
      setError(nextError instanceof Error ? nextError.message : text.error);
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }

  function handleCompared(result: PairwiseComparisonResponse) {
    setLeaderboard(result.leaderboard);
    setNextPair(result.next_pair ?? null);
    void loadArchive();
  }

  useEffect(() => {
    void loadBoard(true);
  }, []);

  return (
    <section className="rounded-[28px] border border-[#d6dbe6] bg-white/90 p-5 shadow-[0_16px_38px_-28px_rgba(17,48,105,0.22)] dark:border-slate-800 dark:bg-slate-950/60 dark:shadow-none">
      <div className="flex flex-col gap-4 xl:flex-row xl:items-start xl:justify-between">
        <div>
          <div className="flex items-center gap-2 text-[20px] font-semibold tracking-[-0.04em] text-[#111111] dark:text-slate-100">
            <Trophy className="h-5 w-5" />
            {text.title}
          </div>
          <div className="mt-2 max-w-3xl text-[13px] leading-6 text-[#6b7280] dark:text-slate-400">
            {text.subtitle}
          </div>
        </div>
        <Button
          type="button"
          variant="outline"
          size="sm"
          onClick={() => void loadBoard(false)}
          className="h-8 rounded-full text-[11px]"
        >
          {refreshing ? <Loader2 className="mr-1 h-3.5 w-3.5 animate-spin" /> : <RefreshCcw className="mr-1 h-3.5 w-3.5" />}
          {text.refresh}
        </Button>
      </div>

      <div className="mt-5 grid gap-3 md:grid-cols-2 xl:grid-cols-5">
        <div className="rounded-[18px] border border-[#d6dbe6] bg-[#fbfcff] px-4 py-4 dark:border-slate-800 dark:bg-slate-900/60">
          <div className="flex items-center gap-2 text-[11px] uppercase tracking-[0.14em] text-[#6b7280] dark:text-slate-500">
            <Swords className="h-3.5 w-3.5" />
            {text.comps}
          </div>
          <div className="mt-2 text-[28px] font-semibold tracking-[-0.04em] text-[#111111] dark:text-slate-100">
            {leaderboard?.metrics.comparisons_count ?? 0}
          </div>
        </div>
        <div className="rounded-[18px] border border-[#d6dbe6] bg-[#fbfcff] px-4 py-4 dark:border-slate-800 dark:bg-slate-900/60">
          <div className="flex items-center gap-2 text-[11px] uppercase tracking-[0.14em] text-[#6b7280] dark:text-slate-500">
            <ShieldCheck className="h-3.5 w-3.5" />
            {text.reliability}
          </div>
          <div className="mt-2 text-[28px] font-semibold tracking-[-0.04em] text-[#111111] dark:text-slate-100">
            {percent(leaderboard?.metrics.reliability_weighted ?? 0)}
          </div>
        </div>
        <div className="rounded-[18px] border border-[#d6dbe6] bg-[#fbfcff] px-4 py-4 dark:border-slate-800 dark:bg-slate-900/60">
          <div className="flex items-center gap-2 text-[11px] uppercase tracking-[0.14em] text-[#6b7280] dark:text-slate-500">
            <Gauge className="h-3.5 w-3.5" />
            {text.stability}
          </div>
          <div className="mt-2 text-[28px] font-semibold tracking-[-0.04em] text-[#111111] dark:text-slate-100">
            {percent(leaderboard?.metrics.rank_stability ?? 1)}
          </div>
        </div>
        <div className="rounded-[18px] border border-[#d6dbe6] bg-[#fbfcff] px-4 py-4 dark:border-slate-800 dark:bg-slate-900/60">
          <div className="text-[11px] uppercase tracking-[0.14em] text-[#6b7280] dark:text-slate-500">{text.volatility}</div>
          <div className="mt-2 text-[28px] font-semibold tracking-[-0.04em] text-[#111111] dark:text-slate-100">
            {(leaderboard?.metrics.volatility_mean ?? 0).toFixed(1)}
          </div>
        </div>
        <div className="rounded-[18px] border border-[#d6dbe6] bg-[#fbfcff] px-4 py-4 dark:border-slate-800 dark:bg-slate-900/60">
          <div className="text-[11px] uppercase tracking-[0.14em] text-[#6b7280] dark:text-slate-500">{text.ci}</div>
          <div className="mt-2 text-[28px] font-semibold tracking-[-0.04em] text-[#111111] dark:text-slate-100">
            {(leaderboard?.metrics.average_ci_width ?? 0).toFixed(1)}
          </div>
        </div>
      </div>

      <div className="mt-5 grid gap-4 xl:grid-cols-[minmax(0,1.35fr)_minmax(320px,0.8fr)]">
        <div className="space-y-4">
          <PairwiseVote pair={nextPair} onCompared={handleCompared} />

          {loading ? (
            <div className="flex items-center gap-3 rounded-[20px] border border-[#d6dbe6] bg-[#fbfcff] px-4 py-5 text-[13px] text-[#4b5563] dark:border-slate-800 dark:bg-slate-900/60 dark:text-slate-300">
              <Loader2 className="h-4 w-4 animate-spin" />
              {text.loading}
            </div>
          ) : error ? (
            <div className="rounded-[20px] border border-rose-200 bg-rose-50 px-4 py-5 text-[13px] text-rose-700 dark:border-rose-900/60 dark:bg-rose-950/40 dark:text-rose-300">
              {error}
            </div>
          ) : leaderboard && leaderboard.items.length > 0 ? (
            <div className="space-y-3">
              {leaderboard.items.map((item) => (
                <RankRow key={item.idea.idea_id} item={item} />
              ))}
            </div>
          ) : (
            <div className="rounded-[20px] border border-dashed border-[#d6dbe6] bg-[#fbfcff] px-4 py-6 text-[13px] leading-6 text-[#6b7280] dark:border-slate-800 dark:bg-slate-900/60 dark:text-slate-400">
              {text.empty}
            </div>
          )}
        </div>

        <div className="space-y-4">
          <div className="rounded-[24px] border border-[#d6dbe6] bg-white/90 p-4 shadow-[0_12px_32px_-22px_rgba(17,48,105,0.18)] dark:border-slate-800 dark:bg-slate-950/60 dark:shadow-none">
            <div className="flex items-center justify-between gap-3">
              <div>
                <div className="flex items-center gap-2 text-[16px] font-semibold tracking-[-0.03em] text-[#111111] dark:text-slate-100">
                  <GitBranchPlus className="h-4 w-4" />
                  {text.archive}
                </div>
                <div className="mt-1 text-[12px] leading-6 text-[#6b7280] dark:text-slate-400">
                  {text.pool}: {nextPair?.candidate_pool_size ?? leaderboard?.items.length ?? 0}
                </div>
              </div>
            </div>

            {archive && archive.filled_cells > 0 ? (
              <>
                <div className="mt-4 grid gap-3 sm:grid-cols-2">
                  <div className="rounded-[18px] border border-[#d6dbe6] bg-[#fbfcff] px-4 py-3 dark:border-slate-800 dark:bg-slate-900/60">
                    <div className="text-[10px] uppercase tracking-[0.14em] text-[#6b7280] dark:text-slate-500">{text.generation}</div>
                    <div className="mt-1 text-[22px] font-semibold tracking-[-0.03em] text-[#111111] dark:text-slate-100">
                      {archive.generation}
                    </div>
                  </div>
                  <div className="rounded-[18px] border border-[#d6dbe6] bg-[#fbfcff] px-4 py-3 dark:border-slate-800 dark:bg-slate-900/60">
                    <div className="text-[10px] uppercase tracking-[0.14em] text-[#6b7280] dark:text-slate-500">{text.niches}</div>
                    <div className="mt-1 text-[22px] font-semibold tracking-[-0.03em] text-[#111111] dark:text-slate-100">
                      {archive.filled_cells}
                    </div>
                  </div>
                  <div className="rounded-[18px] border border-[#d6dbe6] bg-[#fbfcff] px-4 py-3 dark:border-slate-800 dark:bg-slate-900/60">
                    <div className="text-[10px] uppercase tracking-[0.14em] text-[#6b7280] dark:text-slate-500">{text.coverage}</div>
                    <div className="mt-1 text-[22px] font-semibold tracking-[-0.03em] text-[#111111] dark:text-slate-100">
                      {percent(archive.coverage)}
                    </div>
                  </div>
                  <div className="rounded-[18px] border border-[#d6dbe6] bg-[#fbfcff] px-4 py-3 dark:border-slate-800 dark:bg-slate-900/60">
                    <div className="text-[10px] uppercase tracking-[0.14em] text-[#6b7280] dark:text-slate-500">{text.qd}</div>
                    <div className="mt-1 text-[22px] font-semibold tracking-[-0.03em] text-[#111111] dark:text-slate-100">
                      {archive.qd_score.toFixed(2)}
                    </div>
                    <div className="mt-1 text-[11px] text-[#6b7280] dark:text-slate-400">
                      {text.checkpoints}: {archive.checkpoints.length}
                    </div>
                  </div>
                </div>

                <div className="mt-4">
                  <div className="text-[12px] font-semibold uppercase tracking-[0.14em] text-[#6b7280] dark:text-slate-500">
                    {text.topCells}
                  </div>
                  <div className="mt-3 space-y-3">
                    {archive.cells.slice(0, 4).map((cell) => (
                      <div
                        key={cell.cell_id}
                        className="rounded-[18px] border border-[#d6dbe6] bg-[#fbfcff] px-4 py-3 dark:border-slate-800 dark:bg-slate-900/60"
                      >
                        <div className="truncate text-[13px] font-semibold text-[#111111] dark:text-slate-100">
                          {cell.elite.title}
                        </div>
                        <div className="mt-1 text-[11px] leading-5 text-[#6b7280] dark:text-slate-400">
                          {cell.domain} · {cell.complexity} · {cell.distribution_strategy} · {cell.buyer_type}
                        </div>
                        <div className="mt-3 flex items-center justify-between gap-3 text-[11px] text-[#4b5563] dark:text-slate-300">
                          <span>{text.fit} {percent(cell.elite.fitness)}</span>
                          <span>{text.novelty} {percent(cell.elite.novelty_score)}</span>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>

                <div className="mt-4 grid gap-4 lg:grid-cols-2">
                  <div>
                    <div className="text-[12px] font-semibold uppercase tracking-[0.14em] text-[#6b7280] dark:text-slate-500">
                      {text.promptProfiles}
                    </div>
                    <div className="mt-3 space-y-3">
                      {archive.prompt_profiles.slice(0, 3).map((profile) => (
                        <div
                          key={profile.profile_id}
                          className="rounded-[18px] border border-[#d6dbe6] bg-[#fbfcff] px-4 py-3 dark:border-slate-800 dark:bg-slate-900/60"
                        >
                          <div className="text-[13px] font-semibold text-[#111111] dark:text-slate-100">{profile.label}</div>
                          <div className="mt-1 text-[11px] leading-5 text-[#6b7280] dark:text-slate-400">{profile.operator_kind}</div>
                          <div className="mt-3 flex items-center justify-between gap-3 text-[11px] text-[#4b5563] dark:text-slate-300">
                            <span>Elo {profile.elo_rating.toFixed(1)}</span>
                            <span>{profile.usage_count} {text.uses}</span>
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>

                  <div>
                    <div className="text-[12px] font-semibold uppercase tracking-[0.14em] text-[#6b7280] dark:text-slate-500">
                      {text.recommendations}
                    </div>
                    <div className="mt-3 space-y-3">
                      {archive.recommendations.length > 0 ? (
                        archive.recommendations.slice(0, 3).map((recommendation) => (
                          <div
                            key={recommendation.recommendation_id}
                            className="rounded-[18px] border border-[#d6dbe6] bg-[#fbfcff] px-4 py-3 dark:border-slate-800 dark:bg-slate-900/60"
                          >
                            <div className="text-[13px] font-semibold text-[#111111] dark:text-slate-100">
                              {recommendation.headline}
                            </div>
                            <div className="mt-1 text-[11px] leading-5 text-[#6b7280] dark:text-slate-400">
                              {recommendation.operator_kind}
                            </div>
                            <div className="mt-2 text-[12px] leading-6 text-[#4b5563] dark:text-slate-300">
                              {recommendation.description}
                            </div>
                          </div>
                        ))
                      ) : (
                        <div className="rounded-[18px] border border-dashed border-[#d6dbe6] bg-[#fbfcff] px-4 py-6 text-[13px] leading-6 text-[#6b7280] dark:border-slate-800 dark:bg-slate-900/60 dark:text-slate-400">
                          {text.noRecommendations}
                        </div>
                      )}
                    </div>
                  </div>
                </div>
              </>
            ) : (
              <div className="mt-4 rounded-[18px] border border-dashed border-[#d6dbe6] bg-[#fbfcff] px-4 py-6 text-[13px] leading-6 text-[#6b7280] dark:border-slate-800 dark:bg-slate-900/60 dark:text-slate-400">
                {text.archiveEmpty}
              </div>
            )}
          </div>

          <div className="rounded-[24px] border border-[#d6dbe6] bg-white/90 p-4 shadow-[0_12px_32px_-22px_rgba(17,48,105,0.18)] dark:border-slate-800 dark:bg-slate-950/60 dark:shadow-none">
            <div className="flex items-center justify-between gap-3">
              <div>
                <div className="text-[16px] font-semibold tracking-[-0.03em] text-[#111111] dark:text-slate-100">
                  {text.judges}
                </div>
                <div className="mt-1 text-[12px] leading-6 text-[#6b7280] dark:text-slate-400">
                  {text.pool}: {nextPair?.candidate_pool_size ?? leaderboard?.items.length ?? 0}
                </div>
              </div>
            </div>

            <div className="mt-4 space-y-3">
              {leaderboard && leaderboard.judges.length > 0 ? (
                leaderboard.judges.slice(0, 6).map((judge) => (
                  <div
                    key={judge.judge_key}
                    className="rounded-[18px] border border-[#d6dbe6] bg-[#fbfcff] px-4 py-3 dark:border-slate-800 dark:bg-slate-900/60"
                  >
                    <div className="flex items-center justify-between gap-3">
                      <div className="min-w-0">
                        <div className="truncate text-[13px] font-semibold text-[#111111] dark:text-slate-100">
                          {judge.judge_agent_id || judge.judge_model || judge.judge_source}
                        </div>
                        <div className="mt-1 text-[11px] text-[#6b7280] dark:text-slate-400">
                          {judge.judge_source}
                          {judge.domain_key ? ` · ${judge.domain_key}` : ""}
                        </div>
                      </div>
                      <div className="text-right">
                        <div className="text-[15px] font-semibold tracking-[-0.03em] text-[#111111] dark:text-slate-100">
                          {percent(judge.believability_score)}
                        </div>
                        <div className="text-[11px] text-[#6b7280] dark:text-slate-400">
                          {judge.comparisons_count} {text.compsShort}
                        </div>
                      </div>
                    </div>
                    <div className="mt-3 h-2 rounded-full bg-[#edf0f6] dark:bg-slate-800">
                      <div
                        className="h-2 rounded-full bg-[#111111] dark:bg-slate-100"
                        style={{ width: `${Math.max(8, Math.round(judge.believability_score * 100))}%` }}
                      />
                    </div>
                  </div>
                ))
              ) : (
                <div className="rounded-[18px] border border-dashed border-[#d6dbe6] bg-[#fbfcff] px-4 py-6 text-[13px] leading-6 text-[#6b7280] dark:border-slate-800 dark:bg-slate-900/60 dark:text-slate-400">
                  {text.noJudges}
                </div>
              )}
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}
