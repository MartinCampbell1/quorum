"""Data models for orchestration sessions."""

import copy
import threading
import time
import uuid
from typing import Annotated, Optional

import operator
from pydantic import BaseModel, Field
from typing_extensions import TypedDict

from orchestrator.tool_configs import (
    normalize_tool_id,
    supported_providers_for_tool_type,
    tool_config_store,
)


# ---- API Request/Response models (Pydantic) ----

class ToolDefinition(BaseModel):
    """Tool available for agents."""
    key: str
    name: str
    description: str
    category: str


AVAILABLE_TOOLS: list[ToolDefinition] = [
    # Search (MCP search-server)
    ToolDefinition(key="web_search", name="Веб-поиск", description="Поиск в интернете через Brave Search API", category="search"),
    ToolDefinition(key="perplexity", name="Perplexity AI", description="AI-поиск с цитатами через Perplexity Sonar", category="search"),
    # Execution (MCP exec-server)
    ToolDefinition(key="code_exec", name="Python", description="Выполнение Python кода (вычисления, обработка данных)", category="exec"),
    ToolDefinition(key="shell_exec", name="Shell", description="Выполнение shell команд (файлы, git, система)", category="exec"),
    ToolDefinition(key="http_request", name="HTTP запрос", description="HTTP запросы к любым API (GET/POST/PUT/DELETE)", category="exec"),
]

TOOLS_BY_KEY: dict[str, ToolDefinition] = {t.key: t for t in AVAILABLE_TOOLS}
SUPPORTED_PROVIDERS = {"claude", "gemini", "codex", "minimax"}
SESSION_CAPABILITIES = {
    "live_messages": True,
    "custom_tools": False,
    "pause_resume": True,
    "checkpoints": True,
}

MODE_AGENT_REQUIREMENTS: dict[str, dict[str, object]] = {
    "dictator": {"min": 2, "label": "1 director + at least 1 worker"},
    "board": {"min": 3, "label": "3 directors, optional extra workers"},
    "democracy": {"min": 3, "label": "at least 3 voters"},
    "debate": {"exact": 3, "label": "proponent, opponent, judge"},
    "map_reduce": {"min": 3, "label": "planner, at least 1 worker, synthesizer"},
    "creator_critic": {"exact": 2, "label": "creator and critic"},
    "tournament": {"min": 3, "label": "at least 2 contestants + judge"},
}

PROVIDER_TOOL_ALLOWLIST: dict[str, set[str]] = {
    "claude": set(TOOLS_BY_KEY),
    "gemini": {"web_search", "perplexity", "http_request"},
    # Codex currently relies on native CLI capabilities for these classes of work.
    "codex": {"code_exec", "shell_exec", "web_search"},
    "minimax": set(),
}


class AgentConfig(BaseModel):
    """Agent configuration from API request."""
    role: str
    provider: str
    system_prompt: str = ""
    tools: list[str] = Field(default_factory=list)


class RunRequest(BaseModel):
    """POST /orchestrate/run request body."""
    mode: str
    task: str
    scenario_id: Optional[str] = None
    agents: list[AgentConfig] = Field(default_factory=list)
    config: dict = Field(default_factory=dict)


class MessageRequest(BaseModel):
    """POST /orchestrate/session/{id}/message request body."""
    content: str


class ControlRequest(BaseModel):
    """POST /orchestrate/session/{id}/control request body."""
    action: str
    content: str = ""
    checkpoint_id: str = ""


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
    capabilities: dict = Field(default_factory=lambda: dict(SESSION_CAPABILITIES))
    created_at: float
    elapsed_sec: Optional[float] = None
    current_checkpoint_id: Optional[str] = None
    checkpoints: list[dict] = Field(default_factory=list)
    events: list[dict] = Field(default_factory=list)
    pending_instructions: int = 0
    active_node: Optional[str] = None


# ---- LangGraph State (TypedDict for graph nodes) ----

# NOTE: OrchestratorState is a base reference. Each mode defines its own TypedDict.
# Future: add `error: str = ""` field to each mode state for error propagation.
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


# ---- Session store (in-memory) ----

class SessionStore:
    """Simple in-memory session storage. Keeps last 100 sessions."""

    def __init__(self, max_sessions: int = 100):
        self._sessions: dict[str, dict] = {}
        self._max = max_sessions
        self._lock = threading.Lock()

    def create(
        self,
        mode: str,
        task: str,
        agents: list[AgentConfig],
        config: dict,
        scenario_id: Optional[str] = None,
        forked_from: Optional[str] = None,
        forked_checkpoint_id: Optional[str] = None,
    ) -> str:
        sid = f"sess_{uuid.uuid4().hex[:12]}"
        with self._lock:
            self._sessions[sid] = {
                "id": sid,
                "mode": mode,
                "task": task,
                "agents": [a.model_dump() for a in agents],
                "messages": [],
                "result": None,
                "status": "running",
                "config": copy.deepcopy(config),
                "active_scenario": scenario_id,
                "forked_from": forked_from,
                "forked_checkpoint_id": forked_checkpoint_id,
                "capabilities": dict(SESSION_CAPABILITIES),
                "created_at": time.time(),
                "elapsed_sec": None,
                "current_checkpoint_id": None,
                "checkpoints": [],
                "events": [],
                "next_event_seq": 1,
                "pending_instruction_queue": [],
                "pending_instructions": 0,
                "active_node": None,
            }
            if len(self._sessions) > self._max:
                oldest = min(self._sessions, key=lambda k: self._sessions[k]["created_at"])
                del self._sessions[oldest]
        return sid

    def get(self, sid: str) -> Optional[dict]:
        with self._lock:
            session = self._sessions.get(sid)
            if not session:
                return None
            payload = copy.deepcopy(session)
            payload.pop("pending_instruction_queue", None)
            payload.pop("next_event_seq", None)
            return payload

    def update(self, sid: str, **kwargs):
        with self._lock:
            if sid in self._sessions:
                self._sessions[sid].update(kwargs)

    def append_messages(self, sid: str, msgs: list[dict]):
        with self._lock:
            if sid in self._sessions:
                self._sessions[sid]["messages"].extend(msgs)

    def add_checkpoint(self, sid: str, checkpoint: dict):
        with self._lock:
            if sid in self._sessions:
                self._sessions[sid]["checkpoints"].append(copy.deepcopy(checkpoint))
                self._sessions[sid]["current_checkpoint_id"] = checkpoint.get("id")

    def append_event(
        self,
        sid: str,
        event_type: str,
        title: str,
        detail: str = "",
        **extra: object,
    ) -> Optional[dict]:
        with self._lock:
            session = self._sessions.get(sid)
            if not session:
                return None
            event = {
                "id": session["next_event_seq"],
                "timestamp": time.time(),
                "type": event_type,
                "title": title,
                "detail": detail,
                **extra,
            }
            session["events"].append(event)
            session["next_event_seq"] += 1
            return copy.deepcopy(event)

    def list_events(self, sid: str, since: int = 0) -> list[dict]:
        with self._lock:
            session = self._sessions.get(sid)
            if not session:
                return []
            return [
                copy.deepcopy(event)
                for event in session["events"]
                if int(event.get("id", 0)) > since
            ]

    def queue_instruction(self, sid: str, content: str) -> int:
        with self._lock:
            if sid not in self._sessions:
                return 0
            queue = self._sessions[sid]["pending_instruction_queue"]
            queue.append(content)
            self._sessions[sid]["pending_instructions"] = len(queue)
            return len(queue)

    def pop_pending_instructions(self, sid: str) -> list[str]:
        with self._lock:
            if sid not in self._sessions:
                return []
            queue = list(self._sessions[sid]["pending_instruction_queue"])
            self._sessions[sid]["pending_instruction_queue"] = []
            self._sessions[sid]["pending_instructions"] = 0
            return queue

    def list_recent(self, limit: int = 50) -> list[dict]:
        with self._lock:
            sessions = sorted(self._sessions.values(), key=lambda s: s["created_at"], reverse=True)
            return [{"id": s["id"], "mode": s["mode"], "task": s["task"][:100],
                     "status": s["status"], "created_at": s["created_at"]} for s in sessions[:limit]]


# Global store instance
store = SessionStore()


def normalize_agent_configs(agents: list[AgentConfig]) -> list[AgentConfig]:
    """Normalize tool ids so the UI and runtime use the same canonical keys."""
    normalized_agents: list[AgentConfig] = []
    for agent in agents:
        normalized_agents.append(
            agent.model_copy(
                update={
                    "tools": [normalize_tool_id(tool) for tool in agent.tools],
                }
            )
        )
    return normalized_agents


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
        dup_list = ", ".join(duplicate_roles)
        errors.append(f"Agent roles must be unique; duplicate roles: {dup_list}.")

    for index, agent in enumerate(agents):
        if agent.provider not in SUPPORTED_PROVIDERS:
            errors.append(
                f"Agent {index + 1} ('{agent.role}') uses unsupported provider '{agent.provider}'."
            )
            continue

        invalid_tools: list[str] = []
        disallowed_tools: list[str] = []
        for tool in agent.tools:
            if tool in TOOLS_BY_KEY:
                if tool not in PROVIDER_TOOL_ALLOWLIST.get(agent.provider, set()):
                    disallowed_tools.append(tool)
                continue

            configured_tool = tool_config_store.get(tool)
            if not configured_tool or not configured_tool.enabled:
                invalid_tools.append(tool)
                continue

            allowed_providers = supported_providers_for_tool_type(configured_tool.tool_type)
            if agent.provider not in allowed_providers:
                disallowed_tools.append(tool)

        if invalid_tools:
            errors.append(
                f"Agent {index + 1} ('{agent.role}') uses unknown tools: {', '.join(sorted(invalid_tools))}."
            )
            continue

        if disallowed_tools:
            errors.append(
                f"Agent {index + 1} ('{agent.role}') cannot use {agent.provider} with tools: "
                f"{', '.join(sorted(disallowed_tools))}."
            )

    return errors
