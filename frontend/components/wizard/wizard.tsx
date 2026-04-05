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
  onOpenSettings: () => void;
  resumeDraft?: boolean;
}

const WIZARD_DRAFT_KEY = "quorum-wizard-draft-v1";

export interface WizardDraft {
  step: number;
  selectedScenarioId: string | null;
  agents: AgentConfig[];
  workspacePresetIds: string[];
  workspacePaths: string[];
  taskDraft?: string;
  launchConfig?: Record<string, unknown>;
}

function readWizardDraft(): WizardDraft | null {
  if (typeof window === "undefined") return null;
  try {
    const raw = window.sessionStorage.getItem(WIZARD_DRAFT_KEY);
    if (!raw) return null;
    return JSON.parse(raw) as WizardDraft;
  } catch {
    return null;
  }
}

export function saveWizardDraft(draft: WizardDraft) {
  if (typeof window === "undefined") return;
  window.sessionStorage.setItem(WIZARD_DRAFT_KEY, JSON.stringify(draft));
}

export function clearWizardDraft() {
  if (typeof window === "undefined") return;
  window.sessionStorage.removeItem(WIZARD_DRAFT_KEY);
}

export function Wizard({ onSessionCreated, onOpenSettings, resumeDraft = false }: WizardProps) {
  const { scenarios, isLoading } = useScenarios();
  const [initialDraft] = useState<WizardDraft | null>(() => (resumeDraft ? readWizardDraft() : null));
  const [step, setStep] = useState(initialDraft?.step ?? 0);
  const [selectedScenarioId, setSelectedScenarioId] = useState<string | null>(initialDraft?.selectedScenarioId ?? null);
  const [agents, setAgents] = useState<AgentConfig[]>(initialDraft?.agents ?? []);
  const [isLaunching, setIsLaunching] = useState(false);
  const [workspacePresetIds, setWorkspacePresetIds] = useState<string[]>(initialDraft?.workspacePresetIds ?? []);
  const [workspacePaths, setWorkspacePaths] = useState<string[]>(initialDraft?.workspacePaths ?? []);
  const [taskDraft, setTaskDraft] = useState(initialDraft?.taskDraft ?? "");
  const [launchConfigDraft, setLaunchConfigDraft] = useState<Record<string, unknown>>(initialDraft?.launchConfig ?? {});
  const [launchError, setLaunchError] = useState<string | null>(null);

  function cloneAgents(source: AgentConfig[]): AgentConfig[] {
    return source.map((agent) => ({
      ...agent,
      tools: [...(agent.tools ?? [])],
      workspace_paths: [...(agent.workspace_paths ?? [])],
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

  useEffect(() => {
    if (resumeDraft) return;
    clearWizardDraft();
  }, [resumeDraft]);

  useEffect(() => {
    if (typeof window === "undefined") return;
    saveWizardDraft({
      step,
      selectedScenarioId,
      agents,
      workspacePresetIds,
      workspacePaths,
      taskDraft,
      launchConfig: launchConfigDraft,
    } satisfies WizardDraft);
  }, [step, selectedScenarioId, agents, workspacePresetIds, workspacePaths, taskDraft, launchConfigDraft]);

  function handleScenarioSelect(scenarioId: string) {
    setLaunchError(null);
    setSelectedScenarioId(scenarioId);
    const scenario = findScenario(scenarios, scenarioId);
    if (scenario) {
      setAgents(cloneAgents(scenario.default_agents));
    }
  }

  async function handleLaunch(task: string, config: Record<string, unknown>) {
    const scenario = findScenario(scenarios, selectedScenarioId);
    if (!scenario) return;
    setIsLaunching(true);
    setLaunchError(null);
    try {
      const result = await runSession({
        mode: scenario.mode,
        task,
        scenario_id: scenario.is_local_fallback ? undefined : scenario.id,
        agents,
        config,
        workspace_preset_ids: workspacePresetIds,
        workspace_paths: workspacePaths,
        attached_tool_ids: Array.from(new Set(agents.flatMap((agent) => agent.tools ?? []))),
      });
      clearWizardDraft();
      onSessionCreated(result.session_id);
    } catch (err) {
      console.error("Launch failed:", err);
      setLaunchError(err instanceof Error ? err.message : "Не удалось запустить сессию.");
    } finally {
      setIsLaunching(false);
    }
  }

  if (isLoading || !scenarios) {
    return (
      <div className="flex h-full items-center justify-center bg-[#f6f7fb] dark:bg-[#05070c]">
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
      mode={selectedScenario?.mode ?? ""}
      scenarioId={selectedScenario?.id}
      scenarioLabel={selectedScenario?.name}
      agents={agents}
      onChange={setAgents}
      onNext={() => setStep(2)}
      onBack={() => setStep(0)}
      onOpenSettings={onOpenSettings}
    />,
    <StepTask
      key={`task-${selectedScenario?.id ?? "none"}`}
      mode={selectedScenario?.mode ?? ""}
      scenarioId={selectedScenario?.id}
      agents={agents}
      onLaunch={handleLaunch}
      onBack={() => setStep(1)}
      isLaunching={isLaunching}
      taskPlaceholder={selectedScenario?.task_placeholder}
      scenarioLabel={selectedScenario?.name}
      workspacePresetIds={workspacePresetIds}
      workspacePaths={workspacePaths}
      onWorkspacePresetIdsChange={setWorkspacePresetIds}
      onWorkspacePathsChange={setWorkspacePaths}
      defaultConfig={selectedScenario?.default_config}
      initialTask={taskDraft}
      initialConfig={launchConfigDraft}
      launchError={launchError}
      onClearLaunchError={() => setLaunchError(null)}
      onDraftChange={(task, config) => {
        setTaskDraft(task);
        setLaunchConfigDraft(config);
      }}
    />,
  ];

  return (
    <div className="flex h-full flex-col bg-[#f6f7fb] dark:bg-[#05070c]">
      {steps[step]}
    </div>
  );
}
