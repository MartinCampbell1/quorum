import { type ButtonHTMLAttributes } from "react";

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: "primary" | "cta" | "ghost";
  size?: "sm" | "md";
}

const base =
  "inline-flex items-center justify-center rounded-lg font-medium transition-colors duration-150 focus:outline-none focus:ring-2 focus:ring-accent focus:ring-offset-2 focus:ring-offset-bg-primary disabled:opacity-40 disabled:cursor-not-allowed cursor-pointer";

const variantStyles: Record<string, string> = {
  primary: "bg-accent hover:bg-accent-hover text-white",
  cta: "bg-cta hover:brightness-110 text-white",
  ghost: "bg-transparent hover:bg-bg-card text-text-secondary",
};

const sizeStyles: Record<string, string> = {
  sm: "px-3 py-1.5 text-xs",
  md: "px-4 py-2 text-sm",
};

export function Button({
  variant = "primary",
  size = "md",
  className = "",
  ...props
}: ButtonProps) {
  return (
    <button
      className={`${base} ${variantStyles[variant]} ${sizeStyles[size]} ${className}`}
      {...props}
    />
  );
}
