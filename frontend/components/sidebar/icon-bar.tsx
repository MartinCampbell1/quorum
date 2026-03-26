"use client";

import { Clock3, LogOut, Search, Settings2, SlidersHorizontal, SunMedium } from "lucide-react";

import { cn } from "@/lib/utils";

type View = "chat" | "history" | "settings";

interface IconBarProps {
  activeView: View;
  onViewChange: (view: View) => void;
}

const PRIMARY_ITEMS: Array<{ id: View; icon: typeof Search; label: string }> = [
  { id: "chat", icon: Search, label: "Сессии" },
  { id: "history", icon: Clock3, label: "История" },
  { id: "settings", icon: SlidersHorizontal, label: "Настройки" },
];

export function IconBar({ activeView, onViewChange }: IconBarProps) {
  return (
    <aside className="flex h-full w-[68px] flex-col items-center border-r border-[#e6e8ee] bg-white py-4">
      <div className="flex flex-col items-center gap-4 pt-1">
        {PRIMARY_ITEMS.map(({ id, icon: Icon, label }) => (
          <button
            key={id}
            type="button"
            aria-label={label}
            onClick={() => onViewChange(id)}
            className={cn(
              "flex h-12 w-12 items-center justify-center rounded-[14px] text-[#09090b] transition-colors",
              activeView === id
                ? "bg-[#f0f1f5] text-[#09090b]"
                : "bg-transparent text-[#09090b] hover:bg-[#f7f7fa]"
            )}
          >
            <Icon className="h-[25px] w-[25px] stroke-[1.8]" />
          </button>
        ))}
      </div>

      <div className="mt-auto flex flex-col items-center gap-4 pb-1">
        <button
          type="button"
          aria-label="Theme"
          className="flex h-12 w-12 items-center justify-center rounded-[14px] text-[#09090b] transition-colors hover:bg-[#f7f7fa]"
        >
          <SunMedium className="h-[23px] w-[23px] stroke-[1.8]" />
        </button>
        <button
          type="button"
          aria-label="Settings"
          className="flex h-12 w-12 items-center justify-center rounded-[14px] text-[#09090b] transition-colors hover:bg-[#f7f7fa]"
        >
          <Settings2 className="h-[23px] w-[23px] stroke-[1.8]" />
        </button>
        <button
          type="button"
          aria-label="Exit"
          className="flex h-12 w-12 items-center justify-center rounded-[14px] text-[#09090b] transition-colors hover:bg-[#f7f7fa]"
        >
          <LogOut className="h-[23px] w-[23px] stroke-[1.8]" />
        </button>
      </div>
    </aside>
  );
}
