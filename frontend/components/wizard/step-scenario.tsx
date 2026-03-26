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
  const totalAgents = selectedScenario?.default_agents.length ?? 0;

  return (
    <div className="flex h-full flex-col bg-[radial-gradient(circle_at_top_left,_rgba(14,165,233,0.1),_transparent_20%),linear-gradient(180deg,rgba(255,255,255,0.3),transparent_48%)] dark:bg-[radial-gradient(circle_at_top_left,_rgba(56,189,248,0.14),_transparent_18%),linear-gradient(180deg,rgba(15,23,42,0.34),transparent_48%)]">
      <div className="flex-1 overflow-y-auto">
        <div className="mx-auto max-w-6xl px-8 pb-6 pt-8">
          <Stepper currentStep={0} />

          <div className="mb-8 grid gap-5 xl:grid-cols-[minmax(0,1.6fr)_minmax(18rem,0.9fr)]">
            <div className="overflow-hidden rounded-[30px] border border-slate-200/80 bg-[linear-gradient(135deg,rgba(255,255,255,0.94),rgba(241,245,249,0.9))] p-7 shadow-[0_30px_80px_-48px_rgba(15,23,42,0.55)] dark:border-slate-800/80 dark:bg-[linear-gradient(135deg,rgba(15,23,42,0.92),rgba(15,23,42,0.78))]">
              <div className="flex items-center gap-2">
                <span className="rounded-full border border-sky-200 bg-sky-50 px-3 py-1 text-[10px] font-semibold uppercase tracking-[0.2em] text-sky-700 dark:border-sky-900/60 dark:bg-sky-950/40 dark:text-sky-300">
                  Scenario Layer
                </span>
                <span className="rounded-full border border-slate-200 bg-white px-3 py-1 text-[10px] font-medium text-slate-500 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-400">
                  Local multi-agent cockpit
                </span>
              </div>
              <h1 className="mt-5 max-w-3xl text-[2.25rem] font-semibold tracking-tight leading-[1.05] text-slate-950 dark:text-white">
                Выбери готовый сценарий, а не абстрактный orchestration mode
              </h1>
              <p className="mt-4 max-w-3xl text-[15px] leading-7 text-slate-600 dark:text-slate-300">
                Это стартовые multi-agent сценарии под реальные задачи: ревью кода, поиск паттернов, ресёрч рынка
                и жёсткая критика стратегий. Ты выбираешь задачу верхнего уровня, а режим работы команды скрыт под капотом.
              </p>
              <div className="mt-6 flex flex-wrap gap-2.5">
                {["Personal-first", "Subscription-first", "Без orchestration-кода"].map((item) => (
                  <span
                    key={item}
                    className="rounded-full border border-slate-200/80 bg-white/90 px-3.5 py-1.5 text-[11px] font-medium text-slate-700 shadow-sm dark:border-slate-700 dark:bg-slate-900/70 dark:text-slate-300"
                  >
                    {item}
                  </span>
                ))}
              </div>
            </div>

            <div className="rounded-[30px] border border-slate-200/80 bg-[linear-gradient(180deg,rgba(255,255,255,0.96),rgba(241,245,249,0.92))] p-6 shadow-[0_26px_70px_-52px_rgba(15,23,42,0.55)] dark:border-slate-800/80 dark:bg-[linear-gradient(180deg,rgba(15,23,42,0.88),rgba(2,6,23,0.88))]">
              <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-slate-500 dark:text-slate-400">
                Current Selection
              </p>
              {selectedScenario ? (
                <>
                  <div className="mt-4 flex items-start gap-3">
                    <div className="flex h-12 w-12 items-center justify-center rounded-2xl border border-slate-200 bg-white shadow-sm dark:border-slate-700 dark:bg-slate-900">
                      {SelectedModeIcon ? <SelectedModeIcon className="h-5 w-5 text-slate-900 dark:text-white" /> : null}
                    </div>
                    <div>
                      <p className="text-lg font-semibold tracking-tight text-slate-950 dark:text-white">
                        {selectedScenario.name}
                      </p>
                      <p className="mt-1 text-[13px] leading-relaxed text-slate-600 dark:text-slate-300">
                        {selectedScenario.headline}
                      </p>
                    </div>
                  </div>
                  <div className="mt-5 grid grid-cols-2 gap-3">
                    <div className="rounded-2xl border border-slate-200/80 bg-white/90 px-4 py-3 dark:border-slate-800 dark:bg-slate-900/60">
                      <p className="text-[10px] uppercase tracking-[0.16em] text-slate-500 dark:text-slate-400">Mode</p>
                      <p className="mt-1 text-sm font-medium text-slate-900 dark:text-slate-100">
                        {MODE_LABELS[selectedScenario.mode]}
                      </p>
                    </div>
                    <div className="rounded-2xl border border-slate-200/80 bg-white/90 px-4 py-3 dark:border-slate-800 dark:bg-slate-900/60">
                      <p className="text-[10px] uppercase tracking-[0.16em] text-slate-500 dark:text-slate-400">Agents</p>
                      <p className="mt-1 text-sm font-medium text-slate-900 dark:text-slate-100">
                        {totalAgents}
                      </p>
                    </div>
                  </div>
                  <p className="mt-5 text-[12px] leading-relaxed text-slate-600 dark:text-slate-300">
                    {selectedScenario.recommended_for}
                  </p>
                </>
              ) : (
                <p className="mt-4 text-sm text-muted-foreground">Выберите сценарий, чтобы увидеть быстрый бриф.</p>
              )}
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
