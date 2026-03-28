"use client";

import { useEffect, useMemo, useState } from "react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { FolderTree, Rocket, Wrench } from "lucide-react";
import { formatAgentRole, formatScenarioLabel, MODE_LABELS } from "@/lib/constants";
import { getWorkspacePresets } from "@/lib/api";
import type { AgentConfig, WorkspacePreset } from "@/lib/types";
import { Stepper } from "./stepper";

interface StepTaskProps {
  mode: string;
  scenarioId?: string | null;
  agents: AgentConfig[];
  onLaunch: (task: string, config: Record<string, unknown>) => void;
  onBack: () => void;
  isLaunching: boolean;
  taskPlaceholder?: string;
  scenarioLabel?: string;
  workspacePresetIds: string[];
  workspacePaths: string[];
  onWorkspacePresetIdsChange: (ids: string[]) => void;
  onWorkspacePathsChange: (paths: string[]) => void;
  defaultConfig?: Record<string, number>;
}

export function StepTask({
  mode,
  scenarioId,
  agents,
  onLaunch,
  onBack,
  isLaunching,
  taskPlaceholder,
  scenarioLabel,
  workspacePresetIds,
  workspacePaths,
  onWorkspacePresetIdsChange,
  onWorkspacePathsChange,
  defaultConfig,
}: StepTaskProps) {
  const [task, setTask] = useState("");
  const [maxRounds, setMaxRounds] = useState(defaultConfig?.max_rounds ?? defaultConfig?.max_iterations ?? 3);
  const [unlimited, setUnlimited] = useState(false);
  const [executionMode, setExecutionMode] = useState<"sequential" | "parallel">("sequential");
  const [workspacePresets, setWorkspacePresets] = useState<WorkspacePreset[]>([]);
  const [extraPathDraft, setExtraPathDraft] = useState("");

  const needsRounds = ["debate", "democracy", "board", "tournament"].includes(mode);
  const needsIterations = ["dictator", "creator_critic"].includes(mode);
  const isJudgeVerdictMode = mode === "debate" || mode === "tournament";
  const selectedPresetNames = useMemo(
    () =>
      workspacePresets
        .filter((preset) => workspacePresetIds.includes(preset.id))
        .map((preset) => preset.name),
    [workspacePresets, workspacePresetIds]
  );

  useEffect(() => {
    getWorkspacePresets().then(setWorkspacePresets).catch(() => {});
  }, []);

  function togglePreset(id: string) {
    if (workspacePresetIds.includes(id)) {
      onWorkspacePresetIdsChange(workspacePresetIds.filter((item) => item !== id));
      return;
    }
    onWorkspacePresetIdsChange([...workspacePresetIds, id]);
  }

  function addWorkspacePath() {
    const value = extraPathDraft.trim();
    if (!value) return;
    if (!workspacePaths.includes(value)) {
      onWorkspacePathsChange([...workspacePaths, value]);
    }
    setExtraPathDraft("");
  }

  function removeWorkspacePath(path: string) {
    onWorkspacePathsChange(workspacePaths.filter((item) => item !== path));
  }

  return (
    <div className="flex h-full flex-col bg-[#f6f7fb] dark:bg-[#05070c]">
      <div className="flex-1 overflow-y-auto">
        <div className="max-w-xl mx-auto px-10 pt-12 pb-10">
          <Stepper currentStep={2} />

          <h2 className="text-[22px] font-semibold tracking-tight leading-tight mb-1.5">
            Опишите задачу
          </h2>
          <p className="text-[13px] text-muted-foreground/60 mb-7">
            Над чем должна работать команда{" "}
            <span className="font-medium text-foreground">
              {scenarioLabel ?? MODE_LABELS[mode]}
            </span>
            ?
          </p>

          <textarea
            value={task}
            onChange={(e) => setTask(e.target.value)}
            placeholder={taskPlaceholder ?? "Введите задачу или вопрос..."}
            rows={5}
            className="w-full rounded-xl border border-border bg-white px-4 py-3.5 text-sm text-foreground placeholder:text-muted-foreground/50 resize-none focus:outline-none focus:ring-2 focus:ring-ring/30 focus:border-ring transition-colors leading-relaxed dark:border-slate-800 dark:bg-slate-950/70"
            autoFocus
          />

          {mode === "tournament" && (
            <div className="mt-4 rounded-xl border border-border/60 bg-white p-4 text-[12px] leading-6 text-muted-foreground/80 dark:border-slate-800 dark:bg-slate-950/70">
              <div className="text-[11px] font-semibold uppercase tracking-[0.14em] text-foreground/70">
                Подсказка для турнира
              </div>
              <div className="mt-2">
                Лучше просить турнир не “оценить по баллам”, а выбрать, какой проект сильнее в парных матчах.
              </div>
              <div className="mt-2">
                Хороший фокус задачи: скорость до первых денег, надёжность дохода, сложность запуска для соло-фаундера, масштабируемость и реальный AI-edge.
              </div>
              <div className="mt-3 rounded-lg border border-border/60 bg-[#fbfcff] px-3 py-3 font-mono text-[11px] leading-5 text-[#273142] dark:border-slate-800 dark:bg-slate-900/80 dark:text-slate-300">
                Выберите, какой проект мне стоит развивать первым как соло-фаундеру с сильным AI-стеком, чтобы быстрее выйти к стабильным $2K+/мес. В каждом матче пусть участники защищают свой проект и опровергают оппонента. В финале дайте победителя, второе место, что заморозить и почему.
              </div>
            </div>
          )}

          {mode === "tournament" && (
            <div className="mt-6 rounded-xl border border-border/60 bg-white p-4 dark:border-slate-800 dark:bg-slate-950/70">
              <div className="flex items-start justify-between gap-4">
                <div>
                  <div className="text-[13px] font-medium text-foreground">
                    Режим исполнения турнирной стадии
                  </div>
                  <div className="mt-1 text-[11px] leading-relaxed text-muted-foreground/70">
                    Sequential проще для checkpoint/resume. Parallel быстрее по wall-clock времени, но сложнее по runtime-координации.
                  </div>
                </div>
                <div className="inline-flex rounded-full border border-border bg-[#f7f8fc] p-1 dark:border-slate-800 dark:bg-slate-900/80">
                  {([
                    { value: "sequential", label: "Sequential" },
                    { value: "parallel", label: "Parallel" },
                  ] as const).map((option) => (
                    <button
                      key={option.value}
                      type="button"
                      onClick={() => setExecutionMode(option.value)}
                      className={`rounded-full px-3 py-1.5 text-[11px] font-medium transition-colors ${
                        executionMode === option.value
                          ? "bg-black text-white dark:bg-slate-100 dark:text-slate-950"
                          : "text-muted-foreground hover:text-foreground"
                      }`}
                    >
                      {option.label}
                    </button>
                  ))}
                </div>
              </div>
            </div>
          )}

          {(needsRounds || needsIterations) && (
            <div className="mt-6 rounded-xl border border-border/60 bg-white p-4 dark:border-slate-800 dark:bg-slate-950/70">
              <div className="flex items-center justify-between mb-3">
                <label className="text-[13px] font-medium text-foreground">
                  {mode === "tournament"
                    ? "Раундов в каждом матче"
                    : needsRounds
                      ? "Лимит раундов"
                      : "Лимит итераций"}
                </label>
                <button
                  onClick={() => setUnlimited(!unlimited)}
                  className={`text-[11px] px-2.5 py-1 rounded-md transition-colors cursor-pointer ${
                    unlimited
                      ? "bg-primary text-primary-foreground"
                      : "bg-muted text-muted-foreground hover:text-foreground"
                  }`}
                >
                  {unlimited ? "∞ Без лимита" : "С лимитом"}
                </button>
              </div>
              {!unlimited && (
                <div className="flex items-center gap-3">
                  <input
                    type="range"
                    min={1}
                    max={10}
                    value={maxRounds}
                    onChange={(e) => setMaxRounds(Number(e.target.value))}
                    className="flex-1 accent-primary cursor-pointer"
                  />
                  <span className="font-mono text-sm font-medium text-foreground w-6 text-center">
                    {maxRounds}
                  </span>
                </div>
              )}
              {unlimited && (
                <p className="text-[11px] text-muted-foreground/60">
                  {isJudgeVerdictMode
                    ? mode === "tournament"
                      ? "Каждый матч турнира продолжится до явного финального вердикта судьи. Внутри это всё ещё ограничено защитным верхним порогом."
                      : "Дебаты продолжатся до явного финального вердикта судьи. Внутри это всё ещё ограничено защитным верхним порогом."
                    : needsRounds
                      ? "Раунды будут повторяться до достижения результата или защитного лимита."
                      : "Итерации продолжатся пока критик не одобрит результат"}
                </p>
              )}
              {!unlimited && isJudgeVerdictMode && (
                <p className="mt-3 text-[11px] text-muted-foreground/60">
                  {mode === "tournament"
                    ? `При лимите в ${maxRounds} каждый матч по умолчанию использует весь бюджет раундов. Судья сможет завершить конкретный матч раньше только явным финальным вердиктом.`
                    : `При лимите в ${maxRounds} система по умолчанию использует весь бюджет раундов. Судья сможет завершить спор раньше только явным финальным вердиктом.`}
                </p>
              )}
            </div>
          )}

          <div className="mt-6 rounded-xl border border-border/60 bg-white p-4 dark:border-slate-800 dark:bg-slate-950/70">
            <div className="flex items-center gap-2 mb-3">
              <FolderTree className="h-4 w-4 text-muted-foreground" />
              <label className="text-[13px] font-medium text-foreground">
                Дополнительные рабочие директории
              </label>
            </div>
            <p className="mb-3 text-[11px] leading-relaxed text-muted-foreground/70">
              Подключи сохранённые workspace presets и добавь одноразовые директории для текущего запуска.
            </p>

            {workspacePresets.length > 0 ? (
              <div className="mb-4 flex flex-wrap gap-2">
                {workspacePresets.map((preset) => {
                  const active = workspacePresetIds.includes(preset.id);
                  return (
                    <button
                      key={preset.id}
                      type="button"
                      onClick={() => togglePreset(preset.id)}
                      className={`rounded-full border px-3 py-1.5 text-[11px] transition-colors ${
                        active
                          ? "border-black bg-black text-white dark:border-slate-100 dark:bg-slate-100 dark:text-slate-950"
                          : "border-border bg-white text-muted-foreground hover:text-foreground dark:border-slate-800 dark:bg-slate-950 dark:text-slate-400 dark:hover:text-slate-100"
                      }`}
                    >
                      {preset.name}
                    </button>
                  );
                })}
              </div>
            ) : (
              <p className="mb-4 text-[11px] text-muted-foreground/60">
                Workspace presets пока не настроены. Добавь их в Settings.
              </p>
            )}

            <div className="flex gap-2">
              <input
                value={extraPathDraft}
                onChange={(e) => setExtraPathDraft(e.target.value)}
                placeholder="/Users/example/projects/trading-data"
                className="flex-1 rounded-lg border border-border bg-white px-3 py-2 text-xs text-foreground placeholder:text-muted-foreground/50 focus:outline-none focus:ring-2 focus:ring-ring/25 dark:border-slate-800 dark:bg-slate-950/70"
              />
              <Button type="button" variant="outline" size="sm" onClick={addWorkspacePath}>
                Добавить путь
              </Button>
            </div>

            {(selectedPresetNames.length > 0 || workspacePaths.length > 0) && (
              <div className="mt-4 space-y-2">
                {selectedPresetNames.length > 0 && (
                  <div className="flex flex-wrap gap-2">
                    {selectedPresetNames.map((name) => (
                      <Badge key={name} variant="secondary" className="text-[10px]">
                        preset: {name}
                      </Badge>
                    ))}
                  </div>
                )}
                {workspacePaths.length > 0 && (
                  <div className="flex flex-wrap gap-2">
                    {workspacePaths.map((path) => (
                      <button
                        key={path}
                        type="button"
                        onClick={() => removeWorkspacePath(path)}
                        className="rounded-full border border-border bg-white px-3 py-1.5 text-[10px] text-muted-foreground hover:text-foreground dark:border-slate-800 dark:bg-slate-950 dark:text-slate-400 dark:hover:text-slate-100"
                      >
                        {path}
                      </button>
                    ))}
                  </div>
                )}
              </div>
            )}
          </div>

          {/* Summary */}
          <div className="mt-8 rounded-xl border border-border/60 bg-white p-5">
            <div className="text-[10px] uppercase tracking-[0.15em] text-muted-foreground/50 font-semibold mb-4">
              Итого
            </div>
            <div className="flex items-center gap-2 text-[13px] mb-3">
              <span className="text-muted-foreground">Режим</span>
              <Badge variant="secondary" className="font-medium">{MODE_LABELS[mode]}</Badge>
              {(scenarioLabel || scenarioId) && (
                <Badge variant="outline" className="font-medium">
                  {scenarioLabel ?? formatScenarioLabel(scenarioId ?? "")}
                </Badge>
              )}
            </div>
            <div className="flex flex-col gap-2 text-[13px]">
              <span className="text-muted-foreground">Агенты</span>
              {agents.map((a) => (
                <div key={a.role} className="flex items-center gap-2 pl-2">
                  <Badge variant="outline" className="font-mono text-[10px] font-normal">
                    {formatAgentRole(a.role, { mode, scenarioId })}
                  </Badge>
                  {(a.workspace_paths?.length ?? 0) > 0 && (
                    <span className="text-[10px] text-muted-foreground/70">
                      {(a.workspace_paths ?? []).map((path) => path.split("/").filter(Boolean).pop() || path).join(", ")}
                    </span>
                  )}
                  {(a.tools?.length ?? 0) > 0 && (
                    <span className="flex items-center gap-1 text-[10px] text-muted-foreground/60">
                      <Wrench size={9} />
                      {(a.tools ?? []).join(", ")}
                    </span>
                  )}
                </div>
              ))}
            </div>
            {(selectedPresetNames.length > 0 || workspacePaths.length > 0) && (
              <div className="mt-4 flex flex-col gap-2 text-[13px]">
                <span className="text-muted-foreground">Workspaces</span>
                {selectedPresetNames.map((name) => (
                  <div key={name} className="pl-2 text-[11px] text-muted-foreground/80">
                    preset: {name}
                  </div>
                ))}
                {workspacePaths.map((path) => (
                  <div key={path} className="pl-2 text-[11px] text-muted-foreground/80">
                    path: {path}
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Footer */}
      <div className="border-t bg-background">
        <div className="max-w-xl mx-auto px-10 py-4 flex justify-between">
          <Button variant="ghost" onClick={onBack} className="text-muted-foreground">
            Назад
          </Button>
          <Button
            onClick={() => {
              const config: Record<string, unknown> = {};
              if (needsRounds) config.max_rounds = unlimited ? 99 : maxRounds;
              if (needsIterations) config.max_iterations = unlimited ? 99 : maxRounds;
              if (mode === "tournament") config.execution_mode = executionMode;
              onLaunch(task, config);
            }}
            disabled={!task.trim() || isLaunching}
          >
            {isLaunching ? (
              <span className="flex items-center gap-2">
                <div className="h-3 w-3 rounded-full border-2 border-current border-t-transparent animate-spin" />
                Запуск...
              </span>
            ) : (
              <span className="flex items-center gap-2">
                <Rocket className="h-3.5 w-3.5" /> Запуск
              </span>
            )}
          </Button>
        </div>
      </div>
    </div>
  );
}
