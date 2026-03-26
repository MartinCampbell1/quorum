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
import type { ToolDefinition } from "./types";

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

export const BUILTIN_TOOL_DEFINITIONS: ToolDefinition[] = [
  {
    key: "web_search",
    name: "Веб-поиск",
    description: "Поиск в интернете через Brave Search API",
    category: "search",
  },
  {
    key: "perplexity",
    name: "Perplexity AI",
    description: "AI-поиск с цитатами через Perplexity Sonar",
    category: "search",
  },
  {
    key: "code_exec",
    name: "Python",
    description: "Выполнение Python кода (вычисления, обработка данных)",
    category: "exec",
  },
  {
    key: "shell_exec",
    name: "Shell",
    description: "Выполнение shell команд (файлы, git, система)",
    category: "exec",
  },
  {
    key: "http_request",
    name: "HTTP запрос",
    description: "HTTP запросы к любым API (GET/POST/PUT/DELETE)",
    category: "exec",
  },
];

export const TOOL_LABELS: Record<string, string> = Object.fromEntries(
  BUILTIN_TOOL_DEFINITIONS.map((tool) => [tool.key, tool.name])
) as Record<string, string>;

export const TOOL_DESCRIPTIONS: Record<string, string> = Object.fromEntries(
  BUILTIN_TOOL_DEFINITIONS.map((tool) => [tool.key, tool.description])
) as Record<string, string>;

export const ALL_TOOL_KEYS = BUILTIN_TOOL_DEFINITIONS.map((tool) => tool.key);
