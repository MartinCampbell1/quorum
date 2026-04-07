"use client";

import { useState, useEffect } from "react";
import {
  Plus,
  Trash2,
  Settings2,
  Pencil,
  BookOpen,
  Eye,
  EyeOff,
  AlertTriangle,
  CheckCircle2,
  FolderTree,
  Loader2,
  RefreshCw,
  Shield,
  ShieldAlert,
  ShieldCheck,
  X,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  getAccounts,
  getAccountsHealth,
  getConfiguredTools,
  getToolTypes,
  addConfiguredTool,
  updateConfiguredTool,
  deleteConfiguredTool,
  getPromptTemplates,
  getWorkspacePresets,
  addWorkspacePreset,
  updateWorkspacePreset,
  deleteWorkspacePreset,
  validateConfiguredTool,
  openProviderLogin,
  importProviderSession,
  reauthorizeProviderAccount,
  updateProviderAccount,
  reloadAccounts,
} from "@/lib/api";
import type {
  AccountHealth,
  AccountsByProvider,
  ConfiguredTool,
  PromptTemplate,
  ToolFieldSchema,
  ToolTypeDefinition,
  WorkspacePreset,
} from "@/lib/types";
import { cn } from "@/lib/utils";
import { SettingsAccountsPanel } from "@/components/settings-accounts-panel";

const INPUT_CLASS =
  "w-full rounded-2xl border border-[#e0e4ec] bg-white px-3.5 py-2.5 text-xs text-foreground placeholder:text-muted-foreground/50 transition-colors focus:outline-none focus:ring-2 focus:ring-sky-400/25 dark:border-slate-800/80 dark:bg-slate-950/55";

function slugify(text: string): string {
  return text
    .toLowerCase()
    .replace(/[^a-z0-9а-яё]+/g, "_")
    .replace(/^_|_$/g, "");
}

function hasMissingRequired(tool: ConfiguredTool, toolTypes: Record<string, ToolTypeDefinition>): boolean {
  const typeInfo = toolTypes[tool.tool_type];
  if (!typeInfo) return false;
  return typeInfo.fields
    .filter((f) => f.required)
    .some((f) => !tool.config[f.name]?.trim());
}

function renderFieldControl({
  field,
  value,
  onChange,
}: {
  field: ToolFieldSchema;
  value: string;
  onChange: (value: string) => void;
}) {
  if (field.type === "password") {
    return (
      <PasswordField
        value={value}
        onChange={onChange}
        placeholder={field.placeholder}
      />
    );
  }

  if (field.type === "textarea") {
    return (
      <textarea
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder={field.placeholder}
        rows={4}
        className={`${INPUT_CLASS} min-h-24 resize-y leading-relaxed`}
      />
    );
  }

  if (field.type === "select") {
    return (
      <Select value={value} onValueChange={(nextValue) => onChange(nextValue ?? "")}>
        <SelectTrigger className="w-full h-9 text-xs">
          <SelectValue placeholder={field.placeholder || "Выберите..."} />
        </SelectTrigger>
        <SelectContent>
          {(field.options ?? []).map((option) => (
            <SelectItem key={option} value={option} className="text-xs">
              {option}
            </SelectItem>
          ))}
        </SelectContent>
      </Select>
    );
  }

  return (
    <input
      type="text"
      value={value}
      onChange={(e) => onChange(e.target.value)}
      placeholder={field.placeholder}
      className={INPUT_CLASS}
    />
  );
}

function PasswordField({
  value,
  onChange,
  placeholder,
}: {
  value: string;
  onChange: (v: string) => void;
  placeholder?: string;
}) {
  const [visible, setVisible] = useState(false);

  return (
    <div className="relative">
      <input
        type={visible ? "text" : "password"}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder={placeholder}
        className={`${INPUT_CLASS} pr-8`}
      />
      <button
        type="button"
        onClick={() => setVisible((v) => !v)}
        className="absolute right-2 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground cursor-pointer"
        aria-label={visible ? "Скрыть" : "Показать"}
      >
        {visible ? <EyeOff size={13} /> : <Eye size={13} />}
      </button>
    </div>
  );
}

function McpTransportPicker({
  value,
  onChange,
}: {
  value: string;
  onChange: (value: string) => void;
}) {
  const options = ["stdio", "http"];

  return (
    <div className="grid grid-cols-2 gap-2 rounded-2xl border border-[#e2e8f0] bg-white p-1 dark:border-slate-800 dark:bg-slate-950/55">
      {options.map((option) => {
        const active = value === option;
        return (
          <button
            key={option}
            type="button"
            onClick={() => onChange(option)}
            className={cn(
              "rounded-xl px-3 py-2 text-sm font-medium transition-colors",
              active
                ? "bg-[#09090b] text-white dark:bg-white dark:text-[#09090b]"
                : "text-[#445d99] hover:bg-[#f2f3ff] dark:text-slate-400 dark:hover:bg-slate-900"
            )}
          >
            {option}
          </button>
        );
      })}
    </div>
  );
}

function McpHandshakeLog({
  transport,
  lines,
}: {
  transport: string;
  lines?: string[];
}) {
  const fallbackLines = transport === "http"
    ? [
        "> Resolving remote endpoint...",
        "> Sending capabilities request...",
        "> Waiting for HTTP handshake...",
        "> Connection successful. Remote MCP ready.",
      ]
    : [
        "> Connecting to server...",
        "> Handshake initiated...",
        "> Waiting for stdio response...",
        "> Connection successful. Server ready.",
      ];
  const effectiveLines = lines && lines.length > 0 ? lines : fallbackLines;

  return (
    <div className="rounded-[18px] border border-[#e2e8f0] bg-[#f7f8ff] p-4 dark:border-slate-800 dark:bg-slate-950/65">
      <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-[#445d99] dark:text-slate-400">
        Handshake Log
      </p>
      <div className="mt-3 rounded-[14px] border border-[#e2e8f0] bg-white px-4 py-3 font-mono text-[12px] leading-7 text-[#09090b] dark:border-slate-800 dark:bg-slate-900/80 dark:text-slate-200">
        {effectiveLines.map((line) => (
          <div key={line}>{line}</div>
        ))}
      </div>
    </div>
  );
}

function buildInitialToolDraft(
  initialType: string,
  toolTypes: Record<string, ToolTypeDefinition>,
  initialDraft?: ToolAddDraft | null
) {
  if (initialDraft && toolTypes[initialDraft.tool_type]) {
    const typeInfo = toolTypes[initialDraft.tool_type];
    const initialConfig: Record<string, string> = {};
    for (const field of typeInfo.fields) {
      initialConfig[field.name] = field.name === "transport" ? "stdio" : "";
    }
    return {
      selectedType: initialDraft.tool_type,
      name: initialDraft.name,
      config: { ...initialConfig, ...initialDraft.config },
    };
  }

  if (!initialType || !toolTypes[initialType]) {
    return {
      selectedType: "",
      name: "",
      config: {} as Record<string, string>,
    };
  }

  const typeInfo = toolTypes[initialType];
  const initialConfig: Record<string, string> = {};
  for (const field of typeInfo.fields) {
    initialConfig[field.name] = field.name === "transport" ? "stdio" : "";
  }

  return {
    selectedType: initialType,
    name: "",
    config: initialConfig,
  };
}

interface ToolAddDraft {
  tool_type: string;
  name: string;
  config: Record<string, string>;
}

const QUICK_CONNECT_PRESETS = [
  {
    type: "http_api",
    eyebrow: "API",
    title: "Подключить HTTP API",
    description: "Вставь base URL и заголовки. Для пользователя это выглядит как обычная интеграция API.",
  },
  {
    type: "custom_api",
    eyebrow: "ADVANCED API",
    title: "Подключить custom API",
    description: "Подходит для API с шаблоном тела запроса, особыми заголовками и агентным описанием.",
  },
  {
    type: "ssh",
    eyebrow: "SERVER",
    title: "Подключить SSH сервер",
    description: "Для файлов, контейнеров, логов и удалённых команд. Именно это нужно для реального сервера, а не shell-заглушки.",
  },
  {
    type: "neo4j",
    eyebrow: "GRAPH",
    title: "Подключить граф / Neo4j",
    description: "Дай bolt URL и учётные данные, чтобы агент мог ходить в граф и проверять связи напрямую.",
  },
  {
    type: "mcp_server",
    eyebrow: "MCP",
    title: "Подключить MCP server",
    description: "Для stdio/http MCP серверов, если хочешь завести готовый внешний MCP без промежуточного слоя.",
  },
] as const;
const CONNECTION_TOOL_TYPES = new Set(["http_api", "custom_api", "ssh", "neo4j", "mcp_server"]);
const NON_ADDABLE_TOOL_TYPES = new Set(["code_exec", "shell"]);
const TOOL_ADD_TYPE_META: Record<
  string,
  {
    eyebrow: string;
    title: string;
    description: string;
    detail: string;
    hints: string[];
  }
> = {
  http_api: {
    eyebrow: "UNIVERSAL API",
    title: "Подключение к любому HTTP API",
    description: "Не ограничено каталогом. Используй для любого REST/JSON API, если достаточно base URL, метода и заголовков.",
    detail: "Это универсальный адаптер. Список ниже не про \"разрешённые сервисы\", а про типы подключения, которые система умеет оборачивать во внутренний tool/MCP слой.",
    hints: ["Подходит для большинства SaaS API", "Можно импортировать из URL или curl", "Статика заголовков и auth задаются в форме"],
  },
  custom_api: {
    eyebrow: "ADVANCED API",
    title: "Кастомный API-адаптер",
    description: "Для API, где нужен шаблон тела запроса, особый content-type или агентное описание поведения.",
    detail: "Используй этот режим, если хочешь, чтобы агент работал с API как с более умным инструментом, а не просто как с сырой HTTP-ручкой.",
    hints: ["Подходит для body templates", "Можно импортировать из curl или OpenAPI-like описания", "Удобен для внутренних agent-facing API"],
  },
  ssh: {
    eyebrow: "REMOTE SERVER",
    title: "Удалённый сервер по SSH",
    description: "Для файлов, контейнеров, сервисов, логов и удалённых команд. Это именно server access, а не локальный shell runtime.",
    detail: "SSH нужен для реальной инфраструктуры. Built-in Shell ниже в системе — это локальный runtime tool, он не заменяет доступ к удалённому серверу.",
    hints: ["Поддерживается key-based auth", "Подходит для docker/systemd/logs/files", "Можно импортировать из ssh user@host"],
  },
  neo4j: {
    eyebrow: "GRAPH ACCESS",
    title: "Графовая база / Neo4j",
    description: "Дай bolt URL и учётные данные, чтобы агент мог выполнять графовые запросы и проверять связи напрямую.",
    detail: "Это первый-class graph connector, а не просто ещё один generic API. Его нужно воспринимать как доступ к knowledge graph / graph DB слою.",
    hints: ["Подходит для knowledge graph и связей", "Можно импортировать из bolt://", "Агент использует его как графовый инструмент"],
  },
  brave_search: {
    eyebrow: "SEARCH",
    title: "Brave Search",
    description: "Быстрое веб-поисковое подключение с отдельным API key профилем.",
    detail: "Это не ограничение списка API, а просто готовый search connector, который удобно добавить отдельно от универсальных HTTP-интеграций.",
    hints: ["Быстрый web search", "Отдельный key profile", "Удобно для research-сценариев"],
  },
  perplexity: {
    eyebrow: "SEARCH",
    title: "Perplexity AI",
    description: "Поиск с answer-first выдачей и citations через отдельный API key профиль.",
    detail: "Подходит как отдельный research connector. Если нужен любой другой поставщик, используй HTTP API или Custom API.",
    hints: ["Answer-first search", "Подходит для research", "Не ограничивает другие API-интеграции"],
  },
  bright_data_serp: {
    eyebrow: "SEARCH",
    title: "Bright Data SERP",
    description: "Google SERP и web-fetch через Bright Data как отдельный research connector.",
    detail: "Это не просто generic POST. Инструмент понимает запросы как search query или URL и годится для более тяжёлого market/web research, чем обычный поиск.",
    hints: ["Можно импортировать из curl Bright Data", "Подходит для current SERP fetch", "Хорошо работает для research-heavy агентов"],
  },
  mcp_server: {
    eyebrow: "MCP",
    title: "External MCP Server",
    description: "Подключение готового stdio/http MCP сервера без промежуточной ручной обвязки.",
    detail: "Это самый прямой путь, если у тебя уже есть совместимый MCP server и хочется завести его как есть.",
    hints: ["Поддерживает stdio и http", "Сильный путь для готовых MCP-интеграций", "Лучший вариант для внешних MCP servers"],
  },
};
const TOOL_ADD_GROUPS = [
  {
    id: "universal",
    label: "Universal Adapters",
    description: "Для любых внешних API, а не только заранее перечисленных сервисов.",
    types: ["http_api", "custom_api"],
  },
  {
    id: "infrastructure",
    label: "Servers & Graph",
    description: "Для доступа к инфраструктуре, графу, контейнерам и удалённым данным.",
    types: ["ssh", "neo4j"],
  },
  {
    id: "search",
    label: "Search Providers",
    description: "Готовые профили для поиска и research-задач.",
    types: ["brave_search", "perplexity", "bright_data_serp"],
  },
  {
    id: "advanced",
    label: "Advanced Runtime",
    description: "Для случаев, когда внешний сервис уже говорит на MCP.",
    types: ["mcp_server"],
  },
] as const;

function normalizeShellToken(token: string) {
  if (
    (token.startsWith('"') && token.endsWith('"')) ||
    (token.startsWith("'") && token.endsWith("'")) ||
    (token.startsWith("`") && token.endsWith("`"))
  ) {
    return token.slice(1, -1);
  }
  return token;
}

function splitShellLike(text: string) {
  return (text.match(/"[^"]*"|'[^']*'|`[^`]*`|[^\s]+/g) ?? []).map(normalizeShellToken);
}

function formatHostName(raw: string, fallback: string) {
  const cleaned = raw.replace(/^www\./, "").split(".")[0]?.replace(/[-_]+/g, " ").trim();
  if (!cleaned) return fallback;
  return cleaned
    .split(" ")
    .filter(Boolean)
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(" ");
}

function detectHttpUrlDraft(raw: string): ToolAddDraft | null {
  const value = raw.trim();
  if (!/^https?:\/\//i.test(value)) return null;
  try {
    const url = new URL(value);
    return {
      tool_type: "http_api",
      name: `${formatHostName(url.hostname, "HTTP")} API`,
      config: {
        base_url: `${url.origin}${url.pathname}${url.search}`,
        method: "GET",
        auth_header: "",
        headers_json: "",
      },
    };
  } catch {
    return null;
  }
}

function detectBoltDraft(raw: string): ToolAddDraft | null {
  const value = raw.trim();
  if (!/^(bolt|neo4j(\+s|\+ssc)?):\/\//i.test(value)) return null;
  return {
    tool_type: "neo4j",
    name: "Neo4j Graph",
    config: {
      bolt_url: value,
      user: "neo4j",
      password: "",
      database: "neo4j",
    },
  };
}

function detectSshDraft(raw: string): ToolAddDraft | null {
  const trimmed = raw.trim();
  if (!trimmed) return null;

  const tokens = splitShellLike(trimmed.startsWith("ssh ") ? trimmed : `ssh ${trimmed}`);
  if (!tokens.length || tokens[0] !== "ssh") return null;

  let port = "22";
  let keyPath = "";
  let target = "";
  for (let i = 1; i < tokens.length; i += 1) {
    const token = tokens[i];
    if ((token === "-p" || token === "-P") && tokens[i + 1]) {
      port = tokens[i + 1];
      i += 1;
      continue;
    }
    if (token === "-i" && tokens[i + 1]) {
      keyPath = tokens[i + 1];
      i += 1;
      continue;
    }
    if (!token.startsWith("-")) {
      target = token;
    }
  }

  if (!target.includes("@")) return null;
  const [user, host] = target.split("@");
  if (!user || !host) return null;

  return {
    tool_type: "ssh",
    name: `${formatHostName(host, "Server")} SSH`,
    config: {
      host,
      port,
      user,
      auth_type: "key",
      password: keyPath,
    },
  };
}

function detectOpenApiDraft(raw: string): ToolAddDraft | null {
  const text = raw.trim();
  if (!text || (!/openapi/i.test(text) && !/swagger/i.test(text))) return null;

  const urlMatch = text.match(/https?:\/\/[^\s'",]+/i);
  if (!urlMatch) return null;

  const title =
    text.match(/"title"\s*:\s*"([^"]+)"/)?.[1] ??
    text.match(/^\s*title\s*:\s*["']?(.+?)["']?\s*$/im)?.[1];

  return {
    tool_type: "custom_api",
    name: title?.trim() || "OpenAPI Import",
    config: {
      base_url: urlMatch[0],
      method: "GET",
      auth_header: "",
      headers_json: "",
      content_type: "application/json",
      body_template: "",
      description: "Импортировано из OpenAPI/Swagger-подобного описания. Проверь endpoint и дополни схему вызова перед сохранением.",
    },
  };
}

function detectCurlDraft(raw: string): ToolAddDraft | null {
  const trimmed = raw.trim();
  if (!trimmed.startsWith("curl ")) return null;

  const tokens = splitShellLike(trimmed);
  let method = "GET";
  let url = "";
  const headers: Record<string, string> = {};
  const bodyParts: string[] = [];

  for (let i = 1; i < tokens.length; i += 1) {
    const token = tokens[i];
    if ((token === "-X" || token === "--request") && tokens[i + 1]) {
      method = tokens[i + 1].toUpperCase();
      i += 1;
      continue;
    }
    if ((token === "-H" || token === "--header") && tokens[i + 1]) {
      const headerLine = tokens[i + 1];
      const separator = headerLine.indexOf(":");
      if (separator !== -1) {
        const key = headerLine.slice(0, separator).trim();
        const value = headerLine.slice(separator + 1).trim();
        if (key) headers[key] = value;
      }
      i += 1;
      continue;
    }
    if (
      ["-d", "--data", "--data-raw", "--data-binary", "--data-urlencode"].includes(token) &&
      tokens[i + 1]
    ) {
      bodyParts.push(tokens[i + 1]);
      i += 1;
      continue;
    }
    if (token === "--url" && tokens[i + 1]) {
      url = tokens[i + 1];
      i += 1;
      continue;
    }
    if (!url && /^https?:\/\//i.test(token)) {
      url = token;
    }
  }

  if (!url) return null;

  try {
    const parsed = new URL(url);
    const authHeader = headers.Authorization ?? headers.authorization ?? "";
    const contentType = headers["Content-Type"] ?? headers["content-type"] ?? "";
    delete headers.Authorization;
    delete headers.authorization;
    delete headers["Content-Type"];
    delete headers["content-type"];

    const hasBody = bodyParts.length > 0;
    const bodyText = bodyParts.join("\n");
    if (parsed.hostname === "api.brightdata.com" && parsed.pathname === "/request" && hasBody) {
      let parsedBody: Record<string, unknown> | null = null;
      try {
        const candidate = JSON.parse(bodyText);
        if (candidate && typeof candidate === "object" && !Array.isArray(candidate)) {
          parsedBody = candidate as Record<string, unknown>;
        }
      } catch {
        parsedBody = null;
      }
      return {
        tool_type: "bright_data_serp",
        name: "Bright Data SERP",
        config: {
          api_key: authHeader.replace(/^Bearer\s+/i, "").trim(),
          zone: String(parsedBody?.zone ?? "serp_api1"),
          format: String(parsedBody?.format ?? "raw"),
          description: "Bright Data SERP fetch for current search-result pages and market research. Pass a plain query or full URL.",
        },
      };
    }
    return {
      tool_type: hasBody ? "custom_api" : "http_api",
      name: `${formatHostName(parsed.hostname, "HTTP")} API`,
      config: hasBody
        ? {
            base_url: `${parsed.origin}${parsed.pathname}${parsed.search}`,
            method,
            auth_header: authHeader,
            headers_json: Object.keys(headers).length ? JSON.stringify(headers, null, 2) : "",
            content_type: contentType || "application/json",
            body_template: bodyText,
            description: "Импортировано из curl. Проверь тело запроса и при необходимости замени значения на шаблонные переменные.",
          }
        : {
            base_url: `${parsed.origin}${parsed.pathname}${parsed.search}`,
            method,
            auth_header: authHeader,
            headers_json: Object.keys(headers).length ? JSON.stringify(headers, null, 2) : "",
          },
    };
  } catch {
    return null;
  }
}

function detectImportDraft(raw: string): ToolAddDraft | null {
  return (
    detectCurlDraft(raw) ??
    detectSshDraft(raw) ??
    detectBoltDraft(raw) ??
    detectOpenApiDraft(raw) ??
    detectHttpUrlDraft(raw)
  );
}

function ToolAddForm({
  toolTypes,
  onAdd,
  onCancel,
  initialType = "",
  initialDraft = null,
}: {
  toolTypes: Record<string, ToolTypeDefinition>;
  onAdd: (tool: { name: string; tool_type: string; config: Record<string, string> }) => void;
  onCancel: () => void;
  initialType?: string;
  initialDraft?: ToolAddDraft | null;
}) {
  const seededDraft = buildInitialToolDraft(initialType, toolTypes, initialDraft);
  const [selectedType, setSelectedType] = useState(seededDraft.selectedType);
  const [name, setName] = useState(seededDraft.name);
  const [config, setConfig] = useState<Record<string, string>>(seededDraft.config);

  const typeKeys = Object.keys(toolTypes).filter((key) => !NON_ADDABLE_TOOL_TYPES.has(key));
  const currentType = selectedType ? toolTypes[selectedType] : null;
  const currentMeta = selectedType ? TOOL_ADD_TYPE_META[selectedType] : null;
  const groupedTypeKeys = TOOL_ADD_GROUPS.map((group) => ({
    ...group,
    types: group.types.filter((type) => typeKeys.includes(type) && toolTypes[type]),
  })).filter((group) => group.types.length > 0);

  function resetSelection() {
    setSelectedType("");
    setName("");
    setConfig({});
  }

  function handleTypeChange(type: string | null) {
    if (!type) return;
    setSelectedType(type);
    const typeInfo = toolTypes[type];
    if (typeInfo) {
      setName(typeInfo.name);
      const initialConfig: Record<string, string> = {};
      for (const field of typeInfo.fields) {
        initialConfig[field.name] = field.name === "transport" ? "stdio" : "";
      }
      setConfig(initialConfig);
    }
  }

  function handleSubmit() {
    if (!name.trim() || !selectedType) return;
    if (selectedType === "mcp_server") {
      const transport = config.transport || "stdio";
      if (transport === "http" && !config.url?.trim()) return;
      if (transport === "stdio" && !config.command?.trim()) return;
    }
    onAdd({ name: name.trim(), tool_type: selectedType, config });
  }

  if (!selectedType) {
    return (
      <div className="flex h-full flex-col bg-white">
        <div className="flex-1 overflow-y-auto px-8 py-7">
          <div className="mx-auto max-w-6xl">
            <div className="flex items-start justify-between gap-6">
              <div className="max-w-3xl">
                <p className="text-[11px] font-semibold uppercase tracking-[0.2em] text-[#4b5563]">
                  New Connection
                </p>
                <h1 className="mt-4 text-[2.25rem] font-semibold tracking-[-0.05em] text-[#09090b]">
                  Выбери способ доступа
                </h1>
                <p className="mt-3 max-w-2xl text-[15px] leading-7 text-[#5b6476]">
                  Ниже не список разрешённых сервисов, а типы адаптеров. Если тебе нужен любой внешний API, бери
                  `HTTP API` или `Custom API`. Если нужен сервер, бери `SSH`. Если граф, бери `Neo4j`. Если сервис уже
                  говорит на MCP, тогда `MCP Server`.
                </p>
              </div>
              <button
                onClick={onCancel}
                aria-label="Закрыть"
                className="cursor-pointer rounded-full border border-[#d9dde7] p-2 text-[#6b7280] transition-colors hover:border-[#111111] hover:text-[#111111]"
              >
                <X size={16} />
              </button>
            </div>

            <div className="mt-8 grid gap-6 xl:grid-cols-[320px_minmax(0,1fr)]">
              <aside className="rounded-[24px] border border-[#e0e4ec] bg-[linear-gradient(180deg,#ffffff_0%,#f7f9ff_100%)] p-6">
                <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-[#7b8190]">
                  Правило выбора
                </p>
                <div className="mt-4 space-y-4">
                  <div className="rounded-[16px] border border-[#e0e4ec] bg-white p-4">
                    <div className="text-[12px] font-semibold text-[#111111]">Любой внешний API</div>
                    <div className="mt-1 text-[12px] leading-6 text-[#6b7280]">
                      `HTTP API` для простого REST. `Custom API` для body template, описания и более сложного поведения.
                    </div>
                  </div>
                  <div className="rounded-[16px] border border-[#e0e4ec] bg-white p-4">
                    <div className="text-[12px] font-semibold text-[#111111]">Удалённый сервер</div>
                    <div className="mt-1 text-[12px] leading-6 text-[#6b7280]">
                      `SSH` нужен для файлов, контейнеров, логов и infra-задач. Это не то же самое, что локальный built-in Shell.
                    </div>
                  </div>
                  <div className="rounded-[16px] border border-[#e0e4ec] bg-white p-4">
                    <div className="text-[12px] font-semibold text-[#111111]">Граф и knowledge layer</div>
                    <div className="mt-1 text-[12px] leading-6 text-[#6b7280]">
                      `Neo4j` — для графовых связей и запросов. `MCP Server` — если внешний сервис уже готов в MCP-формате.
                    </div>
                  </div>
                </div>
              </aside>

              <div className="space-y-6">
                {groupedTypeKeys.map((group) => (
                  <section key={group.id}>
                    <div className="mb-3">
                      <h2 className="text-[13px] font-semibold uppercase tracking-[0.16em] text-[#4b5563]">
                        {group.label}
                      </h2>
                      <p className="mt-1 text-[13px] text-[#6b7280]">{group.description}</p>
                    </div>
                    <div className="grid gap-3 md:grid-cols-2">
                      {group.types.map((type) => {
                        const typeInfo = toolTypes[type];
                        const meta = TOOL_ADD_TYPE_META[type];
                        return (
                          <button
                            key={type}
                            type="button"
                            onClick={() => handleTypeChange(type)}
                            className="rounded-[22px] border border-[#d9dde7] bg-white p-5 text-left shadow-[0_18px_34px_-26px_rgba(15,23,42,0.18)] transition-all hover:-translate-y-0.5 hover:border-[#bfd4fb] hover:shadow-[0_24px_50px_-30px_rgba(17,48,105,0.24)]"
                          >
                            <div className="flex items-start justify-between gap-3">
                              <div>
                                <p className="text-[10px] font-semibold uppercase tracking-[0.18em] text-[#7b8190]">
                                  {meta?.eyebrow ?? typeInfo?.category ?? type}
                                </p>
                                <h3 className="mt-2 text-[16px] font-semibold tracking-[-0.03em] text-[#111111]">
                                  {typeInfo?.name ?? type}
                                </h3>
                              </div>
                              <div className="flex h-11 w-11 items-center justify-center rounded-[16px] border border-[#e0e4ec] bg-[#fafbff] text-[18px]">
                                {typeInfo?.icon ?? "•"}
                              </div>
                            </div>
                            <p className="mt-3 text-[13px] leading-6 text-[#5b6476]">
                              {meta?.description ?? typeInfo?.description ?? ""}
                            </p>
                          </button>
                        );
                      })}
                    </div>
                  </section>
                ))}
              </div>
            </div>
          </div>
        </div>
        <div className="flex h-[82px] items-center justify-between border-t border-[#e6e8ee] bg-white px-7">
          <div className="text-[14px] text-[#6b7280]">
            Сначала выбери тип подключения. Потом откроется детальная форма с готовыми полями.
          </div>
          <Button
            type="button"
            variant="ghost"
            onClick={onCancel}
            className="h-[44px] rounded-[12px] px-5 text-[14px] text-[#111111] hover:bg-[#f5f6fa]"
          >
            Закрыть
          </Button>
        </div>
      </div>
    );
  }

  if (selectedType === "mcp_server") {
    const transport = config.transport ?? "stdio";
    return (
      <div className="flex h-full flex-col bg-white">
        <div className="flex-1 px-8 py-6">
          <h1 className="text-[2.15rem] font-medium uppercase tracking-[0.04em] text-[#09090b]">
            CONNECT MCP SERVER
          </h1>
          <form
            onSubmit={(e) => {
              e.preventDefault();
              handleSubmit();
            }}
            className="mx-auto mt-8 max-w-[560px]"
          >
            <div className="overflow-hidden rounded-[18px] border-2 border-[#111111] bg-white">
              <div className="space-y-5 px-7 py-7">
                <div>
                  <label className="mb-2 block text-[13px] font-medium text-[#111111]">Name</label>
                  <input
                    value={name}
                    onChange={(e) => setName(e.target.value)}
                    placeholder="Name"
                    className="h-10 w-full rounded-[10px] border border-[#111111] bg-white px-4 text-[13px] text-[#111111] outline-none placeholder:text-[#111111]/42"
                  />
                </div>
                <div>
                  <label className="mb-3 block text-[13px] font-medium text-[#111111]">Transport Type</label>
                  <div className="rounded-[10px] border border-[#d9dde7] bg-white p-1">
                    <div className="grid grid-cols-2 gap-1">
                      {["stdio", "http"].map((option) => {
                        const active = transport === option;
                        return (
                          <button
                            key={option}
                            type="button"
                            onClick={() => setConfig((prev) => ({ ...prev, transport: option }))}
                            className={cn(
                              "flex h-9 items-center justify-center gap-2 rounded-[8px] text-[13px] text-[#111111]",
                              active ? "bg-[#f8f9fb]" : "bg-white"
                            )}
                          >
                            <span
                              className={cn(
                                "h-4 w-4 rounded-full border border-[#9ca3af]",
                                active && "border-[#6b7280] bg-white"
                              )}
                            >
                              <span
                                className={cn(
                                  "m-auto mt-[3px] block h-2 w-2 rounded-full bg-[#6b7280]",
                                  active ? "opacity-100" : "opacity-0"
                                )}
                              />
                            </span>
                            {option}
                          </button>
                        );
                      })}
                    </div>
                  </div>
                </div>
                <div>
                  <label className="mb-2 block text-[13px] font-medium text-[#111111]">
                    {transport === "http" ? "Command/URL" : "Command/URL"}
                  </label>
                  <input
                    value={transport === "http" ? (config.url ?? "") : (config.command ?? "")}
                    onChange={(e) =>
                      setConfig((prev) => ({
                        ...prev,
                        [transport === "http" ? "url" : "command"]: e.target.value,
                      }))
                    }
                    placeholder="Command/URL"
                    className="h-10 w-full rounded-[10px] border border-[#d9dde7] bg-white px-4 text-[13px] text-[#111111] outline-none placeholder:text-[#111111]/42"
                  />
                </div>
              </div>
              <div className="border-t border-[#e4e6eb] px-7 py-6">
                <div className="text-[13px] font-medium text-[#111111]">Handshake Log</div>
                <div className="mt-4 rounded-[10px] border border-[#d9dde7] bg-[#fafbfc] px-4 py-4 font-mono text-[12px] leading-8 text-[#111111]">
                  <div>&gt; {transport === "http" ? "Resolving remote endpoint..." : "Connecting to server..."}</div>
                  <div>&gt; Handshake initiated...</div>
                  <div>&gt; {transport === "http" ? "Waiting for HTTP response..." : "Waiting for response..."}</div>
                  <div>&gt; Connection successful. Server ready.</div>
                </div>
              </div>
            </div>
          </form>
        </div>
        <div className="flex h-[86px] items-center justify-between border-t border-[#e6e8ee] bg-white px-7">
          <div className="text-[16px] font-medium text-[#111111]">Server Configuration</div>
          <div className="flex items-center gap-3">
            <Button
              type="button"
              variant="ghost"
              onClick={onCancel}
              className="h-[46px] rounded-[12px] px-5 text-[15px] text-[#111111] hover:bg-[#f5f6fa]"
            >
              Cancel
            </Button>
            <Button
              type="submit"
              onClick={handleSubmit}
              disabled={!name.trim() || (transport === "http" ? !config.url?.trim() : !config.command?.trim())}
              className="h-[46px] rounded-[12px] bg-black px-8 text-[15px] font-medium text-white hover:bg-black/92 disabled:bg-black/30"
            >
              Connect
            </Button>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="flex h-full flex-col bg-white">
      <div className="flex-1 overflow-y-auto px-8 py-7">
        <div className="mx-auto max-w-6xl">
          <div className="flex items-start justify-between gap-6">
            <div className="max-w-3xl">
              <button
                type="button"
                onClick={resetSelection}
                className="inline-flex items-center gap-2 rounded-full border border-[#d9dde7] px-3 py-1.5 text-[12px] font-medium text-[#4b5563] transition-colors hover:border-[#111111] hover:text-[#111111]"
              >
                <span aria-hidden="true">‹</span>
                Выбрать другой тип
              </button>
              <p className="mt-5 text-[11px] font-semibold uppercase tracking-[0.18em] text-[#7b8190]">
                {currentMeta?.eyebrow ?? "Connection"}
              </p>
              <h1 className="mt-3 text-[2.2rem] font-semibold tracking-[-0.05em] text-[#09090b]">
                {currentMeta?.title ?? currentType?.name}
              </h1>
              <p className="mt-3 max-w-2xl text-[15px] leading-7 text-[#5b6476]">
                {currentMeta?.description}
              </p>
            </div>
            <button
              onClick={onCancel}
              aria-label="Отмена"
              className="cursor-pointer rounded-full border border-[#d9dde7] p-2 text-[#6b7280] transition-colors hover:border-[#111111] hover:text-[#111111]"
            >
              <X size={16} />
            </button>
          </div>

          <div className="mt-8 grid gap-6 xl:grid-cols-[320px_minmax(0,1fr)]">
            <aside className="rounded-[24px] border border-[#e0e4ec] bg-[linear-gradient(180deg,#ffffff_0%,#f7f9ff_100%)] p-6">
              <div className="flex h-12 w-12 items-center justify-center rounded-[18px] border border-[#d9dde7] bg-white text-[20px]">
                {currentType?.icon ?? "•"}
              </div>
              <p className="mt-4 text-[13px] leading-7 text-[#5b6476]">
                {currentMeta?.detail}
              </p>
              {currentMeta?.hints?.length ? (
                <div className="mt-5 space-y-2">
                  {currentMeta.hints.map((hint) => (
                    <div key={hint} className="rounded-[14px] border border-[#e0e4ec] bg-white px-4 py-3 text-[12px] leading-6 text-[#4b5563]">
                      {hint}
                    </div>
                  ))}
                </div>
              ) : null}
            </aside>

            <form
              onSubmit={(e) => {
                e.preventDefault();
                handleSubmit();
              }}
              className="overflow-hidden rounded-[24px] border border-[#d9dde7] bg-white shadow-[0_24px_60px_-46px_rgba(15,23,42,0.22)]"
            >
              <div className="space-y-6 px-7 py-7">
                <div>
                  <label className="mb-2 block text-[12px] font-semibold uppercase tracking-[0.16em] text-[#7b8190]">
                    Название подключения
                  </label>
                  <input
                    value={name}
                    onChange={(e) => setName(e.target.value)}
                    placeholder="Название подключения..."
                    className="h-11 w-full rounded-[14px] border border-[#d9dde7] bg-white px-4 text-[14px] text-[#111111] outline-none placeholder:text-[#111111]/38"
                  />
                  <p className="mt-2 font-mono text-[10px] text-[#9ca3af]">
                    id: {slugify(name)}
                  </p>
                </div>

                <div className="grid gap-4 md:grid-cols-2">
                  {currentType?.fields.map((field) => (
                    <div
                      key={field.name}
                      className={cn(
                        "rounded-[18px] border border-[#e0e4ec] bg-[#fafbff] p-4",
                        field.type === "textarea" && "md:col-span-2"
                      )}
                    >
                      <label className="mb-2 block text-[12px] font-medium text-[#111111]">
                        {field.label}
                        {field.required ? <span className="ml-1 text-destructive">*</span> : null}
                      </label>
                      {renderFieldControl({
                        field,
                        value: config[field.name] ?? "",
                        onChange: (value) => setConfig((prev) => ({ ...prev, [field.name]: value })),
                      })}
                    </div>
                  ))}
                </div>
              </div>
              <div className="flex h-[82px] items-center justify-between border-t border-[#e6e8ee] bg-white px-7">
                <div className="text-[14px] text-[#6b7280]">
                  {selectedType === "http_api" || selectedType === "custom_api"
                    ? "Этот адаптер подходит для произвольных API, не только для заранее известных провайдеров."
                    : "Проверь поля подключения и сохрани профиль."}
                </div>
                <div className="flex items-center gap-3">
                  <Button
                    type="button"
                    variant="ghost"
                    onClick={resetSelection}
                    className="h-[44px] rounded-[12px] px-5 text-[14px] text-[#111111] hover:bg-[#f5f6fa]"
                  >
                    Назад
                  </Button>
                  <Button
                    type="submit"
                    disabled={!name.trim()}
                    className="h-[44px] rounded-[12px] bg-black px-7 text-[14px] font-medium text-white hover:bg-black/92 disabled:bg-black/25"
                  >
                    <Plus size={14} className="mr-1.5" /> Сохранить подключение
                  </Button>
                </div>
              </div>
            </form>
          </div>
        </div>
      </div>
    </div>
  );
}

function ToolEditForm({
  tool,
  toolType,
  onSave,
  onCancel,
}: {
  tool: ConfiguredTool;
  toolType: ToolTypeDefinition | undefined;
  onSave: (updates: { name: string; config: Record<string, string> }) => void;
  onCancel: () => void;
}) {
  const [name, setName] = useState(tool.name);
  const [config, setConfig] = useState<Record<string, string>>({ ...tool.config });

  const fields = toolType?.fields ?? [];

  function handleSubmit() {
    if (!name.trim()) return;
    if (tool.tool_type === "mcp_server") {
      const transport = config.transport || "stdio";
      if (transport === "http" && !config.url?.trim()) return;
      if (transport === "stdio" && !config.command?.trim()) return;
    }
    onSave({ name: name.trim(), config });
  }

  return (
    <Card className="overflow-hidden border-dashed border-slate-300/80 bg-[linear-gradient(135deg,rgba(255,255,255,0.96),rgba(248,250,252,0.92))] py-0 shadow-[0_20px_60px_-44px_rgba(15,23,42,0.28)] dark:border-slate-700/80 dark:bg-[linear-gradient(135deg,rgba(15,23,42,0.88),rgba(2,6,23,0.78))]">
      <CardContent className="px-5 py-4 space-y-3">
        <div className="flex items-center justify-between">
          <span className="text-[11px] font-semibold uppercase tracking-[0.2em] text-slate-600 dark:text-slate-300">
            Редактирование
          </span>
          <button
            onClick={onCancel}
            aria-label="Отмена"
            className="p-1 rounded-md text-muted-foreground hover:text-foreground cursor-pointer"
          >
            <X size={14} />
          </button>
        </div>

        <form
          onSubmit={(e) => {
            e.preventDefault();
            handleSubmit();
          }}
        >
          <div className="mb-3">
            <label className="mb-1 block text-[11px] text-muted-foreground">Название</label>
            <input
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="Название..."
              className={INPUT_CLASS}
            />
          </div>

          {tool.tool_type === "mcp_server" ? (
            <div className="mb-3 space-y-4">
              <div>
                <label className="mb-1 block text-[11px] text-muted-foreground">Transport Type</label>
                <McpTransportPicker
                  value={config.transport ?? "stdio"}
                  onChange={(value) => setConfig((prev) => ({ ...prev, transport: value }))}
                />
              </div>

              {(config.transport ?? "stdio") === "stdio" ? (
                <>
                  <div>
                    <label className="mb-1 block text-[11px] text-muted-foreground">Command</label>
                    <input
                      value={config.command ?? ""}
                      onChange={(e) => setConfig((prev) => ({ ...prev, command: e.target.value }))}
                      placeholder="npx -y @modelcontextprotocol/server-github"
                      className={INPUT_CLASS}
                    />
                  </div>
                  <div>
                    <label className="mb-1 block text-[11px] text-muted-foreground">Args</label>
                    <input
                      value={config.args ?? ""}
                      onChange={(e) => setConfig((prev) => ({ ...prev, args: e.target.value }))}
                      placeholder="--project my-app"
                      className={INPUT_CLASS}
                    />
                  </div>
                  <div>
                    <label className="mb-1 block text-[11px] text-muted-foreground">Environment (JSON)</label>
                    <textarea
                      value={config.env ?? ""}
                      onChange={(e) => setConfig((prev) => ({ ...prev, env: e.target.value }))}
                      placeholder='{"GITHUB_TOKEN":"ghp_..."}'
                      rows={4}
                      className={`${INPUT_CLASS} min-h-24 resize-y leading-relaxed`}
                    />
                  </div>
                </>
              ) : (
                <>
                  <div>
                    <label className="mb-1 block text-[11px] text-muted-foreground">URL</label>
                    <input
                      value={config.url ?? ""}
                      onChange={(e) => setConfig((prev) => ({ ...prev, url: e.target.value }))}
                      placeholder="https://stitch.googleapis.com/mcp"
                      className={INPUT_CLASS}
                    />
                  </div>
                  <div>
                    <label className="mb-1 block text-[11px] text-muted-foreground">HTTP Headers (JSON)</label>
                    <textarea
                      value={config.headers ?? ""}
                      onChange={(e) => setConfig((prev) => ({ ...prev, headers: e.target.value }))}
                      placeholder='{"X-Goog-Api-Key":"..."}'
                      rows={4}
                      className={`${INPUT_CLASS} min-h-24 resize-y leading-relaxed`}
                    />
                  </div>
                </>
              )}

              <McpHandshakeLog
                transport={config.transport ?? "stdio"}
                lines={tool.last_validation_result?.log}
              />
            </div>
          ) : (
            <div className="space-y-2 mb-3">
              {fields.map((field) => (
                <div key={field.name}>
                  <label className="mb-1 block text-[11px] text-muted-foreground">
                    {field.label}
                    {field.required && <span className="text-destructive ml-0.5">*</span>}
                  </label>
                  {renderFieldControl({
                    field,
                    value: config[field.name] ?? "",
                    onChange: (value) => setConfig((prev) => ({ ...prev, [field.name]: value })),
                  })}
                </div>
              ))}
            </div>
          )}

          <div className="flex gap-2">
            <Button type="button" variant="outline" size="sm" className="flex-1 rounded-full text-xs" onClick={onCancel}>
              Отмена
            </Button>
            <Button
              type="submit"
              disabled={!name.trim() || (tool.tool_type === "mcp_server" && ((config.transport ?? "stdio") === "http" ? !config.url?.trim() : !config.command?.trim()))}
              size="sm"
              className="flex-1 rounded-full bg-slate-950 text-xs text-white hover:bg-slate-800 dark:bg-slate-100 dark:text-slate-950 dark:hover:bg-white"
            >
              Сохранить
            </Button>
          </div>
        </form>
      </CardContent>
    </Card>
  );
}

export function SettingsView() {
  const [tools, setTools] = useState<ConfiguredTool[]>([]);
  const [toolTypes, setToolTypes] = useState<Record<string, ToolTypeDefinition>>({});
  const [templates, setTemplates] = useState<Record<string, PromptTemplate>>({});
  const [workspacePresets, setWorkspacePresets] = useState<WorkspacePreset[]>([]);
  const [accounts, setAccounts] = useState<AccountsByProvider>({});
  const [accountsHealth, setAccountsHealth] = useState<AccountHealth | null>(null);
  const [accountsMessage, setAccountsMessage] = useState("");
  const [accountBusyKey, setAccountBusyKey] = useState("");
  const [accountLabelDrafts, setAccountLabelDrafts] = useState<Record<string, string>>({});
  const [addToolType, setAddToolType] = useState<string | null>(null);
  const [addToolDraft, setAddToolDraft] = useState<ToolAddDraft | null>(null);
  const [editingToolId, setEditingToolId] = useState<string | null>(null);
  const [deletingToolId, setDeletingToolId] = useState<string | null>(null);
  const [validatingToolId, setValidatingToolId] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [importSource, setImportSource] = useState("");
  const [importPreview, setImportPreview] = useState<ToolAddDraft | null>(null);
  const [importError, setImportError] = useState<string | null>(null);
  const [workspaceName, setWorkspaceName] = useState("");
  const [workspaceDescription, setWorkspaceDescription] = useState("");
  const [workspacePathsDraft, setWorkspacePathsDraft] = useState("");
  const [editingWorkspaceId, setEditingWorkspaceId] = useState<string | null>(null);

  useEffect(() => {
    let mounted = true;

    async function loadData() {
      setIsLoading(true);
      const results = await Promise.allSettled([
        getAccounts(),
        getAccountsHealth(),
        getConfiguredTools(),
        getToolTypes(),
        getPromptTemplates(),
        getWorkspacePresets(),
      ]);

      if (!mounted) return;

      if (results[0].status === "fulfilled") setAccounts(results[0].value.accounts);
      if (results[1].status === "fulfilled") setAccountsHealth(results[1].value);
      if (results[2].status === "fulfilled") setTools(results[2].value);
      if (results[3].status === "fulfilled") setToolTypes(results[3].value);
      if (results[4].status === "fulfilled") setTemplates(results[4].value);
      if (results[5].status === "fulfilled") setWorkspacePresets(results[5].value);
      setIsLoading(false);
      void refreshAccountsState();
    }

    loadData();
    return () => { mounted = false; };
  }, []);

  async function refreshTools() {
    try {
      const data = await getConfiguredTools();
      setTools(data);
    } catch {
      // keep stale data on error
    }
  }

  async function refreshWorkspaces() {
    try {
      const data = await getWorkspacePresets();
      setWorkspacePresets(data);
    } catch {
      // keep stale data on error
    }
  }

  async function refreshAccountsState() {
    try {
      const [accountsData, healthData] = await Promise.all([
        reloadAccounts(),
        getAccountsHealth(),
      ]);
      setAccounts(accountsData.accounts);
      setAccountsHealth(healthData);
    } catch (error) {
      setAccountsMessage(error instanceof Error ? error.message : "Failed to refresh accounts.");
    }
  }

  function setAccountLabelDraft(provider: string, accountName: string, label: string) {
    setAccountLabelDrafts((prev) => ({
      ...prev,
      [`${provider}:${accountName}`]: label,
    }));
  }

  async function handleOpenProviderLogin(provider: string) {
    setAccountBusyKey(`${provider}:login`);
    try {
      const result = await openProviderLogin(provider);
      setAccountsMessage(result.message);
    } catch (error) {
      setAccountsMessage(error instanceof Error ? error.message : "Failed to open login flow.");
    } finally {
      setAccountBusyKey("");
    }
  }

  async function handleImportProviderSession(provider: string) {
    setAccountBusyKey(`${provider}:import`);
    try {
      const result = await importProviderSession(provider);
      setAccountsMessage(result.message);
      await refreshAccountsState();
    } catch (error) {
      setAccountsMessage(error instanceof Error ? error.message : "Failed to import provider session.");
    } finally {
      setAccountBusyKey("");
    }
  }

  async function handleReauthorizeProviderAccount(provider: string, accountName: string) {
    setAccountBusyKey(`${provider}:${accountName}:reauth`);
    try {
      const result = await reauthorizeProviderAccount(provider, accountName);
      setAccountsMessage(result.message);
    } catch (error) {
      setAccountsMessage(error instanceof Error ? error.message : "Failed to reauthorize account.");
    } finally {
      setAccountBusyKey("");
    }
  }

  async function handleSaveProviderAccountLabel(provider: string, accountName: string) {
    const key = `${provider}:${accountName}`;
    const fallbackLabel = accounts[provider]?.find((account) => account.name === accountName)?.label ?? "";
    const label = accountLabelDrafts[key] ?? fallbackLabel;
    setAccountBusyKey(`${provider}:${accountName}:label`);
    try {
      const result = await updateProviderAccount(provider, accountName, label);
      setAccountsMessage(result.message);
      setAccountLabelDrafts((prev) => ({
        ...prev,
        [key]: result.label,
      }));
      await refreshAccountsState();
    } catch (error) {
      setAccountsMessage(error instanceof Error ? error.message : "Failed to update account label.");
    } finally {
      setAccountBusyKey("");
    }
  }

  async function handleAddTool(tool: { name: string; tool_type: string; config: Record<string, string> }) {
    const id = slugify(tool.name);
    await addConfiguredTool({ id, ...tool, enabled: true });
    setAddToolType(null);
    setAddToolDraft(null);
    await refreshTools();
  }

  async function handleUpdateTool(id: string, updates: { name: string; config: Record<string, string> }) {
    await updateConfiguredTool(id, updates);
    setEditingToolId(null);
    await refreshTools();
  }

  async function handleDeleteTool(id: string) {
    await deleteConfiguredTool(id);
    setDeletingToolId(null);
    await refreshTools();
  }

  async function handleToggleEnabled(tool: ConfiguredTool) {
    await updateConfiguredTool(tool.id, { enabled: !tool.enabled });
    await refreshTools();
  }

  async function handleValidateTool(tool: ConfiguredTool) {
    setValidatingToolId(tool.id);
    try {
      await validateConfiguredTool(tool.id);
      await refreshTools();
    } finally {
      setValidatingToolId(null);
    }
  }

  async function handleAddWorkspacePreset() {
    const name = workspaceName.trim();
    const paths = workspacePathsDraft
      .split("\n")
      .map((item) => item.trim())
      .filter(Boolean);
    if (!name || paths.length === 0) return;
    if (editingWorkspaceId) {
      await updateWorkspacePreset(editingWorkspaceId, {
        name,
        description: workspaceDescription.trim() || null,
        paths,
      });
    } else {
      await addWorkspacePreset({
        id: slugify(name),
        name,
        description: workspaceDescription.trim() || null,
        paths,
      });
    }
    setWorkspaceName("");
    setWorkspaceDescription("");
    setWorkspacePathsDraft("");
    setEditingWorkspaceId(null);
    await refreshWorkspaces();
  }

  async function handleDeleteWorkspacePreset(id: string) {
    await deleteWorkspacePreset(id);
    if (editingWorkspaceId === id) {
      setWorkspaceName("");
      setWorkspaceDescription("");
      setWorkspacePathsDraft("");
      setEditingWorkspaceId(null);
    }
    await refreshWorkspaces();
  }

  function handleEditWorkspacePreset(preset: WorkspacePreset) {
    setEditingWorkspaceId(preset.id);
    setWorkspaceName(preset.name);
    setWorkspaceDescription(preset.description ?? "");
    setWorkspacePathsDraft(preset.paths.join("\n"));
  }

  function resetWorkspaceForm() {
    setWorkspaceName("");
    setWorkspaceDescription("");
    setWorkspacePathsDraft("");
    setEditingWorkspaceId(null);
  }

  function openEmptyAddForm(initialType: string = "") {
    setAddToolDraft(null);
    setAddToolType(initialType);
    setEditingToolId(null);
  }

  function handleAnalyzeImport() {
    const draft = detectImportDraft(importSource);
    if (!draft) {
      setImportPreview(null);
      setImportError("Не смог разобрать ввод. Сейчас поддержаны curl, http(s) URL, ssh user@host и bolt://...");
      return;
    }
    setImportError(null);
    setImportPreview(draft);
  }

  const templateKeys = Object.keys(templates);
  const quickConnectCards = QUICK_CONNECT_PRESETS
    .map((preset) => {
      const typeInfo = toolTypes[preset.type];
      if (!typeInfo) return null;
      return {
        ...preset,
        icon: typeInfo.icon,
        category: typeInfo.category,
      };
    })
    .filter((preset): preset is NonNullable<typeof preset> => preset !== null);
  const connectionTools = tools.filter((tool) => CONNECTION_TOOL_TYPES.has(tool.tool_type));
  const runtimeTools = tools.filter((tool) => !CONNECTION_TOOL_TYPES.has(tool.tool_type));

  function renderToolRow(tool: ConfiguredTool) {
    if (editingToolId === tool.id) {
      return (
        <ToolEditForm
          key={tool.id}
          tool={tool}
          toolType={toolTypes[tool.tool_type]}
          onSave={(updates) => handleUpdateTool(tool.id, updates)}
          onCancel={() => setEditingToolId(null)}
        />
      );
    }

    const isMissing = hasMissingRequired(tool, toolTypes);
    const typeInfo = toolTypes[tool.tool_type];
    const compatibilityEntries = Object.entries(tool.compatibility ?? {}).filter(
      ([provider, capability]) => provider !== "minimax" && capability !== "unavailable"
    );
    const validationOk = tool.validation_status === "valid";
    const validationError = tool.validation_status === "invalid";
    const guardrailBlocked = tool.guardrail_status === "blocked";
    const guardrailWarn = tool.guardrail_status === "warn";
    const guardrailSummary = tool.last_guardrail_report?.summary;

    return (
      <div
        key={tool.id}
        className={cn(
          "group flex items-center gap-3 rounded-[18px] border border-[#e0e4ec] bg-white p-3.5 transition-all",
          !tool.enabled && "opacity-50"
        )}
      >
        <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-[14px] border border-[#e0e4ec] bg-white text-muted-foreground">
          {typeInfo?.icon ? (
            <span className="text-sm">{typeInfo.icon}</span>
          ) : (
            <Settings2 size={14} strokeWidth={1.5} />
          )}
        </div>

        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2">
            <span className="text-sm font-medium truncate">{tool.name}</span>
            {isMissing && (
              <span title="Не заполнены обязательные поля" className="text-amber-500">
                <AlertTriangle size={13} />
              </span>
            )}
            {validationOk ? (
              <span title="Проверено" className="text-emerald-600">
                <CheckCircle2 size={13} />
              </span>
            ) : null}
            {guardrailBlocked ? (
              <span title="Заблокировано guardrails" className="text-rose-600">
                <ShieldAlert size={13} />
              </span>
            ) : guardrailWarn ? (
              <span title="Под guarded wrapper" className="text-amber-600">
                <Shield size={13} />
              </span>
            ) : tool.guardrail_status === "safe" ? (
              <span title="Security scan чистый" className="text-emerald-600">
                <ShieldCheck size={13} />
              </span>
            ) : null}
          </div>
          <div className="mt-0.5 flex flex-wrap items-center gap-1.5">
            <Badge variant="outline" className="border-[#e0e4ec] bg-white px-1.5 py-0 text-[10px] font-normal">
              {typeInfo?.name ?? tool.tool_type}
            </Badge>
            <Badge variant="outline" className="border-[#e0e4ec] bg-white px-1.5 py-0 text-[10px] font-normal">
              {CONNECTION_TOOL_TYPES.has(tool.tool_type) ? "external connection" : "built-in runtime"}
            </Badge>
            {tool.tool_type === "mcp_server" && (
              <Badge variant="outline" className="border-[#e0e4ec] bg-white px-1.5 py-0 text-[10px] font-normal uppercase">
                {(tool.config.transport || "stdio").toUpperCase()}
              </Badge>
            )}
            {tool.guardrail_status && tool.guardrail_status !== "unknown" && (
              <Badge
                variant="outline"
                className={cn(
                  "px-1.5 py-0 text-[10px] font-normal uppercase",
                  guardrailBlocked
                    ? "border-rose-200 bg-rose-50 text-rose-700"
                    : guardrailWarn
                      ? "border-amber-200 bg-amber-50 text-amber-700"
                      : "border-emerald-200 bg-emerald-50 text-emerald-700"
                )}
              >
                security: {tool.guardrail_status}
              </Badge>
            )}
            {tool.wrapper_mode && tool.wrapper_mode !== "direct" && (
              <Badge variant="outline" className="border-sky-200 bg-sky-50 px-1.5 py-0 text-[10px] font-normal uppercase text-sky-700">
                {tool.wrapper_mode}
              </Badge>
            )}
            {compatibilityEntries.map(([provider, capability]) => (
              <Badge
                key={`${tool.id}-${provider}`}
                variant="outline"
                className={cn(
                  "px-1.5 py-0 text-[10px] font-normal uppercase",
                  capability === "native"
                    ? "border-emerald-200 bg-emerald-50 text-emerald-700"
                    : "border-amber-200 bg-amber-50 text-amber-700"
                )}
              >
                {provider}: {capability}
              </Badge>
            ))}
            <span className="text-[10px] text-muted-foreground/50 font-mono">
              {tool.id}
            </span>
          </div>
          {validationError && tool.last_validation_result?.error ? (
            <p className="mt-1 text-[11px] text-rose-600">
              {tool.last_validation_result.error}
            </p>
          ) : null}
          {tool.last_validation_result?.log?.length ? (
            <p className="mt-1 text-[11px] text-muted-foreground/70">
              {tool.last_validation_result.log[tool.last_validation_result.log.length - 1]}
            </p>
          ) : null}
          {guardrailSummary ? (
            <p className={cn("mt-1 text-[11px]", guardrailBlocked ? "text-rose-600" : guardrailWarn ? "text-amber-700" : "text-emerald-700")}>
              {guardrailSummary}
            </p>
          ) : null}
        </div>

        <div className="flex items-center gap-1 shrink-0">
          <Button
            variant="ghost"
            size="icon-xs"
            onClick={() => handleValidateTool(tool)}
            aria-label="Проверить"
            disabled={validatingToolId === tool.id}
          >
            {validatingToolId === tool.id ? (
              <Loader2 size={12} className="animate-spin" />
            ) : (
              <RefreshCw size={12} />
            )}
          </Button>
          <button
            onClick={() => handleToggleEnabled(tool)}
            className={cn(
              "relative h-5 w-9 rounded-full border transition-colors cursor-pointer",
              tool.enabled
                ? "bg-green-500/20 border-green-500/30"
                : "bg-muted border-border"
            )}
            aria-label={tool.enabled ? "Выключить" : "Включить"}
          >
            <span
              className={cn(
                "absolute top-0.5 h-3.5 w-3.5 rounded-full transition-all",
                tool.enabled
                  ? "left-[18px] bg-green-500"
                  : "left-0.5 bg-muted-foreground/40"
              )}
            />
          </button>
          <Button
            variant="ghost"
            size="icon-xs"
            onClick={() => {
              setEditingToolId(tool.id);
              setAddToolType(null);
              setAddToolDraft(null);
            }}
            aria-label="Редактировать"
          >
            <Pencil size={12} />
          </Button>
          {deletingToolId === tool.id ? (
            <div className="flex items-center gap-1">
              <Button
                variant="destructive"
                size="icon-xs"
                onClick={() => handleDeleteTool(tool.id)}
                aria-label="Подтвердить удаление"
              >
                <Trash2 size={12} />
              </Button>
              <Button
                variant="ghost"
                size="icon-xs"
                onClick={() => setDeletingToolId(null)}
                aria-label="Отменить удаление"
              >
                <X size={12} />
              </Button>
            </div>
          ) : (
            <Button
              variant="ghost"
              size="icon-xs"
              onClick={() => setDeletingToolId(tool.id)}
              aria-label="Удалить"
            >
              <Trash2 size={12} />
            </Button>
          )}
        </div>
      </div>
    );
  }

  if (addToolType !== null || addToolDraft !== null) {
    return (
      <div className="flex h-full flex-col bg-white">
        <ToolAddForm
          key={
            addToolDraft
              ? `${addToolDraft.tool_type}:${addToolDraft.name}`
              : addToolType || "manual"
          }
          toolTypes={toolTypes}
          onAdd={handleAddTool}
          onCancel={() => {
            setAddToolType(null);
            setAddToolDraft(null);
          }}
          initialType={addToolDraft?.tool_type ?? addToolType ?? ""}
          initialDraft={addToolDraft}
        />
      </div>
    );
  }

  return (
    <div className="flex h-full flex-col bg-white">
      <div className="flex-1 overflow-y-auto px-8 py-6">
        <div className="mx-auto max-w-5xl space-y-8">
          <section className="rounded-[24px] border border-[#e6e8ee] bg-white px-6 py-6">
            <div className="flex items-start justify-between gap-6">
              <div className="max-w-2xl">
                <span className="rounded-full border border-[#b8d3f7] bg-white px-3 py-1 text-[10px] font-medium uppercase tracking-[0.18em] text-[#3b82f6]">
                  Tool Registry
                </span>
                <h2 className="mt-4 text-[2rem] font-semibold tracking-[-0.04em] text-[#111111]">
                  Настройки рабочего пространства
                </h2>
                <p className="mt-2 text-[15px] leading-7 text-[#5b6476]">
                  Здесь живут инструменты, prompt templates и конфигурация для локального multi-agent cockpit.
                  Держи registry в порядке, чтобы сценарии запускались без ручной переклейки.
                </p>
              </div>
              <div className="grid min-w-[200px] grid-cols-2 gap-3">
                <div className="rounded-[16px] border border-[#e0e4ec] bg-white px-4 py-3">
                  <p className="text-[10px] uppercase tracking-[0.16em] text-[#7b8190]">Connections</p>
                  <p className="mt-1 text-[28px] font-semibold tracking-[-0.04em] text-[#111111]">{connectionTools.length}</p>
                </div>
                <div className="rounded-[16px] border border-[#e0e4ec] bg-white px-4 py-3">
                  <p className="text-[10px] uppercase tracking-[0.16em] text-[#7b8190]">Templates</p>
                  <p className="mt-1 text-[28px] font-semibold tracking-[-0.04em] text-[#111111]">{templateKeys.length}</p>
                </div>
              </div>
            </div>
          </section>

          <SettingsAccountsPanel
            accounts={accounts}
            health={accountsHealth}
            message={accountsMessage}
            busyKey={accountBusyKey}
            labelDrafts={accountLabelDrafts}
            onLabelDraftChange={setAccountLabelDraft}
            onRefresh={() => {
              void refreshAccountsState();
            }}
            onOpenLogin={(provider) => {
              void handleOpenProviderLogin(provider);
            }}
            onImport={(provider) => {
              void handleImportProviderSession(provider);
            }}
            onReauthorize={(provider, accountName) => {
              void handleReauthorizeProviderAccount(provider, accountName);
            }}
            onSaveLabel={(provider, accountName) => {
              void handleSaveProviderAccountLabel(provider, accountName);
            }}
          />

          {/* Section 1: Tools */}
          <section className="rounded-[24px] border border-[#e6e8ee] bg-white p-6">
            <div className="mb-4 flex items-center justify-between">
              <div>
                <div className="flex items-center gap-2">
                  <Settings2 size={16} className="text-[#3b82f6]" />
                  <h3 className="text-sm font-medium text-slate-950">Подключения и инструменты</h3>
                  {tools.length > 0 && (
                    <Badge variant="outline" className="border-[#e0e4ec] bg-white px-1.5 py-0 text-[10px] font-normal">
                      {tools.length}
                    </Badge>
                  )}
                </div>
                <p className="mt-1 text-[12px] leading-6 text-[#6b7280]">
                  API, SSH, граф и MCP живут здесь как отдельные подключения. Внутри система всё равно приводит их к tool/MCP слою,
                  но в UX это должны быть нормальные интеграции, а не только кнопка для MCP.
                </p>
              </div>
              <Button
                variant="outline"
                size="sm"
                className="rounded-[12px] border-[#d9dde7] bg-white text-xs"
                onClick={() => {
                  openEmptyAddForm();
                }}
              >
                <Plus size={12} className="mr-1" /> Добавить подключение
              </Button>
            </div>

            {isLoading ? (
              <div className="flex items-center justify-center py-12">
                <div className="h-1.5 w-1.5 rounded-full bg-muted-foreground/40 animate-pulse" />
              </div>
            ) : (
              <div className="space-y-2">
                <div className="mb-4 rounded-[20px] border border-[#e0e4ec] bg-white p-4">
                  <div className="flex items-start justify-between gap-4">
                    <div className="max-w-2xl">
                      <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-[#4b5563]">
                        Import
                      </p>
                      <p className="mt-1 text-[12px] leading-6 text-[#6b7280]">
                        Вставь `curl`, обычный API URL, `ssh user@host` или `bolt://...`, и я подготовлю подключение с уже заполненными полями.
                      </p>
                    </div>
                    <Button
                      variant="outline"
                      size="sm"
                      className="shrink-0 rounded-[12px] text-xs"
                      onClick={handleAnalyzeImport}
                      disabled={!importSource.trim()}
                    >
                      Разобрать ввод
                    </Button>
                  </div>
                  <div className="mt-4 grid gap-4 xl:grid-cols-[minmax(0,1fr)_280px]">
                    <textarea
                      value={importSource}
                      onChange={(e) => setImportSource(e.target.value)}
                      placeholder={"curl https://api.example.com/v1/search -H 'Authorization: Bearer ...'\nssh admin@10.0.0.5 -i ~/.ssh/prod\nbolt://localhost:7687"}
                      rows={6}
                      className={`${INPUT_CLASS} min-h-32 resize-y leading-relaxed`}
                    />
                    <div className="rounded-[18px] border border-[#e0e4ec] bg-[#fafbfc] p-4">
                      {importPreview ? (
                        <>
                          <p className="text-[10px] font-semibold uppercase tracking-[0.18em] text-[#7b8190]">
                            Detected
                          </p>
                          <p className="mt-2 text-sm font-medium text-[#111111]">{importPreview.name}</p>
                          <p className="mt-1 text-[12px] text-[#6b7280]">{importPreview.tool_type}</p>
                          <div className="mt-3 space-y-1">
                            {Object.entries(importPreview.config)
                              .filter(([, value]) => String(value).trim())
                              .slice(0, 4)
                              .map(([key, value]) => (
                                <div key={key} className="font-mono text-[10px] text-[#6b7280]">
                                  {key}: {String(value).slice(0, 72)}
                                </div>
                              ))}
                          </div>
                          <Button
                            type="button"
                            size="sm"
                            className="mt-4 w-full rounded-[12px] bg-black text-xs text-white hover:bg-black/90"
                            onClick={() => {
                              setAddToolDraft(importPreview);
                              setAddToolType(importPreview.tool_type);
                            }}
                          >
                            Открыть форму с автозаполнением
                          </Button>
                        </>
                      ) : (
                        <>
                          <p className="text-[10px] font-semibold uppercase tracking-[0.18em] text-[#7b8190]">
                            Preview
                          </p>
                          <p className="mt-2 text-[12px] leading-6 text-[#6b7280]">
                            {importError ?? "Сюда придёт распознанный тип подключения и основные поля."}
                          </p>
                        </>
                      )}
                    </div>
                  </div>
                </div>

                <div className="mb-4 rounded-[20px] border border-[#e0e4ec] bg-[#fafbff] p-4">
                  <div className="flex items-start justify-between gap-4">
                    <div className="max-w-2xl">
                      <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-[#4b5563]">
                        Quick connect
                      </p>
                      <p className="mt-1 text-[12px] leading-6 text-[#6b7280]">
                        Самые полезные подключения вынесены отдельно: обычный API, SSH-сервер, графовая база и чистый MCP.
                      </p>
                    </div>
                    <Button
                      variant="ghost"
                      size="sm"
                      className="rounded-[12px] px-3 text-xs text-[#111111] hover:bg-white"
                      onClick={() => {
                        openEmptyAddForm();
                      }}
                    >
                      Выбрать тип вручную
                    </Button>
                  </div>
                  <div className="mt-4 grid gap-3 md:grid-cols-2 xl:grid-cols-5">
                    {quickConnectCards.map((preset) => (
                      <button
                        key={preset.type}
                        type="button"
                        onClick={() => {
                          openEmptyAddForm(preset.type);
                        }}
                        className="rounded-[18px] border border-[#d9dde7] bg-white p-4 text-left transition-colors hover:border-[#bfd4fb] hover:bg-[#fdfdff]"
                      >
                        <div className="flex items-start justify-between gap-3">
                          <div>
                            <p className="text-[10px] font-semibold uppercase tracking-[0.18em] text-[#7b8190]">
                              {preset.eyebrow}
                            </p>
                            <p className="mt-2 text-sm font-medium text-[#111111]">{preset.title}</p>
                          </div>
                          <span className="text-lg leading-none">{preset.icon}</span>
                        </div>
                        <p className="mt-3 text-[12px] leading-5 text-[#6b7280]">
                          {preset.description}
                        </p>
                        <p className="mt-3 text-[10px] uppercase tracking-[0.16em] text-[#9ca3af]">
                          {preset.category}
                        </p>
                      </button>
                    ))}
                  </div>
                </div>

                <div className="rounded-[18px] border border-dashed border-[#d9dde7] bg-[#fafbff] px-4 py-4 text-[12px] leading-6 text-[#6b7280]">
                  `Connections` ниже — это твои реальные внешние API / SSH / graph / MCP. `Built-ins` — локальные runtime-инструменты системы, они не заменяют серверные подключения.
                </div>

                <div className="pt-2">
                  <div className="mb-2 flex items-center gap-2">
                    <span className="text-[11px] font-semibold uppercase tracking-[0.18em] text-[#4b5563]">
                      External Connections
                    </span>
                    <Badge variant="outline" className="border-[#e0e4ec] bg-white px-1.5 py-0 text-[10px] font-normal">
                      {connectionTools.length}
                    </Badge>
                  </div>
                  {connectionTools.length > 0 ? (
                    <div className="space-y-2">
                      {connectionTools.map(renderToolRow)}
                    </div>
                  ) : (
                    <div className="rounded-[18px] border border-dashed border-[#d9dde7] bg-[#fafbff] px-4 py-5 text-[12px] text-[#6b7280]">
                      Пока нет ни одного внешнего подключения. Добавь API, SSH, граф или MCP выше через quick connect или import.
                    </div>
                  )}
                </div>

                {runtimeTools.length > 0 && (
                  <div className="pt-4">
                    <div className="mb-2 flex items-center gap-2">
                      <span className="text-[11px] font-semibold uppercase tracking-[0.18em] text-[#4b5563]">
                        Built-in Runtime
                      </span>
                      <Badge variant="outline" className="border-[#e0e4ec] bg-white px-1.5 py-0 text-[10px] font-normal">
                        {runtimeTools.length}
                      </Badge>
                    </div>
                    <div className="space-y-2">
                      {runtimeTools.map(renderToolRow)}
                    </div>
                  </div>
                )}

                {/* Empty state */}
                {tools.length === 0 && addToolType === null && (
                  <div className="flex flex-col items-center justify-center py-12 text-muted-foreground">
                    <Settings2 className="h-8 w-8 mb-3 opacity-30" />
                    <p className="text-sm">Нет настроенных подключений</p>
                    <p className="text-xs text-muted-foreground/50 mt-1">
                      Добавьте API, SSH, граф или MCP-сервер для начала работы
                    </p>
                  </div>
                )}

                {/* Add form */}
              </div>
            )}
          </section>

          <section className="rounded-[24px] border border-[#e6e8ee] bg-white p-6">
            <div className="mb-4 flex items-center gap-2">
              <FolderTree size={16} className="text-[#3b82f6]" />
              <h3 className="text-sm font-medium text-slate-950">Workspace Presets</h3>
              {workspacePresets.length > 0 && (
                <Badge variant="outline" className="border-[#e0e4ec] bg-white px-1.5 py-0 text-[10px] font-normal">
                  {workspacePresets.length}
                </Badge>
              )}
            </div>

            <div className="grid gap-5 xl:grid-cols-[minmax(0,1fr)_280px]">
              <div className="space-y-2">
                {workspacePresets.length === 0 ? (
                  <div className="rounded-[18px] border border-dashed border-[#d9dde7] bg-[#fafbff] px-4 py-5 text-[12px] text-[#6b7280]">
                    Пока нет сохранённых наборов директорий. Добавь хотя бы один preset для trading repo, логов или docs.
                  </div>
                ) : (
                  workspacePresets.map((preset) => (
                    <div
                      key={preset.id}
                      className="rounded-[18px] border border-[#e0e4ec] bg-white px-4 py-4"
                    >
                      <div className="flex items-start justify-between gap-3">
                        <div className="min-w-0">
                          <div className="text-sm font-medium text-[#111111]">{preset.name}</div>
                          {preset.description ? (
                            <p className="mt-1 text-[12px] text-[#6b7280]">{preset.description}</p>
                          ) : null}
                          <div className="mt-2 flex flex-col gap-1">
                            {preset.paths.map((path) => (
                              <span key={path} className="font-mono text-[11px] text-[#6b7280]">
                                {path}
                              </span>
                            ))}
                          </div>
                        </div>
                        <div className="flex items-center gap-1">
                          <Button
                            variant="ghost"
                            size="icon-xs"
                            onClick={() => handleEditWorkspacePreset(preset)}
                            aria-label="Редактировать workspace preset"
                          >
                            <Pencil size={12} />
                          </Button>
                          <Button
                            variant="ghost"
                            size="icon-xs"
                            onClick={() => handleDeleteWorkspacePreset(preset.id)}
                            aria-label="Удалить workspace preset"
                          >
                            <Trash2 size={12} />
                          </Button>
                        </div>
                      </div>
                    </div>
                  ))
                )}
              </div>

              <Card className="overflow-hidden border border-[#d9dde7] bg-white py-0 shadow-none">
                <CardContent className="space-y-3 px-5 py-4">
                  <div className="flex items-center justify-between">
                    <span className="text-[11px] font-medium uppercase tracking-[0.16em] text-[#4b5563]">
                      {editingWorkspaceId ? "Редактировать preset" : "Новый preset"}
                    </span>
                    {editingWorkspaceId ? (
                      <button
                        type="button"
                        onClick={resetWorkspaceForm}
                        className="cursor-pointer rounded-md p-1 text-muted-foreground hover:text-foreground"
                        aria-label="Сбросить workspace preset"
                      >
                        <X size={14} />
                      </button>
                    ) : null}
                  </div>
                  <div>
                    <label className="mb-1 block text-[11px] text-muted-foreground">Название</label>
                    <input
                      value={workspaceName}
                      onChange={(e) => setWorkspaceName(e.target.value)}
                      placeholder="Trading repo + logs"
                      className={INPUT_CLASS}
                    />
                  </div>
                  <div>
                    <label className="mb-1 block text-[11px] text-muted-foreground">Описание</label>
                    <input
                      value={workspaceDescription}
                      onChange={(e) => setWorkspaceDescription(e.target.value)}
                      placeholder="Репозиторий и данные для pattern mining"
                      className={INPUT_CLASS}
                    />
                  </div>
                  <div>
                    <label className="mb-1 block text-[11px] text-muted-foreground">Пути (по одному на строку)</label>
                    <textarea
                      value={workspacePathsDraft}
                      onChange={(e) => setWorkspacePathsDraft(e.target.value)}
                      placeholder={"/Users/example/project\n/Users/example/logs"}
                      rows={5}
                      className={`${INPUT_CLASS} min-h-28 resize-y leading-relaxed`}
                    />
                  </div>
                  <Button
                    type="button"
                    size="sm"
                    className="w-full rounded-[10px] bg-black text-xs text-white hover:bg-black/90"
                    onClick={handleAddWorkspacePreset}
                    disabled={!workspaceName.trim() || !workspacePathsDraft.trim()}
                  >
                    <Plus size={12} className="mr-1.5" /> {editingWorkspaceId ? "Обновить preset" : "Сохранить preset"}
                  </Button>
                </CardContent>
              </Card>
            </div>
          </section>

          {/* Section 2: Prompt templates */}
          <section className="rounded-[24px] border border-[#e6e8ee] bg-white p-6">
            <div className="flex items-center gap-2 mb-4">
              <BookOpen size={16} className="text-muted-foreground" />
              <h3 className="text-sm font-medium">Шаблоны промптов</h3>
              {templateKeys.length > 0 && (
                <Badge variant="outline" className="text-[10px] px-1.5 py-0 font-normal">
                  {templateKeys.length}
                </Badge>
              )}
            </div>

            {templateKeys.length === 0 ? (
              <div className="flex flex-col items-center justify-center py-12 text-muted-foreground">
                <BookOpen className="h-8 w-8 mb-3 opacity-30" />
                <p className="text-sm">Шаблоны не загружены</p>
                <p className="text-xs text-muted-foreground/50 mt-1">
                  Шаблоны появятся когда бэкенд будет доступен
                </p>
              </div>
            ) : (
              <div className="space-y-2">
                {templateKeys.map((key) => {
                  const tmpl = templates[key];
                  return (
                    <div
                      key={key}
                      className="rounded-xl border border-border p-3 space-y-1.5"
                    >
                      <div className="flex items-center gap-2">
                        <span className="text-sm font-medium">{tmpl.name ?? key}</span>
                        <Badge variant="outline" className="text-[10px] px-1.5 py-0 font-normal font-mono">
                          {key}
                        </Badge>
                      </div>
                      {tmpl.description && (
                        <p className="text-xs text-muted-foreground">{tmpl.description}</p>
                      )}
                      {tmpl.prompt && (
                        <pre className="text-[11px] text-muted-foreground/70 font-mono bg-[#fafbfc] border border-[#e6e8ee] rounded-md p-2 max-h-24 overflow-y-auto whitespace-pre-wrap">
                          {tmpl.prompt.length > 300
                            ? `${tmpl.prompt.slice(0, 300)}...`
                            : tmpl.prompt}
                        </pre>
                      )}
                    </div>
                  );
                })}
              </div>
            )}
          </section>

          {/* Section 3: Backend API status (existing) */}
          <section>
            <div className="rounded-[20px] border border-[#e6e8ee] p-5">
              <div className="flex items-center justify-between mb-3">
                <h3 className="text-sm font-medium">Бэкенд API</h3>
                <Badge
                  variant="outline"
                  className="text-[10px] px-1.5 py-0 font-normal border-green-500/30 text-green-600"
                >
                  Подключён
                </Badge>
              </div>
              <div className="flex items-center gap-2 text-xs text-muted-foreground font-mono">
                <div className="h-1.5 w-1.5 rounded-full bg-green-500" />
                http://localhost:8800
              </div>
            </div>

            <div className="mt-2 rounded-[20px] border border-[#e6e8ee] p-5">
              <h3 className="text-sm font-medium mb-3">О приложении</h3>
              <div className="space-y-2 text-xs text-muted-foreground">
                <div className="flex justify-between">
                  <span>Версия</span>
                  <span className="font-mono">0.1.0</span>
                </div>
                <div className="flex justify-between">
                  <span>Фронтенд</span>
                  <span className="font-mono">Next.js 16 + shadcn/ui</span>
                </div>
                <div className="flex justify-between">
                  <span>Оркестратор</span>
                  <span className="font-mono">LangGraph + FastAPI</span>
                </div>
              </div>
            </div>
          </section>
        </div>
      </div>
    </div>
  );
}
