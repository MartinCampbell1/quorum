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
    <div
      className="flex h-full w-[56px] flex-col items-center py-4"
      style={{ background: "#0a0a0a", borderRight: "1px solid #1a1a1a" }}
    >
      {/* Logo */}
      <div className="mb-8 relative">
        <div
          className="flex h-9 w-9 items-center justify-center rounded-lg font-mono text-[14px] font-bold"
          style={{
            background: "linear-gradient(135deg, #cfa872, #b8935f)",
            color: "#0c0c0c",
            boxShadow: "0 2px 12px rgba(207,168,114,0.2)",
          }}
        >
          Q
        </div>
      </div>

      {/* Nav */}
      <nav className="flex flex-col gap-1">
        {navItems.map(({ id, icon: Icon, label }) => (
          <button
            key={id}
            onClick={() => onViewChange(id)}
            aria-label={label}
            className="relative flex h-10 w-10 items-center justify-center rounded-lg transition-all duration-200 cursor-pointer"
            style={{
              color: activeView === id ? "#cfa872" : "#555",
              background: activeView === id ? "rgba(207,168,114,0.08)" : "transparent",
            }}
          >
            <Icon size={17} strokeWidth={1.5} />
            {activeView === id && (
              <div
                className="absolute left-0 top-1/2 -translate-y-1/2 w-[2px] h-4 rounded-r"
                style={{ background: "#cfa872" }}
              />
            )}
          </button>
        ))}
      </nav>
      <div className="mt-auto">
        <ThemeToggle />
      </div>
    </div>
  );
}
