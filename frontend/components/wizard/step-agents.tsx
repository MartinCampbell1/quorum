"use client";

import { useState, useEffect } from "react";
import { ChevronDown, ChevronUp, ArrowRight, Plus, Trash2, Wrench } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { SelectorChips } from "@/components/ui/selector-chips";
import { PROVIDER_LABELS } from "@/lib/constants";
import { cn } from "@/lib/utils";
import type { AgentConfig } from "@/lib/types";
import { getTools, getPromptTemplates } from "@/lib/api";
import { Stepper } from "./stepper";

interface StepAgentsProps {
  agents: AgentConfig[];
  onChange: (agents: AgentConfig[]) => void;
  onNext: () => void;
  onBack: () => void;
}

const providers = ["claude", "gemini", "codex", "minimax"] as const;

export function StepAgents({ agents, onChange, onNext, onBack }: StepAgentsProps) {
  const [expandedIdx, setExpandedIdx] = useState<number | null>(null);
  const [availableTools, setAvailableTools] = useState<{ key: string; name: string; icon?: string }[]>([]);
  const [promptTemplates, setPromptTemplates] = useState<Record<string, { name: string; description: string; prompt: string }>>({});

  useEffect(() => {
    getTools().then((tools: any[]) => setAvailableTools(tools)).catch(() => {});
    getPromptTemplates().then((templates) => setPromptTemplates(templates as Record<string, { name: string; description: string; prompt: string }>)).catch(() => {});
  }, []);

  const toolKeys = availableTools.map((t) => t.key);
  const toolLabels = Object.fromEntries(availableTools.map((t) => [t.key, `${t.icon ?? ""} ${t.name}`.trim()]));

  function updateAgent(index: number, updates: Partial<AgentConfig>) {
    const next = agents.map((a, i) => (i === index ? { ...a, ...updates } : a));
    onChange(next);
  }

  function addWorker() {
    const workerCount = agents.filter((a) => a.role.startsWith("worker")).length;
    const newWorker: AgentConfig = {
      role: `worker_${workerCount + 1}`,
      provider: "codex",
      system_prompt: "",
      tools: [],
    };
    onChange([...agents, newWorker]);
  }

  function removeAgent(index: number) {
    if (agents.length <= 2) return;
    onChange(agents.filter((_, i) => i !== index));
  }

  return (
    <div className="flex flex-col h-full">
      <div className="flex-1 overflow-y-auto">
        <div className="max-w-xl mx-auto px-10 pt-12 pb-10">
          <Stepper currentStep={1} />

          <h2 className="text-[22px] font-semibold tracking-tight leading-tight mb-1.5">
            Настройка агентов
          </h2>
          <p className="text-[13px] text-muted-foreground/60 mb-7">
            Назначьте провайдера и инструменты каждой роли. Раскройте для детальной настройки.
          </p>

          <div className="flex flex-col gap-2.5">
            {agents.map((agent, i) => (
              <Card key={agent.role} className={cn(
                "py-0 transition-shadow duration-200",
                expandedIdx === i && "shadow-sm"
              )}>
                <CardContent className="px-4 py-3.5">
                  <div className="flex items-center gap-3">
                    <div className="flex h-8 w-8 items-center justify-center rounded-md bg-muted text-muted-foreground">
                      <span className="font-mono text-[10px] font-semibold uppercase">
                        {agent.role.slice(0, 2)}
                      </span>
                    </div>
                    <span className="font-mono text-xs font-medium text-foreground truncate flex-1">
                      {agent.role}
                    </span>

                    {/* Tool count badge */}
                    {(agent.tools?.length ?? 0) > 0 && (
                      <span className="flex items-center gap-1 text-[10px] text-muted-foreground bg-muted px-1.5 py-0.5 rounded-full">
                        <Wrench size={10} />
                        {agent.tools?.length}
                      </span>
                    )}

                    <Select
                      value={agent.provider}
                      onValueChange={(v) => updateAgent(i, { provider: v as AgentConfig["provider"] })}
                    >
                      <SelectTrigger className="w-28 h-7 text-xs">
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        {providers.map((p) => (
                          <SelectItem key={p} value={p} className="text-xs">
                            {PROVIDER_LABELS[p]}
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                    <button
                      onClick={() => setExpandedIdx(expandedIdx === i ? null : i)}
                      className="ml-1 p-1 rounded-md text-muted-foreground hover:text-foreground hover:bg-muted transition-colors cursor-pointer"
                    >
                      {expandedIdx === i ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
                    </button>
                    {agents.length > 2 && (
                      <button
                        onClick={() => removeAgent(i)}
                        className="p-1 rounded-md text-muted-foreground/40 hover:text-destructive hover:bg-destructive/10 transition-colors cursor-pointer"
                        aria-label="Удалить агента"
                      >
                        <Trash2 size={13} />
                      </button>
                    )}
                  </div>
                  {expandedIdx === i && (
                    <div className="mt-3 pt-3 border-t border-border/50" style={{ animation: "fade-in 0.15s ease-out" }}>
                      {/* Tools section */}
                      <label className="text-[10px] uppercase tracking-widest text-muted-foreground/60 mb-2 block font-medium">
                        Инструменты
                      </label>
                      {toolKeys.length > 0 ? (
                        <SelectorChips
                          options={toolKeys}
                          value={agent.tools ?? []}
                          onChange={(selected) => updateAgent(i, { tools: selected })}
                          labels={toolLabels}
                        />
                      ) : (
                        <p className="text-[11px] leading-relaxed text-muted-foreground/60">
                          Нет настроенных инструментов. Добавьте их в Настройках.
                        </p>
                      )}

                      {/* Prompt template section */}
                      <label className="text-[10px] uppercase tracking-widest text-muted-foreground/60 mb-1.5 mt-4 block font-medium">
                        Шаблон промпта
                      </label>
                      <Select
                        onValueChange={(templateKey) => {
                          if (typeof templateKey !== "string") return;
                          const tmpl = promptTemplates[templateKey];
                          if (tmpl) updateAgent(i, { system_prompt: tmpl.prompt });
                        }}
                      >
                        <SelectTrigger className="h-8 text-xs">
                          <SelectValue placeholder="Выбрать шаблон..." />
                        </SelectTrigger>
                        <SelectContent>
                          {Object.entries(promptTemplates).map(([key, tmpl]) => (
                            <SelectItem key={key} value={key} className="text-xs">
                              {tmpl.name} — {tmpl.description}
                            </SelectItem>
                          ))}
                        </SelectContent>
                      </Select>

                      {/* System prompt section */}
                      <label className="text-[10px] uppercase tracking-widest text-muted-foreground/60 mb-1.5 mt-4 block font-medium">
                        Системный промпт
                      </label>
                      <textarea
                        value={agent.system_prompt}
                        onChange={(e) => updateAgent(i, { system_prompt: e.target.value })}
                        placeholder="Дополнительные инструкции для агента..."
                        rows={3}
                        className="w-full rounded-lg border border-border bg-muted/30 px-3 py-2.5 text-xs text-foreground placeholder:text-muted-foreground/50 resize-none focus:outline-none focus:ring-2 focus:ring-ring/30 focus:border-ring transition-colors"
                      />
                    </div>
                  )}
                </CardContent>
              </Card>
            ))}
          </div>

          {/* Add worker button */}
          <button
            onClick={addWorker}
            className="mt-3 w-full flex items-center justify-center gap-2 rounded-xl border border-dashed border-border/60 py-3 text-[13px] text-muted-foreground hover:text-foreground hover:border-foreground/20 hover:bg-muted/30 transition-colors cursor-pointer"
          >
            <Plus size={14} />
            Добавить воркера
          </button>
        </div>
      </div>

      {/* Footer */}
      <div className="border-t bg-background">
        <div className="max-w-xl mx-auto px-10 py-4 flex justify-between">
          <Button variant="ghost" onClick={onBack} className="text-muted-foreground">
            Назад
          </Button>
          <Button onClick={onNext}>
            Далее <ArrowRight className="ml-1.5 h-3.5 w-3.5" />
          </Button>
        </div>
      </div>
    </div>
  );
}
