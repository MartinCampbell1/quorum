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
    <div className="flex h-full w-[88px] flex-col items-center gap-2 border-r border-slate-800/90 bg-slate-950 px-3 py-4 text-slate-100 shadow-[18px_0_40px_-28px_rgba(15,23,42,0.95)]">
      <div className="flex h-12 w-12 items-center justify-center rounded-2xl border border-slate-700/80 bg-[linear-gradient(180deg,rgba(15,23,42,0.96),rgba(30,41,59,0.96))] text-sm font-semibold tracking-tight text-white shadow-[0_16px_34px_-24px_rgba(148,163,184,0.8)]">
        Q
      </div>
      <span className="text-[10px] font-semibold uppercase tracking-[0.24em] text-slate-400">
        Quorum
      </span>
      <div className="mb-1 h-px w-10 bg-slate-800" />
      {navItems.map(({ id, icon: Icon, label }) => (
        <Button
          key={id}
          variant={activeView === id ? "secondary" : "ghost"}
          size="icon"
          className={cn(
            "h-auto w-full flex-col gap-1.5 rounded-2xl border px-2 py-3 transition-all duration-200",
            activeView === id
              ? "border-slate-700 bg-slate-900 text-white shadow-[0_14px_26px_-20px_rgba(255,255,255,0.35)]"
              : "border-transparent text-slate-400 hover:border-slate-800 hover:bg-slate-900/80 hover:text-slate-100"
          )}
          onClick={() => onViewChange(id)}
          aria-label={label}
        >
          <Icon className="h-4 w-4" />
          <span className="text-[10px] font-medium leading-none">{label}</span>
        </Button>
      ))}
      <div className="mt-auto w-full rounded-2xl border border-slate-800 bg-slate-900/70 p-2">
        <Button
          variant="ghost"
          size="icon"
          className="relative h-auto w-full flex-col gap-1.5 rounded-xl px-2 py-2.5 text-slate-300 hover:bg-slate-800/80 hover:text-white"
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
