"use client";

import { Check } from "lucide-react";

import { MODE_ICONS } from "@/lib/constants";
import { cn } from "@/lib/utils";
import type { ScenarioDefinition } from "@/lib/types";

interface ScenarioCardProps {
  scenario: ScenarioDefinition;
  isSelected: boolean;
  isRecommended?: boolean;
  onClick: () => void;
  index: number;
}

export function ScenarioCard({
  scenario,
  isSelected,
  isRecommended,
  onClick,
  index,
}: ScenarioCardProps) {
  const Icon = MODE_ICONS[scenario.mode];

  return (
    <button
      onClick={onClick}
      className={cn(
        "group relative w-full overflow-hidden rounded-[18px] border p-8 text-center transition-all duration-200",
        isSelected
          ? "border-[#09090b] bg-[#09090b] text-white shadow-none dark:border-slate-100 dark:bg-slate-100 dark:text-slate-950"
          : "border-[#e2e8f0] bg-white text-[#09090b] shadow-[0_4px_6px_-1px_rgba(17,48,105,0.04),0_2px_4px_-1px_rgba(17,48,105,0.02)] hover:border-[#98b1f2]/60 hover:bg-[#fdfdff] dark:border-slate-800 dark:bg-slate-950/60"
      )}
      style={{ animation: `fade-up 0.22s ease-out ${index * 32}ms both` }}
    >
      <div className="relative">
        <div className="flex justify-end">
          {isSelected ? (
            <div className="flex h-7 w-7 items-center justify-center rounded-full bg-white text-[#09090b] dark:bg-slate-950 dark:text-white">
              <Check className="h-4 w-4" strokeWidth={2.5} />
            </div>
          ) : isRecommended ? (
            <span className="text-[10px] font-semibold uppercase tracking-[0.18em] text-[#445d99] dark:text-slate-300">
              Top
            </span>
          ) : <span className="h-7 w-7" />}
        </div>

        <div className="mt-3 flex justify-center">
          <div className={cn(
            "flex h-[72px] w-[72px] items-center justify-center rounded-[18px]",
            isSelected ? "bg-white/6 dark:bg-slate-950/10" : "bg-[#faf8ff] dark:bg-slate-900/70"
          )}>
            {Icon && <Icon className={cn("h-11 w-11", isSelected ? "text-white dark:text-slate-950" : "text-[#09090b] dark:text-white")} />}
          </div>
        </div>

        <p className={cn("mt-7 text-[2rem] font-semibold leading-none tracking-[-0.04em]", isSelected ? "text-white dark:text-slate-950" : "text-[#09090b] dark:text-white")}>
          {scenario.name}
        </p>
        <p className={cn("mx-auto mt-4 max-w-xs text-[15px] leading-7", isSelected ? "text-white/72 dark:text-slate-900/70" : "text-[#445d99] dark:text-slate-300")}>
          {scenario.headline || scenario.description}
        </p>
      </div>
    </button>
  );
}
