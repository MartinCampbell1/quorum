"use client";

import { useEffect, useState } from "react";
import { Inbox as InboxIcon, Loader2, RefreshCcw } from "lucide-react";

import { DossierInboxCard } from "@/components/ideas/DossierInboxCard";
import { ReviewEvent } from "@/components/ideas/ReviewEvent";
import { Button } from "@/components/ui/button";
import { actOnDiscoveryInboxItem, getDiscoveryDossier, getDiscoveryInboxFeed } from "@/lib/api";
import { useLocale } from "@/lib/locale";
import type { DiscoveryInboxActionRequest, DiscoveryInboxFeed, DiscoveryInboxItem, IdeaDossier } from "@/lib/types";

export function Inbox() {
  const { locale } = useLocale();
  const text =
    locale === "ru"
      ? {
          title: "Review Inbox",
          subtitle: "Inbox-first approval queue для идей, debate verdicts, simulation outcomes и handoff-кандидатов.",
          refresh: "Обновить",
          loading: "Собираю review queue…",
          error: "Не удалось загрузить review inbox.",
          empty: "Сейчас review queue пуста.",
          open: "Открытые",
          resolved: "Resolved",
          stale: "Stale",
          actionable: "Actionable",
          noSelection: "Детали появятся после выбора review item.",
        }
      : {
          title: "Review Inbox",
          subtitle: "Inbox-first approval queue for ideas, debate verdicts, simulation outcomes, and handoff candidates.",
          refresh: "Refresh",
          loading: "Loading the review queue…",
          error: "Failed to load the review inbox.",
          empty: "The review queue is empty right now.",
          open: "Open",
          resolved: "Resolved",
          stale: "Stale",
          actionable: "Actionable",
          noSelection: "Details will appear once a review item is selected.",
        };

  const [statusFilter, setStatusFilter] = useState<"open" | "resolved">("open");
  const [feed, setFeed] = useState<DiscoveryInboxFeed | null>(null);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [selectedDossier, setSelectedDossier] = useState<IdeaDossier | null>(null);
  const [loading, setLoading] = useState(true);
  const [dossierLoading, setDossierLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [busyKey, setBusyKey] = useState<string | null>(null);

  async function load(showLoader: boolean = false) {
    if (showLoader) setLoading(true);
    setError(null);
    try {
      const nextFeed = await getDiscoveryInboxFeed(40, statusFilter);
      setFeed(nextFeed);
      setSelectedId((current) => {
        if (current && nextFeed.items.some((item) => item.item_id === current)) {
          return current;
        }
        return nextFeed.items[0]?.item_id ?? null;
      });
    } catch (nextError) {
      setError(nextError instanceof Error ? nextError.message : text.error);
    } finally {
      setLoading(false);
    }
  }

  async function loadDossier(item: DiscoveryInboxItem | null) {
    if (!item?.idea_id) {
      setSelectedDossier(null);
      return;
    }
    setDossierLoading(true);
    try {
      setSelectedDossier(await getDiscoveryDossier(item.idea_id));
    } catch {
      setSelectedDossier(null);
    } finally {
      setDossierLoading(false);
    }
  }

  async function handleAction(item: DiscoveryInboxItem, body: DiscoveryInboxActionRequest) {
    const key = `${item.item_id}:${body.action}`;
    setBusyKey(key);
    setError(null);
    try {
      const updated = await actOnDiscoveryInboxItem(item.item_id, body);
      await load(false);
      if (updated.status === "open") {
        setSelectedId(updated.item_id);
      }
    } catch (nextError) {
      setError(nextError instanceof Error ? nextError.message : text.error);
    } finally {
      setBusyKey(null);
    }
  }

  useEffect(() => {
    void load(true);
  }, [statusFilter]);

  const selectedItem = feed?.items.find((item) => item.item_id === selectedId) ?? null;

  useEffect(() => {
    void loadDossier(selectedItem);
  }, [selectedItem?.item_id]);

  return (
    <section className="rounded-[28px] border border-[#d6dbe6] bg-white/90 p-5 shadow-[0_16px_38px_-28px_rgba(17,48,105,0.22)] dark:border-slate-800 dark:bg-slate-950/60 dark:shadow-none">
      <div className="flex flex-col gap-4 xl:flex-row xl:items-start xl:justify-between">
        <div>
          <div className="flex items-center gap-2 text-[20px] font-semibold tracking-[-0.04em] text-[#111111] dark:text-slate-100">
            <InboxIcon className="h-5 w-5" />
            {text.title}
          </div>
          <div className="mt-2 max-w-3xl text-[13px] leading-6 text-[#6b7280] dark:text-slate-400">
            {text.subtitle}
          </div>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <button
            type="button"
            onClick={() => setStatusFilter("open")}
            className={[
              "rounded-full border px-3 py-1 text-[11px]",
              statusFilter === "open"
                ? "border-[#111111] bg-black text-white dark:border-slate-100"
                : "border-[#d6dbe6] bg-[#fafbff] text-[#4b5563] dark:border-slate-800 dark:bg-slate-900 dark:text-slate-300",
            ].join(" ")}
          >
            {text.open}: {feed?.summary.open_count ?? 0}
          </button>
          <button
            type="button"
            onClick={() => setStatusFilter("resolved")}
            className={[
              "rounded-full border px-3 py-1 text-[11px]",
              statusFilter === "resolved"
                ? "border-[#111111] bg-black text-white dark:border-slate-100"
                : "border-[#d6dbe6] bg-[#fafbff] text-[#4b5563] dark:border-slate-800 dark:bg-slate-900 dark:text-slate-300",
            ].join(" ")}
          >
            {text.resolved}: {feed?.summary.resolved_count ?? 0}
          </button>
          <div className="rounded-full border border-[#d6dbe6] bg-[#fafbff] px-3 py-1 text-[11px] text-[#4b5563] dark:border-slate-800 dark:bg-slate-900 dark:text-slate-300">
            {text.stale}: {feed?.summary.stale_count ?? 0}
          </div>
          <div className="rounded-full border border-[#d6dbe6] bg-[#fafbff] px-3 py-1 text-[11px] text-[#4b5563] dark:border-slate-800 dark:bg-slate-900 dark:text-slate-300">
            {text.actionable}: {feed?.summary.action_required_count ?? 0}
          </div>
          <Button type="button" variant="outline" size="sm" onClick={() => void load(true)} className="h-8 rounded-full text-[11px]">
            {loading ? <Loader2 className="mr-1 h-3.5 w-3.5 animate-spin" /> : <RefreshCcw className="mr-1 h-3.5 w-3.5" />}
            {text.refresh}
          </Button>
        </div>
      </div>

      <div className="mt-5 grid gap-4 xl:grid-cols-[minmax(0,1.1fr)_minmax(360px,0.9fr)]">
        <div className="space-y-3">
          {loading ? (
            <div className="flex items-center gap-3 rounded-[20px] border border-[#d6dbe6] bg-[#fbfcff] px-4 py-5 text-[13px] text-[#4b5563] dark:border-slate-800 dark:bg-slate-900/60 dark:text-slate-300">
              <Loader2 className="h-4 w-4 animate-spin" />
              {text.loading}
            </div>
          ) : error ? (
            <div className="rounded-[20px] border border-rose-200 bg-rose-50 px-4 py-5 text-[13px] text-rose-700 dark:border-rose-900/60 dark:bg-rose-950/40 dark:text-rose-300">
              {error}
            </div>
          ) : feed?.items.length ? (
            feed.items.map((item) => (
              <ReviewEvent
                key={item.item_id}
                item={item}
                selected={selectedId === item.item_id}
                busyKey={busyKey}
                onSelect={() => setSelectedId(item.item_id)}
                onAction={(nextItem, body) => void handleAction(nextItem, body)}
              />
            ))
          ) : (
            <div className="rounded-[20px] border border-dashed border-[#d6dbe6] bg-[#fbfcff] px-4 py-6 text-[13px] leading-6 text-[#6b7280] dark:border-slate-800 dark:bg-slate-900/60 dark:text-slate-400">
              {text.empty}
            </div>
          )}
        </div>

        {selectedItem ? (
          <DossierInboxCard item={selectedItem} dossier={selectedDossier} loading={dossierLoading} />
        ) : (
          <div className="rounded-[24px] border border-dashed border-[#d6dbe6] bg-[#fbfcff] px-5 py-5 text-[13px] leading-6 text-[#6b7280] dark:border-slate-800 dark:bg-slate-900/60 dark:text-slate-400">
            {text.noSelection}
          </div>
        )}
      </div>
    </section>
  );
}
