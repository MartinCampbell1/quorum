"use client";

import { useState } from "react";
import { Button } from "@/components/common/button";
import { MODE_LABELS } from "@/lib/constants";
import type { AgentConfig } from "@/lib/types";

interface StepTaskProps {
  mode: string;
  agents: AgentConfig[];
  onLaunch: (task: string, config: Record<string, number>) => void;
  onBack: () => void;
  isLaunching: boolean;
}

export function StepTask({
  mode,
  agents,
  onLaunch,
  onBack,
  isLaunching,
}: StepTaskProps) {
  const [task, setTask] = useState("");
  const [maxRounds, setMaxRounds] = useState(3);

  const needsRounds = ["debate", "democracy", "board"].includes(mode);
  const needsIterations = ["dictator", "creator_critic"].includes(mode);

  return (
    <div className="flex flex-col h-full">
      <div className="flex-1 overflow-y-auto p-8">
        <h2 className="text-xl font-semibold tracking-tight mb-1">
          Describe your task
        </h2>
        <p className="text-sm text-text-muted mb-8">
          What should the {MODE_LABELS[mode]} team work on?
        </p>

        <textarea
          value={task}
          onChange={(e) => setTask(e.target.value)}
          placeholder="Enter your task or question..."
          rows={5}
          className="w-full max-w-xl rounded-xl border border-border bg-bg-card px-4 py-3 text-sm text-text-primary placeholder-text-muted resize-none focus:outline-none focus:ring-2 focus:ring-accent"
          autoFocus
        />

        {(needsRounds || needsIterations) && (
          <div className="mt-6 max-w-xl">
            <label className="text-[10px] uppercase tracking-widest text-text-muted mb-2 block">
              {needsRounds ? "Max rounds" : "Max iterations"}
            </label>
            <input
              type="number"
              min={1}
              max={10}
              value={maxRounds}
              onChange={(e) => setMaxRounds(Number(e.target.value))}
              className="w-20 rounded-lg border border-border bg-bg-secondary px-3 py-1.5 text-xs text-text-primary focus:outline-none focus:ring-2 focus:ring-accent"
            />
          </div>
        )}

        <div className="mt-8 max-w-xl rounded-xl border border-border bg-bg-secondary p-4">
          <div className="text-[10px] uppercase tracking-widest text-text-muted mb-3">
            Summary
          </div>
          <div className="flex flex-wrap gap-2 text-xs">
            <span className="text-text-secondary">Mode:</span>
            <span className="font-medium text-text-primary">
              {MODE_LABELS[mode]}
            </span>
          </div>
          <div className="flex flex-wrap gap-1 mt-2 text-xs">
            <span className="text-text-secondary">Agents:</span>
            {agents.map((a, i) => (
              <span
                key={i}
                className="rounded bg-bg-card px-1.5 py-0.5 font-mono text-[10px] text-text-muted"
              >
                {a.role}({a.provider})
              </span>
            ))}
          </div>
        </div>
      </div>
      <div className="border-t border-border p-4 flex justify-between">
        <Button variant="ghost" onClick={onBack}>
          Back
        </Button>
        <Button
          variant="cta"
          onClick={() => {
            const config: Record<string, number> = {};
            if (needsRounds) config.max_rounds = maxRounds;
            if (needsIterations) config.max_iterations = maxRounds;
            onLaunch(task, config);
          }}
          disabled={!task.trim() || isLaunching}
        >
          {isLaunching ? "Launching..." : "Launch"}
        </Button>
      </div>
    </div>
  );
}
