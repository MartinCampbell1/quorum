"use client";

import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Rocket } from "lucide-react";
import { MODE_LABELS } from "@/lib/constants";
import type { AgentConfig } from "@/lib/types";

interface StepTaskProps {
  mode: string;
  agents: AgentConfig[];
  onLaunch: (task: string, config: Record<string, number>) => void;
  onBack: () => void;
  isLaunching: boolean;
}

export function StepTask({ mode, agents, onLaunch, onBack, isLaunching }: StepTaskProps) {
  const [task, setTask] = useState("");
  const [maxRounds, setMaxRounds] = useState(3);

  const needsRounds = ["debate", "democracy", "board"].includes(mode);
  const needsIterations = ["dictator", "creator_critic"].includes(mode);

  return (
    <div className="flex flex-col h-full">
      <div className="flex-1 overflow-y-auto">
        <div className="max-w-xl mx-auto px-8 pt-10 pb-8">
          <h2 className="text-2xl font-bold tracking-tight mb-2">Describe your task</h2>
          <p className="text-sm text-muted-foreground mb-8">
            What should the {MODE_LABELS[mode]} team work on?
          </p>

          <textarea
            value={task}
            onChange={(e) => setTask(e.target.value)}
            placeholder="Enter your task or question..."
            rows={5}
            className="w-full rounded-lg border bg-background px-4 py-3 text-sm placeholder:text-muted-foreground resize-none focus:outline-none focus:ring-2 focus:ring-ring"
            autoFocus
          />

          {(needsRounds || needsIterations) && (
            <div className="mt-6">
              <label className="text-xs text-muted-foreground mb-2 block">
                {needsRounds ? "Max rounds" : "Max iterations"}
              </label>
              <input
                type="number"
                min={1}
                max={10}
                value={maxRounds}
                onChange={(e) => setMaxRounds(Number(e.target.value))}
                className="w-20 rounded-md border bg-background px-3 py-1.5 text-xs focus:outline-none focus:ring-2 focus:ring-ring"
              />
            </div>
          )}

          <Card className="mt-8">
            <CardContent className="p-4">
              <div className="text-[10px] uppercase tracking-widest text-muted-foreground mb-3">Summary</div>
              <div className="flex items-center gap-2 text-xs mb-2">
                <span className="text-muted-foreground">Mode:</span>
                <Badge variant="secondary">{MODE_LABELS[mode]}</Badge>
              </div>
              <div className="flex flex-wrap gap-1 text-xs">
                <span className="text-muted-foreground">Agents:</span>
                {agents.map((a, i) => (
                  <Badge key={i} variant="outline" className="font-mono text-[10px]">
                    {a.role}
                  </Badge>
                ))}
              </div>
            </CardContent>
          </Card>
        </div>
      </div>
      <div className="border-t px-8 py-4 flex justify-between">
        <Button variant="ghost" onClick={onBack}>Back</Button>
        <Button
          onClick={() => {
            const config: Record<string, number> = {};
            if (needsRounds) config.max_rounds = maxRounds;
            if (needsIterations) config.max_iterations = maxRounds;
            onLaunch(task, config);
          }}
          disabled={!task.trim() || isLaunching}
        >
          {isLaunching ? "Launching..." : <><Rocket className="mr-2 h-4 w-4" /> Launch</>}
        </Button>
      </div>
    </div>
  );
}
