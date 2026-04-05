"use client";

import { useEffect, useState } from "react";
import { CheckCheck, GitCompare, Loader2, MessageSquareMore, PencilLine, SkipForward } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { useLocale } from "@/lib/locale";
import type { DiscoveryInboxActionRequest, DiscoveryInboxItem } from "@/lib/types";

interface ReviewEventProps {
  item: DiscoveryInboxItem;
  selected: boolean;
  busyKey: string | null;
  onSelect: () => void;
  onAction: (item: DiscoveryInboxItem, body: DiscoveryInboxActionRequest) => void;
}

function ageLabel(ageMinutes: number): string {
  if (ageMinutes >= 24 * 60) return `${Math.round(ageMinutes / 60)}h`;
  if (ageMinutes >= 60) return `${Math.round(ageMinutes / 60)}h`;
  return `${ageMinutes}m`;
}

export function ReviewEvent({ item, selected, busyKey, onSelect, onAction }: ReviewEventProps) {
  const { locale } = useLocale();
  const text =
    locale === "ru"
      ? {
          accept: "Принять",
          ignore: "Игнор",
          respond: "Ответить",
          edit: "Правка",
          compare: "Сравнить",
          send: "Отправить",
          save: "Сохранить",
          responsePlaceholder: "Что должен сделать агент дальше?",
          editPlaceholder: item.subject_kind === "handoff" ? "Отредактируй brief summary…" : "Отредактируй summary идеи…",
          compareHint: "Сравнить с соседними идеями",
        }
      : {
          accept: "Accept",
          ignore: "Ignore",
          respond: "Respond",
          edit: "Edit",
          compare: "Compare",
          send: "Send",
          save: "Save",
          responsePlaceholder: "What should the agent do next?",
          editPlaceholder: item.subject_kind === "handoff" ? "Edit the brief summary…" : "Edit the idea summary…",
          compareHint: "Compare against nearby ideas",
        };

  const [composer, setComposer] = useState<"respond" | "edit" | null>(null);
  const [responseText, setResponseText] = useState("");
  const [editText, setEditText] = useState(item.dossier_preview?.idea_summary ?? "");
  const [showCompare, setShowCompare] = useState(false);

  useEffect(() => {
    setEditText(item.dossier_preview?.idea_summary ?? "");
    setShowCompare(false);
  }, [item.dossier_preview?.idea_summary, item.item_id]);

  const actionBusy = (action: string) => busyKey === `${item.item_id}:${action}`;

  return (
    <article
      role="button"
      tabIndex={0}
      onClick={onSelect}
      onKeyDown={(event) => {
        if (event.key === "Enter" || event.key === " ") {
          event.preventDefault();
          onSelect();
        }
      }}
      className={[
        "rounded-[22px] border px-4 py-4 transition-colors",
        selected
          ? "border-[#111111] bg-[#fffdf8] shadow-[0_14px_26px_-24px_rgba(17,17,17,0.45)] dark:border-slate-200 dark:bg-slate-950/80"
          : "border-[#d6dbe6] bg-[#fbfcff] hover:border-[#aeb9ce] dark:border-slate-800 dark:bg-slate-900/60",
      ].join(" ")}
    >
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-2">
            <div className="text-[14px] font-semibold tracking-[-0.03em] text-[#111111] dark:text-slate-100">
              {item.title}
            </div>
            <Badge variant="secondary" className="rounded-full bg-[#eef2f8] text-[#475569] dark:bg-slate-800 dark:text-slate-300">
              {item.subject_kind}
            </Badge>
            <Badge variant="secondary" className="rounded-full bg-[#f6efe2] text-[#7c4f10] dark:bg-amber-950/40 dark:text-amber-200">
              {item.aging_bucket} · {ageLabel(item.age_minutes)}
            </Badge>
          </div>
          <div className="mt-2 text-[13px] leading-6 text-[#4b5563] dark:text-slate-300">
            {item.interrupt?.summary || item.detail}
          </div>
        </div>
        <div className="text-right text-[11px] uppercase tracking-[0.14em] text-[#6b7280] dark:text-slate-500">
          p{item.priority_score.toFixed(2)}
        </div>
      </div>

      {item.dossier_preview ? (
        <div className="mt-3 grid gap-2 md:grid-cols-2">
          <div className="rounded-[16px] bg-white px-3 py-3 text-[12px] leading-6 text-[#374151] dark:bg-slate-950/70 dark:text-slate-300">
            <div className="text-[10px] uppercase tracking-[0.14em] text-[#6b7280] dark:text-slate-500">Summary</div>
            <div className="mt-1">{item.dossier_preview.idea_summary || item.detail}</div>
          </div>
          <div className="rounded-[16px] bg-white px-3 py-3 text-[12px] leading-6 text-[#374151] dark:bg-slate-950/70 dark:text-slate-300">
            <div className="text-[10px] uppercase tracking-[0.14em] text-[#6b7280] dark:text-slate-500">Evidence</div>
            <div className="mt-1 space-y-1">
              {(item.dossier_preview.evidence.observations.slice(0, 2).length
                ? item.dossier_preview.evidence.observations.slice(0, 2)
                : item.dossier_preview.evidence.validations.slice(0, 2)
              ).map((line) => (
                <div key={line}>{line}</div>
              ))}
            </div>
          </div>
        </div>
      ) : null}

      <div className="mt-4 flex flex-wrap gap-2">
        {item.interrupt?.config.allow_accept ? (
          <Button
            type="button"
            size="sm"
            onClick={(event) => {
              event.stopPropagation();
              onAction(item, { action: "accept", note: `Accepted ${item.subject_kind} review.` });
            }}
            disabled={actionBusy("accept")}
            className="h-8 rounded-full bg-black text-[11px] text-white hover:bg-black/90"
          >
            {actionBusy("accept") ? <Loader2 className="mr-1 h-3.5 w-3.5 animate-spin" /> : <CheckCheck className="mr-1 h-3.5 w-3.5" />}
            {text.accept}
          </Button>
        ) : null}
        {item.interrupt?.config.allow_ignore ? (
          <Button
            type="button"
            variant="outline"
            size="sm"
            onClick={(event) => {
              event.stopPropagation();
              onAction(item, { action: "ignore", note: `Ignored ${item.subject_kind} review.` });
            }}
            disabled={actionBusy("ignore")}
            className="h-8 rounded-full text-[11px]"
          >
            {actionBusy("ignore") ? <Loader2 className="mr-1 h-3.5 w-3.5 animate-spin" /> : <SkipForward className="mr-1 h-3.5 w-3.5" />}
            {text.ignore}
          </Button>
        ) : null}
        {item.interrupt?.config.allow_respond ? (
          <Button
            type="button"
            variant="outline"
            size="sm"
            onClick={(event) => {
              event.stopPropagation();
              setShowCompare(false);
              setComposer(composer === "respond" ? null : "respond");
            }}
            className="h-8 rounded-full text-[11px]"
          >
            <MessageSquareMore className="mr-1 h-3.5 w-3.5" />
            {text.respond}
          </Button>
        ) : null}
        {item.interrupt?.config.allow_edit ? (
          <Button
            type="button"
            variant="outline"
            size="sm"
            onClick={(event) => {
              event.stopPropagation();
              setShowCompare(false);
              setComposer(composer === "edit" ? null : "edit");
            }}
            className="h-8 rounded-full text-[11px]"
          >
            <PencilLine className="mr-1 h-3.5 w-3.5" />
            {text.edit}
          </Button>
        ) : null}
        {item.interrupt?.config.allow_compare && item.dossier_preview?.compare_options.length ? (
          <Button
            type="button"
            variant="outline"
            size="sm"
            onClick={(event) => {
              event.stopPropagation();
              setComposer(null);
              setShowCompare((value) => !value);
            }}
            className="h-8 rounded-full text-[11px]"
            title={text.compareHint}
          >
            <GitCompare className="mr-1 h-3.5 w-3.5" />
            {text.compare}
          </Button>
        ) : null}
      </div>

      {selected && showCompare && item.dossier_preview?.compare_options.length ? (
        <div className="mt-3 space-y-2 rounded-[18px] border border-[#d6dbe6] bg-white px-3 py-3 dark:border-slate-800 dark:bg-slate-950/70">
          <div className="text-[10px] uppercase tracking-[0.14em] text-[#6b7280] dark:text-slate-500">{text.compareHint}</div>
          {item.dossier_preview.compare_options.map((option) => (
            <button
              key={option.idea_id}
              type="button"
              onClick={(event) => {
                event.stopPropagation();
                onAction(item, {
                  action: "compare",
                  compare_target_idea_id: option.idea_id,
                  note: option.reason,
                });
              }}
              className="w-full rounded-[14px] border border-[#d6dbe6] bg-[#fbfcff] px-3 py-2 text-left text-[12px] leading-6 text-[#374151] transition-colors hover:border-[#111111] dark:border-slate-800 dark:bg-slate-900/60 dark:text-slate-300"
            >
              <div className="font-medium text-[#111111] dark:text-slate-100">{option.title}</div>
              <div className="text-[11px] text-[#6b7280] dark:text-slate-500">
                {option.latest_stage} · {option.reason}
              </div>
            </button>
          ))}
        </div>
      ) : null}

      {composer === "respond" ? (
        <div className="mt-3 space-y-2 rounded-[18px] border border-[#d6dbe6] bg-white px-3 py-3 dark:border-slate-800 dark:bg-slate-950/70">
          <textarea
            value={responseText}
            onClick={(event) => event.stopPropagation()}
            onChange={(event) => setResponseText(event.target.value)}
            placeholder={text.responsePlaceholder}
            className="min-h-[92px] w-full rounded-[14px] border border-[#d6dbe6] bg-[#fbfcff] px-3 py-2 text-[13px] leading-6 text-[#111111] outline-none transition-colors focus:border-[#111111] dark:border-slate-800 dark:bg-slate-900 dark:text-slate-100"
          />
          <div className="flex justify-end">
            <Button
              type="button"
              size="sm"
              onClick={(event) => {
                event.stopPropagation();
                onAction(item, {
                  action: "respond",
                  note: responseText,
                  response_text: responseText,
                });
                setResponseText("");
                setComposer(null);
              }}
              disabled={!responseText.trim() || actionBusy("respond")}
              className="h-8 rounded-full bg-black text-[11px] text-white hover:bg-black/90"
            >
              {actionBusy("respond") ? <Loader2 className="mr-1 h-3.5 w-3.5 animate-spin" /> : null}
              {text.send}
            </Button>
          </div>
        </div>
      ) : null}

      {composer === "edit" ? (
        <div className="mt-3 space-y-2 rounded-[18px] border border-[#d6dbe6] bg-white px-3 py-3 dark:border-slate-800 dark:bg-slate-950/70">
          <textarea
            value={editText}
            onClick={(event) => event.stopPropagation()}
            onChange={(event) => setEditText(event.target.value)}
            placeholder={text.editPlaceholder}
            className="min-h-[92px] w-full rounded-[14px] border border-[#d6dbe6] bg-[#fbfcff] px-3 py-2 text-[13px] leading-6 text-[#111111] outline-none transition-colors focus:border-[#111111] dark:border-slate-800 dark:bg-slate-900 dark:text-slate-100"
          />
          <div className="flex justify-end">
            <Button
              type="button"
              size="sm"
              onClick={(event) => {
                event.stopPropagation();
                onAction(item, {
                  action: "edit",
                  note: `Edited ${item.subject_kind} payload from inbox.`,
                  edited_fields: {
                    [item.subject_kind === "handoff" ? "prd_summary" : "summary"]: editText,
                  },
                });
                setComposer(null);
              }}
              disabled={!editText.trim() || actionBusy("edit")}
              className="h-8 rounded-full bg-black text-[11px] text-white hover:bg-black/90"
            >
              {actionBusy("edit") ? <Loader2 className="mr-1 h-3.5 w-3.5 animate-spin" /> : null}
              {text.save}
            </Button>
          </div>
        </div>
      ) : null}
    </article>
  );
}
