"use client";

import { ArrowUpRight, Loader2, Sparkles } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { useLocale } from "@/lib/locale";
import type { DiscoverySwipeAction, IdeaQueueItem } from "@/lib/types";

interface IdeaCardProps {
  item: IdeaQueueItem;
  busyAction?: DiscoverySwipeAction | null;
  compact?: boolean;
  onOpenDossier?: () => void;
  onSwipe?: (action: DiscoverySwipeAction) => void;
}

export function IdeaCard({
  item,
  busyAction,
  compact = false,
  onOpenDossier,
  onSwipe,
}: IdeaCardProps) {
  const { locale } = useLocale();
  const text =
    locale === "ru"
      ? {
          pass: "Пас",
          maybe: "Может",
          yes: "Да",
          now: "Сейчас",
          dossier: "Dossier",
          score: "Приоритет",
          source: "Источник",
          repoDna: "RepoDNA",
          changes: "Изменения",
          evidence: "Новые сигналы",
          waiting: "Ожидает",
          ready: "Готово",
        }
      : {
          pass: "Pass",
          maybe: "Maybe",
          yes: "Yes",
          now: "Now",
          dossier: "Dossier",
          score: "Priority",
          source: "Source",
          repoDna: "RepoDNA",
          changes: "Changes",
          evidence: "Fresh signals",
          waiting: "Watching",
          ready: "Ready",
        };

  const actions: DiscoverySwipeAction[] = ["pass", "maybe", "yes", "now"];

  return (
    <Card className={`border border-[#d6dbe6] bg-[#fbfcff] shadow-none dark:border-slate-800 dark:bg-slate-900/60 ${compact ? "" : "min-h-[270px]"}`}>
      <CardHeader className="gap-3">
        <div className="flex items-start justify-between gap-3">
          <div className="min-w-0">
            <CardTitle className="text-[16px] font-semibold tracking-[-0.03em] text-[#111111] dark:text-slate-100">
              {item.idea.title}
            </CardTitle>
            <div className="mt-2 flex flex-wrap gap-2">
              <Badge variant="outline" className="rounded-full border-[#d6dbe6] bg-white text-[#4b5563] dark:border-slate-800 dark:bg-slate-950 dark:text-slate-300">
                {text.score}: {item.priority_score.toFixed(2)}
              </Badge>
              <Badge variant="outline" className="rounded-full border-[#d6dbe6] bg-white text-[#4b5563] dark:border-slate-800 dark:bg-slate-950 dark:text-slate-300">
                {text.source}: {item.idea.source}
              </Badge>
              {item.recheck_status ? (
                <Badge className={`rounded-full ${item.recheck_status === "ready" ? "bg-[#111111] text-white dark:bg-slate-100 dark:text-slate-950" : "bg-[#edf0f6] text-[#4b5563] dark:bg-slate-800 dark:text-slate-300"}`}>
                  {item.recheck_status === "ready" ? text.ready : text.waiting}
                </Badge>
              ) : null}
            </div>
          </div>
          <Button
            type="button"
            variant="outline"
            size="sm"
            onClick={onOpenDossier}
            className="h-8 rounded-full border-[#d6dbe6] bg-white text-[11px] text-[#111111] dark:border-slate-800 dark:bg-slate-950/70 dark:text-slate-100"
          >
            <ArrowUpRight className="mr-1 h-3.5 w-3.5" />
            {text.dossier}
          </Button>
        </div>
      </CardHeader>

      <CardContent className="space-y-4">
        <div className="text-[13px] leading-6 text-[#4b5563] dark:text-slate-300">
          {item.idea.summary || item.idea.thesis || item.idea.description || item.explanation.headline}
        </div>

        <div className="rounded-[18px] border border-[#e4e8f0] bg-white/80 p-3 dark:border-slate-800 dark:bg-slate-950/60">
          <div className="flex items-center gap-2 text-[11px] font-semibold uppercase tracking-[0.14em] text-[#6b7280] dark:text-slate-500">
            <Sparkles className="h-3.5 w-3.5" />
            {item.explanation.headline}
          </div>
          <div className="mt-3 grid gap-3 md:grid-cols-2">
            <div>
              <div className="text-[11px] font-semibold uppercase tracking-[0.14em] text-[#6b7280] dark:text-slate-500">
                {text.evidence}
              </div>
              <ul className="mt-2 space-y-1.5 text-[12px] leading-5 text-[#4b5563] dark:text-slate-300">
                {item.explanation.source_signals.slice(0, 2).map((signal) => (
                  <li key={signal}>{signal}</li>
                ))}
              </ul>
            </div>
            <div>
              <div className="text-[11px] font-semibold uppercase tracking-[0.14em] text-[#6b7280] dark:text-slate-500">
                {text.changes}
              </div>
              <ul className="mt-2 space-y-1.5 text-[12px] leading-5 text-[#4b5563] dark:text-slate-300">
                {item.explanation.change_summary.slice(0, 2).map((signal) => (
                  <li key={signal}>{signal}</li>
                ))}
              </ul>
            </div>
          </div>
          {item.explanation.repo_dna_match ? (
            <div className="mt-3 rounded-[14px] bg-[#f4f6fb] px-3 py-2 text-[12px] leading-5 text-[#374151] dark:bg-slate-900 dark:text-slate-300">
              <span className="font-semibold">{text.repoDna}:</span> {item.explanation.repo_dna_match}
            </div>
          ) : null}
        </div>

        <div className="flex flex-wrap gap-2">
          {item.idea.topic_tags.slice(0, compact ? 4 : 6).map((tag) => (
            <Badge key={tag} variant="secondary" className="rounded-full bg-[#edf0f6] text-[#4b5563] dark:bg-slate-800 dark:text-slate-300">
              {tag}
            </Badge>
          ))}
        </div>

        {onSwipe ? (
          <div className="flex flex-wrap gap-2 pt-1">
            {actions.map((action) => (
              <Button
                key={action}
                type="button"
                size="sm"
                variant={action === "pass" ? "outline" : "secondary"}
                onClick={() => onSwipe(action)}
                disabled={Boolean(busyAction)}
                className={`h-8 rounded-full px-3 text-[11px] ${
                  action === "now"
                    ? "bg-black text-white hover:bg-black/90 dark:bg-slate-100 dark:text-slate-950"
                    : action === "yes"
                      ? "bg-[#111111] text-white hover:bg-[#111111]/90 dark:bg-slate-200 dark:text-slate-950"
                      : action === "maybe"
                        ? "bg-[#eef2ff] text-[#243b74] hover:bg-[#e1e8ff] dark:bg-slate-800 dark:text-slate-100"
                        : "border-[#d6dbe6] bg-white text-[#4b5563] dark:border-slate-800 dark:bg-slate-950/60 dark:text-slate-300"
                }`}
              >
                {busyAction === action ? <Loader2 className="mr-1 h-3.5 w-3.5 animate-spin" /> : null}
                {text[action]}
              </Button>
            ))}
          </div>
        ) : null}
      </CardContent>
    </Card>
  );
}
