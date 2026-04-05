"use client";

import { useEffect, useState } from "react";
import { Inbox, Loader2, Newspaper, RefreshCcw } from "lucide-react";

import { Button } from "@/components/ui/button";
import { getDiscoveryDaemonDigests, getDiscoveryInbox } from "@/lib/api";
import { useLocale } from "@/lib/locale";
import type { DiscoveryDailyDigest, DiscoveryInboxItem } from "@/lib/types";


function formatDate(value: string): string {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleString();
}

export function DailyDigest() {
  const { locale } = useLocale();
  const text =
    locale === "ru"
      ? {
          title: "Daily digest",
          subtitle: "Founder-facing output from daemon routines: highlights, overnight queue и inbox-ready follow-ups.",
          refresh: "Обновить",
          loading: "Собираю daily digest…",
          error: "Не удалось загрузить daily digest.",
          empty: "Daily digest ещё не сформирован. Запусти daemon или прогон `daily_digest` вручную.",
          highlights: "Highlights",
          topIdeas: "Top ideas",
          overnight: "Overnight queue",
          summaries: "Routine summaries",
          inbox: "Inbox preview",
          noInbox: "Открытых daemon inbox items пока нет.",
        }
      : {
          title: "Daily digest",
          subtitle: "Founder-facing output from daemon routines: highlights, overnight queue, and inbox-ready follow-ups.",
          refresh: "Refresh",
          loading: "Loading the daily digest…",
          error: "Failed to load the daily digest.",
          empty: "No daily digest has been generated yet. Start the daemon or run `daily_digest` manually.",
          highlights: "Highlights",
          topIdeas: "Top ideas",
          overnight: "Overnight queue",
          summaries: "Routine summaries",
          inbox: "Inbox preview",
          noInbox: "No open daemon inbox items yet.",
        };

  const [digests, setDigests] = useState<DiscoveryDailyDigest[]>([]);
  const [inboxItems, setInboxItems] = useState<DiscoveryInboxItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function load(showLoader: boolean) {
    if (showLoader) {
      setLoading(true);
    } else {
      setRefreshing(true);
    }
    setError(null);
    try {
      const [nextDigests, nextInbox] = await Promise.all([
        getDiscoveryDaemonDigests(6),
        getDiscoveryInbox(6, "open"),
      ]);
      setDigests(nextDigests);
      setInboxItems(nextInbox);
    } catch (nextError) {
      setError(nextError instanceof Error ? nextError.message : text.error);
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }

  useEffect(() => {
    void load(true);
  }, []);

  const digest = digests[0] ?? null;

  return (
    <section className="rounded-[28px] border border-[#d6dbe6] bg-white/90 p-5 shadow-[0_16px_38px_-28px_rgba(17,48,105,0.22)] dark:border-slate-800 dark:bg-slate-950/60 dark:shadow-none">
      <div className="flex flex-col gap-4 xl:flex-row xl:items-start xl:justify-between">
        <div>
          <div className="flex items-center gap-2 text-[20px] font-semibold tracking-[-0.04em] text-[#111111] dark:text-slate-100">
            <Newspaper className="h-5 w-5" />
            {text.title}
          </div>
          <div className="mt-2 max-w-3xl text-[13px] leading-6 text-[#6b7280] dark:text-slate-400">
            {text.subtitle}
          </div>
        </div>
        <Button type="button" variant="outline" size="sm" onClick={() => void load(false)} className="h-8 rounded-full text-[11px]">
          {refreshing ? <Loader2 className="mr-1 h-3.5 w-3.5 animate-spin" /> : <RefreshCcw className="mr-1 h-3.5 w-3.5" />}
          {text.refresh}
        </Button>
      </div>

      {loading ? (
        <div className="mt-5 flex items-center gap-3 rounded-[20px] border border-[#d6dbe6] bg-[#fbfcff] px-4 py-5 text-[13px] text-[#4b5563] dark:border-slate-800 dark:bg-slate-900/60 dark:text-slate-300">
          <Loader2 className="h-4 w-4 animate-spin" />
          {text.loading}
        </div>
      ) : error ? (
        <div className="mt-5 rounded-[20px] border border-rose-200 bg-rose-50 px-4 py-5 text-[13px] text-rose-700 dark:border-rose-900/60 dark:bg-rose-950/40 dark:text-rose-300">
          {error}
        </div>
      ) : !digest ? (
        <div className="mt-5 rounded-[20px] border border-dashed border-[#d6dbe6] bg-[#fbfcff] px-4 py-6 text-[13px] leading-6 text-[#6b7280] dark:border-slate-800 dark:bg-slate-900/60 dark:text-slate-400">
          {text.empty}
        </div>
      ) : (
        <>
          <div className="mt-5 rounded-[20px] border border-[#d6dbe6] bg-[#fbfcff] px-4 py-4 dark:border-slate-800 dark:bg-slate-900/60">
            <div className="text-[11px] uppercase tracking-[0.14em] text-[#6b7280] dark:text-slate-500">{digest.digest_date}</div>
            <div className="mt-2 text-[20px] font-semibold tracking-[-0.04em] text-[#111111] dark:text-slate-100">{digest.headline}</div>
            <div className="mt-2 text-[12px] text-[#6b7280] dark:text-slate-400">{formatDate(digest.created_at)}</div>
          </div>

          <div className="mt-5 grid gap-4 xl:grid-cols-[minmax(0,1.05fr)_minmax(320px,0.95fr)]">
            <div className="space-y-4">
              <div className="rounded-[20px] border border-[#d6dbe6] bg-[#fbfcff] px-4 py-4 dark:border-slate-800 dark:bg-slate-900/60">
                <div className="text-[11px] uppercase tracking-[0.14em] text-[#6b7280] dark:text-slate-500">{text.highlights}</div>
                <div className="mt-3 space-y-2">
                  {digest.highlights.map((item) => (
                    <div key={item} className="rounded-[14px] bg-white px-3 py-2 text-[12px] leading-6 text-[#4b5563] dark:bg-slate-950/70 dark:text-slate-300">
                      {item}
                    </div>
                  ))}
                </div>
              </div>

              <div className="grid gap-4 xl:grid-cols-2">
                <div className="rounded-[20px] border border-[#d6dbe6] bg-[#fbfcff] px-4 py-4 dark:border-slate-800 dark:bg-slate-900/60">
                  <div className="text-[11px] uppercase tracking-[0.14em] text-[#6b7280] dark:text-slate-500">{text.topIdeas}</div>
                  <div className="mt-3 space-y-2">
                    {digest.top_ideas.map((idea) => (
                      <div key={idea.idea_id} className="rounded-[14px] bg-white px-3 py-3 dark:bg-slate-950/70">
                        <div className="text-[13px] font-medium text-[#111111] dark:text-slate-100">{idea.title}</div>
                        <div className="mt-1 text-[12px] text-[#6b7280] dark:text-slate-400">
                          {idea.reason}
                        </div>
                      </div>
                    ))}
                  </div>
                </div>

                <div className="rounded-[20px] border border-[#d6dbe6] bg-[#fbfcff] px-4 py-4 dark:border-slate-800 dark:bg-slate-900/60">
                  <div className="text-[11px] uppercase tracking-[0.14em] text-[#6b7280] dark:text-slate-500">{text.overnight}</div>
                  <div className="mt-3 space-y-2">
                    {digest.overnight_queue.map((idea) => (
                      <div key={idea.idea_id} className="rounded-[14px] bg-white px-3 py-3 dark:bg-slate-950/70">
                        <div className="text-[13px] font-medium text-[#111111] dark:text-slate-100">{idea.title}</div>
                        <div className="mt-1 text-[12px] text-[#6b7280] dark:text-slate-400">
                          {idea.reason}
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              </div>

              <div className="rounded-[20px] border border-[#d6dbe6] bg-[#fbfcff] px-4 py-4 dark:border-slate-800 dark:bg-slate-900/60">
                <div className="text-[11px] uppercase tracking-[0.14em] text-[#6b7280] dark:text-slate-500">{text.summaries}</div>
                <div className="mt-3 space-y-2">
                  {digest.routine_summaries.map((item) => (
                    <div key={`${digest.digest_id}-${item.routine_kind}`} className="rounded-[14px] bg-white px-3 py-3 dark:bg-slate-950/70">
                      <div className="text-[13px] font-medium text-[#111111] dark:text-slate-100">{item.routine_kind}</div>
                      <div className="mt-1 text-[12px] leading-6 text-[#4b5563] dark:text-slate-300">{item.headline}</div>
                    </div>
                  ))}
                </div>
              </div>
            </div>

            <div className="rounded-[20px] border border-[#d6dbe6] bg-[#fbfcff] px-4 py-4 dark:border-slate-800 dark:bg-slate-900/60">
              <div className="flex items-center gap-2 text-[11px] uppercase tracking-[0.14em] text-[#6b7280] dark:text-slate-500">
                <Inbox className="h-3.5 w-3.5" />
                {text.inbox}
              </div>
              <div className="mt-3 space-y-2">
                {inboxItems.length === 0 ? (
                  <div className="rounded-[14px] bg-white px-3 py-3 text-[12px] leading-6 text-[#4b5563] dark:bg-slate-950/70 dark:text-slate-300">
                    {text.noInbox}
                  </div>
                ) : (
                  inboxItems.map((item) => (
                    <div key={item.item_id} className="rounded-[14px] bg-white px-3 py-3 dark:bg-slate-950/70">
                      <div className="flex items-center justify-between gap-3">
                        <div className="text-[13px] font-medium text-[#111111] dark:text-slate-100">{item.title}</div>
                        <div className="text-[10px] uppercase tracking-[0.14em] text-[#6b7280] dark:text-slate-400">{item.kind}</div>
                      </div>
                      <div className="mt-1 text-[12px] leading-6 text-[#4b5563] dark:text-slate-300">{item.detail}</div>
                    </div>
                  ))
                )}
              </div>
            </div>
          </div>
        </>
      )}
    </section>
  );
}
