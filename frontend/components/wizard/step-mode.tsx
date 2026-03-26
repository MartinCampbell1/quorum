import { ModeCard } from "./mode-card";
import { Button } from "@/components/common/button";
import type { ModeInfo } from "@/lib/types";

interface StepModeProps {
  modes: Record<string, ModeInfo>;
  selected: string | null;
  onSelect: (mode: string) => void;
  onNext: () => void;
}

export function StepMode({ modes, selected, onSelect, onNext }: StepModeProps) {
  return (
    <div className="flex flex-col h-full">
      <div className="flex-1 overflow-y-auto p-8">
        <h2 className="text-xl font-semibold tracking-tight mb-1">
          Choose orchestration mode
        </h2>
        <p className="text-sm text-text-muted mb-8">
          How should the agents collaborate?
        </p>
        <div className="grid grid-cols-2 gap-3 max-w-2xl lg:grid-cols-3">
          {Object.entries(modes).map(([key, info]) => (
            <ModeCard
              key={key}
              modeKey={key}
              info={info}
              isSelected={selected === key}
              onClick={() => onSelect(key)}
            />
          ))}
        </div>
      </div>
      <div className="border-t border-border p-4 flex justify-end">
        <Button onClick={onNext} disabled={!selected}>
          Next
        </Button>
      </div>
    </div>
  );
}
