"use client";

import { ModeCard } from "./mode-card";
import { Button } from "@/components/ui/button";
import { ArrowRight } from "lucide-react";
import { MODE_ICONS, MODE_LABELS } from "@/lib/constants";
import type { ModeInfo } from "@/lib/types";
import { Stepper } from "./stepper";

interface StepModeProps {
  modes: Record<string, ModeInfo>;
  selected: string | null;
  onSelect: (mode: string) => void;
  onNext: () => void;
}

export function StepMode({ modes, selected, onSelect, onNext }: StepModeProps) {
  const entries = Object.entries(modes);

  return (
    <div className="flex flex-col h-full">
      <div className="flex-1 overflow-y-auto">
        <div className="max-w-3xl mx-auto px-8 pt-10 pb-6">
          <Stepper currentStep={0} />

          {/* Header */}
          <div className="mb-10">
            <h1 className="text-3xl font-bold tracking-tight leading-tight">
              Выберите режим оркестрации
            </h1>
            <p className="mt-3 text-[15px] text-muted-foreground leading-relaxed">
              Каждый режим определяет, как AI-агенты взаимодействуют для решения задачи.
            </p>
          </div>

          {/* Cards grid */}
          <div className="grid grid-cols-2 gap-3">
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
      <div className="border-t bg-background">
        <div className="max-w-3xl mx-auto px-8 py-3.5 flex items-center justify-between">
          <div className="flex items-center gap-3">
            {selected ? (
              <>
                {(() => { const I = MODE_ICONS[selected]; return I ? <I className="h-4 w-4 text-foreground" /> : null; })()}
                <div>
                  <span className="font-semibold text-sm text-foreground">{MODE_LABELS[selected]}</span>
                  <span className="text-xs text-muted-foreground ml-2">Шаг 1 из 3</span>
                </div>
              </>
            ) : (
              <span className="text-sm text-muted-foreground">Выберите режим для продолжения</span>
            )}
          </div>
          <Button onClick={onNext} disabled={!selected} size="lg">
            Далее <ArrowRight className="ml-1.5 h-4 w-4" />
          </Button>
        </div>
      </div>
    </div>
  );
}
