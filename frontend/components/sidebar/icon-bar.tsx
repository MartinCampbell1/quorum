"use client";

import { MessageSquare, Clock, Sliders, Sun, Moon } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Separator } from "@/components/ui/separator";
import { useTheme } from "next-themes";

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
    <div className="flex h-full w-[60px] flex-col items-center border-r bg-muted/30 py-4 gap-1.5">
      <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-primary text-primary-foreground font-mono text-sm font-bold mb-4">
        Q
      </div>
      <Separator className="w-8 mb-2" />
      {navItems.map(({ id, icon: Icon, label }) => (
        <Button
          key={id}
          variant={activeView === id ? "secondary" : "ghost"}
          size="icon"
          className="h-9 w-9"
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
          className="h-9 w-9"
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
