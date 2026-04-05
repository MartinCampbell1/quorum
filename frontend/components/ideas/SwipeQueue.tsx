"use client";

import { useEffect, useState } from "react";
import { BrainCircuit, Loader2, RefreshCcw, Sparkles, Telescope } from "lucide-react";

import { DossierDrawer } from "@/components/ideas/DossierDrawer";
import { IdeaCard } from "@/components/ideas/IdeaCard";
import { MaybeQueue } from "@/components/ideas/MaybeQueue";
import { Button } from "@/components/ui/button";
import {
  getDiscoveryDossier,
  getDiscoveryIdeaChanges,
  getDiscoveryMaybeQueue,
  getDiscoverySwipeQueue,
  swipeDiscoveryIdea,
} from "@/lib/api";
import { useLocale } from "@/lib/locale";
import type {
  DiscoverySwipeAction,
  IdeaChangeRecord,
  IdeaDossier,
  IdeaQueueItem,
  MaybeQueueResponse,
  SwipeQueueResponse,
} from "@/lib/types";

function percentage(value: number): string {
  return `${Math.round(value * 100)}%`;
}

export function SwipeQueue() {
  const { locale } = useLocale();
  const text =
    locale === "ru"
      ? {
          title: "Portfolio Triage",
          subtitle: "Очередь `Pass / Maybe / Yes / Now` и обучаемые founder preferences.",
          refresh: "Обновить",
          loading: "Собираю очередь…",
          empty: "Сейчас нет идей, требующих triage.",
          error: "Не удалось загрузить swipe queue.",
          active: "Активно",
          swipes: "Свайпов",
          maybeReady: "Maybe ready",
          preference: "Founder preference model",
          topDomains: "Сильные домены",
          buyerTilt: "Buyer tilt",
          aiNeed: "AI bias",
          complexity: "Complexity band",
        }
      : {
          title: "Portfolio Triage",
          subtitle: "Mission-control style Pass / Maybe / Yes / Now queue with learned founder priors.",
          refresh: "Refresh",
          loading: "Loading the swipe queue…",
          empty: "No ideas need triage right now.",
          error: "Failed to load the swipe queue.",
          active: "Active",
          swipes: "Swipes",
          maybeReady: "Maybe ready",
          preference: "Founder preference model",
          topDomains: "Strong domains",
          buyerTilt: "Buyer tilt",
          aiNeed: "AI bias",
          complexity: "Complexity band",
        };

  const [queue, setQueue] = useState<SwipeQueueResponse | null>(null);
  const [maybeQueue, setMaybeQueue] = useState<MaybeQueueResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [busyIdeaId, setBusyIdeaId] = useState<string | null>(null);
  const [busyAction, setBusyAction] = useState<DiscoverySwipeAction | null>(null);
  const [drawerItem, setDrawerItem] = useState<IdeaQueueItem | null>(null);
  const [drawerDossier, setDrawerDossier] = useState<IdeaDossier | null>(null);
  const [drawerChanges, setDrawerChanges] = useState<IdeaChangeRecord | null>(null);
  const [drawerLoading, setDrawerLoading] = useState(false);

  async function refreshQueues(showLoader: boolean = false) {
    if (showLoader) {
      setLoading(true);
    }
    setError(null);
    try {
      const [nextQueue, nextMaybeQueue] = await Promise.all([
        getDiscoverySwipeQueue(12),
        getDiscoveryMaybeQueue(8),
      ]);
      setQueue(nextQueue);
      setMaybeQueue(nextMaybeQueue);
    } catch (nextError) {
      setError(nextError instanceof Error ? nextError.message : text.error);
    } finally {
      setLoading(false);
    }
  }

  async function openDossier(item: IdeaQueueItem) {
    setDrawerItem(item);
    setDrawerLoading(true);
    try {
      const [dossier, changes] = await Promise.all([
        getDiscoveryDossier(item.idea.idea_id),
        getDiscoveryIdeaChanges(item.idea.idea_id),
      ]);
      setDrawerDossier(dossier);
      setDrawerChanges(changes);
    } catch {
      setDrawerDossier(null);
      setDrawerChanges(null);
    } finally {
      setDrawerLoading(false);
    }
  }

  async function handleSwipe(item: IdeaQueueItem, action: DiscoverySwipeAction) {
    setBusyIdeaId(item.idea.idea_id);
    setBusyAction(action);
    try {
      await swipeDiscoveryIdea(item.idea.idea_id, {
        action,
        actor: "founder",
        rationale: `FounderOS swipe action: ${action}.`,
        revisit_after_hours: action === "maybe" ? 72 : undefined,
      });
      setDrawerItem(null);
      setDrawerDossier(null);
      setDrawerChanges(null);
      await refreshQueues(false);
    } catch (nextError) {
      setError(nextError instanceof Error ? nextError.message : text.error);
    } finally {
      setBusyIdeaId(null);
      setBusyAction(null);
    }
  }

  useEffect(() => {
    void refreshQueues(true);
  }, []);

  const topDomains = Object.entries(queue?.preference_profile.domain_weights ?? {})
    .sort((left, right) => right[1] - left[1])
    .slice(0, 4);
  const buyerTilt =
    (queue?.preference_profile.buyer_preferences.b2b ?? 0) >=
    (queue?.preference_profile.buyer_preferences.b2c ?? 0)
      ? "B2B"
      : "B2C";

  return (
    <section className="rounded-[28px] border border-[#d6dbe6] bg-white/90 p-5 shadow-[0_16px_38px_-28px_rgba(17,48,105,0.22)] dark:border-slate-800 dark:bg-slate-950/60 dark:shadow-none">
      <div className="flex flex-col gap-4 xl:flex-row xl:items-start xl:justify-between">
        <div>
          <div className="flex items-center gap-2 text-[20px] font-semibold tracking-[-0.04em] text-[#111111] dark:text-slate-100">
            <Telescope className="h-5 w-5" />
            {text.title}
          </div>
          <div className="mt-2 max-w-3xl text-[13px] leading-6 text-[#6b7280] dark:text-slate-400">
            {text.subtitle}
          </div>
        </div>
        <div className="flex items-center gap-2">
          {queue ? (
            <>
              <div className="rounded-full border border-[#d6dbe6] bg-[#fafbff] px-3 py-1 text-[11px] text-[#4b5563] dark:border-slate-800 dark:bg-slate-900 dark:text-slate-300">
                {text.active}: {queue.summary.active_count}
              </div>
              <div className="rounded-full border border-[#d6dbe6] bg-[#fafbff] px-3 py-1 text-[11px] text-[#4b5563] dark:border-slate-800 dark:bg-slate-900 dark:text-slate-300">
                {text.swipes}: {queue.preference_profile.swipe_count}
              </div>
              <div className="rounded-full border border-[#d6dbe6] bg-[#fafbff] px-3 py-1 text-[11px] text-[#4b5563] dark:border-slate-800 dark:bg-slate-900 dark:text-slate-300">
                {text.maybeReady}: {queue.summary.maybe_ready_count}
              </div>
            </>
          ) : null}
          <Button type="button" variant="outline" size="sm" onClick={() => void refreshQueues(true)} className="h-8 rounded-full text-[11px]">
            {loading ? <Loader2 className="mr-1 h-3.5 w-3.5 animate-spin" /> : <RefreshCcw className="mr-1 h-3.5 w-3.5" />}
            {text.refresh}
          </Button>
        </div>
      </div>

      <div className="mt-5 grid gap-4 xl:grid-cols-[minmax(0,1.35fr)_minmax(340px,0.95fr)]">
        <div className="space-y-4">
          <div className="rounded-[22px] border border-[#d6dbe6] bg-[#fbfcff] p-4 dark:border-slate-800 dark:bg-slate-900/60">
            <div className="flex items-center gap-2 text-[13px] font-semibold tracking-[-0.02em] text-[#111111] dark:text-slate-100">
              <BrainCircuit className="h-4 w-4" />
              {text.preference}
            </div>
            {queue ? (
              <div className="mt-4 grid gap-3 md:grid-cols-4">
                <div className="rounded-[16px] bg-white px-3 py-3 dark:bg-slate-950/70">
                  <div className="text-[10px] uppercase tracking-[0.14em] text-[#6b7280] dark:text-slate-500">{text.topDomains}</div>
                  <div className="mt-2 text-[12px] leading-5 text-[#111111] dark:text-slate-100">
                    {topDomains.length ? topDomains.map(([label]) => label).join(", ") : "Neutral"}
                  </div>
                </div>
                <div className="rounded-[16px] bg-white px-3 py-3 dark:bg-slate-950/70">
                  <div className="text-[10px] uppercase tracking-[0.14em] text-[#6b7280] dark:text-slate-500">{text.buyerTilt}</div>
                  <div className="mt-2 text-[18px] font-semibold tracking-[-0.03em] text-[#111111] dark:text-slate-100">{buyerTilt}</div>
                </div>
                <div className="rounded-[16px] bg-white px-3 py-3 dark:bg-slate-950/70">
                  <div className="text-[10px] uppercase tracking-[0.14em] text-[#6b7280] dark:text-slate-500">{text.aiNeed}</div>
                  <div className="mt-2 text-[18px] font-semibold tracking-[-0.03em] text-[#111111] dark:text-slate-100">
                    {percentage(queue.preference_profile.ai_necessity_preference)}
                  </div>
                </div>
                <div className="rounded-[16px] bg-white px-3 py-3 dark:bg-slate-950/70">
                  <div className="text-[10px] uppercase tracking-[0.14em] text-[#6b7280] dark:text-slate-500">{text.complexity}</div>
                  <div className="mt-2 text-[18px] font-semibold tracking-[-0.03em] text-[#111111] dark:text-slate-100">
                    {percentage(queue.preference_profile.preferred_complexity)}
                  </div>
                </div>
              </div>
            ) : null}
          </div>

          <div className="grid gap-4 lg:grid-cols-2">
            {loading ? (
              <div className="col-span-full flex items-center gap-3 rounded-[20px] border border-[#d6dbe6] bg-[#fbfcff] px-4 py-5 text-[13px] text-[#4b5563] dark:border-slate-800 dark:bg-slate-900/60 dark:text-slate-300">
                <Loader2 className="h-4 w-4 animate-spin" />
                {text.loading}
              </div>
            ) : error ? (
              <div className="col-span-full rounded-[20px] border border-rose-200 bg-rose-50 px-4 py-5 text-[13px] text-rose-700 dark:border-rose-900/60 dark:bg-rose-950/40 dark:text-rose-300">
                {error}
              </div>
            ) : queue && queue.items.length > 0 ? (
              queue.items.map((item) => (
                <IdeaCard
                  key={item.queue_id}
                  item={item}
                  busyAction={busyIdeaId === item.idea.idea_id ? busyAction : null}
                  onOpenDossier={() => void openDossier(item)}
                  onSwipe={(action) => void handleSwipe(item, action)}
                />
              ))
            ) : (
              <div className="col-span-full rounded-[20px] border border-dashed border-[#d6dbe6] bg-[#fbfcff] px-4 py-6 text-[13px] leading-6 text-[#6b7280] dark:border-slate-800 dark:bg-slate-900/60 dark:text-slate-400">
                {text.empty}
              </div>
            )}
          </div>
        </div>

        <MaybeQueue
          items={maybeQueue?.items ?? []}
          summary={maybeQueue?.summary ?? { total_count: 0, ready_count: 0, waiting_count: 0 }}
          busyIdeaId={busyIdeaId}
          busyAction={busyAction}
          onOpenDossier={(item) => void openDossier(item)}
          onSwipe={(item, action) => void handleSwipe(item, action)}
        />
      </div>

      <DossierDrawer
        open={Boolean(drawerItem)}
        item={drawerItem}
        dossier={drawerDossier}
        changes={drawerChanges}
        loading={drawerLoading}
        onClose={() => {
          setDrawerItem(null);
          setDrawerDossier(null);
          setDrawerChanges(null);
        }}
      />
    </section>
  );
}
