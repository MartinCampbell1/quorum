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

export const TOOL_LABELS: Record<string, string> = {
  web_search: "Веб-поиск",
  perplexity: "Perplexity AI",
  code_exec: "Python",
  shell_exec: "Shell",
  http_request: "HTTP запрос",
};

export const TOOL_DESCRIPTIONS: Record<string, string> = {
  web_search: "Поиск в интернете через Brave Search API",
  perplexity: "AI-поиск с цитатами через Perplexity Sonar",
  code_exec: "Выполнение Python кода (вычисления, обработка данных)",
  shell_exec: "Выполнение shell команд (файлы, git, система)",
  http_request: "HTTP запросы к любым API (GET/POST/PUT/DELETE)",
};

export const ALL_TOOL_KEYS = Object.keys(TOOL_LABELS);
