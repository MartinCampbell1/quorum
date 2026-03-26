"use client";

import { MessageSquare, Clock, Sliders, Sun, Moon } from "lucide-react";
import { Button } from "@/components/ui/button";
import { useTheme } from "next-themes";
import { cn } from "@/lib/utils";

type View = "chat" | "history" | "settings";

interface IconBarProps {
  activeView: View;
  onViewChange: (view: View) => void;
}

const navItems: { id: View; icon: typeof MessageSquare; label: string }[] = [
  { id: "chat", icon: MessageSquare, label: "Сессии" },
  { id: "history", icon: Clock, label: "История" },
  { id: "settings", icon: Sliders, label: "Настройки" },
];

export function IconBar({ activeView, onViewChange }: IconBarProps) {
  const { theme, setTheme } = useTheme();

  return (
    <div className="flex h-full w-[76px] flex-col items-center border-r bg-background/95 py-3 gap-1.5">
      <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-foreground text-background font-semibold text-xs tracking-tight mb-1.5 shadow-sm">
        Q
      </div>
      <span className="text-[10px] font-semibold uppercase tracking-[0.18em] text-muted-foreground/60">
        Quorum
      </span>
      <div className="h-px w-8 bg-border mb-2" />
      {navItems.map(({ id, icon: Icon, label }) => (
        <Button
          key={id}
          variant={activeView === id ? "secondary" : "ghost"}
          size="icon"
          className={cn(
            "h-auto w-14 flex-col gap-1 rounded-xl px-2 py-2.5 transition-colors",
            activeView === id && "bg-secondary text-foreground shadow-sm"
          )}
          onClick={() => onViewChange(id)}
          aria-label={label}
        >
          <Icon className="h-4 w-4" />
          <span className="text-[10px] font-medium leading-none">{label}</span>
        </Button>
      ))}
      <div className="mt-auto">
        <Button
          variant="ghost"
          size="icon"
          className="h-auto w-14 flex-col gap-1 rounded-xl px-2 py-2.5"
          onClick={() => setTheme(theme === "dark" ? "light" : "dark")}
          aria-label="Toggle theme"
        >
          <Sun className="h-4 w-4 rotate-0 scale-100 transition-all dark:-rotate-90 dark:scale-0" />
          <Moon className="absolute h-4 w-4 rotate-90 scale-0 transition-all dark:rotate-0 dark:scale-100" />
          <span className="text-[10px] font-medium leading-none">Тема</span>
        </Button>
      </div>
    </div>
  );
}
