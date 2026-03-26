import { MODE_LABELS, MODE_ICONS } from "@/lib/constants";
import type { ModeInfo } from "@/lib/types";

interface ModeCardProps {
  modeKey: string;
  info: ModeInfo;
  isSelected: boolean;
  onClick: () => void;
  index: number;
}

export function ModeCard({ modeKey, info, isSelected, onClick, index }: ModeCardProps) {
  const Icon = MODE_ICONS[modeKey];

  return (
    <button
      onClick={onClick}
      className={`group relative flex flex-col items-start rounded-2xl border p-7 text-left cursor-pointer transition-all duration-[250ms] ease-[cubic-bezier(0.4,0,0.2,1)] ${
        isSelected
          ? "border-amber-700/50 bg-amber-900/[0.08] shadow-[0_0_0_1px_rgba(217,171,123,0.25),0_4px_24px_rgba(217,171,123,0.08)]"
          : "border-white/[0.08] bg-white/[0.04] hover:bg-white/[0.07] hover:border-white/[0.15] hover:-translate-y-0.5 hover:shadow-[0_2px_20px_rgba(0,0,0,0.3)]"
      }`}
      style={{
        animation: `card-enter 0.4s ease-out ${index * 60}ms both`,
      }}
    >
      {Icon && (
        <div className="absolute top-6 right-6">
          <Icon size={28} strokeWidth={1.5} className="text-white/[0.2]" />
        </div>
      )}
      <div className="text-[16px] font-semibold text-white/90 tracking-tight mt-1">
        {MODE_LABELS[modeKey] ?? modeKey}
      </div>
      <div className="mt-2.5 text-[13.5px] font-normal leading-[1.5] text-white/[0.6] tracking-[0.01em]">
        {info.description}
      </div>
    </button>
  );
}
