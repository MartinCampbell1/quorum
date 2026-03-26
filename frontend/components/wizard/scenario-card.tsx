"use client";

import { MODE_ICONS } from "@/lib/constants";
import { cn } from "@/lib/utils";

interface ScenarioCardProps {
  mode: string;
  title: string;
  description: string;
  isSelected: boolean;
  isDisabled?: boolean;
  onClick: () => void;
}

export function ScenarioCard({
  mode,
  title,
  description,
  isSelected,
  isDisabled = false,
  onClick,
}: ScenarioCardProps) {
  const Icon = MODE_ICONS[mode];

  return (
    <button
      type="button"
      onClick={onClick}
      disabled={isDisabled}
      className={cn(
        "relative flex min-h-[218px] w-full flex-col items-center justify-center rounded-[18px] border px-8 py-10 text-center transition-all",
        isSelected
          ? "border-[#09090b] bg-[#09090b] text-white"
          : "border-[#d7dce8] bg-white text-[#09090b] shadow-[0_10px_24px_-16px_rgba(17,48,105,0.18)]",
        isDisabled && "cursor-not-allowed opacity-55"
      )}
    >
      <div
        className={cn(
          "mb-8 flex h-[76px] w-[76px] items-center justify-center rounded-[18px]",
          isSelected ? "bg-white/7" : "bg-white"
        )}
      >
        {Icon ? (
          <Icon
            className={cn(
              "h-[44px] w-[44px] stroke-[1.7]",
              isSelected ? "text-white" : "text-[#09090b]"
            )}
          />
        ) : null}
      </div>
      <h3 className="text-[20px] font-semibold tracking-[-0.03em]">{title}</h3>
      <p
        className={cn(
          "mt-3 max-w-[260px] text-[15px] leading-[1.45]",
          isSelected ? "text-white/82" : "text-[#444b59]"
        )}
      >
        {description}
      </p>
    </button>
  );
}
