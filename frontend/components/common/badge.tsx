interface BadgeProps {
  label: string;
  variant?: "default" | "success" | "error" | "accent";
}

const variants: Record<string, string> = {
  default: "bg-white/[0.08] text-white/50 border-transparent",
  success: "bg-white/[0.08] text-white/50 border-transparent",
  error: "bg-red-950/50 text-red-400/70 border-transparent",
  accent: "bg-white/[0.08] text-white/50 border-transparent",
};

export function Badge({ label, variant = "default" }: BadgeProps) {
  return (
    <span
      className={`inline-flex items-center rounded px-2 py-0.5 font-mono text-[10px] font-medium tracking-[0.05em] uppercase border ${variants[variant]}`}
    >
      {label}
    </span>
  );
}
