"use client";

import { useState } from "react";
import { useModes } from "@/hooks/use-modes";
import { runSession } from "@/lib/api";
import { StepMode } from "./step-mode";
import { StepAgents } from "./step-agents";
import { StepTask } from "./step-task";
import type { AgentConfig } from "@/lib/types";

interface WizardProps {
  onSessionCreated: (sessionId: string) => void;
}

export function Wizard({ onSessionCreated }: WizardProps) {
  const { modes, isLoading } = useModes();
  const [step, setStep] = useState(0);
  const [selectedMode, setSelectedMode] = useState<string | null>(null);
  const [agents, setAgents] = useState<AgentConfig[]>([]);
  const [isLaunching, setIsLaunching] = useState(false);

  function handleModeSelect(mode: string) {
    setSelectedMode(mode);
    if (modes?.[mode]) {
      setAgents(modes[mode].default_agents);
    }
  }

  async function handleLaunch(task: string, config: Record<string, number>) {
    if (!selectedMode) return;
    setIsLaunching(true);
    try {
      const result = await runSession({
        mode: selectedMode,
        task,
        agents,
        config,
      });
      onSessionCreated(result.session_id);
    } catch (err) {
      console.error("Launch failed:", err);
    } finally {
      setIsLaunching(false);
    }
  }

  if (isLoading || !modes) {
    return (
      <div className="flex h-full items-center justify-center text-sm text-text-muted">
        Loading modes...
      </div>
    );
  }

  const steps = [
    <StepMode
      key="mode"
      modes={modes}
      selected={selectedMode}
      onSelect={handleModeSelect}
      onNext={() => setStep(1)}
    />,
    <StepAgents
      key="agents"
      agents={agents}
      onChange={setAgents}
      onNext={() => setStep(2)}
      onBack={() => setStep(0)}
    />,
    <StepTask
      key="task"
      mode={selectedMode ?? ""}
      agents={agents}
      onLaunch={handleLaunch}
      onBack={() => setStep(1)}
      isLaunching={isLaunching}
    />,
  ];

  const stepLabels = ["Mode", "Agents", "Task"];

  return (
    <div className="flex flex-col h-full">
      <div className="flex items-center gap-2 border-b border-border px-8 py-3">
        {stepLabels.map((label, i) => (
          <div key={i} className="flex items-center gap-2">
            <div
              className={`flex h-6 w-6 items-center justify-center rounded-full text-[10px] font-bold ${
                i === step
                  ? "bg-accent text-white"
                  : i < step
                    ? "bg-green-950 text-success"
                    : "bg-bg-card text-text-muted"
              }`}
            >
              {i + 1}
            </div>
            <span
              className={`text-xs font-medium ${
                i === step ? "text-text-primary" : "text-text-muted"
              }`}
            >
              {label}
            </span>
            {i < stepLabels.length - 1 && (
              <div className="mx-2 h-px w-8 bg-border" />
            )}
          </div>
        ))}
      </div>
      {steps[step]}
    </div>
  );
}
