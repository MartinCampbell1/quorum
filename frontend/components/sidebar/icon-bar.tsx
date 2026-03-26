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
    <div className="flex h-full w-16 flex-col items-center border-r border-white/[0.05] bg-black py-4">
      <div className="mb-6 flex h-9 w-9 items-center justify-center rounded-xl bg-accent shadow-[0_0_12px_rgba(37,99,235,0.3)]">
        <span className="font-mono text-sm font-bold text-white">Q</span>
      </div>
      <nav className="flex flex-col gap-2">
        {navItems.map(({ id, icon: Icon, label }) => (
          <button
            key={id}
            onClick={() => onViewChange(id)}
            aria-label={label}
            className={`flex h-10 w-10 items-center justify-center rounded-xl transition-all duration-200 cursor-pointer ${
              activeView === id
                ? "text-accent [filter:drop-shadow(0_0_8px_rgba(37,99,235,0.4))]"
                : "text-text-muted hover:text-text-secondary"
            }`}
          >
            <Icon size={18} strokeWidth={1.5} />
          </button>
        ))}
      </nav>
      <div className="mt-auto">
        <ThemeToggle />
      </div>
    </div>
  );
}
