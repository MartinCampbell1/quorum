import { MODE_LABELS, MODE_ICONS } from "@/lib/constants";
import type { ModeInfo } from "@/lib/types";

interface ModeCardProps {
  modeKey: string;
  info: ModeInfo;
  isSelected: boolean;
  onClick: () => void;
  index: number;
}

const ACCENT_MAP: Record<string, string> = {
  dictator: "#cfa872",
  board: "#72a8cf",
  democracy: "#72cf8a",
  debate: "#cf7272",
  map_reduce: "#a872cf",
  creator_critic: "#72cfcf",
  tournament: "#cfcf72",
};

export function ModeCard({ modeKey, info, isSelected, onClick, index }: ModeCardProps) {
  const Icon = MODE_ICONS[modeKey];
  const accent = ACCENT_MAP[modeKey] ?? "#cfa872";

  return (
    <button
      onClick={onClick}
      style={{
        animation: `fade-up 0.5s ease-out ${index * 70}ms both`,
      }}
      className={`
        group relative w-full text-left cursor-pointer
        rounded-xl transition-all duration-300 ease-out
        ${isSelected
          ? "ring-2 ring-offset-1 ring-offset-[#0c0c0c] scale-[1.02]"
          : "hover:scale-[1.015] hover:shadow-2xl"
        }
      `}
    >
      {/* Card surface */}
      <div
        className="relative overflow-hidden rounded-xl p-6"
        style={{
          background: isSelected
            ? `linear-gradient(135deg, ${accent}18 0%, #1a1a18 100%)`
            : "linear-gradient(135deg, #181818 0%, #141414 100%)",
          border: isSelected ? `1px solid ${accent}66` : "1px solid #252525",
          boxShadow: isSelected
            ? `0 0 40px ${accent}15, 0 20px 40px rgba(0,0,0,0.3)`
            : "0 2px 8px rgba(0,0,0,0.3)",
          // @ts-expect-error CSS custom property for ring color
          "--tw-ring-color": accent,
        }}
      >
        {/* Subtle corner glow on selected */}
        {isSelected && (
          <div
            className="absolute -top-12 -right-12 w-32 h-32 rounded-full blur-3xl opacity-20"
            style={{ background: accent }}
          />
        )}

        {/* Icon row */}
        <div className="flex items-center justify-between mb-5 relative z-10">
          {Icon && (
            <div
              className="flex items-center justify-center w-10 h-10 rounded-lg"
              style={{
                background: isSelected ? `${accent}20` : "rgba(255,255,255,0.05)",
                border: `1px solid ${isSelected ? `${accent}40` : "rgba(255,255,255,0.06)"}`,
              }}
            >
              <Icon
                size={20}
                strokeWidth={1.5}
                style={{ color: isSelected ? accent : "#666" }}
              />
            </div>
          )}
          {/* Selection indicator */}
          <div
            className="w-5 h-5 rounded-full border-2 flex items-center justify-center transition-all duration-200"
            style={{
              borderColor: isSelected ? accent : "#333",
              background: isSelected ? accent : "transparent",
            }}
          >
            {isSelected && (
              <svg width="10" height="10" viewBox="0 0 10 10" fill="none">
                <path d="M2 5L4.5 7.5L8 3" stroke="#0c0c0c" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
              </svg>
            )}
          </div>
        </div>

        {/* Text */}
        <div className="relative z-10">
          <h3
            className="text-[15px] font-semibold tracking-tight mb-1.5"
            style={{ color: isSelected ? "#f0ebe0" : "#c8c5bc" }}
          >
            {MODE_LABELS[modeKey] ?? modeKey}
          </h3>
          <p
            className="text-[13px] leading-[1.5]"
            style={{ color: isSelected ? "#9e9a8f" : "#666" }}
          >
            {info.description}
          </p>
        </div>

        {/* Bottom accent line */}
        <div
          className="absolute bottom-0 left-0 right-0 h-[2px] transition-opacity duration-300"
          style={{
            background: `linear-gradient(90deg, transparent, ${accent}, transparent)`,
            opacity: isSelected ? 0.6 : 0,
          }}
        />
      </div>
    </button>
  );
}
