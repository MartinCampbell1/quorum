"use client";

import { useState, useEffect } from "react";
import { ChevronDown, ChevronUp, ArrowRight, Plus, Trash2, Wrench, Settings2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent } from "@/components/ui/card";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { SelectorChips } from "@/components/ui/selector-chips";
import { formatAgentRole, formatScenarioLabel, MODE_LABELS, PROVIDER_LABELS, roleMonogram } from "@/lib/constants";
import { cn } from "@/lib/utils";
import type { AgentConfig, ToolDefinition } from "@/lib/types";
import { getTools, getPromptTemplates } from "@/lib/api";
import { Stepper } from "./stepper";

interface StepAgentsProps {
  mode: string;
  scenarioId?: string | null;
  scenarioLabel?: string;
  agents: AgentConfig[];
  onChange: (agents: AgentConfig[]) => void;
  onNext: () => void;
  onBack: () => void;
  onOpenSettings: () => void;
}

const providers = ["claude", "gemini", "codex", "minimax"] as const;
const CONNECTION_TOOL_TYPES = new Set(["http_api", "custom_api", "ssh", "neo4j", "mcp_server"]);

export function StepAgents({
  mode,
  scenarioId,
  scenarioLabel,
  agents,
  onChange,
  onNext,
  onBack,
  onOpenSettings,
}: StepAgentsProps) {
  const [expandedIdx, setExpandedIdx] = useState<number | null>(null);
  const [availableTools, setAvailableTools] = useState<ToolDefinition[]>([]);
  const [promptTemplates, setPromptTemplates] = useState<Record<string, { name: string; description: string; prompt: string }>>({});
  const [workspaceDrafts, setWorkspaceDrafts] = useState<Record<string, string>>({});

  useEffect(() => {
    getTools().then((tools) => setAvailableTools(tools)).catch(() => {});
    getPromptTemplates().then((templates) => setPromptTemplates(templates as Record<string, { name: string; description: string; prompt: string }>)).catch(() => {});
  }, []);

  const toolLabels = Object.fromEntries(availableTools.map((t) => [t.key, `${t.icon ?? ""} ${t.name}`.trim()]));
  const toolsByKey = Object.fromEntries(availableTools.map((tool) => [tool.key, tool]));
  const connectionToolKeys = availableTools.filter((tool) => CONNECTION_TOOL_TYPES.has(tool.tool_type ?? "")).map((tool) => tool.key);
  const builtinToolKeys = availableTools.filter((tool) => !CONNECTION_TOOL_TYPES.has(tool.tool_type ?? "")).map((tool) => tool.key);

  function updateAgent(index: number, updates: Partial<AgentConfig>) {
    const next = agents.map((a, i) => (i === index ? { ...a, ...updates } : a));
    onChange(next);
  }

  function addAgent() {
    if (mode === "tournament") {
      const contestantCount = agents.filter((a) => a.role.startsWith("contestant_")).length;
      const newContestant: AgentConfig = {
        role: `contestant_${contestantCount + 1}`,
        provider: "codex",
        system_prompt: "",
        tools: [],
        workspace_paths: [],
      };
      const judgeIndex = agents.findIndex((agent) => agent.role === "judge");
      if (judgeIndex >= 0) {
        onChange([
          ...agents.slice(0, judgeIndex),
          newContestant,
          ...agents.slice(judgeIndex),
        ]);
        return;
      }
      onChange([...agents, newContestant]);
      return;
    }

    const workerCount = agents.filter((a) => a.role.startsWith("worker")).length;
    const newWorker: AgentConfig = {
      role: `worker_${workerCount + 1}`,
      provider: "codex",
      system_prompt: "",
      tools: [],
      workspace_paths: [],
    };
    onChange([...agents, newWorker]);
  }

  function removeAgent(index: number) {
    if (agents.length <= 2) return;
    if (mode === "tournament" && agents[index]?.role === "judge") return;
    onChange(agents.filter((_, i) => i !== index));
  }

  function updateWorkspaceDraft(role: string, value: string) {
    setWorkspaceDrafts((current) => ({ ...current, [role]: value }));
  }

  function addWorkspacePath(index: number) {
    const agent = agents[index];
    if (!agent) return;
    const value = String(workspaceDrafts[agent.role] ?? "").trim();
    if (!value) return;
    const nextPaths = Array.from(new Set([...(agent.workspace_paths ?? []), value]));
    updateAgent(index, { workspace_paths: nextPaths });
    updateWorkspaceDraft(agent.role, "");
  }

  function removeWorkspacePath(index: number, path: string) {
    const agent = agents[index];
    if (!agent) return;
    updateAgent(index, {
      workspace_paths: (agent.workspace_paths ?? []).filter((item) => item !== path),
    });
  }

  function addButtonLabel() {
    if (mode === "tournament") return "Добавить участника";
    return "Добавить воркера";
  }

  function capabilityTone(capability: "native" | "bridged" | "unavailable" | undefined) {
    if (capability === "native") return "border-emerald-200 bg-emerald-50 text-emerald-700";
    if (capability === "bridged") return "border-amber-200 bg-amber-50 text-amber-700";
    return "border-slate-200 bg-white text-slate-500 dark:border-slate-800 dark:bg-slate-950 dark:text-slate-400";
  }

  return (
    <div className="flex h-full flex-col bg-[#f6f7fb] dark:bg-[#05070c]">
      <div className="flex-1 overflow-y-auto">
        <div className="max-w-xl mx-auto px-10 pt-12 pb-10">
          <Stepper currentStep={1} />

          <h2 className="text-[22px] font-semibold tracking-tight leading-tight mb-1.5">
            Настройка агентов
          </h2>
          <p className="text-[13px] text-muted-foreground/60 mb-7">
            Назначьте провайдера и инструменты каждой роли. Раскройте для детальной настройки.
          </p>
          <div className="mb-5 flex flex-wrap items-center gap-2">
            {mode ? (
              <Badge variant="secondary" className="font-medium">
                {MODE_LABELS[mode] ?? mode}
              </Badge>
            ) : null}
            {(scenarioLabel || scenarioId) ? (
              <Badge variant="outline" className="font-medium">
                {scenarioLabel ?? formatScenarioLabel(scenarioId ?? "")}
              </Badge>
            ) : null}
          </div>

          <div className="mb-5 rounded-2xl border border-border/60 bg-white p-4 dark:border-slate-800 dark:bg-slate-950/70">
            <div className="flex items-start justify-between gap-4">
              <div className="min-w-0">
                <div className="flex items-center gap-2">
                  <Settings2 className="h-4 w-4 text-muted-foreground" />
                  <div className="text-[13px] font-medium text-foreground">
                    Внешние подключения
                  </div>
                </div>
                <p className="mt-2 text-[12px] leading-6 text-muted-foreground/70">
                  API, SSH, граф и MCP подключаются в Settings, после чего их можно выдать любому агенту здесь.
                </p>
                <div className="mt-3 flex flex-wrap gap-2">
                  {connectionToolKeys.length > 0 ? (
                    connectionToolKeys.map((toolKey) => (
                      <span
                        key={`connection-${toolKey}`}
                        className="rounded-full border border-border bg-background px-2.5 py-1 text-[10px] text-muted-foreground dark:border-slate-800 dark:bg-slate-950"
                      >
                        {toolLabels[toolKey] ?? toolKey}
                      </span>
                    ))
                  ) : (
                    <span className="rounded-full border border-dashed border-border px-2.5 py-1 text-[10px] text-muted-foreground/70 dark:border-slate-800">
                      Пока подключены только built-ins
                    </span>
                  )}
                </div>
              </div>
              <Button type="button" variant="outline" size="sm" className="shrink-0 text-xs" onClick={onOpenSettings}>
                Открыть Settings
              </Button>
            </div>
          </div>

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
                        {roleMonogram(agent.role, { mode, scenarioId })}
                      </span>
                    </div>
                    <div className="min-w-0 flex-1">
                      <div className="truncate text-xs font-medium text-foreground">
                        {formatAgentRole(agent.role, { mode, scenarioId })}
                      </div>
                      <div className="truncate font-mono text-[10px] text-muted-foreground/60">
                        {agent.role}
                      </div>
                      {(agent.workspace_paths?.length ?? 0) > 0 && (
                        <div className="mt-1 truncate text-[10px] text-muted-foreground/70">
                          {(agent.workspace_paths ?? []).map((path) => path.split("/").filter(Boolean).pop() || path).join(", ")}
                        </div>
                      )}
                    </div>

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
                        disabled={mode === "tournament" && agent.role === "judge"}
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
                        Подключения
                      </label>
                      {connectionToolKeys.length > 0 ? (
                        <SelectorChips
                          options={connectionToolKeys}
                          value={agent.tools ?? []}
                          onChange={(selected) => updateAgent(i, { tools: selected })}
                          labels={toolLabels}
                        />
                      ) : (
                        <div className="rounded-xl border border-dashed border-border/70 bg-background px-3 py-3 text-[11px] leading-relaxed text-muted-foreground/70 dark:border-slate-800 dark:bg-slate-950/60">
                          Подключений пока нет. Добавь `API`, `SSH`, `граф` или `MCP` в Settings, потом вернись сюда и прикрепи их к агенту.
                        </div>
                      )}

                      {builtinToolKeys.length > 0 && (
                        <>
                          <label className="text-[10px] uppercase tracking-widest text-muted-foreground/60 mb-2 mt-4 block font-medium">
                            Built-ins
                          </label>
                          <SelectorChips
                            options={builtinToolKeys}
                            value={agent.tools ?? []}
                            onChange={(selected) => updateAgent(i, { tools: selected })}
                            labels={toolLabels}
                          />
                        </>
                      )}

                      {(agent.tools?.length ?? 0) > 0 && (
                        <div className="mt-2 flex flex-wrap gap-2">
                          {(agent.tools ?? []).map((toolKey) => {
                            const tool = toolsByKey[toolKey];
                            const capability = tool?.compatibility?.[agent.provider];
                            return (
                              <span
                                key={`${agent.role}-${toolKey}`}
                                className={cn(
                                  "rounded-full border px-2.5 py-1 text-[10px] font-medium capitalize",
                                  capabilityTone(capability)
                                )}
                              >
                                {(tool?.name ?? toolKey)}: {capability ?? "unknown"}
                              </span>
                            );
                          })}
                        </div>
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
                        className="w-full rounded-lg border border-border bg-white px-3 py-2.5 text-xs text-foreground placeholder:text-muted-foreground/50 resize-none focus:outline-none focus:ring-2 focus:ring-ring/30 focus:border-ring transition-colors dark:border-slate-800 dark:bg-slate-950/70"
                      />

                      <label className="text-[10px] uppercase tracking-widest text-muted-foreground/60 mb-1.5 mt-4 block font-medium">
                        Рабочие директории агента
                      </label>
                      <p className="mb-2 text-[11px] leading-relaxed text-muted-foreground/70">
                        Укажи папки, которые доступны только этому агенту. Для турнира сюда удобно положить корень конкретного проекта.
                      </p>
                      <div className="flex gap-2">
                        <input
                          value={workspaceDrafts[agent.role] ?? ""}
                          onChange={(e) => updateWorkspaceDraft(agent.role, e.target.value)}
                          placeholder="/Users/example/projects/my-repo"
                          className="flex-1 rounded-lg border border-border bg-white px-3 py-2 text-xs text-foreground placeholder:text-muted-foreground/50 focus:outline-none focus:ring-2 focus:ring-ring/25 dark:border-slate-800 dark:bg-slate-950/70"
                        />
                        <Button type="button" variant="outline" size="sm" onClick={() => addWorkspacePath(i)}>
                          Добавить
                        </Button>
                      </div>
                      {(agent.workspace_paths?.length ?? 0) > 0 && (
                        <div className="mt-2 flex flex-wrap gap-2">
                          {(agent.workspace_paths ?? []).map((path) => (
                            <button
                              key={`${agent.role}-${path}`}
                              type="button"
                              onClick={() => removeWorkspacePath(i, path)}
                              className="rounded-full border border-border bg-white px-3 py-1.5 text-[10px] text-muted-foreground hover:text-foreground dark:border-slate-800 dark:bg-slate-950 dark:text-slate-400 dark:hover:text-slate-100"
                            >
                              {path}
                            </button>
                          ))}
                        </div>
                      )}
                    </div>
                  )}
                </CardContent>
              </Card>
            ))}
          </div>

          {/* Add worker button */}
          <button
            onClick={addAgent}
            className="mt-3 w-full flex items-center justify-center gap-2 rounded-xl border border-dashed border-border/60 py-3 text-[13px] text-muted-foreground hover:text-foreground hover:border-foreground/20 hover:bg-white transition-colors cursor-pointer dark:border-slate-800 dark:hover:bg-slate-950/70"
          >
            <Plus size={14} />
            {addButtonLabel()}
          </button>
        </div>
      </div>

      {/* Footer */}
      <div className="border-t bg-background dark:border-slate-800/80 dark:bg-[#0b0f17]/95">
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
