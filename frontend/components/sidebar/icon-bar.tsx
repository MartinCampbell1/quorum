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
  { id: "chat", icon: MessageSquare, label: "Chat" },
  { id: "history", icon: Clock, label: "History" },
  { id: "settings", icon: Sliders, label: "Settings" },
];

export function IconBar({ activeView, onViewChange }: IconBarProps) {
  const { theme, setTheme } = useTheme();

  return (
    <div className="flex h-full w-[56px] flex-col items-center border-r bg-background py-3 gap-1">
      <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-foreground text-background font-semibold text-xs tracking-tight mb-3">
        Q
      </div>
      <div className="h-px w-6 bg-border mb-2" />
      {navItems.map(({ id, icon: Icon, label }) => (
        <Button
          key={id}
          variant={activeView === id ? "secondary" : "ghost"}
          size="icon"
          className={cn(
            "h-8 w-8 transition-colors",
            activeView === id && "bg-secondary text-foreground"
          )}
          onClick={() => onViewChange(id)}
          aria-label={label}
        >
          <Icon className="h-4 w-4" />
        </Button>
      ))}
      <div className="mt-auto">
        <Button
          variant="ghost"
          size="icon"
          className="h-8 w-8"
          onClick={() => setTheme(theme === "dark" ? "light" : "dark")}
          aria-label="Toggle theme"
        >
          <Sun className="h-4 w-4 rotate-0 scale-100 transition-all dark:-rotate-90 dark:scale-0" />
          <Moon className="absolute h-4 w-4 rotate-90 scale-0 transition-all dark:rotate-0 dark:scale-100" />
        </Button>
      </div>
    </div>
  );
}
