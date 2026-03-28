import {
  Crown,
  Users,
  Vote,
  Swords,
  LayoutGrid,
  RefreshCw,
  Trophy,
  type LucideIcon,
} from "lucide-react";

export const AGENT_COLORS: Record<string, string> = {
  claude: "var(--color-agent-claude)",
  codex: "var(--color-agent-codex)",
  gemini: "var(--color-agent-gemini)",
  minimax: "var(--color-agent-minimax)",
  system: "var(--color-agent-system)",
  user: "var(--color-agent-user)",
};

export const MODE_ICONS: Record<string, LucideIcon> = {
  dictator: Crown,
  board: Users,
  democracy: Vote,
  debate: Swords,
  tournament_match: Swords,
  map_reduce: LayoutGrid,
  creator_critic: RefreshCw,
  tournament: Trophy,
};

export const MODE_LABELS: Record<string, string> = {
  dictator: "Диктатор",
  board: "Совет",
  democracy: "Демократия",
  debate: "Дебаты",
  tournament_match: "Матч турнира",
  map_reduce: "Map-Reduce",
  creator_critic: "Создатель-Критик",
  tournament: "Турнир",
};

export const PROVIDER_LABELS: Record<string, string> = {
  claude: "Claude",
  codex: "Codex",
  gemini: "Gemini",
  minimax: "MiniMax",
};

export interface RoleDisplayContext {
  mode?: string | null;
  scenarioId?: string | null;
}

function isTournamentContestant(role: string): boolean {
  return /^contestant_\d+$/.test(String(role || "").trim());
}

const BASE_ROLE_DISPLAY_LABELS: Record<string, string> = {
  lead_reviewer: "Ведущий ревьюер",
  runtime_investigator: "Инженер рантайма",
  evidence_analyst: "Аналитик фактов",
  planner: "Планировщик",
  pattern_worker_1: "Аналитик паттернов 1",
  pattern_worker_2: "Аналитик паттернов 2",
  synthesizer: "Синтезатор",
  macro_reader: "Макро-аналитик",
  market_reader: "Рыночный аналитик",
  skeptic: "Скептик",
  voter_1: "Голосующий 1",
  voter_2: "Голосующий 2",
  voter_3: "Голосующий 3",
  proponent: "Защитник",
  opponent: "Критик",
  judge: "Судья",
  strategist: "Стратег",
  risk_critic: "Критик рисков",
  creator: "Создатель",
  critic: "Критик",
  director: "Директор",
  chair: "Председатель",
};

const MODE_ROLE_DISPLAY_LABELS: Record<string, Record<string, string>> = {
  debate: {
    proponent: "Защитник",
    opponent: "Критик",
    judge: "Судья",
  },
  creator_critic: {
    creator: "Создатель",
    critic: "Критик",
  },
};

const SCENARIO_ROLE_DISPLAY_LABELS: Record<string, Record<string, string>> = {
  structured_debate: MODE_ROLE_DISPLAY_LABELS.debate,
};

function humanizeIdentifier(value: string): string {
  return value
    .replace(/-/g, "_")
    .split("_")
    .filter(Boolean)
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(" ");
}

export function formatWorkspaceLabel(paths?: string[] | null): string | null {
  const labels = (paths ?? [])
    .map((path) => String(path ?? "").trim().replace(/[\\/]+$/, ""))
    .filter(Boolean)
    .map((path) => {
      const parts = path.split(/[\\/]/).filter(Boolean);
      return parts[parts.length - 1] ?? path;
    });

  if (labels.length === 0) return null;
  return labels.join(", ");
}

function resolveContextualRoleLabel(role: string, context?: RoleDisplayContext): string | null {
  const scenarioId = String(context?.scenarioId ?? "").trim();
  if (scenarioId) {
    const scenarioLabel = SCENARIO_ROLE_DISPLAY_LABELS[scenarioId]?.[role];
    if (scenarioLabel) return scenarioLabel;
  }

  const mode = String(context?.mode ?? "").trim();
  if (mode) {
    const modeLabel = MODE_ROLE_DISPLAY_LABELS[mode]?.[role];
    if (modeLabel) return modeLabel;
  }

  return null;
}

export function formatAgentRole(role: string, context?: RoleDisplayContext): string {
  const normalized = String(role || "").trim();
  if (!normalized) return "Агент";

  const contextual = resolveContextualRoleLabel(normalized, context);
  if (contextual) return contextual;

  const mapped = BASE_ROLE_DISPLAY_LABELS[normalized];
  if (mapped) return mapped;

  const patternWorker = normalized.match(/^pattern_worker_(\d+)$/);
  if (patternWorker) return `Аналитик паттернов ${patternWorker[1]}`;

  const genericWorker = normalized.match(/^worker_(\d+)$/);
  if (genericWorker) return `Воркер ${genericWorker[1]}`;

  const contestant = normalized.match(/^contestant_(\d+)$/);
  if (contestant) return `Участник ${contestant[1]}`;

  const voter = normalized.match(/^voter_(\d+)$/);
  if (voter) return `Голосующий ${voter[1]}`;

  return humanizeIdentifier(normalized);
}

export function formatAgentDisplay(
  role: string,
  context?: RoleDisplayContext & { projectLabel?: string | null }
): string {
  const roleLabel = formatAgentRole(role, context);
  const projectLabel = String(context?.projectLabel ?? "").trim();
  if (!projectLabel) return roleLabel;
  if (!isTournamentContestant(role)) return roleLabel;
  return `${roleLabel} (${projectLabel})`;
}

export function roleMonogram(role: string, context?: RoleDisplayContext): string {
  const label = formatAgentRole(role, context);
  const tokens = label.split(/\s+/).filter(Boolean);
  if (tokens.length === 1) {
    return tokens[0].slice(0, 2).toUpperCase();
  }
  return `${tokens[0][0] ?? ""}${tokens[1][0] ?? ""}`.toUpperCase();
}

export function formatScenarioLabel(scenarioId: string): string {
  const normalized = String(scenarioId || "").trim();
  if (!normalized) return "";
  return humanizeIdentifier(normalized);
}
