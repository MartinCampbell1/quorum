"use client";

import { useState } from "react";
import { ChevronDown, ChevronUp } from "lucide-react";
import { Button } from "@/components/common/button";
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
    const next = agents.map((a, i) =>
      i === index ? { ...a, ...updates } : a
    );
    onChange(next);
  }

  return (
    <div className="flex flex-col h-full">
      <div className="flex-1 overflow-y-auto p-8">
        <h2 className="text-xl font-semibold tracking-tight mb-1">
          Configure agents
        </h2>
        <p className="text-sm text-text-muted mb-8">
          Assign providers to each role. Expand to set custom prompts.
        </p>
        <div className="flex flex-col gap-3 max-w-xl">
          {agents.map((agent, i) => (
            <div
              key={i}
              className="rounded-xl border border-border bg-bg-card overflow-hidden"
            >
              <div className="flex items-center gap-3 px-4 py-3">
                <span className="font-mono text-xs font-medium text-text-secondary w-28 truncate">
                  {agent.role}
                </span>
                <select
                  value={agent.provider}
                  onChange={(e) =>
                    updateAgent(i, {
                      provider: e.target.value as AgentConfig["provider"],
                    })
                  }
                  className="rounded-lg border border-border bg-bg-secondary px-3 py-1.5 text-xs text-text-primary cursor-pointer focus:outline-none focus:ring-2 focus:ring-accent"
                >
                  {providers.map((p) => (
                    <option key={p} value={p}>
                      {PROVIDER_LABELS[p]}
                    </option>
                  ))}
                </select>
                <button
                  onClick={() =>
                    setExpandedIdx(expandedIdx === i ? null : i)
                  }
                  className="ml-auto text-text-muted hover:text-text-secondary cursor-pointer"
                  aria-label="Toggle prompt editor"
                >
                  {expandedIdx === i ? (
                    <ChevronUp size={14} />
                  ) : (
                    <ChevronDown size={14} />
                  )}
                </button>
              </div>
              {expandedIdx === i && (
                <div className="border-t border-border px-4 py-3">
                  <label className="text-[10px] uppercase tracking-widest text-text-muted mb-1 block">
                    System prompt
                  </label>
                  <textarea
                    value={agent.system_prompt}
                    onChange={(e) =>
                      updateAgent(i, { system_prompt: e.target.value })
                    }
                    placeholder="Optional custom instructions for this agent..."
                    rows={3}
                    className="w-full rounded-lg border border-border bg-bg-secondary px-3 py-2 text-xs text-text-primary placeholder-text-muted resize-none focus:outline-none focus:ring-2 focus:ring-accent"
                  />
                </div>
              )}
            </div>
          ))}
        </div>
      </div>
      <div className="border-t border-border p-4 flex justify-between">
        <Button variant="ghost" onClick={onBack}>
          Back
        </Button>
        <Button onClick={onNext}>Next</Button>
      </div>
    </div>
  );
}
