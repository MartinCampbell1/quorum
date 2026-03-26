interface BadgeProps {
  label: string;
  variant?: "default" | "success" | "error" | "accent";
}

const variants: Record<string, string> = {
  default: "bg-bg-card text-text-secondary border-border",
  success: "bg-green-950 text-success border-green-900",
  error: "bg-red-950 text-error border-red-900",
  accent: "bg-blue-950 text-accent border-blue-900",
};

export function Badge({ label, variant = "default" }: BadgeProps) {
  return (
    <span
      className={`inline-flex items-center rounded px-2 py-0.5 font-mono text-[10px] font-medium border ${variants[variant]}`}
    >
      {label}
    </span>
  );
}
