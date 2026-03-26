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
      <div className="flex-1 overflow-y-auto px-10 py-10">
        <h2 className="text-2xl font-semibold tracking-tight mb-2">
          Choose orchestration mode
        </h2>
        <p className="text-sm text-text-muted mb-10 max-w-md">
          How should the agents collaborate on your task?
        </p>
        <div className="grid grid-cols-2 gap-4 max-w-3xl lg:grid-cols-3 [&>div:first-child]:col-span-2 [&>div:last-child:nth-child(7)]:lg:col-start-2">
          {Object.entries(modes).map(([key, info]) => (
            <div key={key}>
              <ModeCard
                modeKey={key}
                info={info}
                isSelected={selected === key}
                onClick={() => onSelect(key)}
              />
            </div>
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
