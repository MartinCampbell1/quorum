"use client";

import { MessageSquare, Clock, Sliders } from "lucide-react";
import { ThemeToggle } from "@/components/common/theme-toggle";

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
  return (
    <div className="flex h-full w-[52px] flex-col items-center border-r border-border bg-bg-secondary py-3">
      <div className="mb-4 flex h-8 w-8 items-center justify-center rounded-lg bg-accent">
        <span className="font-mono text-xs font-bold text-white">Q</span>
      </div>
      <nav className="flex flex-col gap-1.5">
        {navItems.map(({ id, icon: Icon, label }) => (
          <button
            key={id}
            onClick={() => onViewChange(id)}
            aria-label={label}
            className={`flex h-9 w-9 items-center justify-center rounded-lg transition-colors cursor-pointer ${
              activeView === id
                ? "bg-accent text-white"
                : "text-text-muted hover:bg-bg-card hover:text-text-secondary"
            }`}
          >
            <Icon size={16} />
          </button>
        ))}
      </nav>
      <div className="mt-auto">
        <ThemeToggle />
      </div>
    </div>
  );
}
