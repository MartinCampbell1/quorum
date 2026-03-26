"use client";

import { ModeCard } from "./mode-card";
import { ShimmerButton } from "@/components/ui/shimmer-button";
import { Button } from "@/components/ui/button";
import { Separator } from "@/components/ui/separator";
import { ArrowRight } from "lucide-react";
import { cn } from "@/lib/utils";
import type { ModeInfo } from "@/lib/types";

interface StepModeProps {
  modes: Record<string, ModeInfo>;
  selected: string | null;
  onSelect: (mode: string) => void;
  onNext: () => void;
}

const STEPS = ["Select Mode", "Configure", "Launch"];

export function StepMode({ modes, selected, onSelect, onNext }: StepModeProps) {
  const entries = Object.entries(modes);

  return (
    <div className="flex flex-col h-full">
      <div className="flex-1 overflow-y-auto">
        <div className="max-w-3xl mx-auto px-8 pt-12 pb-8">
          {/* Stepper */}
          <div className="flex items-center gap-3 mb-10">
            {STEPS.map((label, i) => (
              <div key={i} className="flex items-center gap-2">
                <div className={cn(
                  "flex h-7 w-7 items-center justify-center rounded-full text-xs font-semibold",
                  i === 0
                    ? "bg-primary text-primary-foreground"
                    : "bg-muted text-muted-foreground"
                )}>
                  {i + 1}
                </div>
                <span className={cn(
                  "text-sm",
                  i === 0 ? "text-foreground font-semibold" : "text-muted-foreground/60 font-normal"
                )}>
                  {label}
                </span>
                {i < STEPS.length - 1 && <Separator className="w-12" />}
              </div>
            ))}
          </div>

          {/* Header */}
          <div className="mb-10">
            <h1 className="text-3xl font-bold tracking-tight">
              Choose orchestration mode
            </h1>
            <p className="mt-3 text-base text-muted-foreground max-w-lg">
              Each mode defines how agents communicate, make decisions, and deliver results.
            </p>
          </div>

          {/* Cards grid */}
          <div className="grid grid-cols-2 gap-5 lg:grid-cols-3">
            {entries.map(([key, info], idx) => (
              <ModeCard
                key={key}
                modeKey={key}
                info={info}
                isSelected={selected === key}
                isRecommended={idx === 0}
                onClick={() => onSelect(key)}
                index={idx}
              />
            ))}
          </div>
        </div>
      </div>

      {/* Footer */}
      <Separator />
      <div className="px-8 py-4 flex items-center justify-between">
        <div className="flex items-center gap-2 text-sm text-muted-foreground">
          {selected ? (
            <>
              {(() => { const I = MODE_ICONS[selected]; return I ? <I className="h-4 w-4" /> : null; })()}
              <span className="font-medium text-foreground">{MODE_LABELS[selected]}</span>
              <span>selected</span>
            </>
          ) : (
            <span>Select a mode to continue</span>
          )}
        </div>
        {selected ? (
          <ShimmerButton onClick={onNext} className="shadow-lg">
            <span className="flex items-center gap-2 text-sm font-medium">
              Continue <ArrowRight className="h-4 w-4" />
            </span>
          </ShimmerButton>
        ) : (
          <Button onClick={onNext} disabled size="lg">
            Continue <ArrowRight className="ml-2 h-4 w-4" />
          </Button>
        )}
      </div>
    </div>
  );
}
