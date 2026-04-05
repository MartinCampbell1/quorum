"use client";

import { Loader2, X } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { useLocale } from "@/lib/locale";
import type { IdeaChangeRecord, IdeaDossier, IdeaQueueItem } from "@/lib/types";

interface DossierDrawerProps {
  open: boolean;
  item: IdeaQueueItem | null;
  dossier: IdeaDossier | null;
  changes: IdeaChangeRecord | null;
  loading?: boolean;
  onClose: () => void;
}

export function DossierDrawer({
  open,
  item,
  dossier,
  changes,
  loading = false,
  onClose,
}: DossierDrawerProps) {
  const { locale } = useLocale();
  const text =
    locale === "ru"
      ? {
          title: "Dossier",
          subtitle: "Что изменилось с прошлого просмотра",
          close: "Закрыть",
          loading: "Загружаю dossier…",
          evidence: "Evidence",
          validation: "Validation",
          timeline: "Timeline",
          changes: "Изменения",
          brief: "Execution Brief",
          graph: "Idea graph",
          memory: "Institutional memory",
          explainability: "Explainability",
          ranking: "Почему здесь",
          judge: "Judge",
          simulationExplain: "Simulation",
          skills: "Skills",
          related: "Связанные идеи",
          none: "Пока пусто.",
        }
      : {
          title: "Dossier",
          subtitle: "What changed since you last saw this idea",
          close: "Close",
          loading: "Loading dossier…",
          evidence: "Evidence",
          validation: "Validation",
          timeline: "Timeline",
          changes: "Changes",
          brief: "Execution Brief",
          graph: "Idea graph",
          memory: "Institutional memory",
          explainability: "Explainability",
          ranking: "Why here",
          judge: "Judge",
          simulationExplain: "Simulation",
          skills: "Skills",
          related: "Related ideas",
          none: "Nothing is attached yet.",
        };

  if (!open) return null;

  return (
    <div className="fixed inset-0 z-40 flex justify-end bg-black/30 backdrop-blur-[2px]">
      <div className="flex h-full w-full max-w-[680px] flex-col overflow-hidden border-l border-[#d6dbe6] bg-[#f7f8fc] shadow-2xl dark:border-slate-800 dark:bg-[#070a11]">
        <div className="flex items-start justify-between gap-4 border-b border-[#d6dbe6] bg-white/95 px-6 py-5 dark:border-slate-800 dark:bg-[#0b0f17]/95">
          <div className="min-w-0">
            <div className="text-[18px] font-semibold tracking-[-0.03em] text-[#111111] dark:text-slate-100">
              {item?.idea.title ?? text.title}
            </div>
            <div className="mt-1 text-[12px] leading-6 text-[#6b7280] dark:text-slate-400">{text.subtitle}</div>
          </div>
          <Button type="button" variant="outline" size="sm" onClick={onClose} className="h-8 rounded-full">
            <X className="mr-1 h-3.5 w-3.5" />
            {text.close}
          </Button>
        </div>

        <div className="min-h-0 flex-1 overflow-auto px-6 py-5">
          {loading ? (
            <div className="flex items-center gap-3 rounded-[18px] border border-[#d6dbe6] bg-white px-4 py-4 text-[13px] text-[#4b5563] dark:border-slate-800 dark:bg-slate-950/70 dark:text-slate-300">
              <Loader2 className="h-4 w-4 animate-spin" />
              {text.loading}
            </div>
          ) : (
            <div className="space-y-5">
              <section className="rounded-[22px] border border-[#d6dbe6] bg-white px-5 py-4 dark:border-slate-800 dark:bg-slate-950/70">
                <div className="text-[11px] font-semibold uppercase tracking-[0.14em] text-[#6b7280] dark:text-slate-500">
                  {text.changes}
                </div>
                <div className="mt-3 flex flex-wrap gap-2">
                  {changes?.summary_points?.length ? (
                    changes.summary_points.map((point) => (
                      <Badge key={point} variant="secondary" className="rounded-full bg-[#edf0f6] text-[#4b5563] dark:bg-slate-800 dark:text-slate-300">
                        {point}
                      </Badge>
                    ))
                  ) : (
                    <div className="text-[13px] text-[#6b7280] dark:text-slate-400">{text.none}</div>
                  )}
                </div>
              </section>

              <section className="rounded-[22px] border border-[#d6dbe6] bg-white px-5 py-4 dark:border-slate-800 dark:bg-slate-950/70">
                <div className="text-[11px] font-semibold uppercase tracking-[0.14em] text-[#6b7280] dark:text-slate-500">
                  {text.evidence}
                </div>
                <div className="mt-3 space-y-3">
                  {dossier?.observations?.length ? (
                    dossier.observations.slice(-4).reverse().map((observation) => (
                      <div key={observation.observation_id} className="rounded-[16px] bg-[#f4f6fb] px-4 py-3 text-[13px] leading-6 text-[#374151] dark:bg-slate-900 dark:text-slate-300">
                        <div className="font-medium text-[#111111] dark:text-slate-100">
                          {observation.source} · {observation.entity}
                        </div>
                        <div className="mt-1">{observation.raw_text}</div>
                      </div>
                    ))
                  ) : (
                    <div className="text-[13px] text-[#6b7280] dark:text-slate-400">{text.none}</div>
                  )}
                </div>
              </section>

              <section className="grid gap-5 lg:grid-cols-2">
                <div className="rounded-[22px] border border-[#d6dbe6] bg-white px-5 py-4 dark:border-slate-800 dark:bg-slate-950/70">
                  <div className="text-[11px] font-semibold uppercase tracking-[0.14em] text-[#6b7280] dark:text-slate-500">
                    {text.validation}
                  </div>
                  <div className="mt-3 space-y-3">
                    {dossier?.validation_reports?.length ? (
                      dossier.validation_reports.slice(-3).reverse().map((report) => (
                        <div key={report.report_id} className="rounded-[16px] bg-[#f4f6fb] px-4 py-3 text-[13px] leading-6 text-[#374151] dark:bg-slate-900 dark:text-slate-300">
                          <div className="font-medium text-[#111111] dark:text-slate-100">{report.verdict}</div>
                          <div className="mt-1">{report.summary}</div>
                        </div>
                      ))
                    ) : (
                      <div className="text-[13px] text-[#6b7280] dark:text-slate-400">{text.none}</div>
                    )}
                  </div>
                </div>

                <div className="rounded-[22px] border border-[#d6dbe6] bg-white px-5 py-4 dark:border-slate-800 dark:bg-slate-950/70">
                  <div className="text-[11px] font-semibold uppercase tracking-[0.14em] text-[#6b7280] dark:text-slate-500">
                    {text.timeline}
                  </div>
                  <div className="mt-3 space-y-3">
                    {dossier?.timeline?.length ? (
                      dossier.timeline.slice(-5).reverse().map((event) => (
                        <div key={event.event_id} className="rounded-[16px] bg-[#f4f6fb] px-4 py-3 text-[13px] leading-6 text-[#374151] dark:bg-slate-900 dark:text-slate-300">
                          <div className="font-medium text-[#111111] dark:text-slate-100">{event.title}</div>
                          <div className="mt-1">{event.detail || event.stage}</div>
                        </div>
                      ))
                    ) : (
                      <div className="text-[13px] text-[#6b7280] dark:text-slate-400">{text.none}</div>
                    )}
                  </div>
                </div>
              </section>

              <section className="grid gap-5 lg:grid-cols-2">
                <div className="rounded-[22px] border border-[#d6dbe6] bg-white px-5 py-4 dark:border-slate-800 dark:bg-slate-950/70">
                  <div className="text-[11px] font-semibold uppercase tracking-[0.14em] text-[#6b7280] dark:text-slate-500">
                    {text.graph}
                  </div>
                  <div className="mt-3 space-y-3">
                    {dossier?.idea_graph_context ? (
                      <>
                        <div className="rounded-[16px] bg-[#f4f6fb] px-4 py-3 text-[13px] leading-6 text-[#374151] dark:bg-slate-900 dark:text-slate-300">
                          <div className="font-medium text-[#111111] dark:text-slate-100">{text.related}</div>
                          <div className="mt-1">
                            {dossier.idea_graph_context.related_idea_ids.length
                              ? dossier.idea_graph_context.related_idea_ids.join(", ")
                              : text.none}
                          </div>
                        </div>
                        <StringChipList items={dossier.idea_graph_context.domain_clusters} emptyLabel={text.none} />
                        <StringChipList items={dossier.idea_graph_context.reusable_patterns} emptyLabel={text.none} />
                      </>
                    ) : (
                      <div className="text-[13px] text-[#6b7280] dark:text-slate-400">{text.none}</div>
                    )}
                  </div>
                </div>

                <div className="rounded-[22px] border border-[#d6dbe6] bg-white px-5 py-4 dark:border-slate-800 dark:bg-slate-950/70">
                  <div className="text-[11px] font-semibold uppercase tracking-[0.14em] text-[#6b7280] dark:text-slate-500">
                    {text.memory}
                  </div>
                  <div className="mt-3 space-y-3">
                    {dossier?.memory_context ? (
                      <>
                        <StringChipList items={dossier.memory_context.semantic_highlights} emptyLabel={text.none} />
                        <div className="rounded-[16px] bg-[#f4f6fb] px-4 py-3 text-[13px] leading-6 text-[#374151] dark:bg-slate-900 dark:text-slate-300">
                          <div className="font-medium text-[#111111] dark:text-slate-100">{text.skills}</div>
                          <div className="mt-2 space-y-2">
                            {dossier.memory_context.skill_hits.length ? (
                              dossier.memory_context.skill_hits.map((skill) => (
                                <div key={skill.skill_id} className="rounded-[14px] bg-white px-3 py-2 dark:bg-slate-950/70">
                                  <div className="font-medium text-[#111111] dark:text-slate-100">{skill.label}</div>
                                  <div className="mt-1 text-[12px] leading-6">{skill.description}</div>
                                </div>
                              ))
                            ) : (
                              <div className="text-[13px] text-[#6b7280] dark:text-slate-400">{text.none}</div>
                            )}
                          </div>
                        </div>
                      </>
                    ) : (
                      <div className="text-[13px] text-[#6b7280] dark:text-slate-400">{text.none}</div>
                    )}
                  </div>
                </div>
              </section>

              <section className="rounded-[22px] border border-[#d6dbe6] bg-white px-5 py-4 dark:border-slate-800 dark:bg-slate-950/70">
                <div className="text-[11px] font-semibold uppercase tracking-[0.14em] text-[#6b7280] dark:text-slate-500">
                  {text.explainability}
                </div>
                {dossier?.explainability_context ? (
                  <div className="mt-3 grid gap-4 lg:grid-cols-2">
                    <div className="rounded-[16px] bg-[#f4f6fb] px-4 py-3 text-[13px] leading-6 text-[#374151] dark:bg-slate-900 dark:text-slate-300">
                      <div className="font-medium text-[#111111] dark:text-slate-100">{text.ranking}</div>
                      <div className="mt-1">{dossier.explainability_context.ranking_summary}</div>
                      <div className="mt-2 space-y-1">
                        {dossier.explainability_context.ranking_drivers.slice(0, 3).map((item) => (
                          <div key={item}>{item}</div>
                        ))}
                      </div>
                    </div>
                    <div className="rounded-[16px] bg-[#f4f6fb] px-4 py-3 text-[13px] leading-6 text-[#374151] dark:bg-slate-900 dark:text-slate-300">
                      <div className="font-medium text-[#111111] dark:text-slate-100">{text.judge}</div>
                      <div className="mt-1">{dossier.explainability_context.judge_summary}</div>
                      <div className="mt-2 space-y-1">
                        {dossier.explainability_context.judge_fail_reasons.slice(0, 3).map((item) => (
                          <div key={item}>{item}</div>
                        ))}
                      </div>
                    </div>
                    <div className="rounded-[16px] bg-[#f4f6fb] px-4 py-3 text-[13px] leading-6 text-[#374151] dark:bg-slate-900 dark:text-slate-300">
                      <div className="font-medium text-[#111111] dark:text-slate-100">Evidence</div>
                      <div className="mt-1">{dossier.explainability_context.evidence_change_summary}</div>
                      <div className="mt-2 space-y-1">
                        {dossier.explainability_context.evidence_changes.slice(0, 3).map((item) => (
                          <div key={item}>{item}</div>
                        ))}
                      </div>
                    </div>
                    <div className="rounded-[16px] bg-[#f4f6fb] px-4 py-3 text-[13px] leading-6 text-[#374151] dark:bg-slate-900 dark:text-slate-300">
                      <div className="font-medium text-[#111111] dark:text-slate-100">{text.simulationExplain}</div>
                      <div className="mt-1">{dossier.explainability_context.simulation_summary}</div>
                      <div className="mt-2 space-y-1">
                        {dossier.explainability_context.simulation_objections.slice(0, 3).map((item) => (
                          <div key={item}>{item}</div>
                        ))}
                      </div>
                    </div>
                  </div>
                ) : (
                  <div className="mt-3 text-[13px] text-[#6b7280] dark:text-slate-400">{text.none}</div>
                )}
              </section>

              <section className="rounded-[22px] border border-[#d6dbe6] bg-white px-5 py-4 dark:border-slate-800 dark:bg-slate-950/70">
                <div className="text-[11px] font-semibold uppercase tracking-[0.14em] text-[#6b7280] dark:text-slate-500">
                  {text.brief}
                </div>
                {dossier?.execution_brief_candidate ? (
                  <div className="mt-3 rounded-[16px] bg-[#f4f6fb] px-4 py-3 text-[13px] leading-6 text-[#374151] dark:bg-slate-900 dark:text-slate-300">
                    <div className="font-medium text-[#111111] dark:text-slate-100">
                      {dossier.execution_brief_candidate.title}
                    </div>
                    <div className="mt-1">{dossier.execution_brief_candidate.prd_summary}</div>
                  </div>
                ) : (
                  <div className="mt-3 text-[13px] text-[#6b7280] dark:text-slate-400">{text.none}</div>
                )}
              </section>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

function StringChipList({ items, emptyLabel }: { items: string[]; emptyLabel: string }) {
  if (!items.length) {
    return <div className="text-[13px] text-[#6b7280] dark:text-slate-400">{emptyLabel}</div>;
  }
  return (
    <div className="flex flex-wrap gap-2">
      {items.map((item) => (
        <Badge key={item} variant="secondary" className="rounded-full bg-[#edf0f6] text-[#4b5563] dark:bg-slate-800 dark:text-slate-300">
          {item}
        </Badge>
      ))}
    </div>
  );
}
