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
    <div className="flex h-full w-16 flex-col items-center border-r border-white/[0.06] bg-[#0f0f0f] py-4">
      <div className="mb-6 flex h-9 w-9 items-center justify-center rounded-xl bg-white/10">
        <span className="font-mono text-sm font-semibold text-[#f5f5f7]">Q</span>
      </div>
      <nav className="flex flex-col gap-2">
        {navItems.map(({ id, icon: Icon, label }) => (
          <button
            key={id}
            onClick={() => onViewChange(id)}
            aria-label={label}
            className={`flex h-10 w-10 items-center justify-center rounded-xl transition-all duration-200 cursor-pointer ${
              activeView === id
                ? "text-[#f5f5f7]"
                : "text-white/25 hover:text-white/55"
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
