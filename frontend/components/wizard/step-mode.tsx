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
      <div className="flex-1 overflow-y-auto px-16 pt-12 pb-8">
        <h2 className="text-[32px] font-semibold tracking-tight text-[#f5f5f7]">
          Choose orchestration mode
        </h2>
        <p className="text-[15px] text-white/45 mt-2 mb-12">
          How should the agents collaborate on your task?
        </p>
        <div className="grid grid-cols-2 gap-4 max-w-[840px] lg:grid-cols-3">
          {Object.entries(modes).map(([key, info], idx) => (
            <div key={key} className={idx === 0 ? "col-span-2 lg:col-span-2" : ""}>
              <ModeCard
                modeKey={key}
                info={info}
                isSelected={selected === key}
                onClick={() => onSelect(key)}
                index={idx}
              />
            </div>
          ))}
        </div>
      </div>
      <div className="border-t border-white/[0.06] px-16 py-5 flex justify-end">
        <button
          onClick={onNext}
          disabled={!selected}
          className="rounded-[10px] bg-white/90 px-7 py-2.5 text-[14px] font-semibold text-black/85 hover:bg-white transition-colors disabled:opacity-15 disabled:cursor-not-allowed cursor-pointer"
        >
          Next
        </button>
      </div>
    </div>
  );
}
