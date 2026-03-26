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
  repo_audit: "from-violet-500/18 via-violet-400/8 to-transparent",
  pattern_mining: "from-sky-500/18 via-sky-400/8 to-transparent",
  news_context: "from-emerald-500/18 via-emerald-400/8 to-transparent",
  strategy_review: "from-amber-500/18 via-amber-400/8 to-transparent",
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
        "group relative w-full overflow-hidden rounded-[26px] border p-5 text-left transition-all duration-200",
        isSelected
          ? "border-foreground bg-foreground text-background shadow-[0_20px_48px_rgba(15,23,42,0.18)]"
          : "border-border/70 bg-background shadow-[0_12px_40px_rgba(15,23,42,0.06)] hover:-translate-y-0.5 hover:border-foreground/15 hover:shadow-[0_16px_44px_rgba(15,23,42,0.12)]"
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
                isSelected ? "border-background/12 bg-background/10" : "border-border/60 bg-background/80"
              )}
            >
              {Icon && <Icon className={cn("h-5 w-5", isSelected ? "text-background" : "text-foreground/85")} />}
            </div>
            <div>
              <p className={cn("text-lg tracking-tight", isSelected ? "font-semibold text-background" : "font-semibold text-foreground")}>
                {scenario.name}
              </p>
              <p className={cn("mt-1 text-[12px]", isSelected ? "text-background/68" : "text-muted-foreground")}>
                {scenario.headline}
              </p>
            </div>
          </div>
          {isSelected ? (
            <div className="flex h-7 w-7 items-center justify-center rounded-full bg-background text-foreground">
              <Check className="h-4 w-4" strokeWidth={2.5} />
            </div>
          ) : isRecommended ? (
            <span className="text-[10px] font-semibold uppercase tracking-[0.18em] text-violet-500">
              Топ
            </span>
          ) : null}
        </div>

        <p className={cn("mt-5 text-[13px] leading-[1.65]", isSelected ? "text-background/80" : "text-foreground/74")}>
          {scenario.description}
        </p>

        <div className="mt-5 flex flex-wrap gap-2">
          <Badge variant="outline" className={cn("text-[10px] font-normal", isSelected && "border-background/15 text-background/80")}>
            {MODE_LABELS[scenario.mode]}
          </Badge>
          <Badge variant="outline" className={cn("text-[10px] font-normal", isSelected && "border-background/15 text-background/80")}>
            {scenario.default_agents.length} агентов
          </Badge>
          {scenario.tags.slice(0, 2).map((tag) => (
            <Badge
              key={tag}
              variant="outline"
              className={cn("text-[10px] font-normal capitalize", isSelected && "border-background/15 text-background/80")}
            >
              {tag}
            </Badge>
          ))}
        </div>

        <p className={cn("mt-4 text-[11px] leading-relaxed", isSelected ? "text-background/58" : "text-muted-foreground/80")}>
          Лучше всего подходит для: {scenario.recommended_for}
        </p>
      </div>
    </button>
  );
}
