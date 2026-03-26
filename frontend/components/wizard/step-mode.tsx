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
  const selectedLabel = selected ? MODE_LABELS[selected] : null;

  return (
    <div className="flex flex-col h-full bg-[radial-gradient(circle_at_top,_rgba(0,0,0,0.035),_transparent_45%)]">
      <div className="flex-1 overflow-y-auto">
        <div className="max-w-5xl mx-auto px-8 pt-8 pb-6">
          <Stepper currentStep={0} />

          {/* Header */}
          <div className="mb-8">
            <h1 className="text-3xl font-bold tracking-tight leading-tight">
              Выберите режим оркестрации
            </h1>
            <p className="mt-3 text-[15px] text-muted-foreground leading-relaxed">
              Это готовые схемы работы команды агентов. Сначала выбери, как они будут взаимодействовать,
              потом настроишь роли и задачу.
            </p>
            <div className="mt-4 flex flex-wrap gap-2">
              <span className="rounded-full border border-border/80 bg-background px-3 py-1 text-[11px] font-medium text-foreground/80">
                Без кода
              </span>
              <span className="rounded-full border border-border/80 bg-background px-3 py-1 text-[11px] font-medium text-foreground/80">
                Готовые сценарии
              </span>
              <span className="rounded-full border border-border/80 bg-background px-3 py-1 text-[11px] font-medium text-foreground/80">
                3 шага до запуска
              </span>
            </div>
          </div>

          {/* Cards grid */}
          <div className="grid grid-cols-1 gap-3 md:grid-cols-2 xl:grid-cols-3">
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
        <div className="max-w-5xl mx-auto px-8 py-3.5 flex items-center justify-between">
          <div className="flex items-center gap-3">
            {selected ? (
              <>
                {(() => { const I = MODE_ICONS[selected]; return I ? <I className="h-4 w-4 text-foreground" /> : null; })()}
                <div>
                  <span className="font-semibold text-sm text-foreground">{selectedLabel}</span>
                  <span className="text-xs text-muted-foreground ml-2">Шаг 1 из 3</span>
                  <p className="text-[11px] text-muted-foreground mt-0.5">
                    Дальше настроишь роли агентов, инструменты и системные промпты.
                  </p>
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
