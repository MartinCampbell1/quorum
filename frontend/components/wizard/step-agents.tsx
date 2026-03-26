"use client";

import { useState } from "react";
import { ChevronDown, ChevronUp } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { PROVIDER_LABELS } from "@/lib/constants";
import type { AgentConfig } from "@/lib/types";

interface StepAgentsProps {
  agents: AgentConfig[];
  onChange: (agents: AgentConfig[]) => void;
  onNext: () => void;
  onBack: () => void;
}

const providers = ["claude", "gemini", "codex", "minimax"] as const;

export function StepAgents({ agents, onChange, onNext, onBack }: StepAgentsProps) {
  const [expandedIdx, setExpandedIdx] = useState<number | null>(null);

  function updateAgent(index: number, updates: Partial<AgentConfig>) {
    const next = agents.map((a, i) => (i === index ? { ...a, ...updates } : a));
    onChange(next);
  }

  return (
    <div className="flex flex-col h-full">
      <div className="flex-1 overflow-y-auto">
        <div className="max-w-xl mx-auto px-8 pt-10 pb-8">
          <h2 className="text-2xl font-bold tracking-tight mb-2">Configure agents</h2>
          <p className="text-sm text-muted-foreground mb-8">
            Assign a provider to each role. Expand to customize prompts.
          </p>
          <div className="flex flex-col gap-3">
            {agents.map((agent, i) => (
              <Card key={i}>
                <CardContent className="p-4">
                  <div className="flex items-center gap-3">
                    <span className="font-mono text-xs font-medium text-muted-foreground w-28 truncate">
                      {agent.role}
                    </span>
                    <Select
                      value={agent.provider}
                      onValueChange={(v) => updateAgent(i, { provider: v as AgentConfig["provider"] })}
                    >
                      <SelectTrigger className="w-32 h-8 text-xs">
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        {providers.map((p) => (
                          <SelectItem key={p} value={p}>{PROVIDER_LABELS[p]}</SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                    <button
                      onClick={() => setExpandedIdx(expandedIdx === i ? null : i)}
                      className="ml-auto text-muted-foreground hover:text-foreground cursor-pointer"
                    >
                      {expandedIdx === i ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
                    </button>
                  </div>
                  {expandedIdx === i && (
                    <div className="mt-3 pt-3 border-t">
                      <label className="text-[10px] uppercase tracking-widest text-muted-foreground mb-1 block">
                        System prompt
                      </label>
                      <textarea
                        value={agent.system_prompt}
                        onChange={(e) => updateAgent(i, { system_prompt: e.target.value })}
                        placeholder="Optional instructions..."
                        rows={3}
                        className="w-full rounded-md border bg-background px-3 py-2 text-xs placeholder:text-muted-foreground resize-none focus:outline-none focus:ring-2 focus:ring-ring"
                      />
                    </div>
                  )}
                </CardContent>
              </Card>
            ))}
          </div>
        </div>
      </div>
      <div className="border-t px-8 py-4 flex justify-between">
        <Button variant="ghost" onClick={onBack}>Back</Button>
        <Button onClick={onNext}>Next</Button>
      </div>
    </div>
  );
}
