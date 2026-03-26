"use client";

import { Check } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { MODE_ICONS, MODE_LABELS } from "@/lib/constants";
import { cn } from "@/lib/utils";
import type { ScenarioDefinition } from "@/lib/types";

interface ScenarioCardProps {
  scenario: ScenarioDefinition;
  isSelected: boolean;
  isRecommended?: boolean;
  onClick: () => void;
  index: number;
}

const SCENARIO_COLORS: Record<string, string> = {
  repo_audit: "from-slate-900/10 via-sky-500/12 to-transparent",
  pattern_mining: "from-sky-500/16 via-cyan-400/10 to-transparent",
  news_context: "from-emerald-500/16 via-teal-400/10 to-transparent",
  strategy_review: "from-amber-500/16 via-orange-400/10 to-transparent",
};

export function ScenarioCard({
  scenario,
  isSelected,
  isRecommended,
  onClick,
  index,
}: ScenarioCardProps) {
  const Icon = MODE_ICONS[scenario.mode];
  const color = SCENARIO_COLORS[scenario.id] ?? SCENARIO_COLORS.repo_audit;

  return (
    <button
      onClick={onClick}
      className={cn(
        "group relative w-full overflow-hidden rounded-[28px] border p-5 text-left transition-all duration-200",
        isSelected
          ? "border-slate-900 bg-slate-950 text-white shadow-[0_24px_54px_-34px_rgba(15,23,42,0.88)] dark:border-slate-100 dark:bg-slate-100 dark:text-slate-950"
          : "border-slate-200/80 bg-[linear-gradient(180deg,rgba(255,255,255,0.96),rgba(248,250,252,0.94))] shadow-[0_16px_42px_-34px_rgba(15,23,42,0.45)] hover:-translate-y-0.5 hover:border-slate-300 hover:shadow-[0_22px_48px_-36px_rgba(15,23,42,0.52)] dark:border-slate-800 dark:bg-[linear-gradient(180deg,rgba(15,23,42,0.88),rgba(15,23,42,0.76))]"
      )}
      style={{ animation: `fade-up 0.22s ease-out ${index * 32}ms both` }}
    >
      <div
        className={cn(
          "pointer-events-none absolute inset-x-0 top-0 h-28 bg-gradient-to-b opacity-100 transition-opacity",
          color,
          isSelected && "opacity-70"
        )}
      />
      <div className="relative">
        <div className="flex items-start justify-between gap-4">
          <div className="flex items-center gap-3">
            <div
              className={cn(
                "flex h-12 w-12 items-center justify-center rounded-2xl border backdrop-blur-sm",
                isSelected
                  ? "border-white/12 bg-white/8 dark:border-slate-900/10 dark:bg-slate-900/6"
                  : "border-slate-200/70 bg-white/88 shadow-sm dark:border-slate-700 dark:bg-slate-900/70"
              )}
            >
              {Icon && <Icon className={cn("h-5 w-5", isSelected ? "text-white dark:text-slate-950" : "text-slate-900 dark:text-slate-100")} />}
            </div>
            <div>
              <p className={cn("text-lg tracking-tight", isSelected ? "font-semibold text-white dark:text-slate-950" : "font-semibold text-slate-950 dark:text-white")}>
                {scenario.name}
              </p>
              <p className={cn("mt-1 text-[12px]", isSelected ? "text-white/68 dark:text-slate-900/68" : "text-muted-foreground")}>
                {scenario.headline}
              </p>
            </div>
          </div>
          {isSelected ? (
            <div className="flex h-7 w-7 items-center justify-center rounded-full bg-background text-foreground">
              <Check className="h-4 w-4" strokeWidth={2.5} />
            </div>
          ) : isRecommended ? (
            <span className="text-[10px] font-semibold uppercase tracking-[0.18em] text-sky-600 dark:text-sky-300">
              Топ
            </span>
          ) : null}
        </div>

        <p className={cn("mt-5 text-[13px] leading-[1.65]", isSelected ? "text-white/82 dark:text-slate-900/82" : "text-slate-700 dark:text-slate-300")}>
          {scenario.description}
        </p>

        <div className="mt-5 flex flex-wrap gap-2">
          <Badge variant="outline" className={cn("text-[10px] font-normal", isSelected && "border-white/15 bg-white/5 text-white/80 dark:border-slate-900/10 dark:bg-slate-900/5 dark:text-slate-900/80")}>
            {MODE_LABELS[scenario.mode]}
          </Badge>
          <Badge variant="outline" className={cn("text-[10px] font-normal", isSelected && "border-white/15 bg-white/5 text-white/80 dark:border-slate-900/10 dark:bg-slate-900/5 dark:text-slate-900/80")}>
            {scenario.default_agents.length} агентов
          </Badge>
          {scenario.tags.slice(0, 2).map((tag) => (
            <Badge
              key={tag}
              variant="outline"
              className={cn("text-[10px] font-normal capitalize", isSelected && "border-white/15 bg-white/5 text-white/80 dark:border-slate-900/10 dark:bg-slate-900/5 dark:text-slate-900/80")}
            >
              {tag}
            </Badge>
          ))}
        </div>

        <div className="mt-5 rounded-2xl border border-slate-200/70 bg-white/70 px-4 py-3 dark:border-slate-800 dark:bg-slate-900/55">
          <p className={cn("text-[11px] leading-relaxed", isSelected ? "text-white/62 dark:text-slate-900/62" : "text-muted-foreground/80")}>
          Лучше всего подходит для: {scenario.recommended_for}
          </p>
        </div>
      </div>
    </button>
  );
}
