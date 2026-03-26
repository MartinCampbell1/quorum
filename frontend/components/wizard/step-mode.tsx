import { ModeCard } from "./mode-card";
import { ArrowRight } from "lucide-react";
import type { ModeInfo } from "@/lib/types";

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
        <div className="max-w-[760px] mx-auto px-8 pt-12 pb-8">
          {/* Header */}
          <div className="mb-10" style={{ animation: "fade-up 0.5s ease-out both" }}>
            <p className="text-[11px] font-mono font-medium uppercase tracking-[0.15em] mb-3" style={{ color: "#cfa872" }}>
              Step 1 of 3
            </p>
            <h2
              className="text-[28px] font-bold tracking-tight leading-tight"
              style={{ color: "#e8e5dc" }}
            >
              How should agents
              <br />
              <span style={{ color: "#cfa872" }}>collaborate?</span>
            </h2>
            <p className="mt-3 text-[14px]" style={{ color: "#777" }}>
              Each mode defines a different decision-making structure.
            </p>
          </div>

          {/* Cards grid */}
          <div className="grid grid-cols-2 gap-3">
            {entries.map(([key, info], idx) => {
              const isLast = idx === entries.length - 1 && entries.length % 2 === 1;
              return (
                <div key={key} className={isLast ? "col-span-2 max-w-[calc(50%-6px)]" : ""}>
                  <ModeCard
                    modeKey={key}
                    info={info}
                    isSelected={selected === key}
                    onClick={() => onSelect(key)}
                    index={idx}
                  />
                </div>
              );
            })}
          </div>
        </div>
      </div>

      {/* Footer */}
      <div
        className="px-8 py-4 flex items-center justify-between"
        style={{
          borderTop: "1px solid #1a1a1a",
          background: "linear-gradient(to top, #0c0c0c, #0c0c0cee)",
          backdropFilter: "blur(8px)",
        }}
      >
        <p className="text-[12px] font-mono" style={{ color: "#444" }}>
          {selected ? `${selected} selected` : "Select a mode to continue"}
        </p>
        <button
          onClick={onNext}
          disabled={!selected}
          className="group flex items-center gap-2 cursor-pointer transition-all duration-200 disabled:cursor-not-allowed"
          style={{
            background: selected
              ? "linear-gradient(135deg, #cfa872, #b8935f)"
              : "#1a1a1a",
            color: selected ? "#0c0c0c" : "#444",
            fontWeight: 600,
            fontSize: "13px",
            padding: "10px 24px",
            borderRadius: "8px",
            border: selected ? "none" : "1px solid #252525",
            opacity: selected ? 1 : 0.6,
            boxShadow: selected ? "0 4px 16px rgba(207,168,114,0.25)" : "none",
          }}
        >
          Continue
          <ArrowRight size={14} className="transition-transform group-hover:translate-x-0.5" />
        </button>
      </div>
    </div>
  );
}
