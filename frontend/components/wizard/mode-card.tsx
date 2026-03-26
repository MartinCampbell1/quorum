"use client";

import { Check } from "lucide-react";
import { MODE_LABELS, MODE_ICONS } from "@/lib/constants";
import { cn } from "@/lib/utils";
import type { ModeInfo } from "@/lib/types";

interface ModeCardProps {
  modeKey: string;
  info: ModeInfo;
  isSelected: boolean;
  isRecommended?: boolean;
  onClick: () => void;
  index: number;
}

const MODE_COLORS: Record<string, { bg: string; fg: string; ring: string }> = {
  dictator:      { bg: "bg-violet-50 dark:bg-violet-950/30",  fg: "text-violet-700",  ring: "ring-violet-200 dark:ring-violet-800" },
  board:         { bg: "bg-blue-50 dark:bg-blue-950/30",      fg: "text-blue-700",    ring: "ring-blue-200 dark:ring-blue-800" },
  democracy:     { bg: "bg-emerald-50 dark:bg-emerald-950/30",fg: "text-emerald-700", ring: "ring-emerald-200 dark:ring-emerald-800" },
  debate:        { bg: "bg-orange-50 dark:bg-orange-950/30",  fg: "text-orange-700",  ring: "ring-orange-200 dark:ring-orange-800" },
  map_reduce:    { bg: "bg-sky-50 dark:bg-sky-950/30",        fg: "text-sky-700",     ring: "ring-sky-200 dark:ring-sky-800" },
  creator_critic:{ bg: "bg-pink-50 dark:bg-pink-950/30",      fg: "text-pink-700",    ring: "ring-pink-200 dark:ring-pink-800" },
  tournament:    { bg: "bg-amber-50 dark:bg-amber-950/30",    fg: "text-amber-700",   ring: "ring-amber-200 dark:ring-amber-800" },
};

const MODE_DESCRIPTIONS: Record<string, string> = {
  dictator: "Один директор делегирует задачи воркерам, собирает и синтезирует результаты",
  board: "Совет из 3 директоров обсуждает и голосует, затем делегирует воркерам",
  democracy: "Все агенты голосуют равноправно, побеждает большинство, ничья — переголосование",
  debate: "Пропонент против оппонента спорят в раундах, судья определяет победителя",
  map_reduce: "Разделить задачу на части, обработать параллельно, синтезировать результат",
  creator_critic: "Создатель делает работу, критик проверяет — итерации до одобрения",
  tournament: "Все агенты соревнуются, турнирная сетка с выбыванием, судья выбирает чемпиона",
};

export function ModeCard({ modeKey, info, isSelected, isRecommended, onClick, index }: ModeCardProps) {
  const Icon = MODE_ICONS[modeKey];
  const agentCount = info.default_agents.length;
  const color = MODE_COLORS[modeKey] ?? MODE_COLORS.dictator;
  const description = MODE_DESCRIPTIONS[modeKey] ?? info.description;

  return (
    <button
      onClick={onClick}
      className={cn(
        "group relative w-full text-left rounded-2xl border-2 p-6 transition-all duration-200 cursor-pointer min-h-[180px]",
        isSelected
          ? "border-foreground bg-foreground text-background shadow-lg scale-[1.02] z-10"
          : "border-transparent bg-background shadow-[0_1px_3px_rgba(0,0,0,0.06)] hover:shadow-md hover:border-border"
      )}
      style={{ animation: `fade-up 0.2s ease-out ${index * 30}ms both` }}
    >
      {/* Icon — larger with colored fill */}
      <div className="mb-4">
        <span className={cn(
          "inline-flex items-center justify-center rounded-xl p-4 ring-1 ring-inset transition-all",
          isSelected
            ? "bg-background text-foreground ring-background/20 shadow-sm"
            : cn(color.bg, color.fg, color.ring)
        )}>
          {Icon && <Icon size={28} strokeWidth={2} />}
        </span>
      </div>

      {/* Content */}
      <h3 className={cn(
        "text-base tracking-tight mb-1.5",
        isSelected ? "font-bold text-background" : "font-semibold text-foreground"
      )}>
        {MODE_LABELS[modeKey] ?? modeKey}
      </h3>
      <p className={cn(
        "text-[13px] leading-[1.6] mb-4",
        isSelected ? "text-background/70" : "text-foreground/60"
      )}>
        {description}
      </p>

      {/* Meta */}
      <span className={cn(
        "text-[11px] font-mono",
        isSelected ? "text-background/40" : "text-muted-foreground/40"
      )}>
        {agentCount} {agentCount === 1 ? "агент" : agentCount < 5 ? "агента" : "агентов"}
      </span>

      {/* Selected indicator */}
      {isSelected && (
        <div className="absolute top-5 right-5">
          <div className="h-6 w-6 rounded-full bg-background flex items-center justify-center">
            <Check className="h-3.5 w-3.5 text-foreground" strokeWidth={2.5} />
          </div>
        </div>
      )}

      {/* Recommended label */}
      {isRecommended && !isSelected && (
        <span className="absolute top-5 right-5 text-[10px] font-semibold text-violet-500 uppercase tracking-wider">
          Топ
        </span>
      )}
    </button>
  );
}
