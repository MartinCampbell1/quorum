import { MODE_ICONS, MODE_LABELS } from "@/lib/constants";
import type { ModeInfo } from "@/lib/types";

interface ModeCardProps {
  modeKey: string;
  info: ModeInfo;
  isSelected: boolean;
  onClick: () => void;
}

export function ModeCard({ modeKey, info, isSelected, onClick }: ModeCardProps) {
  const Icon = MODE_ICONS[modeKey];
  return (
    <button
      onClick={onClick}
      className={`flex flex-col items-center rounded-xl border p-5 text-center transition-all duration-150 cursor-pointer ${
        isSelected
          ? "border-accent bg-blue-950/30 shadow-[0_0_24px_rgba(37,99,235,0.08)]"
          : "border-border bg-bg-card hover:border-border-hover"
      }`}
    >
      <div
        className={`mb-3 flex h-10 w-10 items-center justify-center rounded-lg ${
          isSelected ? "bg-accent text-white" : "bg-bg-secondary text-text-muted"
        }`}
      >
        {Icon && <Icon size={20} />}
      </div>
      <div className="text-sm font-semibold text-text-primary">
        {MODE_LABELS[modeKey] ?? modeKey}
      </div>
      <div className="mt-1 text-xs text-text-muted leading-relaxed">
        {info.description}
      </div>
    </button>
  );
}
