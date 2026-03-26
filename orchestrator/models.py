"""Data models for orchestration sessions."""

import time
import uuid
from typing import Annotated, Optional

import operator
from pydantic import BaseModel, Field
from typing_extensions import TypedDict


# ---- API Request/Response models (Pydantic) ----

class AgentConfig(BaseModel):
    """Agent configuration from API request."""
    role: str
    provider: str
    system_prompt: str = ""


class RunRequest(BaseModel):
    """POST /orchestrate/run request body."""
    mode: str
    task: str
    agents: list[AgentConfig] = []
    config: dict = {}


class MessageRequest(BaseModel):
    """POST /orchestrate/session/{id}/message request body."""
    content: str


class SessionResponse(BaseModel):
    """GET /orchestrate/session/{id} response."""
    id: str
    mode: str
    task: str
    agents: list[AgentConfig]
    messages: list[dict]
    result: Optional[str] = None
    status: str
    config: dict = {}
    created_at: float
    elapsed_sec: Optional[float] = None


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


# ---- Session store (in-memory) ----

class SessionStore:
    """Simple in-memory session storage. Keeps last 100 sessions."""

    def __init__(self, max_sessions: int = 100):
        self._sessions: dict[str, dict] = {}
        self._max = max_sessions

    def create(self, mode: str, task: str, agents: list[AgentConfig], config: dict) -> str:
        sid = f"sess_{uuid.uuid4().hex[:12]}"
        self._sessions[sid] = {
            "id": sid,
            "mode": mode,
            "task": task,
            "agents": [a.model_dump() for a in agents],
            "messages": [],
            "result": None,
            "status": "running",
            "config": config,
            "created_at": time.time(),
            "elapsed_sec": None,
        }
        if len(self._sessions) > self._max:
            oldest = min(self._sessions, key=lambda k: self._sessions[k]["created_at"])
            del self._sessions[oldest]
        return sid

    def get(self, sid: str) -> Optional[dict]:
        return self._sessions.get(sid)

    def update(self, sid: str, **kwargs):
        if sid in self._sessions:
            self._sessions[sid].update(kwargs)

    def append_messages(self, sid: str, msgs: list[dict]):
        if sid in self._sessions:
            self._sessions[sid]["messages"].extend(msgs)

    def list_recent(self, limit: int = 50) -> list[dict]:
        sessions = sorted(self._sessions.values(), key=lambda s: s["created_at"], reverse=True)
        return [{"id": s["id"], "mode": s["mode"], "task": s["task"][:100],
                 "status": s["status"], "created_at": s["created_at"]} for s in sessions[:limit]]


# Global store instance
store = SessionStore()
