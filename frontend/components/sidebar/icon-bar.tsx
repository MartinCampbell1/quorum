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
    <div className="flex h-full w-[66px] flex-col items-center gap-3 border-r border-[#e2e8f0]/75 bg-white px-2 py-4 text-[#09090b] dark:border-slate-800 dark:bg-slate-950/80 dark:text-slate-100">
      <div className="flex h-10 w-10 items-center justify-center rounded-2xl text-sm font-semibold tracking-tight text-[#09090b] dark:text-white">
        A
      </div>
      <span className="text-[10px] font-semibold uppercase tracking-[0.24em] text-[#445d99] dark:text-slate-400">
        AO
      </span>
      <div className="mb-1 h-px w-8 bg-[#e2e8f0] dark:bg-slate-800" />
      {navItems.map(({ id, icon: Icon, label }) => (
        <Button
          key={id}
          variant={activeView === id ? "secondary" : "ghost"}
          size="icon"
          className={cn(
            "h-auto w-full flex-col gap-1.5 rounded-2xl border px-2 py-3 transition-all duration-200",
            activeView === id
              ? "border-[#09090b] bg-[#09090b] text-white"
              : "border-transparent text-[#445d99] hover:bg-[#f2f3ff] hover:text-[#09090b] dark:text-slate-400 dark:hover:bg-slate-900/80 dark:hover:text-slate-100"
          )}
          onClick={() => onViewChange(id)}
          aria-label={label}
        >
          <Icon className="h-4 w-4" />
          <span className="text-[10px] font-medium leading-none">{label}</span>
        </Button>
      ))}
      <div className="mt-auto w-full rounded-2xl border border-[#e2e8f0] bg-[#faf8ff] p-1.5 dark:border-slate-800 dark:bg-slate-900/70">
        <Button
          variant="ghost"
          size="icon"
          className="relative h-auto w-full flex-col gap-1.5 rounded-xl px-2 py-2.5 text-[#445d99] hover:bg-[#f2f3ff] hover:text-[#09090b] dark:text-slate-300 dark:hover:bg-slate-800/80 dark:hover:text-white"
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
