"use client";

import { useEffect, useMemo, useState } from "react";
import {
  ArrowUpRight,
  CircleCheckBig,
  FlaskConical,
  GitBranchPlus,
  Loader2,
  Pause,
  Play,
  Rocket,
  Swords,
  type LucideIcon,
} from "lucide-react";

import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import { useLocale } from "@/lib/locale";
import { useSessions } from "@/hooks/use-sessions";
import { useAutopilotProjects } from "@/hooks/use-autopilot-projects";
import { useScenarios } from "@/hooks/use-scenarios";
import {
  getAutopilotLaunchPresets,
  pauseAutopilotProject,
  prepareTournamentFromSession,
  resumeAutopilotProject,
  sendExecutionBriefToAutopilot,
} from "@/lib/api";
import { MODE_LABELS } from "@/lib/constants";
import type {
  AgentConfig,
  AutopilotLaunchPreset,
  AutopilotProjectSummary,
  ScenarioDefinition,
  SessionSummary,
} from "@/lib/types";
import { saveWizardDraft } from "@/components/wizard/wizard";

interface FounderOsBoardProps {
  onSelectSession: (id: string) => void;
  onOpenDraftWizard: () => void;
}

type FounderStageKey = "research" | "pivots" | "tournaments" | "execution" | "launched";

const RESEARCH_SCENARIOS = new Set([
  "repo_audit",
  "pattern_mining",
  "news_context",
  "consensus_vote",
  "structured_debate",
  "strategy_review",
]);

function cloneAgents(agents: AgentConfig[]): AgentConfig[] {
  return agents.map((agent) => ({
    ...agent,
    tools: [...(agent.tools ?? [])],
    workspace_paths: [...(agent.workspace_paths ?? [])],
  }));
}

function timeAgo(value: string | number | null | undefined, copy: ReturnType<typeof useLocale>["copy"]): string {
  if (!value) return "";
  const timestamp =
    typeof value === "number"
      ? value
      : Math.floor(new Date(value).getTime() / 1000);
  const diff = Math.floor(Date.now() / 1000 - timestamp);
  if (Number.isNaN(diff)) return "";
  if (diff < 60) return copy.shell.time.justNow;
  if (diff < 3600) return `${Math.floor(diff / 60)} ${copy.shell.time.minutes}`;
  if (diff < 86400) return `${Math.floor(diff / 3600)} ${copy.shell.time.hours}`;
  return `${Math.floor(diff / 86400)} ${copy.shell.time.days}`;
}

function statusTone(status: string): string {
  if (status === "running") return "border-emerald-200 bg-emerald-50 text-emerald-700";
  if (status === "paused") return "border-amber-200 bg-amber-50 text-amber-700";
  if (status === "completed") return "border-sky-200 bg-sky-50 text-sky-700";
  if (status === "failed") return "border-rose-200 bg-rose-50 text-rose-700";
  return "border-[#d6dbe6] bg-[#fafbff] text-[#5b6472]";
}

const STAGE_ICONS: Record<FounderStageKey, LucideIcon> = {
  research: FlaskConical,
  pivots: GitBranchPlus,
  tournaments: Swords,
  execution: Rocket,
  launched: CircleCheckBig,
};

function sortSessions(items: SessionSummary[]): SessionSummary[] {
  return [...items].sort((a, b) => Number(b.created_at) - Number(a.created_at));
}

function sortProjects(items: AutopilotProjectSummary[]): AutopilotProjectSummary[] {
  return [...items].sort((a, b) => String(b.last_activity_at ?? "").localeCompare(String(a.last_activity_at ?? "")));
}

function BoardMetric({
  label,
  value,
  hint,
}: {
  label: string;
  value: number;
  hint: string;
}) {
  return (
    <div className="rounded-[20px] border border-[#d6dbe6] bg-white px-5 py-5 shadow-[0_10px_24px_-18px_rgba(17,48,105,0.18)] dark:border-slate-800 dark:bg-slate-950/60 dark:shadow-none">
      <div className="text-[11px] font-semibold uppercase tracking-[0.16em] text-[#6b7280] dark:text-slate-500">
        {label}
      </div>
      <div className="mt-3 text-[32px] font-semibold tracking-[-0.04em] text-[#111111] dark:text-slate-100">
        {value}
      </div>
      <div className="mt-2 text-[12px] leading-6 text-[#6b7280] dark:text-slate-400">
        {hint}
      </div>
    </div>
  );
}

function StageShell({
  stage,
  title,
  description,
  count,
  children,
}: {
  stage: FounderStageKey;
  title: string;
  description: string;
  count: number;
  children: React.ReactNode;
}) {
  const Icon = STAGE_ICONS[stage];
  return (
    <section className="flex min-w-[320px] max-w-[360px] flex-col rounded-[24px] border border-[#d6dbe6] bg-white/90 p-4 shadow-[0_12px_32px_-22px_rgba(17,48,105,0.18)] dark:border-slate-800 dark:bg-slate-950/60 dark:shadow-none">
      <div className="flex items-start justify-between gap-3">
        <div className="flex items-start gap-3">
          <div className="mt-0.5 flex h-10 w-10 items-center justify-center rounded-[14px] border border-[#d6dbe6] bg-[#fafbff] dark:border-slate-800 dark:bg-slate-900">
            <Icon className="h-4.5 w-4.5 text-[#111111] dark:text-slate-100" />
          </div>
          <div>
          <div className="text-[16px] font-semibold tracking-[-0.03em] text-[#111111] dark:text-slate-100">
            {title}
          </div>
          <div className="mt-1 text-[12px] leading-6 text-[#6b7280] dark:text-slate-400">
            {description}
          </div>
        </div>
        </div>
        <span className="rounded-full border border-[#d6dbe6] bg-[#fafbff] px-2.5 py-1 text-[10px] font-semibold uppercase tracking-[0.14em] text-[#6b7280] dark:border-slate-800 dark:bg-slate-900 dark:text-slate-400">
          {count}
        </span>
      </div>
      <div className="mt-4 flex flex-1 flex-col gap-3">{children}</div>
    </section>
  );
}

function EmptyStage({ text }: { text: string }) {
  return (
    <div className="rounded-[18px] border border-dashed border-[#d6dbe6] bg-[#fbfcff] px-4 py-6 text-[13px] leading-6 text-[#6b7280] dark:border-slate-800 dark:bg-slate-900/60 dark:text-slate-400">
      {text}
    </div>
  );
}

function SessionCard({
  session,
  copy,
  onOpen,
  onPrepareTournament,
  onLaunchWinner,
  isPreparing,
  isLaunching,
}: {
  session: SessionSummary;
  copy: ReturnType<typeof useLocale>["copy"];
  onOpen: () => void;
  onPrepareTournament?: () => void;
  onLaunchWinner?: () => void;
  isPreparing?: boolean;
  isLaunching?: boolean;
}) {
  return (
    <div className="rounded-[18px] border border-[#d6dbe6] bg-[#fbfcff] px-4 py-4 dark:border-slate-800 dark:bg-slate-900/60">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <div className="text-[14px] font-semibold leading-6 text-[#111111] dark:text-slate-100">
            {session.task}
          </div>
          <div className="mt-1 text-[11px] text-[#6b7280] dark:text-slate-400">
            {session.active_scenario ? `${copy.founderOs.cards.scenario}: ${session.active_scenario}` : MODE_LABELS[session.mode] ?? session.mode}
          </div>
        </div>
        <span className={cn("rounded-full border px-2.5 py-1 text-[10px] font-semibold uppercase tracking-[0.14em]", statusTone(session.status))}>
          {copy.statuses[session.status as keyof typeof copy.statuses] ?? session.status}
        </span>
      </div>
      <div className="mt-3 text-[11px] text-[#6b7280] dark:text-slate-400">
        {copy.founderOs.cards.lastUpdate}: {timeAgo(session.created_at, copy)}
      </div>
      <div className="mt-4 flex flex-wrap gap-2">
        <Button type="button" variant="outline" size="sm" onClick={onOpen} className="h-8 rounded-full text-[11px]">
          <ArrowUpRight className="mr-1 h-3.5 w-3.5" />
          {copy.founderOs.openSession}
        </Button>
        {onPrepareTournament ? (
          <Button type="button" variant="outline" size="sm" onClick={onPrepareTournament} disabled={isPreparing} className="h-8 rounded-full text-[11px]">
            {isPreparing ? <Loader2 className="mr-1 h-3.5 w-3.5 animate-spin" /> : <GitBranchPlus className="mr-1 h-3.5 w-3.5" />}
            {copy.founderOs.prepareTournament}
          </Button>
        ) : null}
        {onLaunchWinner ? (
          <Button type="button" size="sm" onClick={onLaunchWinner} disabled={isLaunching} className="h-8 rounded-full bg-black text-[11px] text-white hover:bg-black/90">
            {isLaunching ? <Loader2 className="mr-1 h-3.5 w-3.5 animate-spin" /> : <Rocket className="mr-1 h-3.5 w-3.5" />}
            {copy.founderOs.launchWinner}
          </Button>
        ) : null}
      </div>
    </div>
  );
}

function ProjectCard({
  project,
  copy,
  onPause,
  onResume,
  isBusy,
}: {
  project: AutopilotProjectSummary;
  copy: ReturnType<typeof useLocale>["copy"];
  onPause?: () => void;
  onResume?: () => void;
  isBusy?: boolean;
}) {
  const progress = project.stories_total > 0 ? Math.round((project.stories_done / project.stories_total) * 100) : 0;

  return (
    <div className="rounded-[18px] border border-[#d6dbe6] bg-[#fbfcff] px-4 py-4 dark:border-slate-800 dark:bg-slate-900/60">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <div className="text-[14px] font-semibold leading-6 text-[#111111] dark:text-slate-100">
            {project.name}
          </div>
          <div className="mt-1 text-[11px] text-[#6b7280] dark:text-slate-400">
            {project.launch_profile.preset} · {project.priority}
          </div>
        </div>
        <span className={cn("rounded-full border px-2.5 py-1 text-[10px] font-semibold uppercase tracking-[0.14em]", statusTone(project.status))}>
          {project.status}
        </span>
      </div>
      <div className="mt-4">
        <div className="mb-2 flex items-center justify-between text-[11px] text-[#6b7280] dark:text-slate-400">
          <span>{copy.founderOs.cards.progress}</span>
          <span>{project.stories_done}/{project.stories_total}</span>
        </div>
        <div className="h-2 rounded-full bg-[#edf0f6] dark:bg-slate-800">
          <div className="h-2 rounded-full bg-[#111111] dark:bg-slate-100" style={{ width: `${progress}%` }} />
        </div>
      </div>
      {project.current_story_title ? (
        <div className="mt-3 text-[11px] leading-6 text-[#4b5563] dark:text-slate-300">
          <span className="font-medium">{copy.founderOs.cards.currentStory}:</span> {project.current_story_title}
        </div>
      ) : null}
      {project.last_message ? (
        <div className="mt-2 text-[11px] leading-6 text-[#6b7280] dark:text-slate-400">
          {project.last_message}
        </div>
      ) : null}
      <div className="mt-3 text-[11px] text-[#6b7280] dark:text-slate-400">
        {copy.founderOs.cards.lastUpdate}: {timeAgo(project.last_activity_at, copy)}
      </div>
      <div className="mt-4 flex flex-wrap gap-2">
        {onPause ? (
          <Button type="button" variant="outline" size="sm" onClick={onPause} disabled={isBusy} className="h-8 rounded-full text-[11px]">
            {isBusy ? <Loader2 className="mr-1 h-3.5 w-3.5 animate-spin" /> : <Pause className="mr-1 h-3.5 w-3.5" />}
            {copy.founderOs.pauseProject}
          </Button>
        ) : null}
        {onResume ? (
          <Button type="button" variant="outline" size="sm" onClick={onResume} disabled={isBusy} className="h-8 rounded-full text-[11px]">
            {isBusy ? <Loader2 className="mr-1 h-3.5 w-3.5 animate-spin" /> : <Play className="mr-1 h-3.5 w-3.5" />}
            {copy.founderOs.resumeProject}
          </Button>
        ) : null}
      </div>
    </div>
  );
}

export function FounderOsBoard({ onSelectSession, onOpenDraftWizard }: FounderOsBoardProps) {
  const { copy } = useLocale();
  const { sessions } = useSessions();
  const { projects, error: projectsError, refresh: refreshProjects } = useAutopilotProjects();
  const { scenarios } = useScenarios();

  const [launchPresets, setLaunchPresets] = useState<AutopilotLaunchPreset[]>([]);
  const [selectedLaunchPresetId, setSelectedLaunchPresetId] = useState("team");
  const [busyKey, setBusyKey] = useState<string | null>(null);
  const [statusMessage, setStatusMessage] = useState<string | null>(null);

  useEffect(() => {
    getAutopilotLaunchPresets()
      .then((presets) => {
        setLaunchPresets(presets);
        if (!presets.some((preset) => preset.id === selectedLaunchPresetId) && presets[0]) {
          setSelectedLaunchPresetId(presets[0].id);
        }
      })
      .catch(() => {});
  }, [selectedLaunchPresetId]);

  useEffect(() => {
    if (!projectsError) return;
    setStatusMessage(projectsError instanceof Error ? projectsError.message : "Autopilot projects are unavailable.");
  }, [projectsError]);

  const researchSessions = useMemo(
    () =>
      sortSessions(
        sessions.filter((session) =>
          RESEARCH_SCENARIOS.has(String(session.active_scenario ?? "")) ||
          session.active_scenario === "project_strengthening_lab"
        )
      ),
    [sessions]
  );
  const pivotSessions = useMemo(
    () => sortSessions(sessions.filter((session) => session.active_scenario === "portfolio_pivot_lab")),
    [sessions]
  );
  const tournamentSessions = useMemo(
    () =>
      sortSessions(
        sessions.filter(
          (session) => session.active_scenario === "project_tournament" || session.mode === "tournament"
        )
      ),
    [sessions]
  );
  const executionProjects = useMemo(
    () => sortProjects(projects.filter((project) => !project.archived && project.status !== "completed")),
    [projects]
  );
  const launchedProjects = useMemo(
    () => sortProjects(projects.filter((project) => !project.archived && project.status === "completed")),
    [projects]
  );

  function scenarioById(id: string | null | undefined): ScenarioDefinition | null {
    return scenarios?.find((scenario) => scenario.id === id) ?? null;
  }

  function openScenarioDraft(scenarioId: string) {
    const scenario = scenarioById(scenarioId);
    if (!scenario) return;
    saveWizardDraft({
      step: 2,
      selectedScenarioId: scenario.id,
      agents: cloneAgents(scenario.default_agents),
      workspacePresetIds: [],
      workspacePaths: [],
      taskDraft: "",
      launchConfig: { ...scenario.default_config },
    });
    onOpenDraftWizard();
  }

  async function handlePrepareTournament(sessionId: string) {
    setBusyKey(`prepare:${sessionId}`);
    setStatusMessage(null);
    try {
      const response = await prepareTournamentFromSession(sessionId);
      saveWizardDraft({
        step: 2,
        selectedScenarioId: response.tournament.scenario_id,
        agents: response.tournament.agents,
        workspacePresetIds: [],
        workspacePaths: response.tournament.workspace_paths,
        taskDraft: response.tournament.task,
        launchConfig: {
          max_rounds: response.tournament.recommended_max_rounds,
          execution_mode: response.tournament.recommended_execution_mode,
        },
      });
      setStatusMessage(`${copy.monitor.tournamentPrepared} ${response.tournament.contestants.length}`.trim());
      onOpenDraftWizard();
    } catch (error) {
      setStatusMessage(error instanceof Error ? error.message : "Tournament preparation failed.");
    } finally {
      setBusyKey(null);
    }
  }

  async function handleLaunchWinner(sessionId: string) {
    setBusyKey(`launch:${sessionId}`);
    setStatusMessage(null);
    try {
      const selectedPreset = launchPresets.find((preset) => preset.id === selectedLaunchPresetId);
      const response = await sendExecutionBriefToAutopilot(sessionId, {
        launch: true,
        priority: "high",
        launch_profile: selectedPreset?.launch_profile ?? { preset: selectedLaunchPresetId },
      });
      const projectName =
        typeof response.autopilot?.project_name === "string" && response.autopilot.project_name
          ? ` ${response.autopilot.project_name}`
          : "";
      setStatusMessage(`${copy.monitor.launchedInAutopilot}${projectName}`.trim());
      await refreshProjects();
    } catch (error) {
      setStatusMessage(error instanceof Error ? error.message : "Autopilot launch failed.");
    } finally {
      setBusyKey(null);
    }
  }

  async function handleProjectPause(projectId: string) {
    setBusyKey(`pause:${projectId}`);
    setStatusMessage(null);
    try {
      await pauseAutopilotProject(projectId);
      await refreshProjects();
    } catch (error) {
      setStatusMessage(error instanceof Error ? error.message : "Pause failed.");
    } finally {
      setBusyKey(null);
    }
  }

  async function handleProjectResume(projectId: string) {
    setBusyKey(`resume:${projectId}`);
    setStatusMessage(null);
    try {
      await resumeAutopilotProject(projectId);
      await refreshProjects();
    } catch (error) {
      setStatusMessage(error instanceof Error ? error.message : "Resume failed.");
    } finally {
      setBusyKey(null);
    }
  }

  return (
    <div className="flex h-full flex-col overflow-hidden">
      <div className="border-b border-[#e6e8ee] bg-white/95 px-8 py-6 backdrop-blur-sm dark:border-slate-800/80 dark:bg-[#0b0f17]/95">
        <div className="flex flex-col gap-5 xl:flex-row xl:items-start xl:justify-between">
          <div className="max-w-3xl">
            <div className="text-[28px] font-semibold tracking-[-0.05em] text-[#111111] dark:text-slate-100">
              {copy.founderOs.title}
            </div>
            <div className="mt-2 text-[14px] leading-7 text-[#6b7280] dark:text-slate-400">
              {copy.founderOs.subtitle}
            </div>
          </div>
          <div className="flex flex-col gap-3 xl:items-end">
            {launchPresets.length > 0 ? (
              <div className="rounded-[18px] border border-[#d6dbe6] bg-[#fbfcff] px-4 py-3 dark:border-slate-800 dark:bg-slate-900/70">
                <div className="text-[11px] font-semibold uppercase tracking-[0.14em] text-[#6b7280] dark:text-slate-500">
                  {copy.founderOs.launchPresetLabel}
                </div>
                <div className="mt-3 flex flex-wrap gap-2">
                  {launchPresets.map((preset) => (
                    <button
                      key={preset.id}
                      type="button"
                      onClick={() => setSelectedLaunchPresetId(preset.id)}
                      className={`rounded-full border px-3 py-1.5 text-[11px] transition-colors ${
                        selectedLaunchPresetId === preset.id
                          ? "border-black bg-black text-white dark:border-slate-100 dark:bg-slate-100 dark:text-slate-950"
                          : "border-[#d6dbe6] bg-white text-[#4b5563] hover:text-[#111111] dark:border-slate-800 dark:bg-slate-950 dark:text-slate-400 dark:hover:text-slate-100"
                      }`}
                    >
                      {preset.label}
                    </button>
                  ))}
                </div>
              </div>
            ) : null}
            <div className="flex flex-wrap gap-2">
              <Button type="button" variant="outline" onClick={() => openScenarioDraft("portfolio_pivot_lab")} className="h-10 rounded-full">
                <GitBranchPlus className="mr-2 h-4 w-4" />
                {copy.founderOs.newPivotLab}
              </Button>
              <Button type="button" variant="outline" onClick={() => openScenarioDraft("project_strengthening_lab")} className="h-10 rounded-full">
                <FlaskConical className="mr-2 h-4 w-4" />
                {copy.founderOs.newStrengtheningLab}
              </Button>
              <Button type="button" onClick={() => openScenarioDraft("project_tournament")} className="h-10 rounded-full bg-black text-white hover:bg-black/90">
                <Swords className="mr-2 h-4 w-4" />
                {copy.founderOs.newTournament}
              </Button>
            </div>
          </div>
        </div>

        <div className="mt-6 grid gap-4 md:grid-cols-2 xl:grid-cols-5">
          <BoardMetric label={copy.founderOs.summary.research} value={researchSessions.length} hint={copy.founderOs.stages.research.description} />
          <BoardMetric label={copy.founderOs.summary.pivots} value={pivotSessions.length} hint={copy.founderOs.stages.pivots.description} />
          <BoardMetric label={copy.founderOs.summary.tournaments} value={tournamentSessions.length} hint={copy.founderOs.stages.tournaments.description} />
          <BoardMetric label={copy.founderOs.summary.execution} value={executionProjects.length} hint={copy.founderOs.stages.execution.description} />
          <BoardMetric label={copy.founderOs.summary.launched} value={launchedProjects.length} hint={copy.founderOs.stages.launched.description} />
        </div>

        {statusMessage ? (
          <div className="mt-4 rounded-[16px] border border-[#d6dbe6] bg-[#fbfcff] px-4 py-3 text-[13px] leading-6 text-[#4b5563] dark:border-slate-800 dark:bg-slate-900/80 dark:text-slate-300">
            {statusMessage}
          </div>
        ) : null}
      </div>

      <div className="min-h-0 flex-1 overflow-auto px-8 py-6">
        <div className="flex min-h-max items-start gap-4 pb-6">
          <StageShell
            stage="research"
            title={copy.founderOs.stages.research.title}
            description={copy.founderOs.stages.research.description}
            count={researchSessions.length}
          >
            {researchSessions.length === 0 ? (
              <EmptyStage text={copy.founderOs.empty} />
            ) : (
              researchSessions.map((session) => (
                <SessionCard
                  key={session.id}
                  session={session}
                  copy={copy}
                  onOpen={() => onSelectSession(session.id)}
                  onLaunchWinner={
                    session.active_scenario === "project_strengthening_lab" && session.status === "completed"
                      ? () => handleLaunchWinner(session.id)
                      : undefined
                  }
                  isLaunching={busyKey === `launch:${session.id}`}
                />
              ))
            )}
          </StageShell>

          <StageShell
            stage="pivots"
            title={copy.founderOs.stages.pivots.title}
            description={copy.founderOs.stages.pivots.description}
            count={pivotSessions.length}
          >
            {pivotSessions.length === 0 ? (
              <EmptyStage text={copy.founderOs.empty} />
            ) : (
              pivotSessions.map((session) => (
                <SessionCard
                  key={session.id}
                  session={session}
                  copy={copy}
                  onOpen={() => onSelectSession(session.id)}
                  onPrepareTournament={session.status === "completed" ? () => handlePrepareTournament(session.id) : undefined}
                  isPreparing={busyKey === `prepare:${session.id}`}
                />
              ))
            )}
          </StageShell>

          <StageShell
            stage="tournaments"
            title={copy.founderOs.stages.tournaments.title}
            description={copy.founderOs.stages.tournaments.description}
            count={tournamentSessions.length}
          >
            {tournamentSessions.length === 0 ? (
              <EmptyStage text={copy.founderOs.empty} />
            ) : (
              tournamentSessions.map((session) => (
                <SessionCard
                  key={session.id}
                  session={session}
                  copy={copy}
                  onOpen={() => onSelectSession(session.id)}
                  onLaunchWinner={session.status === "completed" ? () => handleLaunchWinner(session.id) : undefined}
                  isLaunching={busyKey === `launch:${session.id}`}
                />
              ))
            )}
          </StageShell>

          <StageShell
            stage="execution"
            title={copy.founderOs.stages.execution.title}
            description={copy.founderOs.stages.execution.description}
            count={executionProjects.length}
          >
            {executionProjects.length === 0 ? (
              <EmptyStage text={copy.founderOs.empty} />
            ) : (
              executionProjects.map((project) => (
                <ProjectCard
                  key={project.id}
                  project={project}
                  copy={copy}
                  onPause={project.status === "running" ? () => handleProjectPause(project.id) : undefined}
                  onResume={project.status === "paused" ? () => handleProjectResume(project.id) : undefined}
                  isBusy={busyKey === `pause:${project.id}` || busyKey === `resume:${project.id}`}
                />
              ))
            )}
          </StageShell>

          <StageShell
            stage="launched"
            title={copy.founderOs.stages.launched.title}
            description={copy.founderOs.stages.launched.description}
            count={launchedProjects.length}
          >
            {launchedProjects.length === 0 ? (
              <EmptyStage text={copy.founderOs.empty} />
            ) : (
              launchedProjects.map((project) => (
                <ProjectCard key={project.id} project={project} copy={copy} />
              ))
            )}
          </StageShell>
        </div>
      </div>
    </div>
  );
}
