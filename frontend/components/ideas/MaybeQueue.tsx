"use client";

import { Clock3, Inbox } from "lucide-react";

import { IdeaCard } from "@/components/ideas/IdeaCard";
import { useLocale } from "@/lib/locale";
import type { DiscoverySwipeAction, IdeaQueueItem, MaybeQueueSummary } from "@/lib/types";

interface MaybeQueueProps {
  items: IdeaQueueItem[];
  summary: MaybeQueueSummary;
  busyIdeaId?: string | null;
  busyAction?: DiscoverySwipeAction | null;
  onOpenDossier: (item: IdeaQueueItem) => void;
  onSwipe: (item: IdeaQueueItem, action: DiscoverySwipeAction) => void;
}

function dueLabel(dueAt: string | null | undefined, locale: "ru" | "en"): string {
  if (!dueAt) {
    return locale === "ru" ? "без дедлайна" : "no revisit window";
  }
  const deltaMs = new Date(dueAt).getTime() - Date.now();
  const hours = Math.round(deltaMs / 3_600_000);
  if (hours <= 0) {
    return locale === "ru" ? "можно пересмотреть сейчас" : "ready to recheck now";
  }
  if (hours < 24) {
    return locale === "ru" ? `через ${hours} ч` : `in ${hours}h`;
  }
  const days = Math.round(hours / 24);
  return locale === "ru" ? `через ${days} д` : `in ${days}d`;
}

export function MaybeQueue({
  items,
  summary,
  busyIdeaId,
  busyAction,
  onOpenDossier,
  onSwipe,
}: MaybeQueueProps) {
  const { locale } = useLocale();
  const text =
    locale === "ru"
      ? {
          title: "Maybe Queue",
          subtitle: "Идеи на отложенном пересмотре",
          ready: "Готовы",
          waiting: "Ждут",
          empty: "Сейчас нет идей в maybe-очереди.",
          due: "Пересмотр",
        }
      : {
          title: "Maybe Queue",
          subtitle: "Ideas parked for timed or evidence-based revisit",
          ready: "Ready",
          waiting: "Waiting",
          empty: "No ideas are parked in the maybe queue right now.",
          due: "Recheck",
        };

  return (
    <div className="rounded-[24px] border border-[#d6dbe6] bg-white/90 p-4 shadow-[0_12px_32px_-22px_rgba(17,48,105,0.18)] dark:border-slate-800 dark:bg-slate-950/60 dark:shadow-none">
      <div className="flex items-start justify-between gap-4">
        <div>
          <div className="flex items-center gap-2 text-[16px] font-semibold tracking-[-0.03em] text-[#111111] dark:text-slate-100">
            <Inbox className="h-4.5 w-4.5" />
            {text.title}
          </div>
          <div className="mt-1 text-[12px] leading-6 text-[#6b7280] dark:text-slate-400">{text.subtitle}</div>
        </div>
        <div className="flex gap-2">
          <div className="rounded-full border border-[#d6dbe6] bg-[#fafbff] px-3 py-1 text-[11px] text-[#4b5563] dark:border-slate-800 dark:bg-slate-900 dark:text-slate-300">
            {text.ready}: {summary.ready_count}
          </div>
          <div className="rounded-full border border-[#d6dbe6] bg-[#fafbff] px-3 py-1 text-[11px] text-[#4b5563] dark:border-slate-800 dark:bg-slate-900 dark:text-slate-300">
            {text.waiting}: {summary.waiting_count}
          </div>
        </div>
      </div>

      <div className="mt-4 space-y-3">
        {items.length === 0 ? (
          <div className="rounded-[18px] border border-dashed border-[#d6dbe6] bg-[#fbfcff] px-4 py-6 text-[13px] leading-6 text-[#6b7280] dark:border-slate-800 dark:bg-slate-900/60 dark:text-slate-400">
            {text.empty}
          </div>
        ) : (
          items.map((item) => (
            <div key={item.queue_id} className="space-y-2">
              <div className="flex items-center gap-2 text-[11px] uppercase tracking-[0.14em] text-[#6b7280] dark:text-slate-500">
                <Clock3 className="h-3.5 w-3.5" />
                {text.due}: {dueLabel(item.maybe_entry?.due_at, locale)}
              </div>
              <IdeaCard
                item={item}
                compact
                busyAction={busyIdeaId === item.idea.idea_id ? busyAction : null}
                onOpenDossier={() => onOpenDossier(item)}
                onSwipe={(action) => onSwipe(item, action)}
              />
            </div>
          ))
        )}
      </div>
    </div>
  );
}
