"use client";

import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { MODE_LABELS } from "@/lib/constants";
import type { ScenarioDefinition } from "@/lib/types";
import { cn } from "@/lib/utils";

import { ScenarioCard } from "./scenario-card";

interface StepScenarioProps {
  scenarios: ScenarioDefinition[];
  selectedId: string | null;
  onSelect: (scenarioId: string) => void;
  onNext: () => void;
}

const DISPLAY_MODES = [
  {
    mode: "dictator",
    description: "Изящная типографика и ясная иерархия ролей для режима диктатора.",
  },
  {
    mode: "board",
    description: "Покадровое обсуждение между несколькими директорами и общим итогом.",
  },
  {
    mode: "democracy",
    description: "Похожий визуальный язык для голосования, majority и будущего tally view.",
  },
  {
    mode: "debate",
    description: "Точное противопоставление двух сторон и аккуратная фиксация вердикта.",
  },
  {
    mode: "map_reduce",
    description: "Разделение задачи по блокам и сведение результатов в единый вывод.",
  },
  {
    mode: "moa",
    description: "Layered generation: proposers дают ширину, aggregators собирают сильные варианты, judge-pack помогает выбрать финальный synthesis.",
  },
  {
    mode: "creator_critic",
    description: "Дуэт автора и критика с несколькими итерациями и прозрачной обратной связью.",
  },
  {
    mode: "tournament",
    description: "Несколько проектов проходят по сетке матчей, пока судья не выберет чемпиона.",
  },
];

export function StepScenario({
  scenarios,
  selectedId,
  onSelect,
  onNext,
}: StepScenarioProps) {
  const selectedScenario = scenarios.find((scenario) => scenario.id === selectedId) ?? null;
  const selectedMode = selectedScenario?.mode ?? null;
  const scenariosByMode = Object.fromEntries(
    DISPLAY_MODES.map(({ mode }) => [mode, scenarios.filter((scenario) => scenario.mode === mode)])
  ) as Record<string, ScenarioDefinition[]>;
  const selectedModeScenarios = selectedMode ? scenariosByMode[selectedMode] ?? [] : [];
  const selectedModeDescription = DISPLAY_MODES.find((item) => item.mode === selectedMode)?.description ?? "";

  return (
    <div className="flex h-full flex-col bg-[#f6f7fb] dark:bg-[#05070c]">
      <div className="flex-1 overflow-y-auto">
        <div className="px-12 py-6">
          <h1 className="mb-10 text-[2.15rem] font-medium uppercase tracking-[0.04em] text-[#09090b] dark:text-slate-100">
            MODE SELECTION
          </h1>

          <div className="grid grid-cols-1 gap-6 xl:grid-cols-3">
            {DISPLAY_MODES.map(({ mode, description }) => {
              const modeScenarios = scenariosByMode[mode] ?? [];
              const scenario = modeScenarios[0] ?? null;
              const isModeSelected = selectedScenario?.mode === mode && !!scenario;
              return (
                <ScenarioCard
                  key={mode}
                  mode={mode}
                  title={MODE_LABELS[mode] ?? mode}
                  description={description}
                  isSelected={isModeSelected}
                  isDisabled={!scenario}
                  onClick={() => {
                    if (modeScenarios.length > 0) {
                      const preferredScenario =
                        selectedScenario?.mode === mode
                          ? selectedScenario
                          : modeScenarios[0];
                      onSelect(preferredScenario.id);
                    }
                  }}
                />
              );
            })}
          </div>

          {selectedScenario ? (
            <div className="mt-8 rounded-[22px] border border-[#d7dce8] bg-white p-6 shadow-[0_10px_24px_-16px_rgba(17,48,105,0.18)] dark:border-slate-800 dark:bg-slate-950/70 dark:shadow-none">
              <div className="flex flex-wrap items-center gap-2">
                <Badge variant="secondary" className="font-medium">
                  {MODE_LABELS[selectedScenario.mode] ?? selectedScenario.mode}
                </Badge>
                <Badge variant="outline" className="font-medium">
                  {selectedScenario.name}
                </Badge>
                {selectedScenario.tags.slice(0, 3).map((tag) => (
                  <Badge key={tag} variant="outline" className="text-[10px] uppercase tracking-[0.12em]">
                    {tag}
                  </Badge>
                ))}
              </div>

              <div className="mt-4">
                <div className="text-[18px] font-semibold tracking-[-0.02em] text-[#09090b] dark:text-slate-100">
                  {selectedScenario.headline}
                </div>
                <p className="mt-2 max-w-3xl text-[14px] leading-6 text-[#4b5563] dark:text-slate-400">
                  {selectedScenario.description}
                </p>
                {selectedModeDescription ? (
                  <p className="mt-2 text-[12px] leading-6 text-[#697386] dark:text-slate-500">
                    {selectedModeDescription}
                  </p>
                ) : null}
              </div>

              {selectedModeScenarios.length > 1 ? (
                <div className="mt-6">
                  <div className="text-[12px] font-semibold uppercase tracking-[0.14em] text-[#6b7280] dark:text-slate-500">
                    Preset внутри режима
                  </div>
                  <div className="mt-3 grid gap-3 md:grid-cols-2">
                    {selectedModeScenarios.map((scenario) => {
                      const active = scenario.id === selectedScenario.id;
                      return (
                        <button
                          key={scenario.id}
                          type="button"
                          onClick={() => onSelect(scenario.id)}
                          className={cn(
                            "rounded-[16px] border px-4 py-4 text-left transition-colors",
                            active
                              ? "border-[#09090b] bg-[#09090b] text-white dark:border-slate-100 dark:bg-slate-100 dark:text-slate-950"
                              : "border-[#d7dce8] bg-[#fbfcff] text-[#111827] hover:border-[#09090b]/40 dark:border-slate-800 dark:bg-slate-900/60 dark:text-slate-100"
                          )}
                        >
                          <div className="text-[14px] font-semibold">{scenario.name}</div>
                          <div
                            className={cn(
                              "mt-2 text-[12px] leading-5",
                              active ? "text-white/80 dark:text-slate-700" : "text-[#4b5563] dark:text-slate-400"
                            )}
                          >
                            {scenario.recommended_for}
                          </div>
                        </button>
                      );
                    })}
                  </div>
                </div>
              ) : null}

              <div className="mt-6 grid gap-4 md:grid-cols-2">
                <div className="rounded-[16px] border border-[#e6e8ee] bg-[#fbfcff] px-4 py-4 dark:border-slate-800 dark:bg-slate-900/60">
                  <div className="text-[11px] font-semibold uppercase tracking-[0.14em] text-[#6b7280] dark:text-slate-500">
                    Когда использовать
                  </div>
                  <div className="mt-2 text-[13px] leading-6 text-[#374151] dark:text-slate-300">
                    {selectedScenario.recommended_for}
                  </div>
                </div>
                <div className="rounded-[16px] border border-[#e6e8ee] bg-[#fbfcff] px-4 py-4 dark:border-slate-800 dark:bg-slate-900/60">
                  <div className="text-[11px] font-semibold uppercase tracking-[0.14em] text-[#6b7280] dark:text-slate-500">
                    Типовая формулировка
                  </div>
                  <div className="mt-2 text-[13px] leading-6 text-[#374151] dark:text-slate-300">
                    {selectedScenario.task_placeholder}
                  </div>
                </div>
              </div>
            </div>
          ) : null}
        </div>
      </div>

      <div className="flex h-[86px] items-center justify-between border-t border-[#e6e8ee] bg-white px-7 dark:border-slate-800/80 dark:bg-[#0b0f17]/95">
        <div>
          <div className="text-[16px] font-semibold text-[#09090b] dark:text-slate-100">
            {selectedScenario ? selectedScenario.name : "Выберите режим"}
          </div>
          <div className="mt-1 text-[14px] text-[#4b5563] dark:text-slate-400">
            {selectedScenario ? `${MODE_LABELS[selectedScenario.mode]} · Шаг 1 из 3` : "Шаг 1 из 3"}
          </div>
        </div>
        <Button
          type="button"
          onClick={onNext}
          disabled={!selectedScenario}
          className="h-[46px] rounded-[12px] bg-black px-8 text-[15px] font-medium text-white hover:bg-black/90 disabled:bg-black/25"
        >
          Далее
        </Button>
      </div>
    </div>
  );
}
