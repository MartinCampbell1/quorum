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

const MODE_TAGLINES: Record<string, string> = {
  dictator: "Один лидер делегирует и собирает результат",
  board: "Несколько директоров обсуждают и приходят к решению",
  democracy: "Команда голосует, а система считает итог честно",
  debate: "Две позиции спорят, третий агент выносит вердикт",
  map_reduce: "Большая задача делится на куски и собирается обратно",
  creator_critic: "Один создаёт, второй жёстко улучшает",
  tournament: "Несколько решений соревнуются за лучший финал",
};

const MODE_BEST_FOR: Record<string, string> = {
  dictator: "Когда нужен один ведущий агент и несколько исполнителей",
  board: "Когда важно собрать несколько сильных мнений и договориться",
  democracy: "Когда ты хочешь прозрачное голосование без скрытого арбитра",
  debate: "Когда нужно столкнуть две противоположные позиции",
  map_reduce: "Когда задача большая и её удобно делить на части",
  creator_critic: "Когда нужен быстрый черновик с жёсткой критикой",
  tournament: "Когда хочется столкнуть несколько вариантов и выбрать чемпиона",
};

const MODE_DIFFICULTY: Record<string, string> = {
  dictator: "Лёгкий старт",
  board: "Средний",
  democracy: "Средний",
  debate: "Лёгкий старт",
  map_reduce: "Продвинутый",
  creator_critic: "Лёгкий старт",
  tournament: "Продвинутый",
};

export function ModeCard({ modeKey, info, isSelected, isRecommended, onClick, index }: ModeCardProps) {
  const Icon = MODE_ICONS[modeKey];
  const agentCount = info.default_agents.length;
  const color = MODE_COLORS[modeKey] ?? MODE_COLORS.dictator;
  const description = MODE_TAGLINES[modeKey] ?? info.description;
  const bestFor = MODE_BEST_FOR[modeKey];
  const difficulty = MODE_DIFFICULTY[modeKey] ?? "Средний";

  return (
    <button
      onClick={onClick}
      className={cn(
        "group relative w-full text-left rounded-[24px] border-2 p-5 transition-all duration-200 cursor-pointer min-h-[172px]",
        isSelected
          ? "border-foreground bg-foreground text-background shadow-[0_18px_40px_rgba(0,0,0,0.18)] scale-[1.02] z-10"
          : "border-transparent bg-background shadow-[0_10px_30px_rgba(15,23,42,0.06)] hover:shadow-[0_16px_36px_rgba(15,23,42,0.1)] hover:border-border"
      )}
      style={{ animation: `fade-up 0.2s ease-out ${index * 30}ms both` }}
    >
      {/* Icon — larger with colored fill */}
      <div className="mb-3.5">
        <span className={cn(
          "inline-flex items-center justify-center rounded-xl p-3.5 ring-1 ring-inset transition-all",
          isSelected
            ? "bg-background text-foreground ring-background/20 shadow-sm"
            : cn(color.bg, color.fg, color.ring)
        )}>
          {Icon && <Icon size={24} strokeWidth={2} />}
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
        isSelected ? "text-background/72" : "text-foreground/68"
      )}>
        {description}
      </p>
      <p className={cn(
        "text-[11px] leading-relaxed mb-4",
        isSelected ? "text-background/52" : "text-muted-foreground/82"
      )}>
        Лучше всего подходит, {bestFor?.charAt(0).toLowerCase()}{bestFor?.slice(1)}
      </p>
      <div className="mb-3 flex flex-wrap gap-2">
        <span className={cn(
          "rounded-full px-2.5 py-1 text-[10px] font-medium",
          isSelected ? "bg-background/10 text-background/80" : "bg-muted text-foreground/70"
        )}>
          {difficulty}
        </span>
        <span className={cn(
          "rounded-full px-2.5 py-1 text-[10px] font-medium",
          isSelected ? "bg-background/10 text-background/80" : "bg-muted text-foreground/70"
        )}>
          {agentCount} {agentCount === 1 ? "агент" : agentCount < 5 ? "агента" : "агентов"}
        </span>
      </div>

      {/* Meta */}
      {isSelected && (
        <span className="text-[10px] uppercase tracking-[0.18em] text-background/38">
          Выбранный режим
        </span>
      )}

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
