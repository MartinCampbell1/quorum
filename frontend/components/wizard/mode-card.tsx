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
      className={`group flex flex-col items-start rounded-2xl border p-6 text-left cursor-pointer backdrop-blur-xl transition-all duration-[400ms] ease-[cubic-bezier(0.175,0.885,0.32,1.275)] ${
        isSelected
          ? "border-accent bg-white/[0.07] shadow-[0_0_32px_rgba(37,99,235,0.15)]"
          : "border-white/[0.06] bg-white/[0.02] hover:bg-white/[0.06] hover:border-accent/40 hover:-translate-y-1 hover:shadow-[0_8px_32px_rgba(0,0,0,0.3)]"
      }`}
    >
      <div
        className={`mb-4 flex h-11 w-11 items-center justify-center rounded-xl transition-all duration-300 ${
          isSelected
            ? "bg-accent text-white shadow-[0_0_16px_rgba(37,99,235,0.3)]"
            : "bg-white/[0.04] text-text-muted group-hover:text-accent group-hover:bg-accent/10"
        }`}
      >
        {Icon && <Icon size={20} strokeWidth={1.5} />}
      </div>
      <div className="text-[15px] font-semibold text-text-primary tracking-tight">
        {MODE_LABELS[modeKey] ?? modeKey}
      </div>
      <div className="mt-1.5 text-[13px] text-white/75 leading-relaxed [text-wrap:balance] [font-weight:450]">
        {info.description}
      </div>
    </button>
  );
}
