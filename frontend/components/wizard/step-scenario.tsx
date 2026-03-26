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
    <div className="flex h-full flex-col bg-[radial-gradient(circle_at_top_left,_rgba(0,0,0,0.045),_transparent_42%)]">
      <div className="flex-1 overflow-y-auto">
        <div className="mx-auto max-w-6xl px-8 pb-6 pt-8">
          <Stepper currentStep={0} />

          <div className="mb-8 max-w-3xl">
            <h1 className="text-3xl font-bold tracking-tight leading-tight">
              Выбери готовый сценарий
            </h1>
            <p className="mt-3 text-[15px] leading-relaxed text-muted-foreground">
              Это не абстрактные режимы orchestration, а стартовые multi-agent сценарии под реальные задачи:
              ревью кода, поиск паттернов, ресёрч новостей и жёсткая проверка стратегий.
            </p>
            <div className="mt-4 flex flex-wrap gap-2">
              <span className="rounded-full border border-border/80 bg-background px-3 py-1 text-[11px] font-medium text-foreground/80">
                Personal-first
              </span>
              <span className="rounded-full border border-border/80 bg-background px-3 py-1 text-[11px] font-medium text-foreground/80">
                Subscription-first
              </span>
              <span className="rounded-full border border-border/80 bg-background px-3 py-1 text-[11px] font-medium text-foreground/80">
                Без orchestration-кода
              </span>
            </div>
          </div>

          <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
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

      <div className="border-t bg-background">
        <div className="mx-auto flex max-w-6xl items-center justify-between px-8 py-3.5">
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
          <Button onClick={onNext} disabled={!selectedScenario} size="lg">
            Далее <ArrowRight className="ml-1.5 h-4 w-4" />
          </Button>
        </div>
      </div>
    </div>
  );
}
