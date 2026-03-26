"use client";

import { useEffect, useState } from "react";
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

  function cloneAgents(source: AgentConfig[]): AgentConfig[] {
    return source.map((agent) => ({
      ...agent,
      tools: [...(agent.tools ?? [])],
    }));
  }

  useEffect(() => {
    if (!modes || Object.keys(modes).length === 0) return;
    if (selectedMode && modes[selectedMode]) return;

    const firstMode = Object.keys(modes)[0];
    if (!firstMode) return;

    setSelectedMode(firstMode);
    setAgents(cloneAgents(modes[firstMode].default_agents));
    setStep(0);
  }, [modes, selectedMode]);

  function handleModeSelect(mode: string) {
    setSelectedMode(mode);
    if (modes?.[mode]) {
      setAgents(cloneAgents(modes[mode].default_agents));
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
      <div className="flex h-full items-center justify-center">
        <div className="flex items-center gap-3">
          <div
            className="h-2 w-2 rounded-full bg-foreground/20"
            style={{ animation: "pulse-dot 1.5s ease-in-out infinite" }}
          />
          <span className="text-[13px] text-muted-foreground">Загрузка режимов...</span>
        </div>
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

  return (
    <div className="flex flex-col h-full">
      {steps[step]}
    </div>
  );
}
