"use client";

import { Badge } from "@/components/ui/badge";
import { formatScenarioLabel, MODE_LABELS } from "@/lib/constants";
import { useLocale } from "@/lib/locale";

import type { Session } from "@/lib/types";

interface ChatHeaderProps {
  session: Session;
  onOpenHome?: () => void;
  onOpenSessions?: () => void;
}

export function ChatHeader({ session, onOpenHome, onOpenSessions }: ChatHeaderProps) {
  const { copy } = useLocale();
  const title = session.task.length > 56 ? `${session.task.slice(0, 56)}…` : session.task;
  const statusClasses =
    session.status === "failed"
      ? "border-amber-200 bg-amber-50 text-amber-800 dark:border-amber-900/70 dark:bg-amber-950/40 dark:text-amber-200"
      : session.status === "paused"
        ? "border-sky-200 bg-sky-50 text-sky-800 dark:border-sky-900/70 dark:bg-sky-950/40 dark:text-sky-200"
        : session.status === "cancelled"
          ? "border-slate-200 bg-slate-100 text-slate-700 dark:border-slate-800 dark:bg-slate-900 dark:text-slate-300"
          : session.status === "running"
            ? "border-emerald-200 bg-emerald-50 text-emerald-800 dark:border-emerald-900/70 dark:bg-emerald-950/40 dark:text-emerald-200"
            : "border-[#d6dbe6] bg-white text-[#6b7280] dark:border-slate-800 dark:bg-slate-900 dark:text-slate-400";
  void onOpenHome;
  void onOpenSessions;

  return (
    <div className="border-b border-[#e6e8ee] px-6 py-5 dark:border-slate-800/80">
      <div>
        <div className="text-[24px] font-medium tracking-[-0.04em] text-[#111111] dark:text-slate-100">
          {title}
        </div>
        <div className="mt-2 flex flex-wrap items-center gap-2 text-[11px] uppercase tracking-[0.14em] text-[#6b7280] dark:text-slate-500">
          <Badge variant="outline" className="rounded-full border-[#d6dbe6] bg-white px-2.5 py-1 text-[10px] font-medium uppercase tracking-[0.14em] text-[#6b7280] dark:border-slate-800 dark:bg-slate-900 dark:text-slate-400">
            {copy.monitor.headerTitle}
          </Badge>
          <Badge variant="outline" className="rounded-full border-[#d6dbe6] bg-white px-2.5 py-1 text-[10px] font-medium uppercase tracking-[0.14em] text-[#6b7280] dark:border-slate-800 dark:bg-slate-900 dark:text-slate-400">
            {copy.monitor.mode}: {MODE_LABELS[session.mode] ?? session.mode}
          </Badge>
          <Badge variant="outline" className={`rounded-full px-2.5 py-1 text-[10px] font-medium uppercase tracking-[0.14em] ${statusClasses}`}>
            {copy.statuses[session.status]}
          </Badge>
          {session.active_scenario ? (
            <Badge variant="outline" className="rounded-full border-[#d6dbe6] bg-white px-2.5 py-1 text-[10px] font-medium uppercase tracking-[0.14em] text-[#6b7280] dark:border-slate-800 dark:bg-slate-900 dark:text-slate-400">
              {copy.monitor.scenario}: {formatScenarioLabel(session.active_scenario)}
            </Badge>
          ) : null}
          {session.forked_from ? (
            <Badge variant="outline" className="rounded-full border-[#d6dbe6] bg-white px-2.5 py-1 text-[10px] font-medium uppercase tracking-[0.14em] text-[#6b7280] dark:border-slate-800 dark:bg-slate-900 dark:text-slate-400">
              {copy.monitor.branchOf}: {session.forked_from}
            </Badge>
          ) : null}
          {session.parallel_parent_id ? (
            <Badge variant="outline" className="rounded-full border-[#d6dbe6] bg-white px-2.5 py-1 text-[10px] font-medium uppercase tracking-[0.14em] text-[#6b7280] dark:border-slate-800 dark:bg-slate-900 dark:text-slate-400">
              {copy.monitor.parentSession}: {session.parallel_parent_id}
            </Badge>
          ) : null}
          {session.parallel_stage ? (
            <Badge variant="outline" className="rounded-full border-[#d6dbe6] bg-white px-2.5 py-1 text-[10px] font-medium uppercase tracking-[0.14em] text-[#6b7280] dark:border-slate-800 dark:bg-slate-900 dark:text-slate-400">
              {session.parallel_stage}{session.parallel_slot_key ? ` · ${session.parallel_slot_key}` : ""}
            </Badge>
          ) : null}
        </div>
      </div>
    </div>
  );
}
