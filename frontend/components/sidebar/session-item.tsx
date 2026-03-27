"use client";

import { RefreshCcw } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { useLocale } from "@/lib/locale";
import { cn } from "@/lib/utils";
import type { SessionSummary } from "@/lib/types";

interface SessionItemProps {
  session: SessionSummary;
  isActive: boolean;
  onClick: () => void;
}

function timeAgo(timestamp: number, localeCopy: ReturnType<typeof useLocale>["copy"]): string {
  const diff = Math.floor(Date.now() / 1000 - timestamp);
  if (diff < 60) return localeCopy.shell.time.justNow;
  if (diff < 3600) return `${Math.max(1, Math.floor(diff / 60))} ${localeCopy.shell.time.minutes}`;
  if (diff < 86400) return `${Math.floor(diff / 3600)} ${localeCopy.shell.time.hours}`;
  return `${Math.floor(diff / 86400)} ${localeCopy.shell.time.days}`;
}

export function SessionItem({ session, isActive, onClick }: SessionItemProps) {
  const { copy } = useLocale();
  return (
    <button
      type="button"
      onClick={onClick}
      className={cn(
        "mb-3 w-full rounded-[16px] border bg-white px-4 py-3 text-left transition-all",
        isActive
          ? "border-[#09090b] shadow-none"
          : "border-[#e2e6ef] hover:border-[#cfd5e2]"
      )}
    >
      <div className="flex items-start gap-3">
        <RefreshCcw className="mt-0.5 h-4 w-4 shrink-0 text-[#475569]" />
        <div className="min-w-0 flex-1">
          <div className="truncate text-[13px] font-medium text-[#09090b]">
            {session.task}
          </div>
          <div className="mt-3 flex items-center gap-2">
            <span className="text-[11px] text-[#7b8190]">{timeAgo(session.created_at, copy)}</span>
            <Badge
              variant="outline"
              className="rounded-full border-[#e2e6ef] bg-white px-2 py-0 text-[10px] font-normal text-[#4b5563]"
            >
              {copy.statuses[session.status as keyof typeof copy.statuses] ?? session.status}
            </Badge>
            {session.forked_from ? (
              <Badge
                variant="outline"
                className="rounded-full border-[#e2e6ef] bg-white px-2 py-0 text-[10px] font-normal text-[#4b5563]"
              >
                {copy.shell.branch}
              </Badge>
            ) : null}
          </div>
        </div>
      </div>
    </button>
  );
}
