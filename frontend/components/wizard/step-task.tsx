"use client";

import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Rocket, Wrench } from "lucide-react";
import { MODE_LABELS } from "@/lib/constants";
import type { AgentConfig } from "@/lib/types";
import { Stepper } from "./stepper";

interface StepTaskProps {
  mode: string;
  agents: AgentConfig[];
  onLaunch: (task: string, config: Record<string, number>) => void;
  onBack: () => void;
  isLaunching: boolean;
  taskPlaceholder?: string;
  scenarioLabel?: string;
}

export function StepTask({
  mode,
  agents,
  onLaunch,
  onBack,
  isLaunching,
  taskPlaceholder,
  scenarioLabel,
}: StepTaskProps) {
  const [task, setTask] = useState("");
  const [maxRounds, setMaxRounds] = useState(3);
  const [unlimited, setUnlimited] = useState(false);

  const needsRounds = ["debate", "democracy", "board"].includes(mode);
  const needsIterations = ["dictator", "creator_critic"].includes(mode);

  return (
    <div className="flex flex-col h-full">
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
            className="w-full rounded-xl border border-border bg-muted/20 px-4 py-3.5 text-sm text-foreground placeholder:text-muted-foreground/50 resize-none focus:outline-none focus:ring-2 focus:ring-ring/30 focus:border-ring transition-colors leading-relaxed"
            autoFocus
          />

          {(needsRounds || needsIterations) && (
            <div className="mt-6 rounded-xl border border-border/60 bg-muted/20 p-4">
              <div className="flex items-center justify-between mb-3">
                <label className="text-[13px] font-medium text-foreground">
                  {needsRounds ? "Лимит раундов" : "Лимит итераций"}
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
                  {needsRounds
                    ? "Агенты будут спорить пока не придут к консенсусу"
                    : "Итерации продолжатся пока критик не одобрит результат"}
                </p>
              )}
            </div>
          )}

          {/* Summary */}
          <div className="mt-8 rounded-xl border border-border/60 bg-muted/20 p-5">
            <div className="text-[10px] uppercase tracking-[0.15em] text-muted-foreground/50 font-semibold mb-4">
              Итого
            </div>
            <div className="flex items-center gap-2 text-[13px] mb-3">
              <span className="text-muted-foreground">Режим</span>
              <Badge variant="secondary" className="font-medium">{MODE_LABELS[mode]}</Badge>
              {scenarioLabel && (
                <Badge variant="outline" className="font-medium">{scenarioLabel}</Badge>
              )}
            </div>
            <div className="flex flex-col gap-2 text-[13px]">
              <span className="text-muted-foreground">Агенты</span>
              {agents.map((a) => (
                <div key={a.role} className="flex items-center gap-2 pl-2">
                  <Badge variant="outline" className="font-mono text-[10px] font-normal">
                    {a.role}
                  </Badge>
                  {(a.tools?.length ?? 0) > 0 && (
                    <span className="flex items-center gap-1 text-[10px] text-muted-foreground/60">
                      <Wrench size={9} />
                      {(a.tools ?? []).join(", ")}
                    </span>
                  )}
                </div>
              ))}
            </div>
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
              const config: Record<string, number> = {};
              if (needsRounds) config.max_rounds = unlimited ? 99 : maxRounds;
              if (needsIterations) config.max_iterations = unlimited ? 99 : maxRounds;
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
