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
      <div className="flex items-center gap-8 border-b border-white/[0.06] px-16 py-0">
        {stepLabels.map((label, i) => (
          <button
            key={i}
            onClick={() => i < step && setStep(i)}
            className={`py-4 text-[13px] font-medium transition-colors border-b-2 cursor-pointer ${
              i === step
                ? "text-[#f5f5f7] border-[#f5f5f7]"
                : i < step
                  ? "text-white/55 border-transparent hover:text-white/70"
                  : "text-white/30 border-transparent cursor-default"
            }`}
          >
            {label}
          </button>
        ))}
      </div>
      {steps[step]}
    </div>
  );
}
