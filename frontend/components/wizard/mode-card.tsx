"use client";

import { MagicCard } from "@/components/ui/magic-card";
import { Badge } from "@/components/ui/badge";
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

export function ModeCard({ modeKey, info, isSelected, isRecommended, onClick, index }: ModeCardProps) {
  const Icon = MODE_ICONS[modeKey];

  return (
    <div
      onClick={onClick}
      className="cursor-pointer relative"
      style={{ animation: `fade-up 0.35s ease-out ${index * 50}ms both` }}
    >
      {isRecommended && (
        <Badge className="absolute -top-2.5 right-3 z-10 text-[10px]">
          Popular
        </Badge>
      )}
      <MagicCard
        className={cn(
          "p-6 transition-all duration-200",
          isSelected
            ? "ring-2 ring-primary shadow-lg bg-primary/5"
            : "hover:shadow-md hover:-translate-y-0.5"
        )}
        gradientSize={150}
        gradientOpacity={0.1}
      >
        <div className="flex items-start gap-4">
          <div className={cn(
            "flex h-12 w-12 shrink-0 items-center justify-center rounded-xl transition-colors",
            isSelected
              ? "bg-primary text-primary-foreground"
              : "bg-muted text-muted-foreground"
          )}>
            {Icon && <Icon size={22} strokeWidth={1.5} />}
          </div>
          <div className="min-w-0 pt-0.5">
            <h3 className="text-sm font-semibold tracking-tight leading-tight">
              {MODE_LABELS[modeKey] ?? modeKey}
            </h3>
            <p className="mt-1.5 text-[13px] text-muted-foreground leading-relaxed">
              {info.description}
            </p>
          </div>
        </div>
      </MagicCard>
    </div>
  );
}
