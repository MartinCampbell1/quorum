"""Tool configuration store — manages user-configured tools with their credentials."""

import threading
from typing import Optional
from pydantic import BaseModel


class ToolConfig(BaseModel):
    """A user-configured tool instance."""
    id: str                    # unique slug, e.g. "brave-search", "prod-neo4j"
    name: str                  # display name, e.g. "Brave Search", "Production Graph"
    tool_type: str             # "brave_search", "perplexity", "neo4j", "ssh", "http_api", "shell"
    icon: str = ""             # emoji or icon key
    config: dict = {}          # type-specific: {"api_key": "..."} or {"bolt_url": "...", "user": "...", "password": "..."}
    enabled: bool = True       # can be disabled without deleting


# Tool type definitions — what fields each type needs
TOOL_TYPES = {
    "brave_search": {
        "name": "Brave Search",
        "category": "search",
        "icon": "🔍",
        "fields": [
            {"key": "api_key", "label": "API Key", "type": "password", "required": True, "placeholder": "BSA-..."},
        ],
        "mcp_server": "search-server",
        "mcp_tool": "web_search",
    },
    "perplexity": {
        "name": "Perplexity AI",
        "category": "search",
        "icon": "🧠",
        "fields": [
            {"key": "api_key", "label": "API Key", "type": "password", "required": True, "placeholder": "pplx-..."},
        ],
        "mcp_server": "search-server",
        "mcp_tool": "perplexity_search",
    },
    "neo4j": {
        "name": "Neo4j Graph",
        "category": "database",
        "icon": "📊",
        "fields": [
            {"key": "bolt_url", "label": "Bolt URL", "type": "text", "required": True, "placeholder": "bolt://localhost:7687"},
            {"key": "user", "label": "Пользователь", "type": "text", "required": True, "placeholder": "neo4j"},
            {"key": "password", "label": "Пароль", "type": "password", "required": True, "placeholder": ""},
            {"key": "database", "label": "База данных", "type": "text", "required": False, "placeholder": "neo4j"},
        ],
        "mcp_server": "db-server",
        "mcp_tool": "neo4j_query",
    },
    "ssh": {
        "name": "SSH Server",
        "category": "infrastructure",
        "icon": "🖥",
        "fields": [
            {"key": "host", "label": "Хост", "type": "text", "required": True, "placeholder": "10.0.0.5"},
            {"key": "port", "label": "Порт", "type": "text", "required": False, "placeholder": "22"},
            {"key": "user", "label": "Пользователь", "type": "text", "required": True, "placeholder": "admin"},
            {"key": "auth_type", "label": "Авторизация", "type": "select", "required": True, "options": ["password", "key"], "placeholder": ""},
            {"key": "password", "label": "Пароль / Путь к ключу", "type": "password", "required": False, "placeholder": ""},
        ],
        "mcp_server": "exec-server",
        "mcp_tool": "shell_exec",
    },
    "http_api": {
        "name": "HTTP API",
        "category": "integration",
        "icon": "🔗",
        "fields": [
            {"key": "base_url", "label": "Base URL", "type": "text", "required": True, "placeholder": "https://api.example.com"},
            {"key": "auth_header", "label": "Authorization header", "type": "password", "required": False, "placeholder": "Bearer ..."},
            {"key": "method", "label": "Метод", "type": "select", "required": False, "options": ["GET", "POST", "PUT", "DELETE"], "placeholder": ""},
        ],
        "mcp_server": "exec-server",
        "mcp_tool": "http_request",
    },
    "code_exec": {
        "name": "Python",
        "category": "execution",
        "icon": "🐍",
        "fields": [],  # No config needed — built-in
        "mcp_server": "exec-server",
        "mcp_tool": "code_exec",
    },
    "shell": {
        "name": "Shell",
        "category": "execution",
        "icon": "⚡",
        "fields": [],  # No config needed — built-in
        "mcp_server": "exec-server",
        "mcp_tool": "shell_exec",
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
        self._init_defaults()

    def _init_defaults(self):
        """Register built-in tools that need no configuration."""
        defaults = [
            ToolConfig(id="code-exec", name="Python", tool_type="code_exec", icon="🐍"),
            ToolConfig(id="shell", name="Shell", tool_type="shell", icon="⚡"),
        ]
        for t in defaults:
            self._tools[t.id] = t

    def list_all(self) -> list[ToolConfig]:
        with self._lock:
            return list(self._tools.values())

    def list_enabled(self) -> list[ToolConfig]:
        with self._lock:
            return [t for t in self._tools.values() if t.enabled]

    def get(self, tool_id: str) -> ToolConfig | None:
        with self._lock:
            return self._tools.get(tool_id)

    def add(self, tool: ToolConfig) -> ToolConfig:
        with self._lock:
            self._tools[tool.id] = tool
            return tool

    def update(self, tool_id: str, updates: dict) -> ToolConfig | None:
        with self._lock:
            if tool_id not in self._tools:
                return None
            tool = self._tools[tool_id]
            updated = tool.model_copy(update=updates)
            self._tools[tool_id] = updated
            return updated

    def delete(self, tool_id: str) -> bool:
        with self._lock:
            if tool_id in self._tools:
                del self._tools[tool_id]
                return True
            return False


# Global instance
tool_config_store = ToolConfigStore()
