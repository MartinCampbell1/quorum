import type { AgentConfig, ModeInfo, ScenarioDefinition } from "./types";

const LOCAL_SCENARIO_FALLBACKS: Record<string, Omit<ScenarioDefinition, "default_agents">> = {
  tournament: {
    id: "project_tournament",
    name: "Project Tournament",
    mode: "tournament",
    headline: "Несколько проектов проходят по сетке матчей, а судья выбирает чемпиона.",
    description: "Подходит для отбора лучшей идеи или репозитория среди нескольких локальных проектов через серию очных матчей с аргументами и вердиктом судьи.",
    recommended_for: "Сравнение нескольких pet-проектов, репозиториев, MVP-идей или направлений развития по одной задаче.",
    task_placeholder: "Например: выберите, какой проект соло-фаундеру стоит развивать первым, чтобы быстрее выйти к стабильным $2K+/мес, а в финале назовите победителя, второе место и что заморозить.",
    tags: ["tournament", "projects", "comparison"],
    default_config: { max_rounds: 5 },
    is_local_fallback: true,
  },
};

function cloneAgents(agents: AgentConfig[]): AgentConfig[] {
  return agents.map((agent) => ({
    ...agent,
    tools: [...(agent.tools ?? [])],
    workspace_paths: [...(agent.workspace_paths ?? [])],
  }));
}

export function withScenarioFallbacks(
  scenarios: ScenarioDefinition[],
  modes: Record<string, ModeInfo> | undefined
): ScenarioDefinition[] {
  const merged = [...scenarios];
  const scenarioIds = new Set(merged.map((scenario) => scenario.id));
  const scenarioModes = new Set(merged.map((scenario) => scenario.mode));

  for (const [mode, fallback] of Object.entries(LOCAL_SCENARIO_FALLBACKS)) {
    const modeInfo = modes?.[mode];
    if (!modeInfo) continue;
    if (scenarioIds.has(fallback.id) || scenarioModes.has(mode)) continue;

    merged.push({
      ...fallback,
      default_agents: cloneAgents(modeInfo.default_agents),
    });
  }

  return merged;
}
