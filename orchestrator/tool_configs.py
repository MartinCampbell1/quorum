"""Tool configuration store — manages user-configured tools with their credentials."""

import json
import threading
from pathlib import Path
from typing import Optional

from pydantic import BaseModel, Field


class ToolConfig(BaseModel):
    """A user-configured tool instance."""
    id: str                    # unique slug, e.g. "brave-search", "prod-neo4j"
    name: str                  # display name, e.g. "Brave Search", "Production Graph"
    tool_type: str             # "brave_search", "perplexity", "neo4j", "ssh", "http_api", "shell"
    icon: str = ""             # emoji or icon key
    config: dict = Field(default_factory=dict)
    enabled: bool = True       # can be disabled without deleting
    validation_status: str = "unknown"
    last_validation_result: dict = Field(default_factory=dict)


LEGACY_TOOL_ID_ALIASES = {
    "code-exec": "code_exec",
    "shell": "shell_exec",
}


TOOL_TYPE_PROVIDER_ALLOWLIST: dict[str, set[str]] = {
    "code_exec": {"claude", "codex"},
    "shell": {"claude", "codex"},
    "brave_search": {"claude", "gemini", "codex"},
    "perplexity": {"claude", "gemini", "codex"},
    "http_api": {"claude", "gemini", "codex"},
    "custom_api": {"claude", "gemini", "codex"},
    "ssh": {"claude", "gemini", "codex"},
    "neo4j": {"claude", "gemini", "codex"},
    "mcp_server": {"claude", "gemini", "codex"},
}


def normalize_tool_id(tool_id: str) -> str:
    """Normalize legacy UI aliases to canonical runtime ids."""
    return LEGACY_TOOL_ID_ALIASES.get(tool_id, tool_id)


def supported_providers_for_tool_type(tool_type: str) -> set[str]:
    """Return providers that can execute a configured tool type today."""
    return TOOL_TYPE_PROVIDER_ALLOWLIST.get(tool_type, {"claude"})


def mcp_server_transport(config: dict) -> str:
    """Return normalized MCP transport from a configured tool payload."""
    return str(config.get("transport", "stdio") or "stdio").strip().lower()


def mcp_server_http_headers(config: dict) -> Optional[dict[str, str]]:
    """Parse MCP HTTP headers JSON into a string mapping. Returns None on invalid JSON."""
    raw_headers = config.get("headers", "")
    if isinstance(raw_headers, dict):
        parsed = raw_headers
    else:
        rendered = str(raw_headers or "").strip()
        if not rendered:
            return {}
        try:
            parsed = json.loads(rendered)
        except json.JSONDecodeError:
            return None
    if not isinstance(parsed, dict):
        return None
    return {str(key): str(value) for key, value in parsed.items()}


def codex_native_http_mcp_bearer_token(config: dict) -> Optional[str]:
    """Return a bearer token when Codex can natively attach it to an HTTP MCP server."""
    if mcp_server_transport(config) != "http":
        return None
    headers = mcp_server_http_headers(config)
    if headers is None:
        return None
    normalized = {str(key).strip().lower(): str(value).strip() for key, value in headers.items() if str(key).strip()}
    if not normalized:
        return None
    if set(normalized) != {"authorization"}:
        return None
    auth_header = normalized["authorization"]
    if not auth_header.lower().startswith("bearer "):
        return None
    token = auth_header[7:].strip()
    return token or None


def codex_supports_native_mcp_server(config: dict) -> bool:
    """Codex supports stdio MCP natively and HTTP MCP when no extra headers are needed or only a bearer token is required."""
    transport = mcp_server_transport(config)
    if transport == "stdio":
        return True
    if transport != "http":
        return False
    headers = mcp_server_http_headers(config)
    if headers is None:
        return False
    return not headers or codex_native_http_mcp_bearer_token(config) is not None


# Tool type definitions — what fields each type needs
TOOL_TYPES = {
    "brave_search": {
        "name": "Brave Search",
        "category": "search",
        "icon": "🔍",
        "fields": [
            {"name": "api_key", "label": "API Key", "type": "password", "required": True, "placeholder": "BSA-..."},
        ],
        "mcp_server": "search-server",
        "mcp_tool": "web_search",
    },
    "perplexity": {
        "name": "Perplexity AI",
        "category": "search",
        "icon": "🧠",
        "fields": [
            {"name": "api_key", "label": "API Key", "type": "password", "required": True, "placeholder": "pplx-..."},
        ],
        "mcp_server": "search-server",
        "mcp_tool": "perplexity_search",
    },
    "neo4j": {
        "name": "Neo4j Graph",
        "category": "database",
        "icon": "📊",
        "fields": [
            {"name": "bolt_url", "label": "Bolt URL", "type": "text", "required": True, "placeholder": "bolt://localhost:7687"},
            {"name": "user", "label": "Пользователь", "type": "text", "required": True, "placeholder": "neo4j"},
            {"name": "password", "label": "Пароль", "type": "password", "required": True, "placeholder": ""},
            {"name": "database", "label": "База данных", "type": "text", "required": False, "placeholder": "neo4j"},
        ],
        "mcp_server": "configured-tools",
        "mcp_tool": "neo4j_query",
    },
    "ssh": {
        "name": "SSH Server",
        "category": "infrastructure",
        "icon": "🖥",
        "fields": [
            {"name": "host", "label": "Хост", "type": "text", "required": True, "placeholder": "10.0.0.5"},
            {"name": "port", "label": "Порт", "type": "text", "required": False, "placeholder": "22"},
            {"name": "user", "label": "Пользователь", "type": "text", "required": True, "placeholder": "admin"},
            {"name": "auth_type", "label": "Авторизация", "type": "select", "required": True, "options": ["key", "password"], "placeholder": ""},
            {"name": "password", "label": "Путь к ключу / пароль", "type": "password", "required": False, "placeholder": ""},
        ],
        "mcp_server": "configured-tools",
        "mcp_tool": "ssh_exec",
    },
    "http_api": {
        "name": "HTTP API",
        "category": "integration",
        "icon": "🔗",
        "fields": [
            {"name": "base_url", "label": "Base URL", "type": "text", "required": True, "placeholder": "https://api.example.com"},
            {"name": "auth_header", "label": "Authorization header", "type": "password", "required": False, "placeholder": "Bearer ..."},
            {"name": "method", "label": "Метод", "type": "select", "required": False, "options": ["GET", "POST", "PUT", "DELETE"], "placeholder": ""},
        ],
        "mcp_server": "configured-tools",
        "mcp_tool": "http_api_request",
    },
    "code_exec": {
        "name": "Python",
        "category": "execution",
        "icon": "🐍",
        "fields": [],
        "mcp_server": "exec-server",
        "mcp_tool": "code_exec",
    },
    "shell": {
        "name": "Shell",
        "category": "execution",
        "icon": "⚡",
        "fields": [],
        "mcp_server": "exec-server",
        "mcp_tool": "shell_exec",
    },
    # --- Custom / extensible types ---
    "custom_api": {
        "name": "Custom API",
        "category": "custom",
        "icon": "🔧",
        "fields": [
            {"name": "base_url", "label": "Base URL", "type": "text", "required": True, "placeholder": "https://api.example.com/v1"},
            {"name": "method", "label": "HTTP метод", "type": "select", "required": False, "options": ["GET", "POST", "PUT", "DELETE"], "placeholder": ""},
            {"name": "auth_header", "label": "Authorization", "type": "password", "required": False, "placeholder": "Bearer sk-..."},
            {"name": "content_type", "label": "Content-Type", "type": "text", "required": False, "placeholder": "application/json"},
            {"name": "body_template", "label": "Шаблон тела запроса", "type": "textarea", "required": False, "placeholder": "{\"query\": \"{input}\"}"},
            {"name": "description", "label": "Описание для агента", "type": "textarea", "required": False, "placeholder": "Что этот API делает, как его использовать..."},
        ],
        "mcp_server": "configured-tools",
        "mcp_tool": "custom_api_request",
    },
    "mcp_server": {
        "name": "MCP Server",
        "category": "mcp",
        "icon": "🔌",
        "fields": [
            {"name": "transport", "label": "Transport", "type": "select", "required": True, "options": ["stdio", "http"], "placeholder": ""},
            {"name": "command", "label": "Команда запуска", "type": "text", "required": False, "placeholder": "npx -y @modelcontextprotocol/server-github"},
            {"name": "args", "label": "Аргументы (через пробел)", "type": "text", "required": False, "placeholder": ""},
            {"name": "env", "label": "Переменные окружения (JSON)", "type": "textarea", "required": False, "placeholder": "{\"GITHUB_TOKEN\": \"ghp_...\"}"},
            {"name": "url", "label": "HTTP URL", "type": "text", "required": False, "placeholder": "https://stitch.googleapis.com/mcp"},
            {"name": "headers", "label": "HTTP headers (JSON)", "type": "textarea", "required": False, "placeholder": "{\"X-Goog-Api-Key\": \"...\"}"},
        ],
        "mcp_server": "__custom_mcp__",
        "mcp_tool": "__all__",
    },
}


# Prompt templates
PROMPT_TEMPLATES = {
    "analyst": {
        "name": "Аналитик",
        "description": "Анализ данных, паттернов, трендов",
        "prompt": "Ты аналитик данных. Анализируй информацию системно, ищи паттерны и аномалии. Представляй выводы структурированно с цифрами и фактами. Если есть доступ к графу или базе данных — используй их для проверки гипотез.",
    },
    "researcher": {
        "name": "Исследователь",
        "description": "Глубокий поиск и синтез информации",
        "prompt": "Ты исследователь. Проводи глубокий поиск по теме, используя доступные инструменты поиска. Проверяй факты из нескольких источников. Собирай и синтезируй информацию в структурированный отчёт с источниками.",
    },
    "developer": {
        "name": "Разработчик",
        "description": "Написание и анализ кода",
        "prompt": "Ты опытный разработчик. Пиши чистый, эффективный код. Используй инструменты выполнения кода для тестирования решений. Если есть доступ к серверу — проверяй состояние систем через shell.",
    },
    "critic": {
        "name": "Критик",
        "description": "Критический анализ и ревью",
        "prompt": "Ты критик и рецензент. Анализируй работу критически, ищи слабые места, логические ошибки, пропуски. Давай конструктивную обратную связь с конкретными предложениями по улучшению.",
    },
    "strategist": {
        "name": "Стратег",
        "description": "Планирование и принятие решений",
        "prompt": "Ты стратег. Оценивай ситуацию комплексно, рассматривай альтернативы, взвешивай риски. Формулируй чёткие планы действий с приоритетами и сроками.",
    },
}


class ToolConfigStore:
    """Thread-safe in-memory store for tool configurations."""

    def __init__(self):
        self._tools: dict[str, ToolConfig] = {}
        self._lock = threading.Lock()
        self._store_path = Path.home() / ".multi-agent" / "tool_configs.json"
        self._init_defaults()
        self._load_from_disk()

    def _init_defaults(self):
        """Register built-in tools that need no configuration."""
        defaults = [
            ToolConfig(id="code_exec", name="Python", tool_type="code_exec", icon="🐍"),
            ToolConfig(id="shell_exec", name="Shell", tool_type="shell", icon="⚡"),
        ]
        for t in defaults:
            self._tools[t.id] = t

    def _load_from_disk(self) -> None:
        """Load user-configured tools from disk, if present."""
        if not self._store_path.exists():
            return
        try:
            payload = self._store_path.read_text()
            data = json.loads(payload)
        except Exception:
            return

        for raw_tool in data.get("tools", []):
            try:
                tool = ToolConfig.model_validate(raw_tool)
            except Exception:
                continue
            tool = tool.model_copy(update={"id": normalize_tool_id(tool.id)})
            self._tools[tool.id] = tool

    def _save_to_disk(self) -> None:
        """Persist non-default tools outside the repository."""
        self._store_path.parent.mkdir(parents=True, exist_ok=True)
        tools = []
        for tool in self._tools.values():
            if tool.id in {"code_exec", "shell_exec"}:
                continue
            tools.append(tool.model_dump())
        payload = {"tools": tools}
        self._store_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2))

    def list_all(self) -> list[ToolConfig]:
        with self._lock:
            return list(self._tools.values())

    def list_enabled(self) -> list[ToolConfig]:
        with self._lock:
            return [t for t in self._tools.values() if t.enabled]

    def get(self, tool_id: str) -> ToolConfig | None:
        with self._lock:
            normalized_id = normalize_tool_id(tool_id)
            return self._tools.get(normalized_id)

    def add(self, tool: ToolConfig) -> ToolConfig:
        with self._lock:
            normalized = tool.model_copy(update={"id": normalize_tool_id(tool.id)})
            self._tools[normalized.id] = normalized
            self._save_to_disk()
            return normalized

    def update(self, tool_id: str, updates: dict) -> ToolConfig | None:
        with self._lock:
            normalized_id = normalize_tool_id(tool_id)
            if normalized_id not in self._tools:
                return None
            tool = self._tools[normalized_id]
            updated = tool.model_copy(update=updates)
            self._tools[normalized_id] = updated
            self._save_to_disk()
            return updated

    def delete(self, tool_id: str) -> bool:
        with self._lock:
            normalized_id = normalize_tool_id(tool_id)
            if normalized_id in self._tools:
                if normalized_id in {"code_exec", "shell_exec"}:
                    return False
                del self._tools[normalized_id]
                self._save_to_disk()
                return True
            return False


# Global instance
tool_config_store = ToolConfigStore()
