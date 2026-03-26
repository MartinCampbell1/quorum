"use client";

import { ArrowRight } from "lucide-react";

import { Button } from "@/components/ui/button";
import { MODE_ICONS, MODE_LABELS } from "@/lib/constants";
import type { ScenarioDefinition } from "@/lib/types";

import { ScenarioCard } from "./scenario-card";
import { Stepper } from "./stepper";

interface StepScenarioProps {
  scenarios: ScenarioDefinition[];
  selectedId: string | null;
  onSelect: (scenarioId: string) => void;
  onNext: () => void;
}

export function StepScenario({
  scenarios,
  selectedId,
  onSelect,
  onNext,
}: StepScenarioProps) {
  const selectedScenario = scenarios.find((scenario) => scenario.id === selectedId) ?? null;
  const SelectedModeIcon = selectedScenario ? MODE_ICONS[selectedScenario.mode] : null;

  return (
    <div className="flex h-full flex-col bg-[#faf8ff] dark:bg-transparent">
      <div className="flex-1 overflow-y-auto">
        <div className="mx-auto max-w-5xl px-8 pb-6 pt-8">
          <Stepper currentStep={0} />

          <div className="mb-8">
            <h1 className="text-[2.05rem] font-semibold uppercase tracking-[0.06em] text-[#09090b] dark:text-white">
              Mode Selection
            </h1>
            <p className="mt-3 max-w-2xl text-[14px] leading-7 text-[#445d99] dark:text-slate-300">
              Выбери сценарий под задачу. Внутренний orchestration mode и состав агентов останутся под капотом.
            </p>
          </div>

          <div className="grid grid-cols-1 gap-5 md:grid-cols-2">
            {scenarios.map((scenario, index) => (
              <ScenarioCard
                key={scenario.id}
                scenario={scenario}
                isSelected={selectedId === scenario.id}
                isRecommended={index === 0}
                onClick={() => onSelect(scenario.id)}
                index={index}
              />
            ))}
          </div>
        </div>
      </div>

      <div className="border-t border-[#e2e8f0]/70 bg-white/88 dark:border-slate-800/80 dark:bg-slate-950/45">
        <div className="mx-auto flex max-w-5xl items-center justify-between px-8 py-3.5">
          <div className="flex items-center gap-3">
            {selectedScenario ? (
              <>
                {SelectedModeIcon ? <SelectedModeIcon className="h-4 w-4 text-foreground" /> : null}
                <div>
                  <span className="text-sm font-semibold text-foreground">{selectedScenario.name}</span>
                  <span className="ml-2 text-xs text-muted-foreground">Шаг 1 из 3</span>
                  <p className="mt-0.5 text-[11px] text-muted-foreground">
                    Под капотом будет использован режим {MODE_LABELS[selectedScenario.mode]}.
                  </p>
                </div>
              </>
            ) : (
              <span className="text-sm text-muted-foreground">Выберите сценарий для продолжения</span>
            )}
          </div>
          <Button onClick={onNext} disabled={!selectedScenario} size="lg" className="rounded-[14px] bg-[#09090b] px-6 text-white hover:bg-[#09090b]/92 dark:bg-white dark:text-[#09090b] dark:hover:bg-white/90">
            Далее <ArrowRight className="ml-1.5 h-4 w-4" />
          </Button>
        </div>
      </div>
    </div>
  );
}
