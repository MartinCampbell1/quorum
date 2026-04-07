"use client";

import { useState } from "react";
import { ArrowLeftRight, Loader2, Scale, SplitSquareHorizontal } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { compareRankingIdeas } from "@/lib/api";
import { useLocale } from "@/lib/locale";
import type {
  NextPairResponse,
  PairwiseComparisonResponse,
  PairwiseVerdict,
  RankedIdeaRecord,
} from "@/lib/types";

interface PairwiseVoteProps {
  pair: NextPairResponse | null;
  onCompared?: (result: PairwiseComparisonResponse) => void;
}

function ComparisonCard({
  item,
  side,
  labels,
}: {
  item: RankedIdeaRecord;
  side: "left" | "right";
  labels: {
    leftContender: string;
    rightContender: string;
    rating: string;
    stability: string;
    record: string;
    noSummary: string;
  };
}) {
  const accent =
    side === "left"
      ? "border-[#d6dbe6] bg-white dark:border-slate-800 dark:bg-slate-950/60"
      : "border-[#d9d7ff] bg-[#f7f6ff] dark:border-slate-700 dark:bg-slate-900/80";

  return (
    <div className={`rounded-[20px] border p-4 ${accent}`}>
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <div className="text-[10px] font-semibold uppercase tracking-[0.14em] text-[#6b7280] dark:text-slate-500">
            {side === "left" ? labels.leftContender : labels.rightContender}
          </div>
          <div className="mt-2 text-[17px] font-semibold tracking-[-0.03em] text-[#111111] dark:text-slate-100">
            {item.idea.title}
          </div>
        </div>
        <Badge
          variant="outline"
          className="rounded-full border-[#d6dbe6] bg-white text-[#4b5563] dark:border-slate-800 dark:bg-slate-950 dark:text-slate-300"
        >
          #{item.rank_position}
        </Badge>
      </div>
      <div className="mt-3 text-[13px] leading-6 text-[#4b5563] dark:text-slate-300">
        {item.idea.summary || item.idea.thesis || item.idea.description || labels.noSummary}
      </div>
      <div className="mt-4 grid gap-2 sm:grid-cols-3">
        <div className="rounded-[14px] bg-[#fafbff] px-3 py-2 dark:bg-slate-900">
          <div className="text-[10px] uppercase tracking-[0.14em] text-[#6b7280] dark:text-slate-500">{labels.rating}</div>
          <div className="mt-1 text-[16px] font-semibold tracking-[-0.03em] text-[#111111] dark:text-slate-100">
            {item.rating.toFixed(1)}
          </div>
        </div>
        <div className="rounded-[14px] bg-[#fafbff] px-3 py-2 dark:bg-slate-900">
          <div className="text-[10px] uppercase tracking-[0.14em] text-[#6b7280] dark:text-slate-500">{labels.stability}</div>
          <div className="mt-1 text-[16px] font-semibold tracking-[-0.03em] text-[#111111] dark:text-slate-100">
            {Math.round(item.stability_score * 100)}%
          </div>
        </div>
        <div className="rounded-[14px] bg-[#fafbff] px-3 py-2 dark:bg-slate-900">
          <div className="text-[10px] uppercase tracking-[0.14em] text-[#6b7280] dark:text-slate-500">{labels.record}</div>
          <div className="mt-1 text-[16px] font-semibold tracking-[-0.03em] text-[#111111] dark:text-slate-100">
            {item.wins}-{item.losses}-{item.ties}
          </div>
        </div>
      </div>
    </div>
  );
}

export function PairwiseVote({ pair, onCompared }: PairwiseVoteProps) {
  const { locale } = useLocale();
  const text =
    locale === "ru"
      ? {
          title: "Pairwise ranking vote",
          subtitle: "Голосование head-to-head для самого информативного следующего сравнения.",
          empty: "Нужно минимум две активные идеи, чтобы открыть pairwise vote.",
          leftContender: "Левый кандидат",
          rightContender: "Правый кандидат",
          rationale: "Короткая причина",
          rationalePlaceholder: "Почему эта идея выигрывает именно сейчас?",
          left: "Левая сильнее",
          tie: "Почти ничья",
          right: "Правая сильнее",
          comparing: "Сохраняю сравнение…",
          rating: "Рейтинг",
          stability: "Стабильность",
          record: "Баланс",
          noSummary: "Пока без summary.",
          utility: "Информативность",
          seen: "Прямых сравнений",
        }
      : {
          title: "Pairwise ranking vote",
          subtitle: "Adaptive head-to-head comparison for the most informative next decision.",
          empty: "At least two active ideas are required before pairwise voting can start.",
          leftContender: "Left contender",
          rightContender: "Right contender",
          rationale: "Short rationale",
          rationalePlaceholder: "Why does this side win right now?",
          left: "Left wins",
          tie: "Near tie",
          right: "Right wins",
          comparing: "Saving comparison…",
          rating: "Rating",
          stability: "Stability",
          record: "Record",
          noSummary: "No summary yet.",
          utility: "Utility",
          seen: "Direct comps",
        };

  const [rationale, setRationale] = useState("");
  const [busyVerdict, setBusyVerdict] = useState<PairwiseVerdict | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function submit(verdict: PairwiseVerdict) {
    if (!pair) return;
    setBusyVerdict(verdict);
    setError(null);
    try {
      const result = await compareRankingIdeas({
        left_idea_id: pair.left.idea.idea_id,
        right_idea_id: pair.right.idea.idea_id,
        verdict,
        rationale:
          rationale.trim() ||
          (verdict === "tie"
            ? "Founder marked the pair as effectively tied."
            : `Founder selected the ${verdict === "left" ? "left" : "right"} contender.`),
        judge_source: "human",
        judge_confidence: 0.82,
        evidence_weight: 1.0,
        agent_importance_score: 1.0,
        metadata: { surface: "founder-os-rankboard" },
      });
      setRationale("");
      onCompared?.(result);
    } catch (nextError) {
      setError(nextError instanceof Error ? nextError.message : "Failed to save the comparison.");
    } finally {
      setBusyVerdict(null);
    }
  }

  if (!pair) {
    return (
      <div className="rounded-[22px] border border-dashed border-[#d6dbe6] bg-[#fbfcff] px-4 py-6 text-[13px] leading-6 text-[#6b7280] dark:border-slate-800 dark:bg-slate-900/60 dark:text-slate-400">
        {text.empty}
      </div>
    );
  }

  return (
    <div className="rounded-[24px] border border-[#d6dbe6] bg-[#fbfcff] p-4 dark:border-slate-800 dark:bg-slate-900/60">
      <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
        <div>
          <div className="flex items-center gap-2 text-[16px] font-semibold tracking-[-0.03em] text-[#111111] dark:text-slate-100">
            <ArrowLeftRight className="h-4.5 w-4.5" />
            {text.title}
          </div>
          <div className="mt-1 text-[12px] leading-6 text-[#6b7280] dark:text-slate-400">{text.subtitle}</div>
        </div>
        <div className="flex flex-wrap gap-2">
          <Badge
            variant="outline"
            className="rounded-full border-[#d6dbe6] bg-white text-[#4b5563] dark:border-slate-800 dark:bg-slate-950 dark:text-slate-300"
          >
            {text.utility}: {pair.utility_score.toFixed(2)}
          </Badge>
          <Badge
            variant="outline"
            className="rounded-full border-[#d6dbe6] bg-white text-[#4b5563] dark:border-slate-800 dark:bg-slate-950 dark:text-slate-300"
          >
            {text.seen}: {pair.direct_comparisons}
          </Badge>
        </div>
      </div>

      <div className="mt-4 grid gap-4 xl:grid-cols-[minmax(0,1fr)_auto_minmax(0,1fr)]">
        <ComparisonCard item={pair.left} side="left" labels={text} />
        <div className="flex items-center justify-center">
          <div className="flex h-12 w-12 items-center justify-center rounded-full border border-[#d6dbe6] bg-white dark:border-slate-800 dark:bg-slate-950">
            <Scale className="h-5 w-5 text-[#4b5563] dark:text-slate-300" />
          </div>
        </div>
        <ComparisonCard item={pair.right} side="right" labels={text} />
      </div>

      <div className="mt-4 rounded-[18px] bg-white px-4 py-3 text-[12px] leading-6 text-[#4b5563] dark:bg-slate-950/70 dark:text-slate-300">
        {pair.reason}
      </div>

      <div className="mt-4">
        <label className="text-[11px] font-semibold uppercase tracking-[0.14em] text-[#6b7280] dark:text-slate-500">
          {text.rationale}
        </label>
        <textarea
          value={rationale}
          onChange={(event) => setRationale(event.target.value)}
          rows={3}
          placeholder={text.rationalePlaceholder}
          className="mt-2 w-full rounded-[18px] border border-[#d6dbe6] bg-white px-4 py-3 text-[13px] leading-6 text-[#111111] outline-none transition-colors placeholder:text-[#9aa3b2] focus:border-[#111111] dark:border-slate-800 dark:bg-slate-950 dark:text-slate-100 dark:placeholder:text-slate-500 dark:focus:border-slate-300"
        />
      </div>

      {error ? (
        <div className="mt-3 rounded-[16px] border border-rose-200 bg-rose-50 px-4 py-3 text-[13px] leading-6 text-rose-700 dark:border-rose-900/60 dark:bg-rose-950/40 dark:text-rose-300">
          {error}
        </div>
      ) : null}

      <div className="mt-4 flex flex-wrap gap-2">
        <Button
          type="button"
          variant="outline"
          onClick={() => void submit("left")}
          disabled={Boolean(busyVerdict)}
          className="h-9 rounded-full border-[#d6dbe6] bg-white text-[11px] text-[#111111] dark:border-slate-800 dark:bg-slate-950 dark:text-slate-100"
        >
          {busyVerdict === "left" ? <Loader2 className="mr-1 h-3.5 w-3.5 animate-spin" /> : null}
          {text.left}
        </Button>
        <Button
          type="button"
          variant="outline"
          onClick={() => void submit("tie")}
          disabled={Boolean(busyVerdict)}
          className="h-9 rounded-full border-[#d6dbe6] bg-[#eef2ff] text-[11px] text-[#243b74] hover:bg-[#e1e8ff] dark:border-slate-800 dark:bg-slate-800 dark:text-slate-100"
        >
          {busyVerdict === "tie" ? <Loader2 className="mr-1 h-3.5 w-3.5 animate-spin" /> : <SplitSquareHorizontal className="mr-1 h-3.5 w-3.5" />}
          {text.tie}
        </Button>
        <Button
          type="button"
          onClick={() => void submit("right")}
          disabled={Boolean(busyVerdict)}
          className="h-9 rounded-full bg-black text-[11px] text-white hover:bg-black/90 dark:bg-slate-100 dark:text-slate-950"
        >
          {busyVerdict === "right" ? <Loader2 className="mr-1 h-3.5 w-3.5 animate-spin" /> : null}
          {text.right}
        </Button>
        {busyVerdict ? (
          <div className="flex items-center text-[12px] text-[#6b7280] dark:text-slate-400">
            <Loader2 className="mr-2 h-3.5 w-3.5 animate-spin" />
            {text.comparing}
          </div>
        ) : null}
      </div>
    </div>
  );
}
