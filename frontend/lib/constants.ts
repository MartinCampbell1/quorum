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
  map_reduce: LayoutGrid,
  creator_critic: RefreshCw,
  tournament: Trophy,
};

export const MODE_LABELS: Record<string, string> = {
  dictator: "Диктатор",
  board: "Совет",
  democracy: "Демократия",
  debate: "Дебаты",
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

