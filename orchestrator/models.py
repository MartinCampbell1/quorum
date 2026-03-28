"""Data models, runtime capabilities, and persistent session storage."""

from __future__ import annotations

import copy
import json
import operator
import os
import sqlite3
import threading
import time
import uuid
from pathlib import Path
from typing import Annotated, Literal, Optional

from pydantic import BaseModel, Field
from typing_extensions import TypedDict

from orchestrator.tool_configs import (
    TOOL_TYPES,
    codex_supports_native_mcp_server,
    is_builtin_tool_instance,
    mcp_server_transport,
    normalize_tool_id,
    supported_providers_for_tool_type,
    tool_config_store,
)


CapabilityLevel = Literal["native", "bridged", "unavailable"]
ProviderName = Literal["claude", "gemini", "codex", "minimax"]


# ---- API Request/Response models (Pydantic) ----

class ToolDefinition(BaseModel):
    """Tool available for agents."""

    key: str
    name: str
    description: str
    category: str
    tool_type: str


AVAILABLE_TOOLS: list[ToolDefinition] = [
    ToolDefinition(
        key="web_search",
        name="Веб-поиск",
        description="Поиск в интернете через MCP search-server",
        category="search",
        tool_type="web_search",
    ),
    ToolDefinition(
        key="perplexity",
        name="Perplexity AI",
        description="AI-поиск с цитатами через MCP search-server",
        category="search",
        tool_type="perplexity",
    ),
    ToolDefinition(
        key="code_exec",
        name="Python",
        description="Выполнение Python кода",
        category="exec",
        tool_type="code_exec",
    ),
    ToolDefinition(
        key="shell_exec",
        name="Shell",
        description="Выполнение shell-команд",
        category="exec",
        tool_type="shell",
    ),
    ToolDefinition(
        key="http_request",
        name="HTTP запрос",
        description="HTTP-запросы через MCP exec-server",
        category="exec",
        tool_type="http_api",
    ),
]

TOOLS_BY_KEY: dict[str, ToolDefinition] = {tool.key: tool for tool in AVAILABLE_TOOLS}
SUPPORTED_PROVIDERS: set[str] = {"claude", "gemini", "codex", "minimax"}

SESSION_CAPABILITIES = {
    "live_messages": True,
    "custom_tools": True,
    "pause_resume": True,
    "checkpoints": True,
    "workspace_presets": True,
    "branching": True,
}

MODE_AGENT_REQUIREMENTS: dict[str, dict[str, object]] = {
    "dictator": {"min": 2, "label": "1 director + at least 1 worker"},
    "board": {"min": 3, "label": "3 directors, optional extra workers"},
    "democracy": {"min": 3, "label": "at least 3 voters"},
    "debate": {"exact": 3, "label": "proponent, opponent, judge"},
    "map_reduce": {"min": 3, "label": "planner, at least 1 worker, synthesizer"},
    "creator_critic": {"exact": 2, "label": "creator and critic"},
    "tournament": {"min": 3, "label": "at least 2 contestants + judge"},
    "tournament_match": {"exact": 3, "label": "contestant A, contestant B, judge"},
}

BUILTIN_TOOL_CAPABILITIES: dict[str, dict[str, CapabilityLevel]] = {
    "web_search": {
        "claude": "native",
        "gemini": "native",
        "codex": "native",
        "minimax": "unavailable",
    },
    "perplexity": {
        "claude": "native",
        "gemini": "native",
        "codex": "bridged",
        "minimax": "unavailable",
    },
    "code_exec": {
        "claude": "native",
        "gemini": "native",
        "codex": "bridged",
        "minimax": "unavailable",
    },
    "shell_exec": {
        "claude": "native",
        "gemini": "native",
        "codex": "bridged",
        "minimax": "unavailable",
    },
    "http_request": {
        "claude": "native",
        "gemini": "native",
        "codex": "bridged",
        "minimax": "unavailable",
    },
}

CONFIGURED_TOOL_CAPABILITIES: dict[str, dict[str, CapabilityLevel]] = {
    "code_exec": {
        "claude": "native",
        "gemini": "native",
        "codex": "bridged",
        "minimax": "unavailable",
    },
    "shell": {
        "claude": "native",
        "gemini": "native",
        "codex": "bridged",
        "minimax": "unavailable",
    },
    "brave_search": {
        "claude": "native",
        "gemini": "bridged",
        "codex": "bridged",
        "minimax": "unavailable",
    },
    "perplexity": {
        "claude": "native",
        "gemini": "bridged",
        "codex": "bridged",
        "minimax": "unavailable",
    },
    "http_api": {
        "claude": "native",
        "gemini": "bridged",
        "codex": "bridged",
        "minimax": "unavailable",
    },
    "custom_api": {
        "claude": "native",
        "gemini": "bridged",
        "codex": "bridged",
        "minimax": "unavailable",
    },
    "ssh": {
        "claude": "native",
        "gemini": "bridged",
        "codex": "bridged",
        "minimax": "unavailable",
    },
    "neo4j": {
        "claude": "native",
        "gemini": "bridged",
        "codex": "bridged",
        "minimax": "unavailable",
    },
    "mcp_server": {
        "claude": "native",
        "gemini": "unavailable",
        "codex": "unavailable",
        "minimax": "unavailable",
    },
}


class AgentConfig(BaseModel):
    """Agent configuration from API request."""

    role: str
    provider: str
    system_prompt: str = ""
    tools: list[str] = Field(default_factory=list)
    workspace_paths: list[str] = Field(default_factory=list)


class RunRequest(BaseModel):
    """POST /orchestrate/run request body."""

    mode: str
    task: str
    scenario_id: Optional[str] = None
    agents: list[AgentConfig] = Field(default_factory=list)
    config: dict = Field(default_factory=dict)
    workspace_preset_ids: list[str] = Field(default_factory=list)
    workspace_paths: list[str] = Field(default_factory=list)
    attached_tool_ids: list[str] = Field(default_factory=list)


class MessageRequest(BaseModel):
    """POST /orchestrate/session/{id}/message request body."""

    content: str


class ControlRequest(BaseModel):
    """POST /orchestrate/session/{id}/control request body."""

    action: str
    content: str = ""
    checkpoint_id: str = ""


class WorkspacePreset(BaseModel):
    """Saved multi-root workspace preset."""

    id: str
    name: str
    paths: list[str] = Field(default_factory=list)
    description: Optional[str] = None
    created_at: float = Field(default_factory=time.time)


class SessionResponse(BaseModel):
    """GET /orchestrate/session/{id} response."""

    id: str
    mode: str
    task: str
    agents: list[AgentConfig]
    messages: list[dict]
    result: Optional[str] = None
    status: str
    config: dict = Field(default_factory=dict)
    active_scenario: Optional[str] = None
    forked_from: Optional[str] = None
    forked_checkpoint_id: Optional[str] = None
    parallel_parent_id: Optional[str] = None
    parallel_group_id: Optional[str] = None
    parallel_slot_key: Optional[str] = None
    parallel_stage: Optional[str] = None
    parallel_label: Optional[str] = None
    capabilities: dict = Field(default_factory=lambda: dict(SESSION_CAPABILITIES))
    created_at: float
    elapsed_sec: Optional[float] = None
    current_checkpoint_id: Optional[str] = None
    checkpoints: list[dict] = Field(default_factory=list)
    events: list[dict] = Field(default_factory=list)
    pending_instructions: int = 0
    active_node: Optional[str] = None
    workspace_preset_ids: list[str] = Field(default_factory=list)
    workspace_paths: list[str] = Field(default_factory=list)
    attached_tool_ids: list[str] = Field(default_factory=list)
    attached_tools: list[dict] = Field(default_factory=list)
    provider_capabilities_snapshot: dict = Field(default_factory=dict)
    branch_children: list[dict] = Field(default_factory=list)
    parallel_children: list[dict] = Field(default_factory=list)
    parallel_progress: dict = Field(default_factory=dict)
    runtime_state: dict = Field(default_factory=dict)


# ---- LangGraph State (TypedDict for graph nodes) ----

class OrchestratorState(TypedDict):
    """Base state shared by all orchestration modes."""

    session_id: str
    mode: str
    task: str
    agents: list[dict]
    messages: Annotated[list[dict], operator.add]
    result: str
    status: str
    config: dict
    user_messages: Annotated[list[str], operator.add]
    created_at: float
    workspace_paths: list[str]
    attached_tool_ids: list[str]


def _canonical_provider(provider: str) -> str:
    return provider.strip().lower()


def _tool_metadata(tool_id: str) -> tuple[str | None, str | None]:
    canonical = normalize_tool_id(tool_id)
    builtin = TOOLS_BY_KEY.get(canonical)
    if builtin:
        return builtin.tool_type, builtin.name
    configured = tool_config_store.get(canonical)
    if configured:
        return configured.tool_type, configured.name
    return None, None


def _tool_icon(tool_id: str) -> str:
    canonical = normalize_tool_id(tool_id)
    builtin_icons = {
        "web_search": "globe",
        "perplexity": "sparkles",
        "code_exec": "terminal",
        "shell_exec": "terminal",
        "http_request": "globe",
    }
    if canonical in builtin_icons:
        return builtin_icons[canonical]
    configured = tool_config_store.get(canonical)
    if configured and configured.icon:
        return configured.icon
    return TOOL_TYPES.get(configured.tool_type if configured else "", {}).get("icon", "folder")


def _tool_transport(tool_id: str) -> str:
    canonical = normalize_tool_id(tool_id)
    builtin_transport = {
        "web_search": "mcp",
        "perplexity": "mcp",
        "code_exec": "builtin",
        "shell_exec": "builtin",
        "http_request": "bridge",
    }
    if canonical in builtin_transport:
        return builtin_transport[canonical]
    configured = tool_config_store.get(canonical)
    if not configured:
        return "unknown"
    if configured.tool_type == "mcp_server":
        return str(configured.config.get("transport", "stdio") or "stdio").strip().lower()
    if is_builtin_tool_instance(canonical):
        return "builtin"
    return "bridge"


def _tool_subtitle(tool_id: str) -> str:
    canonical = normalize_tool_id(tool_id)
    builtin_subtitles = {
        "web_search": "Provider: Brave",
        "perplexity": "Provider: Perplexity",
        "code_exec": "Runtime: python",
        "shell_exec": "Path: local shell",
        "http_request": "Service: remote API",
    }
    if canonical in builtin_subtitles:
        return builtin_subtitles[canonical]
    configured = tool_config_store.get(canonical)
    if not configured:
        return "MCP connection"
    if configured.tool_type == "neo4j":
        database = str(configured.config.get("database", "")).strip()
        bolt_url = str(configured.config.get("bolt_url", "")).strip()
        if database:
            return f"DB: {database}"
        if bolt_url:
            return f"URL: {bolt_url}"
    if configured.tool_type == "ssh":
        host = str(configured.config.get("host", "")).strip()
        port = str(configured.config.get("port", "")).strip() or "22"
        return f"Host: {host}:{port}" if host else "Remote shell"
    if configured.tool_type in {"http_api", "custom_api"}:
        base_url = str(configured.config.get("base_url", "")).strip()
        return f"Base URL: {base_url}" if base_url else "Service: remote API"
    if configured.tool_type == "shell":
        command_template = str(configured.config.get("command_template", "")).strip()
        return f"Template: {command_template}" if command_template else "Runtime: local shell"
    if configured.tool_type == "mcp_server":
        transport = _tool_transport(canonical)
        if transport == "http":
            url = str(configured.config.get("url", "")).strip()
            return f"URL: {url}" if url else "Remote MCP"
        command = str(configured.config.get("command", "")).strip()
        return f"Command: {command}" if command else "Stdio MCP"
    if configured.tool_type == "brave_search":
        return "Provider: Brave"
    if configured.tool_type == "perplexity":
        return "Provider: Perplexity"
    return "MCP connection"


def build_attached_tool_details(
    attached_tool_ids: list[str],
    agents: list[dict] | None = None,
    provider_capabilities_snapshot: dict | None = None,
) -> list[dict]:
    details: list[dict] = []
    capability_map: dict[str, CapabilityLevel] = {}
    if agents:
        for agent in agents:
            provider = str(agent.get("provider", "")).strip().lower()
            for raw_tool_id in attached_tool_ids:
                tool_id = normalize_tool_id(raw_tool_id)
                capability = capability_for_tool(provider, tool_id)
                previous = capability_map.get(tool_id)
                if capability == "native" or previous != "native":
                    capability_map[tool_id] = capability
    for agent in (provider_capabilities_snapshot or {}).values():
        for tool_id, info in agent.get("tools", {}).items():
            capability = info.get("capability", "unavailable")
            previous = capability_map.get(tool_id)
            if capability == "native" or previous != "native":
                capability_map[tool_id] = capability

    for raw_tool_id in attached_tool_ids:
        tool_id = normalize_tool_id(raw_tool_id)
        tool_type, name = _tool_metadata(tool_id)
        details.append(
            {
                "id": tool_id,
                "name": name or tool_id,
                "tool_type": tool_type,
                "transport": _tool_transport(tool_id),
                "subtitle": _tool_subtitle(tool_id),
                "icon": _tool_icon(tool_id),
                "capability": capability_map.get(tool_id, "native"),
            }
        )
    return details


def capability_for_tool(provider: str, tool_id: str) -> CapabilityLevel:
    """Return native/bridged/unavailable for a provider-tool combination."""

    provider_key = _canonical_provider(provider)
    canonical_tool_id = normalize_tool_id(tool_id)
    builtin = BUILTIN_TOOL_CAPABILITIES.get(canonical_tool_id)
    if builtin:
        return builtin.get(provider_key, "unavailable")
    configured = tool_config_store.get(canonical_tool_id)
    if not configured or not configured.enabled:
        return "unavailable"
    if configured.tool_type == "mcp_server":
        transport = mcp_server_transport(configured.config)
        if provider_key == "claude":
            return "native"
        if provider_key == "gemini":
            return "native" if transport in {"stdio", "http", "sse"} else "unavailable"
        if provider_key == "codex":
            if codex_supports_native_mcp_server(configured.config):
                return "native"
            if transport in {"http", "sse"}:
                return "bridged"
            return "unavailable"
        return "unavailable"
    return CONFIGURED_TOOL_CAPABILITIES.get(configured.tool_type, {}).get(provider_key, "unavailable")


def build_provider_capabilities_snapshot(agents: list[AgentConfig]) -> dict:
    """Create a frozen session snapshot of provider/tool capabilities."""

    snapshot: dict[str, dict] = {}
    for agent in agents:
        snapshot[agent.role] = {
            "provider": agent.provider,
            "tools": {
                normalize_tool_id(tool): {
                    "capability": capability_for_tool(agent.provider, tool),
                    "tool_type": _tool_metadata(tool)[0],
                    "name": _tool_metadata(tool)[1] or normalize_tool_id(tool),
                }
                for tool in agent.tools
            },
        }
    return snapshot


def capability_matrix_for_enabled_tools() -> dict[str, dict[str, CapabilityLevel]]:
    """Return provider capability levels for all enabled tool ids."""

    matrix: dict[str, dict[str, CapabilityLevel]] = {}
    for builtin in AVAILABLE_TOOLS:
        matrix[builtin.key] = {
            provider: capability_for_tool(provider, builtin.key)
            for provider in sorted(SUPPORTED_PROVIDERS)
        }
    for tool in tool_config_store.list_enabled():
        matrix[tool.id] = {
            provider: capability_for_tool(provider, tool.id)
            for provider in sorted(SUPPORTED_PROVIDERS)
        }
    return matrix


def normalize_agent_configs(agents: list[AgentConfig]) -> list[AgentConfig]:
    """Normalize tool ids so the UI and runtime use the same canonical keys."""

    normalized_agents: list[AgentConfig] = []
    for agent in agents:
        normalized_workspace_paths: list[str] = []
        seen_paths: set[str] = set()
        for raw_path in agent.workspace_paths:
            if not str(raw_path).strip():
                continue
            normalized_path = str(Path(raw_path).expanduser().resolve())
            if normalized_path in seen_paths:
                continue
            seen_paths.add(normalized_path)
            normalized_workspace_paths.append(normalized_path)
        normalized_agents.append(
            agent.model_copy(
                update={
                    "tools": [normalize_tool_id(tool) for tool in agent.tools],
                    "workspace_paths": normalized_workspace_paths,
                },
            )
        )
    return normalized_agents


def collect_attached_tool_ids(
    agents: list[AgentConfig],
    requested_tool_ids: list[str] | None = None,
) -> list[str]:
    """Merge explicitly attached tool ids with agent-level tool usage."""

    attached = {normalize_tool_id(tool_id) for tool_id in requested_tool_ids or [] if str(tool_id).strip()}
    for agent in agents:
        attached.update(normalize_tool_id(tool_id) for tool_id in agent.tools)
    return sorted(attached)


def validate_agents_for_mode(mode: str, agents: list[AgentConfig]) -> list[str]:
    """Validate topology, provider, and tool compatibility before execution."""

    errors: list[str] = []
    requirement = MODE_AGENT_REQUIREMENTS.get(mode, {})
    count = len(agents)
    minimum = requirement.get("min")
    exact = requirement.get("exact")
    label = requirement.get("label", "agent requirements")

    if exact is not None and count != exact:
        errors.append(f"Mode '{mode}' requires exactly {exact} agents ({label}); got {count}.")
    elif minimum is not None and count < minimum:
        errors.append(f"Mode '{mode}' requires at least {minimum} agents ({label}); got {count}.")

    roles = [agent.role.strip() for agent in agents if agent.role.strip()]
    duplicate_roles = sorted({role for role in roles if roles.count(role) > 1})
    if duplicate_roles:
        errors.append(f"Agent roles must be unique; duplicate roles: {', '.join(duplicate_roles)}.")

    if mode in {"tournament", "tournament_match"} and agents:
        judge_positions = [index for index, agent in enumerate(agents) if agent.role.strip() == "judge"]
        if judge_positions != [len(agents) - 1]:
            errors.append(f"Mode '{mode}' requires exactly one judge and it must be the last agent in the list.")

    for index, agent in enumerate(agents):
        provider = _canonical_provider(agent.provider)
        if provider not in SUPPORTED_PROVIDERS:
            errors.append(
                f"Agent {index + 1} ('{agent.role}') uses unsupported provider '{agent.provider}'."
            )
            continue

        invalid_tools: list[str] = []
        unavailable_tools: list[str] = []
        bridged_tools: list[str] = []
        for raw_tool in agent.tools:
            tool_id = normalize_tool_id(raw_tool)
            tool_type, _ = _tool_metadata(tool_id)
            if tool_id not in TOOLS_BY_KEY:
                configured_tool = tool_config_store.get(tool_id)
                if not configured_tool or not configured_tool.enabled:
                    invalid_tools.append(tool_id)
                    continue
                allowed_providers = supported_providers_for_tool_type(configured_tool.tool_type)
                if provider not in allowed_providers and capability_for_tool(provider, tool_id) == "unavailable":
                    unavailable_tools.append(tool_id)
                    continue
            capability = capability_for_tool(provider, tool_id)
            if capability == "unavailable":
                unavailable_tools.append(tool_id)
            elif capability == "bridged":
                bridged_tools.append(tool_id)

            if tool_type is None:
                invalid_tools.append(tool_id)

        if invalid_tools:
            errors.append(
                f"Agent {index + 1} ('{agent.role}') uses unknown tools: {', '.join(sorted(set(invalid_tools)))}."
            )
            continue

        if unavailable_tools:
            errors.append(
                f"Agent {index + 1} ('{agent.role}') cannot use {provider} with tools: "
                f"{', '.join(sorted(set(unavailable_tools)))}."
            )

        if provider == "minimax" and bridged_tools:
            errors.append(
                f"Agent {index + 1} ('{agent.role}') cannot bridge tools through minimax: "
                f"{', '.join(sorted(set(bridged_tools)))}."
            )

    return errors


def resolve_workspace_paths(
    preset_ids: list[str] | None = None,
    extra_paths: list[str] | None = None,
) -> tuple[list[str], list[str]]:
    """Expand saved preset ids plus one-off paths into a deduplicated path list."""

    resolved_preset_ids: list[str] = []
    paths: list[str] = []
    seen: set[str] = set()

    for preset_id in preset_ids or []:
        preset = store.get_workspace(preset_id)
        if not preset:
            continue
        resolved_preset_ids.append(preset.id)
        for raw_path in preset.paths:
            normalized = str(Path(raw_path).expanduser().resolve())
            if normalized not in seen:
                seen.add(normalized)
                paths.append(normalized)

    for raw_path in extra_paths or []:
        if not str(raw_path).strip():
            continue
        normalized = str(Path(raw_path).expanduser().resolve())
        if normalized not in seen:
            seen.add(normalized)
            paths.append(normalized)

    return resolved_preset_ids, paths


_RUN_JSON_COLUMNS = {
    "agents",
    "messages",
    "config",
    "capabilities",
    "pending_instruction_queue",
    "workspace_preset_ids",
    "workspace_paths",
    "attached_tool_ids",
    "provider_capabilities_snapshot",
    "parallel_progress",
}


class SessionStore:
    """SQLite-backed session and workspace storage."""

    def __init__(self, max_sessions: int = 100, db_path: str | None = None):
        self._max = max_sessions
        self._lock = threading.RLock()
        raw_db_path = db_path or os.getenv("MULTI_AGENT_STATE_DB")
        self._db_path = Path(raw_db_path) if raw_db_path else Path.home() / ".multi-agent" / "state.db"
        self._runtime_events_dir = self._db_path.parent / "runtime_events"
        self._checkpoint_runtimes_dir = self._db_path.parent / "checkpoint_runtimes"
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._runtime_events_dir.mkdir(parents=True, exist_ok=True)
        self._checkpoint_runtimes_dir.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._db_path, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS runs (
                    id TEXT PRIMARY KEY,
                    mode TEXT NOT NULL,
                    task TEXT NOT NULL,
                    agents_json TEXT NOT NULL,
                    messages_json TEXT NOT NULL,
                    result TEXT,
                    status TEXT NOT NULL,
                    config_json TEXT NOT NULL,
                    active_scenario TEXT,
                    forked_from TEXT,
                    forked_checkpoint_id TEXT,
                    parallel_parent_id TEXT,
                    parallel_group_id TEXT,
                    parallel_slot_key TEXT,
                    parallel_stage TEXT,
                    parallel_label TEXT,
                    capabilities_json TEXT NOT NULL,
                    created_at REAL NOT NULL,
                    elapsed_sec REAL,
                    current_checkpoint_id TEXT,
                    next_event_seq INTEGER NOT NULL DEFAULT 1,
                    pending_instruction_queue_json TEXT NOT NULL,
                    pending_instructions INTEGER NOT NULL DEFAULT 0,
                    active_node TEXT,
                    workspace_preset_ids_json TEXT NOT NULL,
                    workspace_paths_json TEXT NOT NULL,
                    attached_tool_ids_json TEXT NOT NULL,
                    provider_capabilities_snapshot_json TEXT NOT NULL,
                    parallel_progress_json TEXT NOT NULL DEFAULT '{}'
                )
                """
            )
            self._ensure_run_columns(
                conn,
                {
                    "parallel_parent_id": "TEXT",
                    "parallel_group_id": "TEXT",
                    "parallel_slot_key": "TEXT",
                    "parallel_stage": "TEXT",
                    "parallel_label": "TEXT",
                    "parallel_progress_json": "TEXT NOT NULL DEFAULT '{}'",
                },
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS events (
                    session_id TEXT NOT NULL,
                    event_id INTEGER NOT NULL,
                    timestamp REAL NOT NULL,
                    payload_json TEXT NOT NULL,
                    PRIMARY KEY (session_id, event_id)
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS checkpoints (
                    session_id TEXT NOT NULL,
                    checkpoint_id TEXT NOT NULL,
                    ordinal INTEGER NOT NULL,
                    timestamp REAL NOT NULL,
                    next_node TEXT,
                    status TEXT NOT NULL,
                    result_preview TEXT,
                    graph_checkpoint_id TEXT,
                    payload_json TEXT NOT NULL,
                    PRIMARY KEY (session_id, checkpoint_id)
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS workspace_presets (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    description TEXT,
                    paths_json TEXT NOT NULL,
                    created_at REAL NOT NULL
                )
                """
            )
            conn.execute("CREATE INDEX IF NOT EXISTS idx_runs_created_at ON runs(created_at DESC)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_events_session_seq ON events(session_id, event_id)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_checkpoints_session_ord ON checkpoints(session_id, ordinal)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_runs_forked_from ON runs(forked_from)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_runs_parallel_parent_id ON runs(parallel_parent_id)")

    def _ensure_run_columns(self, conn: sqlite3.Connection, required: dict[str, str]) -> None:
        existing = {row["name"] for row in conn.execute("PRAGMA table_info(runs)").fetchall()}
        for column, definition in required.items():
            if column in existing:
                continue
            conn.execute(f"ALTER TABLE runs ADD COLUMN {column} {definition}")

    @staticmethod
    def _encode(value: object) -> str:
        return json.dumps(value, ensure_ascii=False)

    @staticmethod
    def _decode(value: str | None, default: object) -> object:
        if value is None:
            return copy.deepcopy(default)
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            return copy.deepcopy(default)

    def _trim_sessions(self, conn: sqlite3.Connection) -> None:
        rows = conn.execute(
            "SELECT id FROM runs ORDER BY created_at DESC LIMIT -1 OFFSET ?",
            (self._max,),
        ).fetchall()
        stale_ids = [row["id"] for row in rows]
        if not stale_ids:
            return
        conn.executemany("DELETE FROM events WHERE session_id = ?", [(sid,) for sid in stale_ids])
        conn.executemany("DELETE FROM checkpoints WHERE session_id = ?", [(sid,) for sid in stale_ids])
        conn.executemany("DELETE FROM runs WHERE id = ?", [(sid,) for sid in stale_ids])
        for sid in stale_ids:
            for candidate in self._runtime_events_dir.glob(f"{sid}*.jsonl"):
                candidate.unlink(missing_ok=True)
            self.checkpoint_runtime_path(sid).unlink(missing_ok=True)

    def _runtime_event_path(self, sid: str) -> Path:
        return self._runtime_events_dir / f"{sid}.jsonl"

    def checkpoint_runtime_path(self, sid: str) -> Path:
        return self._checkpoint_runtimes_dir / f"{sid}.pkl"

    def _append_event_conn(
        self,
        conn: sqlite3.Connection,
        sid: str,
        event_type: str,
        title: str,
        detail: str = "",
        **extra: object,
    ) -> Optional[dict]:
        row = conn.execute(
            "SELECT next_event_seq FROM runs WHERE id = ?",
            (sid,),
        ).fetchone()
        if not row:
            return None
        event_id = int(row["next_event_seq"])
        event = {
            "id": event_id,
            "timestamp": time.time(),
            "type": event_type,
            "title": title,
            "detail": detail,
            **extra,
        }
        conn.execute(
            "INSERT INTO events (session_id, event_id, timestamp, payload_json) VALUES (?, ?, ?, ?)",
            (sid, event_id, event["timestamp"], self._encode(event)),
        )
        conn.execute(
            "UPDATE runs SET next_event_seq = ? WHERE id = ?",
            (event_id + 1, sid),
        )
        return copy.deepcopy(event)

    def _ingest_runtime_events(self, conn: sqlite3.Connection, sid: str) -> None:
        path = self._runtime_event_path(sid)
        if not path.exists():
            return

        draining_path = path.with_name(f"{path.stem}.{uuid.uuid4().hex}.drain.jsonl")
        try:
            path.rename(draining_path)
        except FileNotFoundError:
            return

        try:
            with draining_path.open() as handle:
                lines = [line.strip() for line in handle if line.strip()]
        finally:
            draining_path.unlink(missing_ok=True)

        for line in lines:
            try:
                payload = json.loads(line)
            except json.JSONDecodeError:
                continue
            event_type = str(payload.pop("type", "")).strip()
            title = str(payload.pop("title", "")).strip()
            detail = str(payload.pop("detail", "")).strip()
            if not event_type or not title:
                continue
            self._append_event_conn(conn, sid, event_type, title, detail, **payload)

    def create(
        self,
        mode: str,
        task: str,
        agents: list[AgentConfig],
        config: dict,
        scenario_id: Optional[str] = None,
        forked_from: Optional[str] = None,
        forked_checkpoint_id: Optional[str] = None,
        workspace_preset_ids: list[str] | None = None,
        workspace_paths: list[str] | None = None,
        attached_tool_ids: list[str] | None = None,
        provider_capabilities_snapshot: dict | None = None,
        parallel_parent_id: Optional[str] = None,
        parallel_group_id: Optional[str] = None,
        parallel_slot_key: Optional[str] = None,
        parallel_stage: Optional[str] = None,
        parallel_label: Optional[str] = None,
        parallel_progress: dict | None = None,
    ) -> str:
        sid = f"sess_{uuid.uuid4().hex[:12]}"
        payload = {
            "id": sid,
            "mode": mode,
            "task": task,
            "agents": [agent.model_dump() for agent in agents],
            "messages": [],
            "result": None,
            "status": "running",
            "config": copy.deepcopy(config),
            "active_scenario": scenario_id,
            "forked_from": forked_from,
            "forked_checkpoint_id": forked_checkpoint_id,
            "parallel_parent_id": parallel_parent_id,
            "parallel_group_id": parallel_group_id,
            "parallel_slot_key": parallel_slot_key,
            "parallel_stage": parallel_stage,
            "parallel_label": parallel_label,
            "capabilities": dict(SESSION_CAPABILITIES),
            "created_at": time.time(),
            "elapsed_sec": None,
            "current_checkpoint_id": None,
            "next_event_seq": 1,
            "pending_instruction_queue": [],
            "pending_instructions": 0,
            "active_node": None,
            "workspace_preset_ids": list(workspace_preset_ids or []),
            "workspace_paths": list(workspace_paths or []),
            "attached_tool_ids": list(attached_tool_ids or []),
            "provider_capabilities_snapshot": copy.deepcopy(provider_capabilities_snapshot or {}),
            "parallel_progress": copy.deepcopy(parallel_progress or {}),
        }
        with self._lock, self._connect() as conn:
            conn.execute(
                """
                INSERT INTO runs (
                    id, mode, task, agents_json, messages_json, result, status, config_json,
                    active_scenario, forked_from, forked_checkpoint_id,
                    parallel_parent_id, parallel_group_id, parallel_slot_key, parallel_stage, parallel_label,
                    capabilities_json,
                    created_at, elapsed_sec, current_checkpoint_id, next_event_seq,
                    pending_instruction_queue_json, pending_instructions, active_node,
                    workspace_preset_ids_json, workspace_paths_json, attached_tool_ids_json,
                    provider_capabilities_snapshot_json, parallel_progress_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    sid,
                    mode,
                    task,
                    self._encode(payload["agents"]),
                    self._encode(payload["messages"]),
                    payload["result"],
                    payload["status"],
                    self._encode(payload["config"]),
                    payload["active_scenario"],
                    payload["forked_from"],
                    payload["forked_checkpoint_id"],
                    payload["parallel_parent_id"],
                    payload["parallel_group_id"],
                    payload["parallel_slot_key"],
                    payload["parallel_stage"],
                    payload["parallel_label"],
                    self._encode(payload["capabilities"]),
                    payload["created_at"],
                    payload["elapsed_sec"],
                    payload["current_checkpoint_id"],
                    payload["next_event_seq"],
                    self._encode(payload["pending_instruction_queue"]),
                    payload["pending_instructions"],
                    payload["active_node"],
                    self._encode(payload["workspace_preset_ids"]),
                    self._encode(payload["workspace_paths"]),
                    self._encode(payload["attached_tool_ids"]),
                    self._encode(payload["provider_capabilities_snapshot"]),
                    self._encode(payload["parallel_progress"]),
                ),
            )
            self._trim_sessions(conn)
        return sid

    def _row_to_session(self, row: sqlite3.Row, conn: sqlite3.Connection) -> dict:
        sid = row["id"]
        self._ingest_runtime_events(conn, sid)
        checkpoints = [
            self._decode(cp["payload_json"], {})
            for cp in conn.execute(
                "SELECT payload_json FROM checkpoints WHERE session_id = ? ORDER BY ordinal ASC",
                (sid,),
            ).fetchall()
        ]
        events = [
            self._decode(event["payload_json"], {})
            for event in conn.execute(
                "SELECT payload_json FROM events WHERE session_id = ? ORDER BY event_id ASC",
                (sid,),
            ).fetchall()
        ]
        branch_children = [
            {
                "id": child["id"],
                "mode": child["mode"],
                "status": child["status"],
                "created_at": child["created_at"],
                "forked_checkpoint_id": child["forked_checkpoint_id"],
            }
            for child in conn.execute(
                """
                SELECT id, mode, status, created_at, forked_checkpoint_id
                FROM runs
                WHERE forked_from = ?
                ORDER BY created_at ASC
                """,
                (sid,),
            ).fetchall()
        ]
        parallel_children = [
            {
                "id": child["id"],
                "mode": child["mode"],
                "status": child["status"],
                "created_at": child["created_at"],
                "slot_key": child["parallel_slot_key"],
                "stage": child["parallel_stage"],
                "label": child["parallel_label"] or child["task"],
                "winner_label": (self._decode(child["config_json"], {}) or {}).get("match_result", {}).get("winner_label"),
            }
            for child in conn.execute(
                """
                SELECT id, mode, task, status, created_at, parallel_slot_key, parallel_stage, parallel_label, config_json
                FROM runs
                WHERE parallel_parent_id = ?
                ORDER BY created_at ASC
                """,
                (sid,),
            ).fetchall()
        ]
        agents = self._decode(row["agents_json"], [])
        attached_tool_ids = self._decode(row["attached_tool_ids_json"], [])
        provider_capabilities_snapshot = self._decode(
            row["provider_capabilities_snapshot_json"], {}
        )
        return {
            "id": sid,
            "mode": row["mode"],
            "task": row["task"],
            "agents": agents,
            "messages": self._decode(row["messages_json"], []),
            "result": row["result"],
            "status": row["status"],
            "config": self._decode(row["config_json"], {}),
            "active_scenario": row["active_scenario"],
            "forked_from": row["forked_from"],
            "forked_checkpoint_id": row["forked_checkpoint_id"],
            "parallel_parent_id": row["parallel_parent_id"],
            "parallel_group_id": row["parallel_group_id"],
            "parallel_slot_key": row["parallel_slot_key"],
            "parallel_stage": row["parallel_stage"],
            "parallel_label": row["parallel_label"],
            "capabilities": self._decode(row["capabilities_json"], dict(SESSION_CAPABILITIES)),
            "created_at": row["created_at"],
            "elapsed_sec": row["elapsed_sec"],
            "current_checkpoint_id": row["current_checkpoint_id"],
            "checkpoints": checkpoints,
            "events": events,
            "pending_instructions": row["pending_instructions"],
            "active_node": row["active_node"],
            "workspace_preset_ids": self._decode(row["workspace_preset_ids_json"], []),
            "workspace_paths": self._decode(row["workspace_paths_json"], []),
            "attached_tool_ids": attached_tool_ids,
            "provider_capabilities_snapshot": provider_capabilities_snapshot,
            "attached_tools": build_attached_tool_details(
                attached_tool_ids,
                agents,
                provider_capabilities_snapshot,
            ),
            "branch_children": branch_children,
            "parallel_children": parallel_children,
            "parallel_progress": self._decode(row["parallel_progress_json"], {}),
        }

    def get(self, sid: str) -> Optional[dict]:
        with self._lock, self._connect() as conn:
            row = conn.execute("SELECT * FROM runs WHERE id = ?", (sid,)).fetchone()
            if not row:
                return None
            return self._row_to_session(row, conn)

    def update(self, sid: str, **kwargs) -> None:
        if not kwargs:
            return
        field_map = {
            "agents": "agents_json",
            "messages": "messages_json",
            "config": "config_json",
            "capabilities": "capabilities_json",
            "active_scenario": "active_scenario",
            "forked_from": "forked_from",
            "forked_checkpoint_id": "forked_checkpoint_id",
            "parallel_parent_id": "parallel_parent_id",
            "parallel_group_id": "parallel_group_id",
            "parallel_slot_key": "parallel_slot_key",
            "parallel_stage": "parallel_stage",
            "parallel_label": "parallel_label",
            "result": "result",
            "status": "status",
            "elapsed_sec": "elapsed_sec",
            "current_checkpoint_id": "current_checkpoint_id",
            "pending_instruction_queue": "pending_instruction_queue_json",
            "pending_instructions": "pending_instructions",
            "active_node": "active_node",
            "workspace_preset_ids": "workspace_preset_ids_json",
            "workspace_paths": "workspace_paths_json",
            "attached_tool_ids": "attached_tool_ids_json",
            "provider_capabilities_snapshot": "provider_capabilities_snapshot_json",
            "parallel_progress": "parallel_progress_json",
        }
        assignments: list[str] = []
        values: list[object] = []
        for key, value in kwargs.items():
            column = field_map.get(key)
            if not column:
                continue
            assignments.append(f"{column} = ?")
            if key in _RUN_JSON_COLUMNS:
                values.append(self._encode(value))
            else:
                values.append(value)
        if not assignments:
            return
        values.append(sid)
        with self._lock, self._connect() as conn:
            conn.execute(f"UPDATE runs SET {', '.join(assignments)} WHERE id = ?", values)

    def append_messages(self, sid: str, msgs: list[dict]) -> None:
        if not msgs:
            return
        with self._lock, self._connect() as conn:
            row = conn.execute(
                "SELECT messages_json FROM runs WHERE id = ?",
                (sid,),
            ).fetchone()
            if not row:
                return
            current = self._decode(row["messages_json"], [])
            current.extend(copy.deepcopy(msgs))
            conn.execute(
                "UPDATE runs SET messages_json = ? WHERE id = ?",
                (self._encode(current), sid),
            )

    def add_checkpoint(self, sid: str, checkpoint: dict) -> None:
        with self._lock, self._connect() as conn:
            row = conn.execute(
                "SELECT COALESCE(MAX(ordinal), 0) AS last_ordinal FROM checkpoints WHERE session_id = ?",
                (sid,),
            ).fetchone()
            ordinal = int(row["last_ordinal"]) + 1
            conn.execute(
                """
                INSERT OR REPLACE INTO checkpoints (
                    session_id, checkpoint_id, ordinal, timestamp, next_node, status,
                    result_preview, graph_checkpoint_id, payload_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    sid,
                    checkpoint.get("id"),
                    ordinal,
                    checkpoint.get("timestamp", time.time()),
                    checkpoint.get("next_node"),
                    checkpoint.get("status", "ready"),
                    checkpoint.get("result_preview"),
                    checkpoint.get("graph_checkpoint_id"),
                    self._encode(copy.deepcopy(checkpoint)),
                ),
            )
            conn.execute(
                "UPDATE runs SET current_checkpoint_id = ? WHERE id = ?",
                (checkpoint.get("id"), sid),
            )

    def append_event(
        self,
        sid: str,
        event_type: str,
        title: str,
        detail: str = "",
        **extra: object,
    ) -> Optional[dict]:
        with self._lock, self._connect() as conn:
            return self._append_event_conn(conn, sid, event_type, title, detail, **extra)

    def list_events(self, sid: str, since: int = 0) -> list[dict]:
        with self._lock, self._connect() as conn:
            self._ingest_runtime_events(conn, sid)
            rows = conn.execute(
                """
                SELECT payload_json
                FROM events
                WHERE session_id = ? AND event_id > ?
                ORDER BY event_id ASC
                """,
                (sid, since),
            ).fetchall()
            return [self._decode(row["payload_json"], {}) for row in rows]

    def ingest_runtime_events(self, sid: str) -> None:
        with self._lock, self._connect() as conn:
            self._ingest_runtime_events(conn, sid)

    def queue_instruction(self, sid: str, content: str) -> int:
        with self._lock, self._connect() as conn:
            row = conn.execute(
                "SELECT pending_instruction_queue_json FROM runs WHERE id = ?",
                (sid,),
            ).fetchone()
            if not row:
                return 0
            queue = self._decode(row["pending_instruction_queue_json"], [])
            queue.append(content)
            conn.execute(
                """
                UPDATE runs
                SET pending_instruction_queue_json = ?, pending_instructions = ?
                WHERE id = ?
                """,
                (self._encode(queue), len(queue), sid),
            )
            return len(queue)

    def pop_pending_instructions(self, sid: str) -> list[str]:
        with self._lock, self._connect() as conn:
            row = conn.execute(
                "SELECT pending_instruction_queue_json FROM runs WHERE id = ?",
                (sid,),
            ).fetchone()
            if not row:
                return []
            queue = self._decode(row["pending_instruction_queue_json"], [])
            conn.execute(
                """
                UPDATE runs
                SET pending_instruction_queue_json = ?, pending_instructions = 0
                WHERE id = ?
                """,
                (self._encode([]), sid),
            )
            return queue

    def list_recent(self, limit: int = 50) -> list[dict]:
        with self._lock, self._connect() as conn:
            rows = conn.execute(
                """
                SELECT id, mode, task, status, created_at, active_scenario, forked_from,
                       current_checkpoint_id, parallel_parent_id, parallel_group_id,
                       parallel_slot_key, parallel_stage, parallel_label
                FROM runs
                WHERE parallel_parent_id IS NULL
                ORDER BY created_at DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
            return [
                {
                    "id": row["id"],
                    "mode": row["mode"],
                    "task": row["task"][:100],
                    "status": row["status"],
                    "created_at": row["created_at"],
                    "active_scenario": row["active_scenario"],
                    "forked_from": row["forked_from"],
                    "current_checkpoint_id": row["current_checkpoint_id"],
                    "parallel_parent_id": row["parallel_parent_id"],
                    "parallel_group_id": row["parallel_group_id"],
                    "parallel_slot_key": row["parallel_slot_key"],
                    "parallel_stage": row["parallel_stage"],
                    "parallel_label": row["parallel_label"],
                }
                for row in rows
            ]

    def list_parallel_children(self, parent_id: str) -> list[dict]:
        with self._lock, self._connect() as conn:
            rows = conn.execute(
                """
                SELECT id, mode, task, status, created_at, parallel_slot_key, parallel_stage, parallel_label, config_json
                FROM runs
                WHERE parallel_parent_id = ?
                ORDER BY created_at ASC
                """,
                (parent_id,),
            ).fetchall()
            children: list[dict] = []
            for row in rows:
                config = self._decode(row["config_json"], {})
                children.append(
                    {
                        "id": row["id"],
                        "mode": row["mode"],
                        "status": row["status"],
                        "created_at": row["created_at"],
                        "slot_key": row["parallel_slot_key"],
                        "stage": row["parallel_stage"],
                        "label": row["parallel_label"] or row["task"],
                        "winner_label": (config or {}).get("match_result", {}).get("winner_label"),
                    }
                )
            return children

    def list_by_statuses(self, statuses: list[str]) -> list[dict]:
        if not statuses:
            return []
        placeholders = ", ".join("?" for _ in statuses)
        with self._lock, self._connect() as conn:
            rows = conn.execute(
                f"""
                SELECT id, mode, task, status, created_at, current_checkpoint_id
                FROM runs
                WHERE status IN ({placeholders})
                ORDER BY created_at DESC
                """,
                tuple(statuses),
            ).fetchall()
            return [
                {
                    "id": row["id"],
                    "mode": row["mode"],
                    "task": row["task"],
                    "status": row["status"],
                    "created_at": row["created_at"],
                    "current_checkpoint_id": row["current_checkpoint_id"],
                }
                for row in rows
            ]

    def list_workspaces(self) -> list[WorkspacePreset]:
        with self._lock, self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM workspace_presets ORDER BY created_at ASC",
            ).fetchall()
            return [
                WorkspacePreset(
                    id=row["id"],
                    name=row["name"],
                    description=row["description"],
                    paths=self._decode(row["paths_json"], []),
                    created_at=row["created_at"],
                )
                for row in rows
            ]

    def get_workspace(self, workspace_id: str) -> WorkspacePreset | None:
        with self._lock, self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM workspace_presets WHERE id = ?",
                (workspace_id,),
            ).fetchone()
            if not row:
                return None
            return WorkspacePreset(
                id=row["id"],
                name=row["name"],
                description=row["description"],
                paths=self._decode(row["paths_json"], []),
                created_at=row["created_at"],
            )

    def add_workspace(self, preset: WorkspacePreset) -> WorkspacePreset:
        with self._lock, self._connect() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO workspace_presets (id, name, description, paths_json, created_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    preset.id,
                    preset.name,
                    preset.description,
                    self._encode(preset.paths),
                    preset.created_at,
                ),
            )
        return preset

    def update_workspace(self, workspace_id: str, updates: dict) -> WorkspacePreset | None:
        current = self.get_workspace(workspace_id)
        if not current:
            return None
        updated = current.model_copy(update=updates)
        return self.add_workspace(updated)

    def delete_workspace(self, workspace_id: str) -> bool:
        with self._lock, self._connect() as conn:
            cursor = conn.execute(
                "DELETE FROM workspace_presets WHERE id = ?",
                (workspace_id,),
            )
            return cursor.rowcount > 0


# Global store instance
store = SessionStore()
