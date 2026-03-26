"""FastAPI router for orchestration endpoints."""

from fastapi import APIRouter, HTTPException

from orchestrator.models import (
    AVAILABLE_TOOLS,
    MODE_AGENT_REQUIREMENTS,
    store,
    RunRequest,
    MessageRequest,
    validate_agents_for_mode,
)
from orchestrator.engine import run, AVAILABLE_MODES, DEFAULT_AGENTS

router = APIRouter(prefix="/orchestrate", tags=["orchestrate"])


def _resolve_agents(req: RunRequest):
    return req.agents if req.agents else DEFAULT_AGENTS.get(req.mode, [])


@router.post("/run")
async def ep_run(req: RunRequest):
    if req.mode not in AVAILABLE_MODES:
        raise HTTPException(400, f"Unknown mode: {req.mode}. Available: {list(AVAILABLE_MODES.keys())}")
    agents = _resolve_agents(req)
    errors = validate_agents_for_mode(req.mode, agents)
    if errors:
        raise HTTPException(422, {
            "message": "Invalid agent topology or tool selection",
            "errors": errors,
            "requirements": MODE_AGENT_REQUIREMENTS.get(req.mode, {}),
        })
    session_id = await run(
        mode=req.mode, task=req.task,
        agents=agents, config=req.config,
    )
    return {"session_id": session_id, "mode": req.mode, "status": "running"}


@router.get("/session/{session_id}")
async def ep_session(session_id: str):
    session = store.get(session_id)
    if not session:
        raise HTTPException(404, f"Session not found: {session_id}")
    return session


@router.get("/sessions")
async def ep_sessions():
    return store.list_recent()


@router.post("/session/{session_id}/message")
async def ep_user_message(session_id: str, req: MessageRequest):
    session = store.get(session_id)
    if not session:
        raise HTTPException(404, f"Session not found: {session_id}")
    raise HTTPException(
        409,
        "Live user messages are not wired into running graphs in this build. "
        "Treat sessions as read-only until interactive resume support is implemented.",
    )


@router.get("/modes")
async def ep_modes():
    return {
        mode: {
            "description": desc,
            "default_agents": [a.model_dump() for a in DEFAULT_AGENTS.get(mode, [])],
            "requirements": MODE_AGENT_REQUIREMENTS.get(mode, {}),
        }
        for mode, desc in AVAILABLE_MODES.items()
    }


@router.get("/tools")
async def ep_tools():
    return [tool.model_dump() for tool in AVAILABLE_TOOLS]


@router.get("/tools/custom")
async def ep_custom_tools():
    return []


@router.post("/tools/custom")
async def ep_add_custom_tool():
    raise HTTPException(
        501,
        "Executable custom tools are not supported in this build yet. "
        "Only built-in tools are available.",
    )


@router.delete("/tools/custom/{tool_key}")
async def ep_remove_custom_tool(tool_key: str):
    raise HTTPException(
        501,
        f"Custom tool '{tool_key}' cannot be removed because custom tools are disabled in this build.",
    )


@router.get("/tool-logs")
async def ep_tool_logs(limit: int = 50):
    """Read recent tool call logs."""
    import json
    from pathlib import Path
    log_dir = Path(__file__).parent.parent / ".tool_logs"
    if not log_dir.exists():
        return []
    entries = []
    for log_file in log_dir.glob("*.jsonl"):
        with open(log_file) as f:
            for line in f:
                try:
                    entries.append(json.loads(line))
                except json.JSONDecodeError:
                    pass
    entries.sort(key=lambda e: e.get("timestamp", 0), reverse=True)
    return entries[:limit]


@router.get("/agents")
async def ep_agents():
    import httpx
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get("http://localhost:8800/pool")
            pool = resp.json()
    except Exception:
        pool = {}
    return {
        "providers": ["claude", "gemini", "codex", "minimax"],
        "pool_status": pool,
        "minimax": {"model": "minimax/minimax-m2.7", "via": "OpenRouter API"},
    }
