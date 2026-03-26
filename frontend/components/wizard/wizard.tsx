"use client";

import { useEffect, useState } from "react";
import { useScenarios } from "@/hooks/use-scenarios";
import { runSession } from "@/lib/api";
import { StepScenario } from "./step-scenario";
import { StepAgents } from "./step-agents";
import { StepTask } from "./step-task";
import type { AgentConfig, ScenarioDefinition } from "@/lib/types";

interface WizardProps {
  onSessionCreated: (sessionId: string) => void;
}

export function Wizard({ onSessionCreated }: WizardProps) {
  const { scenarios, isLoading } = useScenarios();
  const [step, setStep] = useState(0);
  const [selectedScenarioId, setSelectedScenarioId] = useState<string | null>(null);
  const [agents, setAgents] = useState<AgentConfig[]>([]);
  const [isLaunching, setIsLaunching] = useState(false);

  function cloneAgents(source: AgentConfig[]): AgentConfig[] {
    return source.map((agent) => ({
      ...agent,
      tools: [...(agent.tools ?? [])],
    }));
  }

  function findScenario(list: ScenarioDefinition[] | undefined, scenarioId: string | null) {
    return list?.find((scenario) => scenario.id === scenarioId) ?? null;
  }

  useEffect(() => {
    if (!scenarios || scenarios.length === 0) return;
    const selectedScenario = findScenario(scenarios, selectedScenarioId);
    if (selectedScenario) return;

    const firstScenario = scenarios[0];
    if (!firstScenario) return;

    setSelectedScenarioId(firstScenario.id);
    setAgents(cloneAgents(firstScenario.default_agents));
    setStep(0);
  }, [scenarios, selectedScenarioId]);

  function handleScenarioSelect(scenarioId: string) {
    setSelectedScenarioId(scenarioId);
    const scenario = findScenario(scenarios, scenarioId);
    if (scenario) {
      setAgents(cloneAgents(scenario.default_agents));
    }
  }

  async function handleLaunch(task: string, config: Record<string, number>) {
    const scenario = findScenario(scenarios, selectedScenarioId);
    if (!scenario) return;
    setIsLaunching(true);
    try {
      const result = await runSession({
        mode: scenario.mode,
        task,
        scenario_id: scenario.id,
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

  if (isLoading || !scenarios) {
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

  const selectedScenario = findScenario(scenarios, selectedScenarioId);

  const steps = [
    <StepScenario
      key="scenario"
      scenarios={scenarios}
      selectedId={selectedScenarioId}
      onSelect={handleScenarioSelect}
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
      mode={selectedScenario?.mode ?? ""}
      agents={agents}
      onLaunch={handleLaunch}
      onBack={() => setStep(1)}
      isLaunching={isLaunching}
      taskPlaceholder={selectedScenario?.task_placeholder}
      scenarioLabel={selectedScenario?.name}
    />,
  ];

  return (
    <div className="flex flex-col h-full">
      {steps[step]}
    </div>
  );
}
