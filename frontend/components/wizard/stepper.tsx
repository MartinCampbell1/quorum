import { Check } from "lucide-react";
import { cn } from "@/lib/utils";

const STEPS = ["Режим", "Настройка", "Запуск"];

interface StepperProps {
  currentStep: number;
}

export function Stepper({ currentStep }: StepperProps) {
  return (
    <nav className="flex items-center mb-10">
      {STEPS.map((label, i) => (
        <div key={i} className="flex items-center">
          <div className="flex items-center gap-2">
            <div className={cn(
              "flex h-6 w-6 items-center justify-center rounded-full text-[11px] font-medium transition-all",
              i < currentStep
                ? "bg-foreground text-background"
                : i === currentStep
                  ? "bg-foreground text-background shadow-[0_0_0_3px_rgba(0,0,0,0.06)]"
                  : "bg-muted text-muted-foreground/50"
            )}>
              {i < currentStep ? (
                <Check className="h-3 w-3" strokeWidth={2.5} />
              ) : (
                i + 1
              )}
            </div>
            <span className={cn(
              "text-[12px] select-none hidden sm:inline",
              i === currentStep ? "text-foreground font-medium" : "text-muted-foreground/40"
            )}>
              {label}
            </span>
          </div>
          {i < STEPS.length - 1 && (
            <div className={cn(
              "w-12 h-px mx-3 transition-colors",
              i < currentStep ? "bg-foreground/30" : "bg-border"
            )} />
          )}
        </div>
      ))}
    </nav>
  );
}
