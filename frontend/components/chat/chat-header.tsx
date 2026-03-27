"use client";

import { Badge } from "@/components/ui/badge";
import { MODE_LABELS } from "@/lib/constants";
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
  void onOpenHome;
  void onOpenSessions;

  return (
    <div className="border-b border-[#e6e8ee] px-6 py-5">
      <div>
        <div className="text-[24px] font-medium tracking-[-0.04em] text-[#111111]">
          {title}
        </div>
        <div className="mt-2 flex flex-wrap items-center gap-2 text-[11px] uppercase tracking-[0.14em] text-[#6b7280]">
          <Badge variant="outline" className="rounded-full border-[#d6dbe6] bg-white px-2.5 py-1 text-[10px] font-medium uppercase tracking-[0.14em] text-[#6b7280]">
            {copy.monitor.headerTitle}
          </Badge>
          <Badge variant="outline" className="rounded-full border-[#d6dbe6] bg-white px-2.5 py-1 text-[10px] font-medium uppercase tracking-[0.14em] text-[#6b7280]">
            {copy.monitor.mode}: {MODE_LABELS[session.mode] ?? session.mode}
          </Badge>
          {session.active_scenario ? (
            <Badge variant="outline" className="rounded-full border-[#d6dbe6] bg-white px-2.5 py-1 text-[10px] font-medium uppercase tracking-[0.14em] text-[#6b7280]">
              {copy.monitor.scenario}: {session.active_scenario}
            </Badge>
          ) : null}
          {session.forked_from ? (
            <Badge variant="outline" className="rounded-full border-[#d6dbe6] bg-white px-2.5 py-1 text-[10px] font-medium uppercase tracking-[0.14em] text-[#6b7280]">
              {copy.monitor.branchOf}: {session.forked_from}
            </Badge>
          ) : null}
        </div>
      </div>
    </div>
  );
}
