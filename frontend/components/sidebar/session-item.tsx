"use client";

import { Loader2, RefreshCcw, Trash2 } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { useLocale } from "@/lib/locale";
import { cn } from "@/lib/utils";
import type { SessionSummary } from "@/lib/types";

interface SessionItemProps {
  session: SessionSummary;
  isActive: boolean;
  onClick: () => void;
  onDelete?: () => void;
  isDeleting?: boolean;
  canDelete?: boolean;
}

function timeAgo(timestamp: number, localeCopy: ReturnType<typeof useLocale>["copy"]): string {
  const diff = Math.floor(Date.now() / 1000 - timestamp);
  if (diff < 60) return localeCopy.shell.time.justNow;
  if (diff < 3600) return `${Math.max(1, Math.floor(diff / 60))} ${localeCopy.shell.time.minutes}`;
  if (diff < 86400) return `${Math.floor(diff / 3600)} ${localeCopy.shell.time.hours}`;
  return `${Math.floor(diff / 86400)} ${localeCopy.shell.time.days}`;
}

export function SessionItem({
  session,
  isActive,
  onClick,
  onDelete,
  isDeleting = false,
  canDelete = false,
}: SessionItemProps) {
  const { copy } = useLocale();
  return (
    <div
      className={cn(
        "mb-3 flex w-full items-start gap-2 rounded-[16px] border bg-white px-3 py-3 text-left transition-all dark:bg-slate-950/60",
        isActive
          ? "border-[#09090b] shadow-none dark:border-slate-400"
          : "border-[#e2e6ef] hover:border-[#cfd5e2] dark:border-slate-800 dark:hover:border-slate-700"
      )}
    >
      <button type="button" onClick={onClick} className="flex min-w-0 flex-1 items-start gap-3 text-left">
        <RefreshCcw className="mt-0.5 h-4 w-4 shrink-0 text-[#475569] dark:text-slate-400" />
        <div className="min-w-0 flex-1">
          <div className="truncate text-[13px] font-medium text-[#09090b] dark:text-slate-100">
            {session.task}
          </div>
          <div className="mt-3 flex items-center gap-2">
            <span className="text-[11px] text-[#7b8190] dark:text-slate-500">{timeAgo(session.created_at, copy)}</span>
            <Badge
              variant="outline"
              className="rounded-full border-[#e2e6ef] bg-white px-2 py-0 text-[10px] font-normal text-[#4b5563] dark:border-slate-800 dark:bg-slate-900 dark:text-slate-300"
            >
              {copy.statuses[session.status as keyof typeof copy.statuses] ?? session.status}
            </Badge>
            {session.forked_from ? (
              <Badge
                variant="outline"
                className="rounded-full border-[#e2e6ef] bg-white px-2 py-0 text-[10px] font-normal text-[#4b5563] dark:border-slate-800 dark:bg-slate-900 dark:text-slate-300"
              >
                {copy.shell.branch}
              </Badge>
            ) : null}
          </div>
        </div>
      </button>
      {canDelete ? (
        <button
          type="button"
          aria-label={copy.shell.deleteSession}
          title={copy.shell.deleteSession}
          onClick={onDelete}
          disabled={isDeleting}
          className="mt-0.5 flex h-8 w-8 shrink-0 items-center justify-center rounded-full border border-[#e2e6ef] text-[#7b8190] transition-colors hover:border-[#cbd5e1] hover:bg-[#f8fafc] hover:text-[#111111] disabled:cursor-not-allowed dark:border-slate-800 dark:text-slate-400 dark:hover:border-slate-700 dark:hover:bg-slate-900"
        >
          {isDeleting ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Trash2 className="h-3.5 w-3.5" />}
        </button>
      ) : null}
    </div>
  );
}
