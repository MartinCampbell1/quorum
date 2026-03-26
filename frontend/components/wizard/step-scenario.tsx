"use client";

import { Button } from "@/components/ui/button";
import { MODE_LABELS } from "@/lib/constants";
import type { ScenarioDefinition } from "@/lib/types";

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
    mode: "creator_critic",
    description: "Дуэт автора и критика с несколькими итерациями и прозрачной обратной связью.",
  },
];

function findScenarioByMode(
  scenarios: ScenarioDefinition[],
  mode: string
): ScenarioDefinition | null {
  return scenarios.find((scenario) => scenario.mode === mode) ?? null;
}

export function StepScenario({
  scenarios,
  selectedId,
  onSelect,
  onNext,
}: StepScenarioProps) {
  const selectedScenario = scenarios.find((scenario) => scenario.id === selectedId) ?? null;

  return (
    <div className="flex h-full flex-col bg-white">
      <div className="flex-1 overflow-y-auto">
        <div className="px-12 py-6">
          <h1 className="mb-10 text-[2.15rem] font-medium uppercase tracking-[0.04em] text-[#09090b]">
            MODE SELECTION
          </h1>

          <div className="grid grid-cols-1 gap-6 xl:grid-cols-3">
            {DISPLAY_MODES.map(({ mode, description }) => {
              const scenario = findScenarioByMode(scenarios, mode);
              return (
                <ScenarioCard
                  key={mode}
                  mode={mode}
                  title={MODE_LABELS[mode] ?? mode}
                  description={description}
                  isSelected={selectedScenario?.id === scenario?.id && !!scenario}
                  isDisabled={!scenario}
                  onClick={() => {
                    if (scenario) {
                      onSelect(scenario.id);
                    }
                  }}
                />
              );
            })}
          </div>
        </div>
      </div>

      <div className="flex h-[86px] items-center justify-between border-t border-[#e6e8ee] bg-white px-7">
        <div>
          <div className="text-[16px] font-semibold text-[#09090b]">
            {selectedScenario ? MODE_LABELS[selectedScenario.mode] : "Выберите режим"}
          </div>
          <div className="mt-1 text-[14px] text-[#4b5563]">Шаг 1 из 3</div>
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
